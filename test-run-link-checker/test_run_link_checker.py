"""Webhook which refuses the export of a test run whose work item links are broken.

It passes the HTML through untouched. The only thing it decides is whether the export may proceed,
which the PDF Exporter reads from the status code: configure the webhook with "Fail export on error"
so that anything but HTTP 200 stops the export and shows the response text to the user.

The check itself belongs to the XML Repair extension, whose TestRunBrokenLinksRepairer finds the
test case and defect references of a test run which cannot be resolved or read.
"""

import argparse
import logging
import os

import requests
from flask import Flask, Response, request, json, abort
from flask_httpauth import HTTPBasicAuth
from gevent.pywsgi import WSGIServer
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)

data_limit = 100 * 1024 * 1024  # 100MB;
app.config.update(
    MAX_CONTENT_LENGTH=data_limit,
    MAX_FORM_MEMORY_SIZE=data_limit,
)

auth = HTTPBasicAuth()
service_username = None
service_password_hash = None

polarion_url = None
polarion_token = None
scan_timeout = None

# The repairer is selected by its class name, which is what the scan endpoint matches against.
REPAIRER = "TestRunBrokenLinksRepairer"
# The export dialog puts the test run id here; a test run has no location path.
TEST_RUN_ID_PARAM = "id"
MAX_REPORTED_ISSUES = 20


@auth.verify_password
def verify_password(username, password):
    if username == service_username and check_password_hash(service_password_hash, password):
        return username
    return None


logging.basicConfig(level=logging.DEBUG, format='%(asctime)s [%(levelname)s] - %(message)s')


@app.route("/test-run/check-links", methods=["POST"])
@auth.login_required
def check_links():
    export_params, html = validate_request()

    document_type = export_params.get('documentType')
    if document_type != 'TEST_RUN':
        logging.info(f"Document type is '{document_type}', not a test run. Link check skipped.")
        return html_response(html)

    project_id = export_params.get('projectId')
    test_run_id = (export_params.get('urlQueryParameters') or {}).get(TEST_RUN_ID_PARAM)
    if not project_id or not test_run_id:
        # The export cannot be checked, and a check which silently does nothing is worse than a refusal.
        abort(Response("Cannot check the test run: the export parameters name no project or test run id", 400))

    issues = scan_test_run(project_id, test_run_id, revision_of(export_params))
    if issues:
        logging.warning(f"Test run '{project_id}/{test_run_id}' has {len(issues)} broken link(s). Export refused.")
        abort(Response(refusal_text(project_id, test_run_id, issues), 422))

    logging.info(f"Test run '{project_id}/{test_run_id}' has no broken links. Export allowed.")
    return html_response(html)


def revision_of(export_params):
    """The revision the export reads, so that the scan judges the same content."""
    return export_params.get('revision') or export_params.get('baselineRevision')


def scan_test_run(project_id, test_run_id, revision):
    """The issues the XML Repair extension reports for this test run, newest content or a given revision."""
    scan_params = {
        "projectId": project_id,
        "entityType": "TESTRUN",
        "entities": [{"id": test_run_id}],
        "repairers": [REPAIRER],
        "hideValid": True,
        "limit": 1,
    }
    if revision:
        scan_params["revision"] = revision

    try:
        response = requests.post(
            f"{polarion_url}/polarion/xml-repair/rest/api/scan",
            json=scan_params,
            headers={"Authorization": f"Bearer {polarion_token}"},
            timeout=scan_timeout,
        )
    except requests.RequestException as e:
        # Reaching no verdict is not the same as a clean test run, so the export is refused too.
        abort(Response(f"Cannot check the test run: the XML Repair service could not be called: {e}", 502))
    else:
        if response.status_code != 200:
            abort(Response(f"Cannot check the test run: the XML Repair service answered "
                           f"HTTP {response.status_code}: {response.text[:500]}", 502))

        issues = []
        for item in response.json().get('items', []):
            issues.extend(issue.get('description', '') for issue in item.get('issues', []))
        return issues


def refusal_text(project_id, test_run_id, issues):
    reported = issues[:MAX_REPORTED_ISSUES]
    lines = [f"Test run '{project_id}/{test_run_id}' has {len(issues)} broken work item link(s). "
             f"The export would silently leave the affected content out."]
    lines.extend(f"- {description}" for description in reported)
    if len(issues) > len(reported):
        lines.append(f"- ... and {len(issues) - len(reported)} more")
    return "\n".join(lines)


def html_response(html):
    return Response(bytes(html, "utf-8"), mimetype="application/octet-stream", status=200)


def validate_request():
    export_params_json = request.form.get('exportParams')
    if export_params_json is None:
        abort(Response('Missing exportParams', 400))
    else:
        export_params_json = json.loads(export_params_json)

    html = request.form.get('html')
    if html is None:
        abort(Response('Missing html', 400))
    return export_params_json, html


def start_server(port):
    http_server = WSGIServer(("localhost", port), app)
    http_server.serve_forever()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Webhook: test run link checker")
    parser.add_argument('--port', default=9334, type=int, required=False, help="service port")
    parser.add_argument('--username', type=str, required=True, help='username for basic auth')
    parser.add_argument('--password', type=str, required=True, help='password for basic auth')
    parser.add_argument('--polarion-url', type=str, default='http://localhost', required=False,
                        help='base URL of Polarion, without the /polarion path')
    parser.add_argument('--scan-timeout', default=120, type=int, required=False,
                        help='seconds to wait for the scan')
    args = parser.parse_args()
    service_username = args.username
    service_password_hash = generate_password_hash(args.password)
    polarion_url = args.polarion_url.rstrip('/')
    scan_timeout = args.scan_timeout

    # Kept out of the command line, where it would reach the process list and the shell history.
    polarion_token = os.environ.get('POLARION_TOKEN')
    if not polarion_token:
        parser.error('Environment variable POLARION_TOKEN must hold a Polarion personal access token')

    logging.info(f"Service listening on port: {args.port}, checking test runs through {polarion_url}")

    start_server(args.port)

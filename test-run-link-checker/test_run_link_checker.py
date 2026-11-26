"""Webhook which refuses the export of a test run whose work item links are broken.

It passes the HTML through untouched. The only thing it decides is whether the export may proceed,
which the PDF Exporter reads from the status code: configure the webhook with "Fail export on error"
so that anything but HTTP 200 stops the export and shows the response text to the user.

The check itself belongs to the XML Repair extension, whose TestRunBrokenLinksRepairer finds the
test case and defect references of a test run which cannot be resolved or read.
"""

# The patch must precede the other imports: without it a pending scan blocks every other request.
from gevent import monkey

monkey.patch_socket()
monkey.patch_ssl()

import logging  # noqa: E402
import os  # noqa: E402
import sys  # noqa: E402
from pathlib import Path  # noqa: E402

import requests  # noqa: E402
from flask import abort  # noqa: E402

# The shared module is in the repository root, next to the folder of this sample.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from common.webhook_server import (  # noqa: E402
    app, auth, validate_request, html_response, plain_response, create_parser, configure_auth, start_server,
)

polarion_url = None
polarion_token = None
scan_timeout = None

# The repairer is selected by its class name, which is what the scan endpoint matches against.
REPAIRER = "TestRunBrokenLinksRepairer"
# The export dialog puts the test run id here; a test run has no location path.
TEST_RUN_ID_PARAM = "id"
MAX_REPORTED_ISSUES = 20


@app.route("/test-run/check-links", methods=["POST"])
@auth.login_required
def check_links():
    export_params, html = validate_request()

    document_type = export_params.get('documentType')
    if document_type != 'TEST_RUN':
        logging.info(f"Document type is '{single_line(document_type)}', not a test run. Link check skipped.")
        return html_response(html)

    project_id = export_params.get('projectId')
    query_params = export_params.get('urlQueryParameters')
    test_run_id = query_params.get(TEST_RUN_ID_PARAM) if isinstance(query_params, dict) else None
    if not project_id or not test_run_id:
        # The export cannot be checked, and a check which silently does nothing is worse than a refusal.
        abort(plain_response("Cannot check the test run: the export parameters name no project or test run id", 400))

    run = f"{single_line(project_id)}/{single_line(test_run_id)}"
    issues = scan_test_run(project_id, test_run_id, revision_of(export_params))
    if issues:
        logging.warning(f"Test run '{run}' has {len(issues)} broken link(s). Export refused.")
        abort(plain_response(refusal_text(project_id, test_run_id, issues), 422))

    logging.info(f"Test run '{run}' has no broken links. Export allowed.")
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
        # Only the kind of the failure is reported: the exception text carries the scan URL and the token header.
        abort(plain_response(f"Cannot check the test run: the XML Repair service could not be called "
                             f"({type(e).__name__})", 502))

    if response.status_code != 200:
        abort(plain_response(f"Cannot check the test run: the XML Repair service answered "
                             f"HTTP {response.status_code}", 502))

    try:
        return issue_descriptions(response.json())
    except ValueError:
        # A malformed result is no verdict either.
        abort(plain_response("Cannot check the test run: the XML Repair service returned an invalid scan result", 502))


def issue_descriptions(scan_result):
    """The descriptions of all issues in a scan result. Raises ValueError if its structure is not the expected one."""
    issues = []
    for item in list_field(scan_result, 'items'):
        for issue in list_field(item, 'issues'):
            description = issue.get('description') if isinstance(issue, dict) else None
            if not isinstance(description, str):
                raise ValueError("An issue has no description")
            issues.append(description)
    return issues


def list_field(value, name):
    field = value.get(name) if isinstance(value, dict) else None
    if not isinstance(field, list):
        raise ValueError(f"Field '{name}' is not a list")
    return field


def refusal_text(project_id, test_run_id, issues):
    reported = issues[:MAX_REPORTED_ISSUES]
    lines = [f"Test run '{project_id}/{test_run_id}' has {len(issues)} broken work item link(s). "
             f"The export would silently leave the affected content out."]
    lines.extend(f"- {description}" for description in reported)
    if len(issues) > len(reported):
        lines.append(f"- ... and {len(issues) - len(reported)} more")
    return "\n".join(lines)


def single_line(value):
    """A value of the request kept out of the line structure of the log."""
    return str(value).replace('\r', ' ').replace('\n', ' ')


if __name__ == '__main__':
    parser = create_parser("Webhook: test run link checker", 9334)
    parser.add_argument('--polarion-url', type=str, default='http://localhost', required=False,
                        help='base URL of Polarion, without the /polarion path')
    parser.add_argument('--scan-timeout', default=120, type=int, required=False,
                        help='seconds to wait for the scan')
    args = parser.parse_args()
    polarion_url = args.polarion_url.rstrip('/')
    scan_timeout = args.scan_timeout

    # The token is kept out of the command line, where it would reach the process list and the shell history.
    polarion_token = os.environ.get('POLARION_TOKEN')
    if not polarion_token:
        parser.error('Environment variable POLARION_TOKEN must hold a Polarion personal access token')

    configure_auth(parser, args)

    logging.info(f"Service listening on port: {args.port}, checking test runs through {polarion_url}")

    start_server(args.port)

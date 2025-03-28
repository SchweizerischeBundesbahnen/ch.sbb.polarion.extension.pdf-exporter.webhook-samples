import argparse
import logging
import re

from flask import Flask, Response, request, json, abort
from flask_httpauth import HTTPBasicAuth
from gevent.pywsgi import WSGIServer
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
auth = HTTPBasicAuth()
service_username = None
service_password_hash = None

@auth.verify_password
def verify_password(username, password):
    if username == service_username and check_password_hash(service_password_hash, password):
        return username
    return None


logging.basicConfig(level=logging.DEBUG, format='%(asctime)s [%(levelname)s] - %(message)s')


@app.route("/td-height/<height>", methods=["POST"])
@auth.login_required
def process_html(height):
    export_params, html = validate_request()

    height = sanitize_input(height)
    logging.info(f"Changing HTML table cell height to '{height}'")

    if export_params.get('fitToPage'):
        html = change_height(html, height)
        logging.info("Changing HTML table cell height finished.")
    else:
        logging.info("'fitToPage' is not set. Changing HTML table cell height skipped.")

    # we ignore 'py/reflective-xss' ("Directly writing user input to
    # response without properly sanitizing the input first, allows
    # for a cross-site scripting vulnerability") and 'pythonsecurity:S5131'
    # ("Change this code to not reflect user-controlled data") because
    # this is exactly what we supposed to do - return slightly modified
    # but basically the same html
    return Response(html, mimetype="text/html", status=200)


def change_height(html, height):
    pattern = r'(<t[dh][^>]*?style=[^>]*?height:\s*)(\d+(\.\d+)?px)'
    return re.sub(pattern, lambda m: m.group(1) + height, html)


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

def sanitize_input(user_input):
    return re.sub(r'[\r\n]', '', user_input).strip()

def start_server(port):
    http_server = WSGIServer(("", port), app)
    http_server.serve_forever()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Webhook: table cell auto height setter")
    parser.add_argument('--port', default=9333, type=int, required=False, help="service port")
    parser.add_argument('--username', type=str, required=True, help='username for basic auth')
    parser.add_argument('--password', type=str, required=True, help='password for basic auth')
    args = parser.parse_args()
    service_username = args.username
    service_password_hash = generate_password_hash(args.password)
    logging.info(f"Service listening on port: {args.port}")

    start_server(args.port)

import argparse
import getpass
import logging
import os
import re

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

    if export_params.get('fitToPage'):
        try:
            height = sanitize_input(height)
        except ValueError:
            abort(plain_response('Invalid height value', 400))
        html = change_height(html, height)
        logging.info("Changing HTML table cell height finished.")
    else:
        logging.info("'fitToPage' is not set. Changing HTML table cell height skipped.")

    return Response(bytes(html, "utf-8"), mimetype="application/octet-stream", status=200)


def change_height(html, height):
    pattern = r'(<t[dh][^>]{0,100}?style=[^>]{0,100}?height:\s*)(\d+(?:\.\d+)?px)'
    return re.sub(pattern, lambda m: m.group(1) + height, html)


def validate_request():
    export_params_json = request.form.get('exportParams')
    if export_params_json is None:
        abort(plain_response('Missing exportParams', 400))

    try:
        export_params = json.loads(export_params_json)
    except ValueError:
        abort(plain_response('Invalid exportParams: not valid JSON', 400))
    if not isinstance(export_params, dict):
        abort(plain_response('Invalid exportParams: not a JSON object', 400))

    html = request.form.get('html')
    if html is None:
        abort(plain_response('Missing html', 400))
    return export_params, html


def plain_response(text, status):
    return Response(text, mimetype="text/plain", status=status)


def sanitize_input(user_input):
    user_input = re.sub(r'[\r\n]', '', user_input).strip()
    # Allow only integer + units of measure and 'auto'
    if user_input == "auto" or re.fullmatch(r'\d{1,4}(px|em|%)', user_input):
        return user_input
    raise ValueError("Invalid height value")

def start_server(port):
    http_server = WSGIServer(("localhost", port), app)
    http_server.serve_forever()


if __name__ == '__main__':
    # Without allow_abbrev=False, "--password secret" would be accepted as "--password-env secret".
    parser = argparse.ArgumentParser(description="Webhook: table cell auto height setter", allow_abbrev=False)
    parser.add_argument('--port', default=9333, type=int, required=False, help="service port")
    parser.add_argument('--username', type=str, required=True, help='username for basic auth')
    parser.add_argument('--password-env', type=str, default='SERVICE_PASSWORD', required=False,
                        help='environment variable containing password for basic auth')
    args = parser.parse_args()
    service_username = args.username

    # The password is kept out of the command line, where it would reach the process list and the shell history.
    service_password = os.environ.get(args.password_env)
    if service_password is None:
        try:
            service_password = getpass.getpass('Basic auth password: ')
        except EOFError:
            parser.error(f'No terminal to enter the password: set environment variable {args.password_env}')
    service_password_hash = generate_password_hash(service_password)

    logging.info(f"Service listening on port: {args.port}")

    start_server(args.port)

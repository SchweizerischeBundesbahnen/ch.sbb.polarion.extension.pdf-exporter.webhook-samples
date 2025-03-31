import argparse
import logging
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
        html = change_height(html, sanitize_input(height))
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
        abort(Response('Missing exportParams', 400))
    else:
        export_params_json = json.loads(export_params_json)

    html = request.form.get('html')
    if html is None:
        abort(Response('Missing html', 400))
    return export_params_json, html

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
    parser = argparse.ArgumentParser(description="Webhook: table cell auto height setter")
    parser.add_argument('--port', default=9333, type=int, required=False, help="service port")
    parser.add_argument('--username', type=str, required=True, help='username for basic auth')
    parser.add_argument('--password', type=str, required=True, help='password for basic auth')
    args = parser.parse_args()
    service_username = args.username
    service_password_hash = generate_password_hash(args.password)
    logging.info(f"Service listening on port: {args.port}")

    start_server(args.port)

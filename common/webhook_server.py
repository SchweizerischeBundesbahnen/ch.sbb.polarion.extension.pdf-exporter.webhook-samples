"""Parts which all webhook samples share: the Flask app, basic auth, request validation and the server."""

import argparse
import getpass
import logging
import os

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


def html_response(html):
    return Response(bytes(html, "utf-8"), mimetype="application/octet-stream", status=200)


def plain_response(text, status):
    """A message for the user, never HTML: it can carry values which come from the request."""
    return Response(text, mimetype="text/plain", status=status)


def create_parser(description, default_port):
    """An argument parser with the arguments of every webhook: port, username and password variable."""
    # Without allow_abbrev=False, "--password secret" would be accepted as "--password-env secret".
    parser = argparse.ArgumentParser(description=description, allow_abbrev=False)
    parser.add_argument('--port', default=default_port, type=int, required=False, help="service port")
    parser.add_argument('--username', type=str, required=True, help='username for basic auth')
    parser.add_argument('--password-env', type=str, default='SERVICE_PASSWORD', required=False,
                        help='environment variable containing password for basic auth')
    return parser


def configure_auth(parser, args):
    """Sets the basic auth credentials. Reads the password from the environment, or else asks for it."""
    global service_username, service_password_hash
    service_username = args.username

    # The password is kept out of the command line, where it would reach the process list and the shell history.
    service_password = os.environ.get(args.password_env)
    if service_password is None:
        try:
            service_password = getpass.getpass('Basic auth password: ')
        except EOFError:
            parser.error(f'No terminal to enter the password: set environment variable {args.password_env}')
    service_password_hash = generate_password_hash(service_password)


def start_server(port):
    http_server = WSGIServer(("localhost", port), app)
    http_server.serve_forever()

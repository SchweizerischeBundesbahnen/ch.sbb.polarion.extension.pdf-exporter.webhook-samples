import argparse
import logging
import re

from flask import Flask, Response, request, json, abort
from gevent.pywsgi import WSGIServer

app = Flask(__name__)

logging.basicConfig(level=logging.DEBUG, format='%(asctime)s [%(levelname)s] - %(message)s')


@app.route("/td-height/<height>", methods=["POST"])
def process_html(height):
    authorize()
    export_params, html = validate_request()

    logging.info(f"Changing HTML table cell height to '{height}'")

    if export_params.get('fitToPage'):
        html = change_height(html, height)
        logging.info("Changing HTML table cell height finished.")
    else:
        logging.info("'fitToPage' is not set. Changing HTML table cell height skipped.")

    return Response(html, mimetype="text/html", status=200)


def change_height(html, height):
    pattern = r'(<t[dh].+?height:.*?)(\d+(\.\d+)?px)'
    return re.sub(pattern, lambda m: m.group(1) + height, html)


def authorize():
    if args.username and args.password:
        auth = request.authorization
        if not auth:
            abort(Response('No authorization data', 401))
        if auth.username != args.username or auth.password != args.password:
            abort(Response('Invalid username/password provided', 401))


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
    http_server = WSGIServer(("", port), app)
    http_server.serve_forever()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Webhook: table cell auto height setter")
    parser.add_argument('--port', default=9333, type=int, required=False, help="service port")
    parser.add_argument('--username', type=str, required=False, help='username for basic auth')
    parser.add_argument('--password', type=str, required=False, help='password for basic auth')
    args = parser.parse_args()

    logging.info(f"Service listening on port: {args.port}")

    start_server(args.port)

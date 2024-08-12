import argparse
import logging
import re
from flask import Flask, Response, request, json
from gevent.pywsgi import WSGIServer

app = Flask(__name__)

logging.basicConfig(level=logging.DEBUG, format='%(asctime)s [%(levelname)s] - %(message)s')


@app.route("/td-height/<height>", methods=["POST"])
def process_html(height):
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


def validate_request():
    export_params_json = request.form.get('exportParams')
    if export_params_json is None:
        return "Missing exportParams", 400
    else:
        export_params_json = json.loads(export_params_json)

    html = request.form.get('html')
    if html is None:
        return "Missing html", 400
    return export_params_json, html


def start_server(port):
    http_server = WSGIServer(("", port), app)
    http_server.serve_forever()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Webhook: table cell auto height setter")
    parser.add_argument("--port", default=9333, type=int, required=False, help="Service port")
    args = parser.parse_args()

    logging.info(f"Service listening on port: {args.port}")

    start_server(args.port)

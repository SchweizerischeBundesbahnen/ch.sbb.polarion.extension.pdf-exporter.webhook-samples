import argparse
import logging
import re

from flask import Flask, Response, request
from gevent.pywsgi import WSGIServer

app = Flask(__name__)


@app.route("/process", methods=["POST"])
def process_html():
    html_content = request.form.get('html')
    if html_content:
        pattern = r'(<(?:td|th)[^>]*\sheight:\s*)\d+(\.\d+)?px'
        html_content = re.sub(pattern, r'\1auto', string=html_content)

    response = Response(html_content, mimetype="text/html", status=200)
    return response


def start_server(port):
    http_server = WSGIServer(("", port), app)
    http_server.serve_forever()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Web Hook example")
    parser.add_argument("--port", default=9333, type=int, required=False, help="Service port")
    args = parser.parse_args()

    logging.getLogger().setLevel(logging.DEBUG)
    logging.info("Service listening port: " + str(args.port))

    start_server(args.port)

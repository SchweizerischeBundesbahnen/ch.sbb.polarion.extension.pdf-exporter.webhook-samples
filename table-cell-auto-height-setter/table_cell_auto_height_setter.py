import logging
import re
import sys
from pathlib import Path

from flask import abort

# The shared module is in the repository root, next to the folder of this sample.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from common.webhook_server import (  # noqa: E402
    app, auth, validate_request, html_response, plain_response, create_parser, configure_auth, start_server,
)


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

    return html_response(html)


def change_height(html, height):
    pattern = r'(<t[dh][^>]{0,100}?style=[^>]{0,100}?height:\s*)(\d+(?:\.\d+)?px)'
    return re.sub(pattern, lambda m: m.group(1) + height, html)


def sanitize_input(user_input):
    user_input = re.sub(r'[\r\n]', '', user_input).strip()
    # Allow only integer + units of measure and 'auto'
    if user_input == "auto" or re.fullmatch(r'\d{1,4}(px|em|%)', user_input):
        return user_input
    raise ValueError("Invalid height value")


if __name__ == '__main__':
    parser = create_parser("Webhook: table cell auto height setter", 9333)
    args = parser.parse_args()
    configure_auth(parser, args)

    logging.info(f"Service listening on port: {args.port}")

    start_server(args.port)

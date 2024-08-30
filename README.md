# PDF-Exporter Webhook Samples

This project contains examples of webhooks that can include additional logic to process HTML prior to PDF generation.
Webhooks can be implemented as a REST endpoint by any programming language (Java, JS, Python, etc.) and hosted anywhere (inside Polarion as an extension or completely external).

## TableCellAutoHeightSetter

The TableCellAutHeightSetter webhook processes HTML content by replacing table cell height values specified in pixels (e.g. height: 100px) with height: auto. The processed HTML is then returned as a response to the client.

## Usage
This webhook endpoint can be launched with the following command:

```bash
python table-cell-auto-height-setter/table_cell_auto_height_setter.py [--port PORT] [--username USERNAME] [--password PASSWORD]
```

Optional `--port` parameter is using for changing of listening port.
Optional `--username` and `--password` parameters are using for basic auth.

## Configuration of the webhook URL in the PDF Exporter:

1. Navigate to: `Administration` ➙ `PDF Export` ➙ `Webhooks`
2. Add the webhook URL, for example http://localhost:9333/td-height/auto.

# PDF-exporter webhook samples

This project includes samples of webhooks that can incorporate additional logic for processing HTML prior to PDF generation.
Webhook can be implemented as a REST endpoint by any programming language (Java, JS, Python etc.) and be hosted anywhere (within Polarion as an extension, or absolutely external).

## TableCellAutoHeightSetter

The TableCellAutHeightSetter webhook processes HTML content by replacing table cell height values specified in pixels (e.g., height: 100px) with height: auto. The processed HTML is then returned as a response to the client.

## Usage
This webhook endpoint can be started using the following command:
```bash
python app/TableCellAutoHeightSetter.py --port=9333
```





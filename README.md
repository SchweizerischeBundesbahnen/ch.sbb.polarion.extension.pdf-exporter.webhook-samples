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

## TestRunLinkChecker

The TestRunLinkChecker webhook stops the export of a test run whose work item links are broken. It returns the HTML
unchanged and only decides whether the export may proceed.

A test record can point at a test case or a defect which was deleted, or which the exporting user cannot read. The
export then leaves that content out, attachments included, without saying so. This webhook refuses such an export
instead, and the message names every broken link.

The check itself is done by the
[XML Repair](https://github.com/SchweizerischeBundesbahnen/ch.sbb.polarion.extension.xml-repair) extension, which must
be installed. The webhook calls its `POST /polarion/xml-repair/rest/api/scan` endpoint with the
`TestRunBrokenLinksRepairer` repairer.

An export of anything but a test run passes through untouched, so the same webhook can stay in a style package used
for every document type.

### Usage

The webhook reads a Polarion personal access token from the `POLARION_TOKEN` environment variable. It is kept out of
the command line, where it would reach the process list and the shell history. The scan runs with the permissions of
that token's user, which is therefore the user whose read access decides whether a link counts as broken.

```bash
POLARION_TOKEN=<token> python test-run-link-checker/test_run_link_checker.py --username USERNAME --password PASSWORD [--port PORT] [--polarion-url URL] [--scan-timeout SECONDS]
```

Optional `--port` parameter changes the listening port, 9334 by default.
Optional `--polarion-url` parameter is the base URL of Polarion without the `/polarion` path, `http://localhost` by default.
Optional `--scan-timeout` parameter is the number of seconds to wait for the scan, 120 by default.

### Configuration in the PDF Exporter

1. Navigate to: `Administration` ➙ `PDF Export` ➙ `Webhooks`
2. Add the webhook URL, for example http://localhost:9334/test-run/check-links.
3. Check **Fail export on error** for that webhook. Without it a refusal is logged and the export continues, which
   is exactly what this webhook is there to prevent.
4. Select the webhook configuration in the style package used for test run exports.

The response body of the webhook is what the user sees, for example:

```
Test run 'elibrary/UAT' has 2 broken work item link(s). The export would silently leave the affected content out.
- Test case 'elibrary/EL-384' of a test record does not exist
- Test case 'elibrary/EL-385' of a test record does not exist
```

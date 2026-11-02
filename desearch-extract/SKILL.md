---
name: desearch-extract
description: Extract clean text or raw HTML from any public webpage URL with the canonical Desearch Extract API. Use this when you need the full contents of a specific page, including JavaScript-rendered pages.
metadata: {"clawdbot":{"emoji":"📄","homepage":"https://desearch.ai","requires":{"env":["DESEARCH_API_KEY"]}}}
---

# Extract Webpage By Desearch

Extract content from a public webpage URL as clean text or raw HTML.

## Quick Start

1. Get an API key from https://console.desearch.ai
2. Set environment variable: `export DESEARCH_API_KEY='your-key-here'`

## Usage

```bash
# Extract clean text (default)
scripts/desearch.py extract "https://en.wikipedia.org/wiki/Artificial_intelligence"

# Extract markdown (headings, lists, tables and code)
scripts/desearch.py extract "https://en.wikipedia.org/wiki/Artificial_intelligence" --format markdown

# Extract raw HTML
scripts/desearch.py extract "https://example.com" --format html

# Render a JavaScript application and wait 500 milliseconds after load
scripts/desearch.py extract "https://example.com/app" --js --wait 500

# Every section of the page (hours, fee tables, notices), not only the main article
scripts/desearch.py extract "https://peles.ro/en/program-si-taxe/" --full-page
```

## Options

| Option | Description |
|--------|-------------|
| `--format` | Output content format: `text` (default), `markdown` or `html` |
| `--js` | Render JavaScript before extracting content |
| `--wait` | Extra post-load wait in milliseconds, from 0 to 30000; used with `--js` |
| `--full-page` | Only with `text`: return all visible text of the page, one block per line, instead of its main content |

## Response

The response is plain text, markdown or raw HTML, not JSON. Prefer `markdown` when headings, lists or tables matter, `text` for plain prose, and `html` only when page markup is specifically required. `text` is the page's main content; when the facts you need may sit in tables, tabs or notices outside the main article, use `--full-page`.

## Errors

Status 401 means the API key is missing or invalid. Status 402 means the account balance is depleted. Validation failures, including invalid wait values, return status 422.

Pages that cannot be served return JSON with an `error_code` and are not charged:

- `js_required` (422): the page only shows its content after JavaScript runs. Retry with `--js`.
- `blocked` (503): the site refused the request or answered with a bot check. Retrying with `--js` may work.
- `page_not_found` (404): the site answered 404.
- `upstream_timeout` or `upstream_failed` (503): the page could not be fetched in time. Retry later.

## Resources

- [Extract API Reference](https://desearch.ai/docs/api-reference/get-web-extract)
- [Desearch Console](https://console.desearch.ai)
- Legacy `GET /web/crawl` integrations remain available during the migration.

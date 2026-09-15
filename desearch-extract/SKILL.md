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

# Extract raw HTML
scripts/desearch.py extract "https://example.com" --format html

# Render a JavaScript application and wait 500 milliseconds after load
scripts/desearch.py extract "https://example.com/app" --js --wait 500
```

## Options

| Option | Description |
|--------|-------------|
| `--format` | Output content format: `text` (default) or `html` |
| `--js` | Render JavaScript before extracting content |
| `--wait` | Extra post-load wait in milliseconds, from 0 to 30000; used with `--js` |

## Response

The response is plain text or raw HTML, not JSON. Prefer `text` unless page markup is specifically required.

## Errors

Status 401 means the API key is missing or invalid. Status 402 means the account balance is depleted. Validation failures, including invalid wait values, return status 422.

## Resources

- [Extract API Reference](https://desearch.ai/docs/api-reference/get-web-extract)
- [Desearch Console](https://console.desearch.ai)
- Legacy `GET /web/crawl` integrations remain available during the migration.

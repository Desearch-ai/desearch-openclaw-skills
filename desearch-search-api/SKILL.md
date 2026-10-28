---
name: desearch-search-api
description: Search the web and get ranked pages, each with the passage that best answers the query and, optionally, the full page text. Use this when you need to read sources, not only list links, for example to answer a question or ground a summary in current pages.
metadata: {"clawdbot":{"emoji":"🎯","homepage":"https://desearch.ai","requires":{"env":["DESEARCH_API_KEY"]}}}
---

# Search API By Desearch

Web search that returns ranked pages, each with the passage that best matches the query. Ask for the full page text when you need to read the whole source. For plain SERP links and snippets, use `desearch-web-search`.

## Quick Start

1. Get an API key from https://console.desearch.ai
2. Set environment variable: `export DESEARCH_API_KEY='your-key-here'`

## Usage

```bash
# Ranked pages with the best-matching passage
scripts/desearch.py search "What is Bittensor?"

# Faster results, 20 pages
scripts/desearch.py search "latest AI regulation news" --mode fast --count 20

# Pages published in a date range, with full page text
scripts/desearch.py search "subnet emissions" --start-date 2026-01-01 --end-date 2026-03-31 --page-text
```

## Options

| Option | Description |
|--------|-------------|
| `--mode` | `balanced` (API default) favors relevance; `fast` returns results sooner |
| `--count`, `-n` | Number of results: `10` (API default), `15`, or `20` |
| `--start-date` | Only pages published on or after this date (YYYY-MM-DD) |
| `--end-date` | Only pages published on or before this date (YYYY-MM-DD) |
| `--no-highlights` | Leave out the best-matching passage |
| `--page-text` | Include the full text of each page |

The query can be up to 2000 characters.

## Response

### Example (truncated)
```json
{
  "results": [
    {
      "url": "https://bittensor.com/",
      "title": "Bittensor",
      "highlights": ["Bittensor is an open-source platform ..."]
    }
  ],
  "cost_usd": ...,
  "usage_count": ...,
  "service": "...",
  "currency": "USD"
}
```

| Field | Type | Description |
|-------|------|-------------|
| `results[].url` | string | Page URL |
| `results[].title` | string | Page title |
| `results[].published_date` | string | Publication date (YYYY-MM-DD). Omitted when unknown. |
| `results[].highlights` | string[] | Passage that best matches the query. Left out with `--no-highlights`. |
| `results[].page_text` | string | Full page text. Only with `--page-text`. |
| `cost_usd` | number | Cost charged for this request in USD |
| `usage_count` | int | Billable usage units for this request |
| `service`, `currency` | string | Pricing service and currency of `cost_usd` |

Results are ordered best first.

### Errors
| Status | Meaning |
|--------|---------|
| 401 | Missing or invalid API key |
| 402 | Balance depleted |
| 422 | Invalid parameters, for example a `count` other than 10, 15, or 20 |
| 503 | Search unavailable; retry later |

Error bodies are JSON with a `detail` field and are printed as returned.

## Resources
- [API Reference](https://desearch.ai/docs/api-reference)
- [Desearch Console](https://console.desearch.ai)

---
name: desearch-crawl
description: Crawl/scrape and extract content from any webpage URL. Returns the page content as clean text or raw HTML. Use this when you need to read the full contents of a specific web page.
metadata: {"clawdbot":{"emoji":"🕷️","homepage":"https://desearch.ai","requires":{"env":["DESEARCH_API_KEY"]}}}
---

# Crawl Webpage By Desearch

Extract content from any webpage URL. Returns clean text or raw HTML.

## Setup

1. Get an API key from https://console.desearch.ai
2. Set environment variable: `export DESEARCH_API_KEY='your-key-here'`

## Usage

```bash
# Crawl a webpage (returns clean text by default)
scripts/desearch.py crawl "https://en.wikipedia.org/wiki/Artificial_intelligence"

# Get raw HTML
scripts/desearch.py crawl "https://example.com" --crawl-format html
```


## Options

| Option | Description |
|--------|-------------|
| `--crawl-format` | Output content format: `text` (default) or `html` |

## Examples

### Read a documentation page
```bash
scripts/desearch.py crawl "https://docs.python.org/3/tutorial/index.html"
```

### Get raw HTML for analysis
```bash
scripts/desearch.py crawl "https://example.com/page" --crawl-format html
```


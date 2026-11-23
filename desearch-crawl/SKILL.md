---
name: desearch-crawl
description: Deprecated compatibility skill for existing Desearch crawl integrations. It still extracts clean text or raw HTML through the legacy endpoint; use desearch-extract for new integrations.
metadata: {"clawdbot":{"emoji":"🕷️","homepage":"https://desearch.ai","requires":{"env":["DESEARCH_API_KEY"]}}}
---

# Legacy Crawl Webpage By Desearch

Extract content from any webpage URL. Returns clean text or raw HTML.

> Deprecated: this skill remains functional for existing integrations through `GET /web/crawl`. Use `desearch-extract` and `GET /web/extract` for new integrations.

## Quick Start

Run the setup and command examples below from this skill's directory: the folder containing `SKILL.md` and `scripts/`.

Requires Python 3.10 or newer as `python3` on `PATH`. With Python 3.12 installed, create and activate an environment in this skill's directory:

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python3 --version
```

Confirm that the version printed is Python 3.12. Keep this environment active while running the examples. If `python3.12` is unavailable, install Python 3.12 first. For OpenClaw, ensure its process also finds Python 3.10 or newer as `python3` on `PATH`. The scripts use only the Python standard library.

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

## Response

### Example (`format=text`, truncated, default)
```
Artificial intelligence (AI) is the capability of computational systems to perform tasks that typically require human intelligence, such as learning, reasoning, problem-solving, perception, and decision-making...
```

### Example (`format=html`, truncated)
```html
<!DOCTYPE html>
<html>
  <head><title>Artificial intelligence - Wikipedia</title></head>
  <body>
    <p>Artificial intelligence (AI) is the capability of computational systems...</p>
  </body>
</html>
```

### Notes
- Response is plain text or raw HTML, not JSON.
- Default format is `text`. Use `--crawl-format html` only when you need to inspect page structure.
- Prefer `text` format to avoid bloating the agent context with markup.

### Errors
Status 401, Unauthorized (e.g., missing/invalid API key)
```json
{
  "detail": "Invalid or missing API key"
}
```

Status 402, Payment Required (e.g., balance depleted)
```json
{
  "detail": "Insufficient balance, please add funds to your account to continue using the service."
}
```

## Resources
- [API Reference](https://desearch.ai/docs/api-reference/get-web-crawl)
- [Desearch Console](https://console.desearch.ai)

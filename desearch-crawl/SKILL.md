---
name: desearch-crawl
description: Deprecated compatibility skill for existing Desearch crawl integrations. It still extracts clean text or raw HTML through the legacy endpoint; use desearch-extract for new integrations.
metadata: {"clawdbot":{"emoji":"🕷️","homepage":"https://desearch.ai","requires":{"env":["DESEARCH_API_KEY"]}}}
---

# Legacy Crawl Webpage By Desearch

Extract content from any webpage URL. Returns clean text or raw HTML.

> Deprecated: this skill remains functional for existing integrations through `GET /web/crawl`. Use `desearch-extract` and `GET /web/extract` for new integrations.

## Data transmission

The full crawl URL, including its path, query string and any account identifiers or tokens embedded in it, is sent to `https://api.desearch.ai` along with the requested output format. The `DESEARCH_API_KEY` value is sent to the same service in the HTTP `Authorization` header. Submit only inputs you are authorized to share with Desearch. Keep secrets and confidential information out of queries, account parameters and crawl URLs.

## Permissions and allowed tool scope

Use OpenClaw's `exec` tool for the documented `python3 scripts/desearch.py` commands from this skill's directory. The API commands require the delivered script, a supported Python runtime, the `DESEARCH_API_KEY` environment variable and outbound HTTPS to `api.desearch.ai`; they print results to stdout. They need no browser or messaging tools, elevated execution, or unrelated local files. The optional environment setup writes `.venv` in the skill directory.

This is the intended scope, not an enforced permission boundary. Configure access using OpenClaw's [tool policy](https://docs.openclaw.ai/tools) and [exec controls](https://docs.openclaw.ai/tools/exec). [Skill allowlists](https://docs.openclaw.ai/tools/skills#agent-skill-allowlists) do not constrain host shell access. Keep existing execution approvals and restrictions in place; this skill does not grant additional tools or permissions.

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
python3 scripts/desearch.py crawl "https://en.wikipedia.org/wiki/Artificial_intelligence"

# Get raw HTML
python3 scripts/desearch.py crawl "https://example.com" --crawl-format html
```


## Options

| Option | Description |
|--------|-------------|
| `--crawl-format` | Output content format: `text` (default) or `html` |

## Examples

### Read a documentation page
```bash
python3 scripts/desearch.py crawl "https://docs.python.org/3/tutorial/index.html"
```

### Get raw HTML for analysis
```bash
python3 scripts/desearch.py crawl "https://example.com/page" --crawl-format html
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

---
name: desearch-web-search
description: Search the web and get SERP-style results with titles, URLs and snippets. Use this for general web queries when you need links to sources.
metadata: {"clawdbot":{"emoji":"🌐","homepage":"https://desearch.ai","requires":{"env":["DESEARCH_API_KEY"]}}}
---

# Web Search By Desearch

Search the web and get SERP-style results with titles, URLs and snippets. Use this for general web queries when you need links to sources.

## Data transmission

The full search query and pagination offset are sent to `https://api.desearch.ai`. Any account identifiers or URLs included in your query are part of that transmission. The `DESEARCH_API_KEY` value is sent to the same service in the HTTP `Authorization` header. Submit only inputs you are authorized to share with Desearch. Keep secrets and confidential information out of queries, account parameters and crawl URLs.

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
# Basic web search
python3 scripts/desearch.py web "quantum computing"

# Paginated results
python3 scripts/desearch.py web "quantum computing" --start 10
```

## Options

| Option | Description |
|--------|-------------|
| `--start` | Number of results to skip (default: 0; documented valid range: 0–100). Use this offset to paginate. |

## Response

### Example
```bash
python3 scripts/desearch.py web "best sights in Georgia"
```

```json
{
  "data": [
    {
      "title": "Cool places and fun things to do in Georgia ? : r/solotravel",
      "snippet": "I was in Georgia earlier this month. My favorite place was Mtirala National Park in Adjara. The mountains and forest were absolutely beautiful ...",
      "link": "https://www.reddit.com/r/solotravel/comments/py4wls/cool_places_and_fun_things_to_do_in_georgia/",
    },
  ]
}
```

### Notes
- Returns up to 20 results per request; the actual count may vary. Use `--start` to skip results and paginate.

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
- [API Reference](https://desearch.ai/docs/api-reference/get-web)
- [Desearch Console](https://console.desearch.ai)
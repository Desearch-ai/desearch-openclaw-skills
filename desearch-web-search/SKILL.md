---
name: desearch-web-search
description: Search the web and get real-time SERP-style results with titles, URLs, and snippets. Use this for general web queries when you need current links and information from across the internet.
metadata: {"clawdbot":{"emoji":"🌐","homepage":"https://desearch.ai","requires":{"env":["DESEARCH_API_KEY"]}}}
---

# Web Search By Desearch

Real-time web search returning structured SERP-style results with titles, links, and snippets.

## Setup

1. Get an API key from https://console.desearch.ai
2. Set environment variable: `export DESEARCH_API_KEY='your-key-here'`

## Usage

```bash
# Basic web search
scripts/desearch.py web "latest news on AI"

# Paginated results
scripts/desearch.py web "quantum computing" --start 10
```

## Options

| Option | Description |
|--------|-------------|
| `--start` | Pagination offset (default: 0). Use to get the next page of results. |

## Examples

### Search for current events
```bash
scripts/desearch.py web "latest AI regulations 2025"
```

### Browse paginated results
```bash
scripts/desearch.py web "best python libraries" --start 0
scripts/desearch.py web "best python libraries" --start 10
```


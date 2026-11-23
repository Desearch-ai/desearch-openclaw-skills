---
name: desearch-ai-search
description: AI Search searches X posts and the web and can return a summary. Supported AI Search source IDs are web and twitter. For web-only results, use the Search API.
metadata: {"clawdbot":{"emoji":"🔎","homepage":"https://desearch.ai","requires":{"env":["DESEARCH_API_KEY"]}}}
---

# AI Search By Desearch

AI Search searches X posts and the web and can return a summary. Supported AI Search source IDs are web and twitter. For web-only results, use the Search API.

## Data transmission

The full search query, selected sources and other supplied search parameters are sent to `https://api.desearch.ai`. Any account identifiers or URLs included in your query are part of that transmission. The `DESEARCH_API_KEY` value is sent to the same service in the HTTP `Authorization` header. Submit only inputs you are authorized to share with Desearch. Keep secrets and confidential information out of queries, account parameters and crawl URLs.

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

Run the following from this skill's directory:

```bash
# AI Search with web and X sources
python3 scripts/desearch.py ai_search "What is Bittensor?" --tools web,twitter

# Web results through the Search API (compatibility command)
python3 scripts/desearch.py ai_web "machine learning papers" --tools web

# AI X/Twitter link search
python3 scripts/desearch.py ai_x "crypto market trends" --count 20
```

## Commands

| Command | Description |
|---------|-------------|
| `ai_search` | Search X posts and the web, with an optional summary. |
| `ai_web` | Compatibility command for web results using `POST /search`. Sends `query` instead of `prompt`. |
| `ai_x` | AI-powered X/Twitter search returning post links. |

## Sources

AI Search sources: web, twitter. Other source IDs are unsupported and may be rejected. For Reddit results, use POST /search with include_domains set to ["reddit.com"].

For web results, use POST /search. POST /desearch/ai/search/links/web is deprecated. YouTube is not an AI Search source; use the separate YouTube tools documented in the MCP guide.

See the [MCP guide](https://desearch.ai/docs/guide/sdk/mcp) for the separate YouTube tools and the [Search API guide](https://desearch.ai/docs/guide/apis/search-api) for domain filtering.

## Options

| Option | Description | Applies to |
|--------|-------------|------------|
| `--tools`, `-t` | Comma-separated `web, twitter` (default: `web,twitter`). `ai_web` accepts only `web`; `ai_x` uses X automatically. | `ai_search`, `ai_web` |
| `--count`, `-n` | Number of results. `ai_web` accepts 10, 15 or 20 (Search API default: 10). | All |
| `--date-filter` | Time filter: `PAST_24_HOURS`, `PAST_2_DAYS`, `PAST_WEEK`, `PAST_2_WEEKS`, `PAST_MONTH`, `PAST_2_MONTHS`, `PAST_YEAR`, `PAST_2_YEARS` | `ai_search` |

## REST example

```bash
curl -X POST https://api.desearch.ai/desearch/ai/search \
  -H "Authorization: ${DESEARCH_API_KEY}" \
  -H 'Content-Type: application/json' \
  -d '{"prompt":"What is Bittensor?","tools":["web","twitter"],"streaming":false}'
```

## Response

### Example (truncated)
```json
{
  "tweets": [
    {
      "id": "2023465890369728573",
      "text": "Superposition allows qubits to encode multiple possibilities...",
      "url": "https://x.com/rukky_003/status/2023465890369728573",
      "created_at": "2026-02-16T18:33:57.000Z",
      "like_count": 5,
      "retweet_count": 0,
      "view_count": 155,
      "reply_count": 0,
      "quote_count": 2,
      "lang": "en",
      "is_retweet": false,
      "is_quote_tweet": true,
      "media": [],
      "user": {
        "id": "1316260427190472704",
        "username": "rukky_003",
        "name": "RuqoCrypto 🧠",
        "url": "https://x.com/rukky_003",
        "followers_count": 2424,
        "verified": false,
        "is_blue_verified": true
      }
    }
  ],
  "search": [
    {
      "title": "What Is Quantum Computing? | IBM",
      "link": "https://www.ibm.com/think/topics/quantum-computing",
      "snippet": "Quantum computers take advantage of quantum mechanics..."
    }
  ],
  "miner_link_scores": {
    "2023465890369728573": "HIGH",
    "https://www.ibm.com/think/topics/quantum-computing": "MEDIUM"
  },
  "completion": "Quantum computing uses qubits that leverage superposition and entanglement to compute in fundamentally different ways than classical computers..."
}
```

### Notes
- `miner_link_scores` keys are tweet IDs for Twitter results and full URLs for web results. Values are `"HIGH"`, `"MEDIUM"`, or `"LOW"`.
- `media` is always an array; empty `[]` when no media is attached.
- `completion` is always a string; empty string `""` if summarization fails.

### Errors
Status 401, Unauthorized (e.g., missing/invalid API key)
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
- [API Reference](https://desearch.ai/docs/api-reference/post-desearch-ai-search)
- [Desearch Console](https://console.desearch.ai)

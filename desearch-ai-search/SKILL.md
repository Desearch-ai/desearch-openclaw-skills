---
name: desearch-ai-search
description: AI-powered search that aggregates and summarizes results from multiple sources including web, X/Twitter, Reddit, Hacker News, YouTube, ArXiv, and Wikipedia. Use this when you need a synthesized answer or curated links from across the internet and social platforms.
metadata: {"clawdbot":{"emoji":"🔎","homepage":"https://desearch.ai","requires":{"env":["DESEARCH_API_KEY"]}}}
---

# AI Search By Desearch

AI-powered multi-source search that aggregates results from web, Reddit, Hacker News, YouTube, ArXiv, Wikipedia, and X/Twitter — returning either summarized answers or curated links.

## Setup

1. Get an API key from https://console.desearch.ai
2. Set environment variable: `export DESEARCH_API_KEY='your-key-here'`

## Usage

```bash
# AI contextual search (summarized results from multiple sources)
scripts/desearch.py ai_search "What is Bittensor?" --tools web,reddit,youtube

# AI web link search (curated links from specific sources)
scripts/desearch.py ai_web "machine learning papers" --tools arxiv,web,wikipedia

# AI X/Twitter link search (curated post links)
scripts/desearch.py ai_x "crypto market trends" --count 20
```

## Commands

| Command | Description |
|---------|-------------|
| `ai_search` | AI-summarized search across multiple sources. Returns aggregated results with context. |
| `ai_web` | AI-curated link search. Returns the most relevant links from chosen sources. |
| `ai_x` | AI-powered X/Twitter search. Returns the most relevant post links for a topic. |

## Options

| Option | Description | Applies to |
|--------|-------------|------------|
| `--tools`, `-t` | Sources to search: `web`, `hackernews`, `reddit`, `wikipedia`, `youtube`, `arxiv`, `twitter` (comma-separated) | Both |
| `--count`, `-n` | Number of results (default: 10, max: 200) | All |
| `--date-filter` | Time filter: `PAST_24_HOURS`, `PAST_2_DAYS`, `PAST_WEEK`, `PAST_2_WEEKS`, `PAST_MONTH`, `PAST_2_MONTHS`, `PAST_YEAR`, `PAST_2_YEARS` | `ai_search` |

## Examples

### Research a topic with AI summary
```bash
scripts/desearch.py ai_search "What are the latest developments in quantum computing?" --tools web,arxiv,reddit
```

### Find academic papers
```bash
scripts/desearch.py ai_web "transformer architecture improvements 2025" --tools arxiv,web
```

### Get recent news from multiple sources
```bash
scripts/desearch.py ai_search "AI regulation news" --tools web,hackernews,reddit --date-filter PAST_WEEK
```

### Find YouTube tutorials
```bash
scripts/desearch.py ai_web "learn rust programming" --tools youtube,web
```

### AI-curated X/Twitter links on a topic
```bash
scripts/desearch.py ai_x "latest AI breakthroughs" --count 15
```


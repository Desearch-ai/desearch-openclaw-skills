# Desearch OpenClaw Skills

A collection of [OpenClaw](https://openclaw.ai) skills that bring [Desearch](https://desearch.ai) search and webpage extraction capabilities to OpenClaw.

## Skills

| Skill | Emoji | Description |
|-------|-------|-------------|
| [desearch-ai-search](desearch-ai-search/) | 🔎 | AI search that summarizes results from web, X, Reddit, Hacker News, YouTube, arXiv and Wikipedia, with links to the sources |
| [desearch-extract](desearch-extract/) | 📄 | Extract clean text or raw HTML from any webpage through the canonical Extract API |
| [desearch-crawl](desearch-crawl/) | 🕷️ | Deprecated compatibility skill for existing crawl integrations |
| [desearch-web-search](desearch-web-search/) | 🌐 | Search the web and get SERP-style results with titles, URLs and snippets. Use this for general web queries when you need links to sources. |
| [desearch-x-search](desearch-x-search/) | 𝕏 | Search X (Twitter) posts by keyword, user or hashtag. Get a user's timeline, replies or retweeters, or fetch specific posts by ID or URL. |

## Requirements

- A Desearch API key from [console.desearch.ai](https://console.desearch.ai)
- Set the environment variable:
  ```bash
  export DESEARCH_API_KEY='your-key-here'
  ```

## Quick Start

Each skill uses a `scripts/desearch.py` entry point. Examples:

```bash
# AI-summarized multi-source search
desearch-ai-search/scripts/desearch.py ai_search "What is Bittensor?" --tools web,reddit,youtube

# Extract a webpage
desearch-extract/scripts/desearch.py extract "https://en.wikipedia.org/wiki/Artificial_intelligence"

# Web search
desearch-web-search/scripts/desearch.py web "latest AI news"

# X/Twitter search
desearch-x-search/scripts/desearch.py x "AI breakthroughs" --sort Latest --count 20
```

See each skill's `SKILL.md` for full documentation, options, and examples.

Existing `desearch-crawl` installations remain functional through the deprecated `GET /web/crawl` compatibility route. Use `desearch-extract` for new integrations.

# Desearch OpenClaw Skills

A collection of [OpenClaw](https://openclaw.ai) skills that bring [Desearch](https://desearch.ai) real-time search and web crawling capabilities to OpenClaw.

## Skills

| Skill | Emoji | Description |
|-------|-------|-------------|
| [desearch-ai-search](desearch-ai-search/) | 🔎 | AI-powered search aggregating results from web, X/Twitter, Reddit, Hacker News, YouTube, ArXiv, and Wikipedia — with summarized answers or curated links |
| [desearch-crawl](desearch-crawl/) | 🕷️ | Crawl any webpage and extract clean text or raw HTML |
| [desearch-web-search](desearch-web-search/) | 🌐 | Real-time web search returning SERP-style results with titles, URLs, and snippets |
| [desearch-x-search](desearch-x-search/) | 𝕏 | Real-time X (Twitter) search — posts, timelines, replies, retweeters with advanced filters |

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

# Crawl a webpage
desearch-crawl/scripts/desearch.py crawl "https://en.wikipedia.org/wiki/Artificial_intelligence"

# Web search
desearch-web-search/scripts/desearch.py web "latest AI news"

# X/Twitter search
desearch-x-search/scripts/desearch.py x "AI breakthroughs" --sort Latest --count 20
```

See each skill's `SKILL.md` for full documentation, options, and examples.

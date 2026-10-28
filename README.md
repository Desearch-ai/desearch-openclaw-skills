# Desearch OpenClaw Skills

A collection of [OpenClaw](https://openclaw.ai) skills that bring [Desearch](https://desearch.ai) real-time search and webpage extraction capabilities to OpenClaw.

## Skills

| Skill | Emoji | Description |
|-------|-------|-------------|
| [desearch-ai-search](desearch-ai-search/) | 🔎 | AI-powered search aggregating results from web, X/Twitter, Reddit, Hacker News, YouTube, ArXiv, and Wikipedia — with summarized answers or curated links |
| [desearch-extract](desearch-extract/) | 📄 | Extract clean text or raw HTML from any webpage through the canonical Extract API |
| [desearch-people-search](desearch-people-search/) | 👥 | Find people and creators on X, YouTube, LinkedIn, or TikTok who match a plain-language description. Billed per person found; runs in the background for 1 to 5 minutes |
| [desearch-company-search](desearch-company-search/) | 🏢 | Find companies from a plain-language description, or enrich domains you already have, with public emails, phones, social profiles, and leaders (CEO, founders, CTO, CFO) with checked emails. Billed per company delivered; runs in the background |
| [desearch-crawl](desearch-crawl/) | 🕷️ | Deprecated compatibility skill for existing crawl integrations |
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

# Extract a webpage
desearch-extract/scripts/desearch.py extract "https://en.wikipedia.org/wiki/Artificial_intelligence"

# Web search
desearch-web-search/scripts/desearch.py web "latest AI news"

# X/Twitter search
desearch-x-search/scripts/desearch.py x "AI breakthroughs" --sort Latest --count 20

# People Search (billed, asynchronous): start, wait, read, export
desearch-people-search/scripts/desearch.py people_search x "Indie hackers building in public who share their MRR" --count 10
desearch-people-search/scripts/desearch.py people_wait <task_id>
desearch-people-search/scripts/desearch.py people_results <task_id> --all
desearch-people-search/scripts/desearch.py people_export <task_id> --output people.csv

# Company Search (billed, asynchronous): find companies or enrich domains, then wait, read, export
desearch-company-search/scripts/desearch.py company_search "Series A fintech startups in Berlin building payment infrastructure" --count 25
desearch-company-search/scripts/desearch.py company_enrich acme.com https://www.beta.io/about
desearch-company-search/scripts/desearch.py company_wait <task_id>
desearch-company-search/scripts/desearch.py company_results <task_id> --all
desearch-company-search/scripts/desearch.py company_export <task_id> --output companies.csv
```

See each skill's `SKILL.md` for full documentation, options, and examples.

`desearch-people-search` is billed differently from the other skills: `people_search` starts a background task that reserves `count` people at the platform's per-person price and settles to the people it delivers (a search that finds no one is free). Status, results, exports, task control, and the profiles library are free. See [desearch-people-search/SKILL.md](desearch-people-search/SKILL.md) for prices and the retry-safe `--idempotency-key` flow.

`desearch-company-search` is billed the same way: `company_search` reserves `count` companies at $0.09 each (minimum 2 billed when it delivers any) and `company_enrich` reserves one company per domain at $0.05 each (minimum 1), and each settles to the companies it delivers (a task that delivers none is free). Status, results, exports, and task control are free. See [desearch-company-search/SKILL.md](desearch-company-search/SKILL.md) for how results fill in stage by stage and the retry-safe `--idempotency-key` flow.

Existing `desearch-crawl` installations remain functional through the deprecated `GET /web/crawl` compatibility route. Use `desearch-extract` for new integrations.

## Tests

The tests mock the HTTP layer and never call the API:

```bash
python3 -m unittest discover -s tests
```

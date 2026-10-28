# Desearch OpenClaw Skills

A collection of [OpenClaw](https://openclaw.ai) skills that bring [Desearch](https://desearch.ai) real-time search, social data, and webpage extraction capabilities to OpenClaw.

## Skills

| Skill | Emoji | Description |
|-------|-------|-------------|
| [desearch-ai-search](desearch-ai-search/) | 🔎 | AI-powered search aggregating results from web, X/Twitter, Reddit, Hacker News, YouTube, ArXiv, and Wikipedia — with summarized answers or curated links |
| [desearch-extract](desearch-extract/) | 📄 | Extract clean text or raw HTML from any webpage through the canonical Extract API |
| [desearch-facebook-search](desearch-facebook-search/) | 📘 | Meta Ad Library search, plus public Facebook pages, their posts, single posts, and comments |
| [desearch-instagram-search](desearch-instagram-search/) | 📸 | Public Instagram profile search, profiles, their posts, single posts, comments, and hashtag posts |
| [desearch-people-search](desearch-people-search/) | 👥 | Find people and creators on X, YouTube, LinkedIn, or TikTok who match a plain-language description. Billed per person found; runs in the background for 1 to 5 minutes |
| [desearch-crawl](desearch-crawl/) | 🕷️ | Deprecated compatibility skill for existing crawl integrations |
| [desearch-search-api](desearch-search-api/) | 🎯 | Web search returning ranked pages, each with the passage that best matches the query and optionally the full page text |
| [desearch-tiktok-search](desearch-tiktok-search/) | 🎵 | Public TikTok post search, profiles, their posts, single posts, comments, hashtag posts, and trending posts |
| [desearch-web-search](desearch-web-search/) | 🌐 | Real-time web search returning SERP-style results with titles, URLs, and snippets |
| [desearch-x-search](desearch-x-search/) | 𝕏 | Real-time X (Twitter) search — posts, timelines, replies, retweeters, trends with advanced filters |

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

# Search API: ranked pages with the best-matching passage
desearch-search-api/scripts/desearch.py search "What is Bittensor?" --count 10

# X/Twitter search and trends
desearch-x-search/scripts/desearch.py x "AI breakthroughs" --sort Latest --count 20
desearch-x-search/scripts/desearch.py x_trends 1

# TikTok, Instagram, and Facebook
desearch-tiktok-search/scripts/desearch.py tiktok_hashtag ai --count 20
desearch-instagram-search/scripts/desearch.py instagram_profile_posts instagram --count 12
desearch-facebook-search/scripts/desearch.py facebook_search "running shoes" --count 10

# People Search (billed, asynchronous): start, wait, read, export
desearch-people-search/scripts/desearch.py people_search x "Indie hackers building in public who share their MRR" --count 10
desearch-people-search/scripts/desearch.py people_wait <task_id>
desearch-people-search/scripts/desearch.py people_results <task_id> --all
desearch-people-search/scripts/desearch.py people_export <task_id> --output people.csv
desearch-people-search/scripts/desearch.py people_profiles_export x --has email --output x-people.csv
```

See each skill's `SKILL.md` for full documentation, options, and examples.

`desearch-people-search` is billed differently from the other skills: `people_search` starts a background task that reserves `count` people at the platform's per-person price and settles to the people it delivers (a search that finds no one is free). Status, results, exports, task control, and the profiles library are free. See [desearch-people-search/SKILL.md](desearch-people-search/SKILL.md) for prices and the retry-safe `--idempotency-key` flow.

Existing `desearch-crawl` installations remain functional through the deprecated `GET /web/crawl` compatibility route. Use `desearch-extract` for new integrations.

## Social Pagination

TikTok, Instagram, and Facebook list commands print one page as `{"results": [...], "next_cursor": "..."}`. The API returns the page as a JSON array and the cursor in the `x-desearch-next-cursor` response header; the CLI puts both in one object. To read the next page, repeat the same command and target with `--cursor <next_cursor>`. `next_cursor` is `null` on the last page.

```bash
desearch-tiktok-search/scripts/desearch.py tiktok_profile_posts tiktok --count 20
# {"results": [...], "next_cursor": "eyJ2IjoxLCJyb3V0ZSI6..."}
desearch-tiktok-search/scripts/desearch.py tiktok_profile_posts tiktok --count 20 --cursor "eyJ2IjoxLCJyb3V0ZSI6..."
```

The cursor is opaque: send it back exactly as printed. It is valid for 24 hours, only for the command and target that returned it; any other value returns `422` and is not charged. `tiktok_trending` and `instagram_search` return a plain list and do not page.

## Tests

The tests mock the HTTP layer and never call the API:

```bash
python3 -m unittest discover -s tests
```

`scripts/e2e-full-coverage.py` is a live smoke test for the TikTok, Instagram, Facebook, Search API, X trends, and People Search library export commands. It calls the real API, so it spends balance; see the script header before running it:

```bash
DESEARCH_API_KEY='your-key-here' python3 scripts/e2e-full-coverage.py
```

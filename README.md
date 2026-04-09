# Desearch OpenClaw Skills

Python-based OpenClaw skills for Desearch search and crawling APIs. This repo packages four skills as standalone `SKILL.md` manifests plus executable `scripts/desearch.py` entrypoints.

## What is in this repo

- `desearch-ai-search/` , AI-powered aggregated search across multiple sources
- `desearch-crawl/` , webpage crawling and extraction
- `desearch-web-search/` , structured web search
- `desearch-x-search/` , X/Twitter search and monitoring

Each skill follows the same layout:

- `SKILL.md` , skill metadata, setup, and examples
- `scripts/desearch.py` , executable Python CLI wrapper around `https://api.desearch.ai`

## Tech stack

- Python 3 scripts with `argparse`, `json`, and `urllib` from the standard library
- Desearch HTTP API at `https://api.desearch.ai`
- OpenClaw skill manifests in frontmatter-based `SKILL.md` files
- Docker-oriented deployment target: the skills are intended to be mounted into an OpenClaw/ClawDBot environment, but this repository does not currently ship its own `Dockerfile` or `docker-compose.yml`

## Requirements

- Desearch API key from <https://console.desearch.ai>
- Python 3 available in the runtime
- `DESEARCH_API_KEY` exported in the shell or container environment

```bash
export DESEARCH_API_KEY='your-key-here'
```

## How to run

Because every script has a shebang and executable bit, you can run them directly:

```bash
./desearch-ai-search/scripts/desearch.py ai_search "What is Bittensor?" --tools web,reddit,youtube
./desearch-crawl/scripts/desearch.py crawl "https://en.wikipedia.org/wiki/Artificial_intelligence"
./desearch-web-search/scripts/desearch.py web "latest AI news"
./desearch-x-search/scripts/desearch.py x "AI breakthroughs" --sort Latest --count 20
```

You can also invoke them with Python explicitly:

```bash
python3 desearch-ai-search/scripts/desearch.py ai_search "What is Bittensor?"
python3 desearch-crawl/scripts/desearch.py crawl "https://docs.python.org/3/tutorial/index.html"
python3 desearch-web-search/scripts/desearch.py web "desearch api"
python3 desearch-x-search/scripts/desearch.py x_user elonmusk --query "AI" --count 10
```

## Skills available

### `desearch-ai-search`
- Commands: `ai_search`, `ai_web`, `ai_x`
- API routes:
  - `POST /desearch/ai/search`
  - `POST /desearch/ai/search/links/web`
  - `POST /desearch/ai/search/links/twitter`
- Supports `--tools`, `--count`, and `--date-filter`
- Default tools for `ai_search` are `twitter` and `web` when `--tools` is omitted

### `desearch-crawl`
- Command: `crawl`
- API route: `GET /web/crawl`
- Supports `--crawl-format text|html`

### `desearch-web-search`
- Command: `web`
- API route: `GET /web`
- Supports `--start` pagination offset

### `desearch-x-search`
- Commands: `x`, `x_post`, `x_urls`, `x_user`, `x_timeline`, `x_retweeters`, `x_replies`, `x_post_replies`
- API routes include:
  - `GET /twitter`
  - `GET /twitter/post`
  - `GET /twitter/urls`
  - `GET /twitter/post/user`
  - `GET /twitter/user/posts`
  - `GET /twitter/post/retweeters`
  - `GET /twitter/replies`
  - `GET /twitter/replies/post`
- Supports filters for sort order, date range, language, verified status, media flags, and engagement thresholds

## Repository notes

- The scripts fail fast when `DESEARCH_API_KEY` is missing
- Error handling is implemented for HTTP errors, URL failures, and non-JSON responses
- The CLIs currently print raw JSON responses, even though some files contain unused text-formatting helpers

## Docs

- [docs/features.md](docs/features.md)
- [docs/architecture.md](docs/architecture.md)
- [docs/known-issues.md](docs/known-issues.md)

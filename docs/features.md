# Features Inventory

Status legend:
- ✅ working
- ⚠️ degraded
- ❌ broken
- 🚧 in progress

## Repo-wide summary

| Area | Status | Evidence |
|---|---|---|
| Skill manifests | ✅ | All four skill directories contain `SKILL.md` with frontmatter metadata and setup instructions. |
| Python CLI entrypoints | ✅ | All four skills ship executable `scripts/desearch.py` wrappers. |
| Shared auth pattern | ✅ | Every script reads `DESEARCH_API_KEY` and exits with a clear error when it is missing. |
| Local packaging | ⚠️ | No `Dockerfile`, `docker-compose.yml`, `package.json`, or `pyproject.toml` is present in the repo. |
| Automated verification | ⚠️ | No tests or CI config are present in the repository. |

## `desearch-ai-search`

**Status: ✅**

Implemented surface:
- `ai_search` for summarized multi-source search
- `ai_web` for curated web/source links
- `ai_x` for curated X/Twitter links
- Optional `--tools`, `--count`, `--date-filter`
- Calls live Desearch AI search endpoints under `/desearch/ai/search...`

Evidence from code:
- Command dispatch is defined in `COMMANDS = ["ai_search", "ai_web", "ai_x"]`
- `ai_search` posts to `/desearch/ai/search`
- `ai_web` posts to `/desearch/ai/search/links/web`
- `ai_x` posts to `/desearch/ai/search/links/twitter`
- If `--tools` is omitted for `ai_search`, the script defaults to `twitter` and `web`

Notes:
- The script includes text-formatting helpers, but the current `main()` path prints JSON output directly.

## `desearch-crawl`

**Status: ✅**

Implemented surface:
- `crawl` command
- URL input plus `--crawl-format text|html`
- `GET /web/crawl` request with `url` and `format` query parameters

Evidence from code:
- Parser only accepts `crawl`
- `cmd_crawl()` maps arguments to `/web/crawl`
- `--crawl-format` is constrained to `text` or `html`

Notes:
- This is the smallest and cleanest wrapper in the repo. It exposes a single API operation with minimal transformation.

## `desearch-web-search`

**Status: ✅**

Implemented surface:
- `web` command
- Search query plus `--start` pagination offset
- `GET /web` request with `query` and `start`

Evidence from code:
- Parser only accepts `web`
- `cmd_web()` maps to `/web`
- `format_web_results()` exists for pretty output, but is not currently used by `main()`

Notes:
- Functionality appears complete for a thin API wrapper, but output formatting is raw JSON today.

## `desearch-x-search`

**Status: ⚠️**

Implemented surface:
- Search: `x`
- Lookup: `x_post`, `x_urls`
- User-based retrieval: `x_user`, `x_timeline`, `x_replies`
- Post-based retrieval: `x_retweeters`, `x_post_replies`
- Filters for date range, language, verification, media type, and engagement

Why degraded instead of fully green:
- The code surface is broad and mostly implemented, but the CLI contract is a little inconsistent across commands.
- `x_urls` is handled through a positional `query` plus optional extra `urls`, then rewritten in `main()` into a combined list. It works, but the argument model is less clean than the rest of the repo.
- Like the other larger scripts, it defines formatter helpers that are not used by the final output path.

Evidence from code:
- Eight commands are registered in `COMMANDS`
- Each command maps to a dedicated `/twitter...` endpoint
- `main()` special-cases `x_urls` by prepending `query` into `args.urls`

## Gaps not implemented in this repo

| Item | Status | Notes |
|---|---|---|
| Container build files | ❌ | The repo references Docker-oriented usage in task scope, but no Docker assets are checked in. |
| Test suite | ❌ | No unit, integration, or smoke tests are present. |
| Shared Python module | 🚧 | The scripts duplicate request/auth/error-handling logic instead of using a common library. |

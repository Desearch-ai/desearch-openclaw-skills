# Known Issues

This page documents issues visible from the current repository contents and CLI implementations.

## 1. No Docker files are checked in

**Impact:** The repo is easy to run as raw Python scripts, but it is not self-documenting for local container builds.

**Evidence:** No `Dockerfile` or `docker-compose.yml` exists anywhere in the repository root or skill directories.

**Why it matters:** The skills are a natural fit for containerized OpenClaw deployments, but new contributors do not get a canonical image/build path from the repo itself.

## 2. No automated tests or smoke checks

**Impact:** Endpoint changes, response-shape changes, or argument parsing regressions could land without detection.

**Evidence:** The repo contains only `README.md`, `SKILL.md`, and `scripts/desearch.py` files. There is no `tests/` directory, CI workflow, or validation script.

**Why it matters:** These wrappers depend on external API contracts. A contract change on `api.desearch.ai` would only be discovered during manual use.

## 3. Output formatter helpers are currently unused

**Affected files:**
- `desearch-ai-search/scripts/desearch.py`
- `desearch-web-search/scripts/desearch.py`
- `desearch-x-search/scripts/desearch.py`

**Impact:** The scripts define human-readable formatting helpers like `format_ai_search()`, `format_web_results()`, and `format_tweets()`, but `main()` prints raw JSON instead.

**Why it matters:** The codebase suggests a nicer text presentation was planned, but current CLI behavior is JSON-only.

## 4. Shared HTTP/auth logic is duplicated four times

**Impact:** Fixes to headers, timeout handling, or error parsing must be repeated in every script.

**Evidence:** Each `scripts/desearch.py` file re-implements:
- `get_api_key()`
- `api_request()`
- `DESEARCH_BASE = "https://api.desearch.ai"`
- near-identical `urllib`-based error handling

**Why it matters:** This increases maintenance cost and makes behavior drift more likely over time.

## 5. `desearch-x-search` has the least clean CLI argument model

**Impact:** The `x_urls` command works, but its positional argument handling is more awkward than the rest of the repo.

**Evidence:** `main()` special-cases `x_urls` and rewrites `args.urls = [args.query] + (args.urls or [])` so the first required positional value becomes part of the URLs list.

**Why it matters:** It is functional, but less explicit than a dedicated multi-value positional design would be.

## 6. Repo-level dependency/runtime metadata is minimal

**Impact:** There is no single machine-readable source of truth for runtime versioning.

**Evidence:** No `pyproject.toml`, `requirements.txt`, or `package.json` is present.

**Why it matters:** The scripts are standard-library only today, which keeps things simple, but contributors must infer runtime expectations from the shebang and code instead of reading an explicit manifest.

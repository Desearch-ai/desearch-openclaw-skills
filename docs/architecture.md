# Architecture

## High-level structure

This repository is organized as four standalone OpenClaw skills, one directory per skill:

```text
.
├── README.md
├── desearch-ai-search/
│   ├── SKILL.md
│   └── scripts/desearch.py
├── desearch-crawl/
│   ├── SKILL.md
│   └── scripts/desearch.py
├── desearch-web-search/
│   ├── SKILL.md
│   └── scripts/desearch.py
└── desearch-x-search/
    ├── SKILL.md
    └── scripts/desearch.py
```

There is no shared package directory. Each skill is self-contained and duplicates its own CLI parsing, auth lookup, HTTP request logic, and response printing.

## Skill structure

Every skill follows the same two-part pattern:

### 1. `SKILL.md`
The manifest defines:
- Skill name
- Natural-language description
- Frontmatter metadata under `metadata.clawdbot`
- Required environment variables, currently `DESEARCH_API_KEY`
- Usage examples for the exposed commands

Example metadata pattern used across all four skills:

```yaml
metadata:
  clawdbot:
    homepage: https://desearch.ai
    requires:
      env:
        - DESEARCH_API_KEY
```

### 2. `scripts/desearch.py`
The runtime wrapper handles:
- CLI argument parsing with `argparse`
- Reading `DESEARCH_API_KEY` from the environment
- Constructing a request to `https://api.desearch.ai`
- Returning parsed JSON when possible
- Falling back to plain text or structured error objects on failures

## Request flow

The control flow is nearly identical in all scripts:

1. User runs the executable Python script with a command and arguments
2. `argparse` validates the command and options
3. `get_api_key()` aborts if `DESEARCH_API_KEY` is missing
4. A command handler builds either query params or a JSON body
5. `api_request()` sends the HTTP request with:
   - `Authorization: <DESEARCH_API_KEY>`
   - `Content-Type: application/json`
   - `User-Agent: Desearch-Clawdbot/1.0`
6. The response body is decoded and parsed as JSON when possible
7. `main()` prints the JSON result

That last step matters because the repository contains formatter helpers in several files, but the current runtime path is still JSON-first rather than text-first.

## Endpoint mapping

| Skill | Commands | HTTP method | Endpoint |
|---|---|---|---|
| `desearch-ai-search` | `ai_search` | POST | `/desearch/ai/search` |
| `desearch-ai-search` | `ai_web` | POST | `/desearch/ai/search/links/web` |
| `desearch-ai-search` | `ai_x` | POST | `/desearch/ai/search/links/twitter` |
| `desearch-crawl` | `crawl` | GET | `/web/crawl` |
| `desearch-web-search` | `web` | GET | `/web` |
| `desearch-x-search` | `x` | GET | `/twitter` |
| `desearch-x-search` | `x_post` | GET | `/twitter/post` |
| `desearch-x-search` | `x_urls` | GET | `/twitter/urls` |
| `desearch-x-search` | `x_user` | GET | `/twitter/post/user` |
| `desearch-x-search` | `x_timeline` | GET | `/twitter/user/posts` |
| `desearch-x-search` | `x_retweeters` | GET | `/twitter/post/retweeters` |
| `desearch-x-search` | `x_replies` | GET | `/twitter/replies` |
| `desearch-x-search` | `x_post_replies` | GET | `/twitter/replies/post` |

## Interface consistency notes

The repo is structurally consistent, but not perfectly uniform at the CLI boundary:

- ✅ Every wrapper uses `argparse`, `DESEARCH_API_KEY`, and `https://api.desearch.ai`
- ✅ Every wrapper centralizes outbound requests in a local `api_request()` helper
- ⚠️ Some commands use `user`, while `x_timeline` uses `username` because the underlying endpoint expects a different parameter name
- ⚠️ `x_urls` is implemented as a special-case argument rewrite in `main()` instead of a cleaner dedicated parser shape
- 🚧 Pretty-printer helpers exist in multiple files, but they are not yet wired into the active output path

## Skill configuration

### Required environment

All four skills require:

```bash
export DESEARCH_API_KEY='your-key-here'
```

If the variable is absent, each script exits with a descriptive error and points the user at `https://console.desearch.ai`.

### CLI-level configuration

Skill-specific configuration is exposed as command-line flags rather than config files.

Examples:
- `desearch-ai-search`: `--tools`, `--count`, `--date-filter`
- `desearch-crawl`: `--crawl-format`
- `desearch-web-search`: `--start`
- `desearch-x-search`: `--sort`, `--user`, `--start-date`, `--end-date`, `--lang`, `--verified`, `--blue-verified`, `--is-quote`, `--is-video`, `--is-image`, `--min-retweets`, `--min-replies`, `--min-likes`, `--cursor`, `--query`

## Docker setup

This repo does not currently contain local Docker assets.

What is present:
- Executable Python scripts suitable for being copied or mounted into a container
- Environment-variable based configuration, which fits container deployment well
- No third-party Python dependency files, which simplifies image construction

What is not present:
- No `Dockerfile`
- No `docker-compose.yml`
- No image build instructions in the repo itself

So the current architecture is best described as **Docker-compatible Python skill scripts**, not a fully self-contained Dockerized project.

## Operational profile

| Concern | Status | Notes |
|---|---|---|
| Standard-library only runtime | ✅ | No third-party Python dependencies are required by the checked-in scripts. |
| Container-ready configuration | ✅ | Environment-variable auth and executable scripts fit container mounts well. |
| Self-contained project packaging | ❌ | No Dockerfile, dependency manifest, or CI workflow is checked in. |
| Shared internal library | 🚧 | Repeated request/auth logic has not yet been extracted. |

## Design characteristics

### Strengths
- Very small footprint, standard-library only
- Easy to inspect and modify per skill
- Consistent auth and HTTP handling across scripts
- Skill manifests are easy to register in OpenClaw environments

### Tradeoffs
- Request/auth/error-handling logic is duplicated in every script
- There is no shared schema validation layer
- Pretty-printer helper functions exist in several files, but the current entrypoints always print JSON directly
- Without tests, regressions in endpoint contracts would only be caught at runtime

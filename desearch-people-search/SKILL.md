---
name: desearch-people-search
description: Find people and creators on X, YouTube, LinkedIn, or TikTok who match a plain-language description, each with a fit score, the reasons they matched, their audience, and public contacts and links. Starting a search is billed to your Desearch balance and runs in the background for 1 to 5 minutes; reading status, results, exports, and the library of people already found is free.
metadata: {"clawdbot":{"emoji":"👥","homepage":"https://desearch.ai","requires":{"env":["DESEARCH_API_KEY"]}}}
---

# People Search By Desearch

Find people, not posts. Describe who you want in plain language, for example "Indie hackers building in public who share their MRR". Desearch searches public posts, videos, and profiles on one platform, reads each matching profile, and scores how well each person fits. Public data only.

People Search is **billed** and **asynchronous**:

- `people_search` starts a background task and returns a `task_id` at once, with no people in it yet. It is the only billed command.
- The search usually takes 1 to 5 minutes. Poll it with `people_wait` or `people_task`, read people with `people_results` (they arrive while the search runs), and download them with `people_export`.

## Quick Start

1. Get an API key from https://console.desearch.ai
2. Set environment variable: `export DESEARCH_API_KEY='your-key-here'`

```bash
# 1. Start a billed search (returns task_id)
scripts/desearch.py people_search x "Indie hackers building in public who share their MRR" --count 10

# 2. Wait until it ends (polls every 10 seconds, gives up after 10 minutes)
scripts/desearch.py people_wait 5b33f3ee-168b-4780-9c8e-63a626781872

# 3. Read everyone it found
scripts/desearch.py people_results 5b33f3ee-168b-4780-9c8e-63a626781872 --all

# 4. Optional: save them as CSV
scripts/desearch.py people_export 5b33f3ee-168b-4780-9c8e-63a626781872 --output people.csv
```

## Billing

Starting a search reserves `count` people at the platform's price (`reserved_cost_usd` on the task). When the search ends you pay only for the qualified people it delivered, with a per-search minimum when it finds anyone. The rest of the reservation is returned automatically. A search that finds no one is free.

| Platform | Finds | Price | Minimum billed per search that finds anyone |
|----------|-------|-------|---------------------------------------------|
| `x` | X profiles | $0.04 per profile | 5 profiles ($0.20) |
| `youtube` | YouTube creators | $0.05 per creator | 3 creators ($0.15) |
| `linkedin` | LinkedIn members | $0.05 per profile | 2 profiles ($0.10) |
| `tiktok` | TikTok creators | $0.05 per creator | 2 creators ($0.10) |

Polling, results, exports, pause, resume, cancel, the task list, and the profiles library are free. The task's `reserved_cost_usd` and `final_cost_usd` are the authoritative amounts.

**Agent rules:**
- Before a new search, check `people_profiles` when the user may already have searched for these people.
- Tell the user the platform, `count`, and the maximum reservation (`count` × price) before running `people_search`, and start it only when they ask for a new search.
- Run `people_search` once per request. It prints an `Idempotency-Key` to stderr; if the call fails or times out, retry with `--idempotency-key <that key>` so the API returns the first task instead of starting and charging a second one.

## Commands

### `people_search`: Start a Search (billed)

```bash
scripts/desearch.py people_search x "Indie hackers building in public who share their MRR" --count 10
scripts/desearch.py people_search youtube "Home espresso machine reviewers" --min-subscribers 10000 --require-contact
scripts/desearch.py people_search linkedin "Heads of growth at B2B fintech startups" --countries US,GB --count 20
scripts/desearch.py people_search tiktok "Skincare creators who review sunscreen" --max-followers 500000 --exclude handle1,handle2
```

**Options:**
| Option | Description |
|--------|-------------|
| `--count`, `-n` | People to find, 5 to 200 (API default 25). This many are reserved. |
| `--min-score` | Only return people with at least this fit score (0-100) |
| `--exclude` | Comma-separated handles to leave out, for example people you already contacted |
| `--idempotency-key` | Reuse the key from a previous attempt so a retry is not charged again. A new UUID is generated when omitted. |

**Platform filters** (a filter from another platform is rejected before the billed call):
| Option | `x` | `youtube` | `linkedin` | `tiktok` |
|--------|:---:|:---------:|:----------:|:--------:|
| `--min-followers`, `--max-followers` | ✓ | | ✓ | ✓ |
| `--min-subscribers`, `--max-subscribers` | | ✓ | | |
| `--verified-only` (verified or X Premium) | ✓ | | | |
| `--require-contact` (public email or contact link) | | ✓ | | ✓ |
| `--countries` (comma-separated, e.g. `US,GB`) | ✓ | ✓ | ✓ | |
| `--keywords`, `--exclude-keywords` (comma-separated) | ✓ | ✓ | ✓ | ✓ |

**Response:** `202` with the new task. Repeating the call with the same `--idempotency-key` returns `200` with the same task and is not charged again.

```json
{
  "task_id": "5b33f3ee-168b-4780-9c8e-63a626781872",
  "search_type": "x_profile_search",
  "platform": "x",
  "status": "queued",
  "stage": null,
  "query": "Indie hackers building in public who share their MRR",
  "count": 10,
  "result_count": 0,
  "reserved_cost_usd": 0.4,
  "final_cost_usd": null,
  "created_at": "2026-10-19T09:00:00Z",
  "links": {
    "self": "/desearch/people/tasks/5b33f3ee-168b-4780-9c8e-63a626781872",
    "results": "/desearch/people/tasks/5b33f3ee-168b-4780-9c8e-63a626781872/results",
    "export": "/desearch/people/tasks/5b33f3ee-168b-4780-9c8e-63a626781872/export"
  }
}
```


### `people_task`: Read a Task

Status, progress, and cost of one task.

```bash
scripts/desearch.py people_task 5b33f3ee-168b-4780-9c8e-63a626781872
```

**Response:** the task. `status` moves through `queued`, `running`, and sometimes `pausing` or `paused`, then ends as `completed`, `partial`, `failed`, `cancelled`, or `expired`. While it runs, `stage` is `planning`, `searching`, `processing`, or `finalizing`, and `result_count` counts the people found so far. Once it ends, `final_cost_usd` and `refunded_usd` are set.


### `people_wait`: Poll Until Done

Polls the task until it ends or is paused, printing progress to stderr, then prints the task.

```bash
scripts/desearch.py people_wait 5b33f3ee-168b-4780-9c8e-63a626781872
scripts/desearch.py people_wait 5b33f3ee-168b-4780-9c8e-63a626781872 --interval 15 --timeout 900
```

**Options:**
| Option | Description |
|--------|-------------|
| `--interval` | Seconds between polls (default: 10) |
| `--timeout` | Seconds to wait before giving up (default: 600). The search keeps running after a timeout. |

**Response:** the final task, or `{ error, task }` on timeout.


### `people_results`: Read the People Found

People arrive while the search is still running, in the order they were found.

```bash
scripts/desearch.py people_results 5b33f3ee-168b-4780-9c8e-63a626781872 --limit 50
scripts/desearch.py people_results 5b33f3ee-168b-4780-9c8e-63a626781872 --cursor "<next_cursor>"
scripts/desearch.py people_results 5b33f3ee-168b-4780-9c8e-63a626781872 --all
```

**Options:**
| Option | Description |
|--------|-------------|
| `--cursor` | `next_cursor` from the previous page. Omit to start from the first person. |
| `--limit`, `-n` | People per page, 1 to 500 (API default 100) |
| `--all` | Follow `next_cursor` until every person found so far is returned |

**Response:** `{ task_id, status, results: Person[], next_cursor, has_more }`. When `has_more` is false you have everyone found so far; keep `next_cursor` and call again later to get only people found since.

```json
{
  "task_id": "5b33f3ee-168b-4780-9c8e-63a626781872",
  "status": "completed",
  "results": [
    {
      "id": "1234567890",
      "platform": "x",
      "handle": "example_founder",
      "url": "https://x.com/example_founder",
      "name": "Example Founder",
      "bio": "Building a SaaS in public. $12k MRR.",
      "location": "Austin, TX",
      "metrics": {"followers": 18400},
      "links": [{"type": "website", "url": "https://example.com"}],
      "contacts": [{"type": "email", "value": "hello@example.com"}],
      "evidence": [{"type": "post", "url": "https://x.com/example_founder/status/1", "text": "Month 14: $12k MRR..."}],
      "score": {"value": 86, "qualified": true, "summary": "Founder who posts monthly MRR updates.", "reasons": ["..."], "concerns": []},
      "attributes": {"verified": false}
    }
  ],
  "next_cursor": "1",
  "has_more": false
}
```

**Person fields:** `id`, `platform`, `handle`, `url`, `name`, `avatar_url`, `bio`, `location`, `metrics` (followers, or subscribers on YouTube), `links` and `contacts` (public links and contact details such as an email listed in a bio), `evidence` (the posts or videos behind the match), `score` (`value` 0 to 100, `summary`, `reasons`, `concerns`), and `attributes` (`verified` on X and TikTok, `headline` and `company` on LinkedIn, `region` on TikTok). Fields a platform does not report can be missing or `null`; treat them as unknown, not zero.


### `people_export`: Download as CSV or JSON Lines

Every person found so far, optionally filtered.

```bash
scripts/desearch.py people_export 5b33f3ee-168b-4780-9c8e-63a626781872 --output people.csv
scripts/desearch.py people_export 5b33f3ee-168b-4780-9c8e-63a626781872 --format jsonl --has email -o people.jsonl
```

**Options:**
| Option | Description |
|--------|-------------|
| `--format` | `csv` (default) or `jsonl` |
| `--output`, `-o` | Write the export to this file and print `{ saved, format, bytes }`. Without it the export prints to stdout. |
| `--has`, `--min-audience`, `--max-audience`, `--min-score`, `--location`, `--verified` | Same filters as `people_profiles` |


### `people_pause`, `people_resume`, `people_cancel`: Control a Task

```bash
scripts/desearch.py people_pause 5b33f3ee-168b-4780-9c8e-63a626781872
scripts/desearch.py people_resume 5b33f3ee-168b-4780-9c8e-63a626781872
scripts/desearch.py people_cancel 5b33f3ee-168b-4780-9c8e-63a626781872
```

- **pause:** a queued search pauses at once; a running one finishes its current batch first (`pausing`, then `paused`). A search paused for more than 7 days is cancelled.
- **resume:** continues a paused search where it stopped. It is not charged again.
- **cancel:** stops the search for good. You pay only for the people it already delivered (nothing if it had not started), and the rest of the reservation is returned. Cannot be undone.

**Response:** the task. `409` means the action does not apply to the task's current status.


### `people_tasks`: List Your Searches

Newest first.

```bash
scripts/desearch.py people_tasks
scripts/desearch.py people_tasks --platform x --status running,paused
```

**Options:**
| Option | Description |
|--------|-------------|
| `--platform` | `x`, `youtube`, `linkedin`, or `tiktok` |
| `--status` | Comma-separated statuses, e.g. `running,paused` |
| `--limit`, `-n` | Tasks per page, 1 to 100 (API default 20) |
| `--cursor` | `next_cursor` from the previous page |

**Response:** `{ tasks: Task[], next_cursor }`


### `people_profiles`: Profiles Library

Everyone your searches found on one platform, one entry per person: their best-scoring result plus `found_by` (the search that found them and how many of your searches did). Free; it does not run a new search. People from searches whose results expired (30 days after they ended) are left out.

```bash
scripts/desearch.py people_profiles x --has email --min-audience 1000
scripts/desearch.py people_profiles youtube --query espresso --sort audience --has email,instagram
scripts/desearch.py people_profiles tiktok --verified --location "united states" --min-score 70
```

**Options:**
| Option | Description |
|--------|-------------|
| `--query`, `-q` | Text in the name, handle, bio, or location |
| `--sort` | `score` (API default), `recent`, or `audience` |
| `--limit`, `-n` | People per page, 1 to 200 (API default 50) |
| `--cursor` | `next_cursor` from the previous page (`null` on the last page) |
| `--has` | Comma-separated channels every person must have: `email`, `website`, `x`, `linkedin`, `instagram`, `youtube`, `tiktok` |
| `--min-audience`, `--max-audience` | Followers (subscribers on YouTube) |
| `--min-score` | Minimum fit score (0-100) |
| `--location` | Text in the location, e.g. `united states` |
| `--verified` | Only verified accounts. X and TikTok only. |

**Response:** `{ profiles: Person[] (each with found_by), total, next_cursor }`

### Errors
| Status | Meaning |
|--------|---------|
| 400 | Unknown platform, sort, status, cursor, or `has` channel, or `verified` on a platform without verified accounts |
| 401 | Missing or invalid API key |
| 402 | Balance cannot cover the reservation |
| 404 | Task not found |
| 409 | Pause, resume, or cancel does not apply to the task's current status |
| 410 | Results expired, 30 days after the search ended |
| 422 | Invalid request body or parameters, including a filter the platform does not have |
| 429 | Too many of your searches are already queued, running, or paused |

Error bodies are JSON with a `detail` field. A `409` from pause, resume, or cancel also includes the current `task`. The CLI prints the body as returned. Input it can check locally (platform, `count` range, a filter from another platform, task ID format, `has` channels, statuses) is rejected before any request is sent.

## Resources
- [People Search guide](https://www.desearch.ai/docs/guide/apis/people-search)
- [API Reference](https://desearch.ai/docs/api-reference)
- [Desearch Console](https://console.desearch.ai)

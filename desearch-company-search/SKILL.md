---
name: desearch-company-search
description: Find companies that match a plain-language description (Company Search), or start from domains you already have (Company Enrich), and get each company's public emails, phones, social profiles, and leaders (CEO, founders, CTO, CFO) with their LinkedIn profiles and checked emails. Every contact keeps the page it came from. Starting a task is billed to your Desearch balance and runs in the background for several minutes; reading status, results, and exports is free.
metadata: {"clawdbot":{"emoji":"🏢","homepage":"https://desearch.ai","requires":{"env":["DESEARCH_API_KEY"]}}}
---

# Company Search By Desearch

Find companies, not pages. Describe the companies you want in plain language, for example "Series A fintech startups in Berlin building payment infrastructure", or send the domains you already have. Desearch reads each company's website, collects its public emails, phones, and social profiles, finds its leaders, infers their emails from the company's address pattern, and checks every email. Every contact keeps the page it came from (`source_url`). Public data only.

| | Company Search | Company Enrich |
|---|---|---|
| Command | `company_search` | `company_enrich` |
| You send | a description | 1 to 200 domains or URLs |
| Companies | found on the web, scored for fit | the ones you send, one per domain |
| Fit score | `score`, 0 to 100 | none (`score` is `null`) |
| Price | $0.09 per company | $0.05 per company |

Both are **billed** and **asynchronous**:

- `company_search` and `company_enrich` start a background task and return a `task_id` at once, with no companies in it yet. They are the only billed commands.
- A task runs for several minutes. Poll it with `company_wait` or `company_task`, read companies with `company_results` (they arrive while the task runs and fill in as later stages finish), and download them with `company_export`.

## Quick Start

1. Get an API key from https://console.desearch.ai
2. Set environment variable: `export DESEARCH_API_KEY='your-key-here'`

```bash
# 1. Start a billed search (returns task_id)
scripts/desearch.py company_search "Series A fintech startups in Berlin building payment infrastructure" --count 25

#    ...or enrich domains you already have
scripts/desearch.py company_enrich acme.com https://www.beta.io/about

# 2. Wait until it ends (polls every 10 seconds, gives up after 20 minutes)
scripts/desearch.py company_wait 5b33f3ee-168b-4780-9c8e-63a626781872

# 3. Read every company it delivered
scripts/desearch.py company_results 5b33f3ee-168b-4780-9c8e-63a626781872 --all

# 4. Optional: save them as CSV
scripts/desearch.py company_export 5b33f3ee-168b-4780-9c8e-63a626781872 --output companies.csv
```

## Billing

Starting a task reserves companies at the route price (`reserved_cost_usd` on the task). When the task ends you pay only for the companies it delivered, with a per-task minimum when it delivers any. The rest of the reservation is returned automatically. A task that delivers no companies is free.

| Command | Reserves | Price | Minimum billed per task that delivers any |
|---------|----------|-------|-------------------------------------------|
| `company_search` | `count` companies (API default 25, so $2.25) | $0.09 per company ($90 per 1000) | 2 companies ($0.18) |
| `company_enrich` | one company per domain sent | $0.05 per company ($50 per 1000) | 1 company ($0.05) |

- A company left out by `--min-score` or `--require` is not delivered and not billed.
- Cancelling bills only the companies already delivered (nothing if the task had not started).
- `company_enrich` drops duplicate domains before it sends them, so each company is reserved once.
- Polling, results, exports, pause, resume, cancel, and the task list are free. The task's `reserved_cost_usd` and `final_cost_usd` are the authoritative amounts. Prices: https://desearch.ai/pricing.

**Agent rules:**
- Before a new task, check `company_tasks` when the user may already have run this search or enriched these domains. Results stay available for 30 days after a task ends.
- Tell the user the command, the `count` (or the number of domains), and the maximum reservation (companies × price) before running `company_search` or `company_enrich`, and start it only when they ask for a new task.
- Run each billed command once per request. It prints an `Idempotency-Key` to stderr; if the call fails or times out, retry with `--idempotency-key <that key>` so the API returns the first task instead of starting and charging a second one.
- Treat a company's contacts as final only once its `enrichment.status` is `complete` or the task has ended. A task in stage `enriching` is still filling companies in: wait with `company_wait` until it ends, then read with `company_results --all`.

## How a Task Runs

Each company goes through five stages:

| Stage | What it does |
|-------|--------------|
| `profile` | Reads the homepage: name, description, socials, and the emails and phones on it. Company Search also scores the fit here. |
| `contacts` | Reads up to 4 more pages of the site: contact, imprint (impressum), team, about. |
| `people` | Finds the leaders (`--roles`) on the site's own pages, then on LinkedIn for roles still missing. |
| `email_patterns` | Learns the company's address pattern (for example `first.last`) from the addresses it found and infers the leaders' emails. `skipped` with `--no-infer-emails`. |
| `email_check` | Checks every email: syntax, mail server (MX), and a web search for inferred ones. `skipped` with `--no-verify-emails`. |

A company is published as soon as the stages its request needs have run, with `enrichment.status` `partial`. The later stages fill it in while you read, and it becomes `complete` once no stage is `pending` (a stage cut by the time limit is `skipped`).

| `--require` contains | Company published after |
|----------------------|-------------------------|
| nothing | `profile` |
| `email`, `phone`, `linkedin` | `contacts` |
| `leader` | `people` |
| `leader_email` | `email_check` |

A company that does not have what `--require` asks for once that stage has run is not delivered and not billed.

While the task runs, `stage` is `planning`, `searching`, `processing`, `enriching`, or `finalizing`. `enriching` means every company is published and only the later stages of some of them are left; `status` is still `running`. Read without `--cursor` to get every company in its latest version, or keep `next_cursor` to get only companies delivered since.

## Commands

### `company_search`: Find Companies (billed)

```bash
scripts/desearch.py company_search "Series A fintech startups in Berlin building payment infrastructure" --countries DE --require email
scripts/desearch.py company_search "Independent coffee roasters in Portland that sell wholesale" --count 50 --min-score 60 --roles ceo,founder,owner
scripts/desearch.py company_search "B2B SaaS companies selling to dental clinics" --exclude acme.com,https://www.beta.io/ --metadata campaign=q4
scripts/desearch.py company_search "Robotics startups in Munich" --require leader,leader_email --roles ceo,cto
```

**Options:**
| Option | Description |
|--------|-------------|
| `--count`, `-n` | Companies to deliver, 5 to 200 (API default 25). This many are reserved. |
| `--min-score` | Only deliver companies with at least this fit score (0-100) |
| `--exclude` | Comma-separated domains or URLs to leave out, for example companies you already contacted (up to 1,000) |
| `--countries` | Comma-separated ISO codes or country names, e.g. `DE,AT` (up to 20). Scoring treats them as a location criterion. |
| `--require` | Comma-separated; only deliver companies that have all of: `email`, `phone`, `linkedin` (the company's LinkedIn page), `leader` (one of `--roles`), `leader_email` (a leader with an email) |
| `--roles` | Comma-separated leaders to look for: `ceo`, `founder`, `cto`, `cfo`, `coo`, `cmo`, `president`, `owner`, `managing_director` (API default `ceo,founder,cto,cfo`). A managing director (Geschäftsführer) counts as `ceo` when `ceo` is asked for. |
| `--no-infer-emails` | Do not guess leaders' emails from the company's address pattern |
| `--no-verify-emails` | Skip the email checks to finish sooner; emails then have no `verification` |
| `--metadata` | Your own `key=value` label for the task, repeatable (up to 10), e.g. `--metadata campaign=q4`. Returned on the task and usable with `company_tasks --metadata`. Keys are 1-40 characters of `a-z`, `0-9`, `_`, `.`, `-`; values up to 200 characters. |
| `--idempotency-key` | Reuse the key from a previous attempt so a retry is not charged again. A new UUID is generated when omitted. |

**Response:** `202` with the new task. Repeating the call with the same `--idempotency-key` returns `200` with the same task and is not charged again.

```json
{
  "task_id": "5b33f3ee-168b-4780-9c8e-63a626781872",
  "search_type": "company_search",
  "platform": "company",
  "status": "queued",
  "stage": null,
  "query": "Series A fintech startups in Berlin building payment infrastructure",
  "count": 25,
  "result_count": 0,
  "metadata": {"campaign": "q4"},
  "completion_reason": null,
  "coverage_limited": false,
  "warnings": [],
  "reserved_cost_usd": 2.25,
  "final_cost_usd": null,
  "created_at": "2026-10-28T09:00:00Z",
  "links": {
    "self": "/desearch/companies/tasks/5b33f3ee-168b-4780-9c8e-63a626781872",
    "results": "/desearch/companies/tasks/5b33f3ee-168b-4780-9c8e-63a626781872/results",
    "export": "/desearch/companies/tasks/5b33f3ee-168b-4780-9c8e-63a626781872/export"
  }
}
```


### `company_enrich`: Enrich Domains You Have (billed)

One company per domain, with the same fields as Company Search but no fit score.

```bash
scripts/desearch.py company_enrich acme.com https://www.beta.io/about
scripts/desearch.py company_enrich --file domains.txt --roles ceo,cto --metadata campaign=q4
cat domains.txt | scripts/desearch.py company_enrich --file -
```

**Input:** domains or URLs as arguments (commas or spaces between them), from `--file`, or both. Each is reduced to its host without `www.` and lowercased, so `https://www.beta.io/about` is `beta.io`. The CLI drops duplicates before sending; 1 to 200 domains per task.

**Options:**
| Option | Description |
|--------|-------------|
| `--file`, `-f` | File with one domain or URL per line. Lines starting with `#` are skipped. `-` reads stdin. |
| `--roles`, `--no-infer-emails`, `--no-verify-emails`, `--metadata`, `--idempotency-key` | Same as `company_search` |

**Response:** `202` with the new task: `search_type` `company_enrich`, `platform` `company_enrich`, `query` a short label of the domains (`"acme.com, beta.io and 3 more"`), and `count` the number of domains left after the API removed duplicates. `reserved_cost_usd` is $0.05 per domain sent.


### `company_task`: Read a Task

Status, progress, and cost of one task.

```bash
scripts/desearch.py company_task 5b33f3ee-168b-4780-9c8e-63a626781872
```

**Response:** the task.
- `status` moves through `queued`, `running`, and sometimes `pausing` or `paused`, then ends as `completed`, `partial`, `failed`, `cancelled`, or `expired`.
- `stage` is `planning`, `searching`, `processing`, `enriching`, or `finalizing` while it runs. `result_count` counts the companies delivered so far.
- `progress`: `candidates_found`, `candidates_processed`, `qualified`, `filtered` (companies left out, by reason: `unreachable`, `not_a_company`, `below_min_score`, `no_<requirement>`), `enrichment` (`published`, `complete`, `pending`, `failed`), and `email_checks` (`checked`, `valid`, `invalid`, `risky`, `unknown`).
- Once it ends, `completion_reason` says why: `count_reached`, `all_domains_processed` (Company Enrich), `rounds_exhausted`, `no_candidates`, `zero_qualified`, `candidate_budget`, `cost_limit`, `time_limit`, `cancelled`, or `failed`. `coverage_limited` is true when a budget (`candidate_budget`, `cost_limit`, `time_limit`) stopped it before `count`; `status` alone stays `completed` then. `final_cost_usd` and `refunded_usd` are set.
- `warnings`: what made part of the task less reliable without failing it, e.g. `enrichment_time_limit` (some companies were not fully enriched before the time limit) or `linkedin_verification_unavailable`.
- `request`: the normalized request. `metadata`: your labels (`{}` when none).


### `company_wait`: Poll Until Done

Polls the task until it ends or is paused, printing progress to stderr, then prints the task. A task in stage `enriching` has published every company but is still filling some in, so `company_wait` keeps waiting until the task ends.

```bash
scripts/desearch.py company_wait 5b33f3ee-168b-4780-9c8e-63a626781872
scripts/desearch.py company_wait 5b33f3ee-168b-4780-9c8e-63a626781872 --interval 15 --timeout 2400
```

**Options:**
| Option | Description |
|--------|-------------|
| `--interval` | Seconds between polls (default: 10) |
| `--timeout` | Seconds to wait before giving up (default: 1200, at most 3600). The task keeps running after a timeout. |

**Response:** the final task, or `{ error, task }` on timeout.


### `company_results`: Read the Companies

Companies arrive while the task is still running, in the order they were found, and are filled in place by the later stages.

```bash
scripts/desearch.py company_results 5b33f3ee-168b-4780-9c8e-63a626781872 --limit 50
scripts/desearch.py company_results 5b33f3ee-168b-4780-9c8e-63a626781872 --cursor "<next_cursor>"
scripts/desearch.py company_results 5b33f3ee-168b-4780-9c8e-63a626781872 --all
```

**Options:**
| Option | Description |
|--------|-------------|
| `--cursor` | `next_cursor` from the previous page: only companies delivered after it. Omit to read every company in its latest version. |
| `--limit`, `-n` | Companies per page, 1 to 500 (API default 100) |
| `--all` | Follow `next_cursor` until every company delivered so far is returned |

**Response:** `{ task_id, status, results: Company[], next_cursor, has_more }`. When `has_more` is false you have every company delivered so far.

```json
{
  "task_id": "5b33f3ee-168b-4780-9c8e-63a626781872",
  "status": "completed",
  "results": [
    {
      "id": "company:acme.com",
      "platform": "company",
      "handle": "acme.com",
      "domain": "acme.com",
      "url": "https://acme.com/",
      "name": "Acme",
      "description": "Payment infrastructure for marketplaces.",
      "location": {"country": "DE", "city": "Berlin", "address": "Torstraße 1, 10119 Berlin"},
      "industry": "Fintech",
      "emails": [
        {"value": "hello@acme.com", "type": "general", "source": "website", "source_url": "https://acme.com/impressum", "on_domain": true,
         "verification": {"status": "valid", "checks": {"syntax": true, "mx": "ok", "smtp": "skipped", "web": "skipped"}}}
      ],
      "phones": [{"value": "+493012345678", "type": "main", "source": "website", "source_url": "https://acme.com/impressum", "raw": "+49 30 1234 5678"}],
      "socials": [{"type": "linkedin", "url": "https://www.linkedin.com/company/acme", "handle": "acme", "source": "website", "source_url": "https://acme.com/"}],
      "people": [
        {
          "name": "Anna Schmidt",
          "title": "Co-founder & CEO",
          "roles": ["ceo", "founder"],
          "linkedin_url": "https://www.linkedin.com/in/annaschmidt",
          "emails": [
            {"value": "anna.schmidt@acme.com", "type": "personal", "source": "inferred", "source_url": null, "confidence": "high", "pattern": "first.last",
             "verification": {"status": "valid", "checks": {"syntax": true, "mx": "ok", "smtp": "accepted", "web": "not_found"}}}
          ],
          "evidence": {"quote": "Anna Schmidt, Geschäftsführerin", "source_url": "https://acme.com/impressum", "source": "website"},
          "verified": true
        }
      ],
      "primary_email": {"value": "anna.schmidt@acme.com", "type": "personal", "source": "inferred", "confidence": "high"},
      "primary_contact": {"name": "Anna Schmidt", "title": "Co-founder & CEO", "email": "anna.schmidt@acme.com", "reason": "CEO, email inferred from the company's pattern and verified"},
      "contact_coverage": {"email": true, "phone": true, "linkedin": true, "leader": true, "leader_email": true},
      "enrichment": {"status": "complete", "stages": {"profile": "done", "contacts": "done", "people": "done", "email_patterns": "done", "email_check": "done"}, "errors": []},
      "score": {"value": 86, "qualified": true, "relevance": "high", "summary": "Berlin payments infrastructure startup, Series A in 2025.",
                "criteria_checks": [{"criterion": "Based in Berlin", "verdict": "met", "quote": "Torstraße 1, 10119 Berlin", "source_url": "https://acme.com/impressum"}],
                "fully_verified": true}
    }
  ],
  "next_cursor": "1",
  "has_more": false
}
```

### Reading a Company

- **Identity:** `id`, `domain` (also `handle`), `url`, `name`, `description`, `logo_url`, `location` (`country`, `city`, `address`), `industry`, `pages` (the pages that were read: `home`, `contact`, `about`, `team`, `imprint`, `legal`, `other`), and `found_by` (the search that found it).
- **`emails`:** `value`; `type` (`personal`, `leadership`, `sales`, `general`, `press`, `support`, `careers`, `legal`, `other`); `source` (`website`, `search`, `linkedin`, or `inferred`) and `source_url`, the page it was found on (`null` when inferred); `on_domain`; `person` it belongs to, when known. Inferred emails also have `pattern` (e.g. `first.last`) and `confidence`: `high` when the pattern was learned from the company's own addresses, `low` for a common pattern. System addresses (noreply@, postmaster@) and junk are left out.
- **`verification`** on every email: `status` is `valid`, `invalid`, `risky` (catch-all domain, or no MX but an A record), or `unknown` (nothing could confirm or refute it); `checks` has `syntax`, `mx` (`ok`, `implicit`, `none`, `error`), `smtp` (`accepted`, `rejected`, `catch_all`, `unreachable`, `skipped`), and `web` (`found`, `not_found`, `skipped`). It is `null` until `email_check` ran, or with `--no-verify-emails`. Prefer `valid` emails; treat `risky` and `unknown` as unconfirmed and do not use `invalid` ones.
- **`phones`:** `value` (E.164 when the number parses), `type` (`main`, `sales`, `support`, `mobile`, `other`; fax numbers are left out), `raw` as written, `source`, `source_url`. At most 4.
- **`socials`:** `type` (`linkedin`, `x`, `facebook`, `instagram`, `github`, `youtube`, `tiktok`, `crunchbase`, `discord`, `telegram`, `medium`), `url`, `handle`, `source`, `source_url`.
- **`people`** (leaders with one of `--roles`): `name`, `title`, `roles`, `linkedin_url`, `x_url`, `github_url`, `emails` (same shape as above), `phones`, `evidence` (`quote`, `source_url`, `source`: what shows the role, and where), and `verified` (true when a quote on the company's own site or the person's current LinkedIn position shows the role).
- **`primary_email`:** the company's best email. Never a `support`, `legal`, `careers`, `press`, or `other` address; an inferred one only when `valid`.
- **`primary_contact`:** the leader to reach first: `name`, `title`, `email`, `linkedin_url`, and `reason` it was picked.
- **`contact_coverage`:** what was found, as booleans named like `--require`: `email`, `phone`, `linkedin`, `leader`, `leader_email`.
- **`enrichment`:** `status` (`partial` while any stage is `pending`, then `complete`), `stages` (each `pending`, `done`, `failed`, or `skipped`), and `errors`.
- **`score`** (Company Search only; `null` for Company Enrich): `value` 0 to 100, `qualified`, `relevance` (`high`, `medium`, `low`), `summary`, `matched_signals`, `reasons`, `concerns`, `criteria_checks` (one per criterion: `criterion`, `verdict` `met`, `not_met`, or `unknown`, the `quote` and `source_url` behind it, `reason`, `is_disqualifier`), and `fully_verified` (every criterion `met` and no disqualifier).

Fields a later stage has not filled in yet are missing, empty, or `null`; treat them as unknown, not as "none".


### `company_export`: Download as CSV or JSON Lines

Every company delivered so far.

```bash
scripts/desearch.py company_export 5b33f3ee-168b-4780-9c8e-63a626781872 --output companies.csv
scripts/desearch.py company_export 5b33f3ee-168b-4780-9c8e-63a626781872 --format jsonl -o companies.jsonl
```

**Options:**
| Option | Description |
|--------|-------------|
| `--format` | `csv` (default) or `jsonl` |
| `--output`, `-o` | Write the export to this file and print `{ saved, format, bytes }`. Without it the export prints to stdout. |

**CSV columns**, one row per company: `domain`, `name`, `url`, `score`, `country`, `city`, `industry`, `primary_email`, `primary_email_type`, `emails` and `phones` (`; `-separated), `linkedin`, `x`, `facebook`, `instagram`, `github`, `youtube`, `tiktok`, then for each of `ceo` (or the managing director), `founder`, `cto`, and `cfo`: `<role>_name`, `<role>_title`, `<role>_email`, `<role>_email_status`, `<role>_linkedin`, and finally `fully_verified`, `unverified_criteria` (`; `-separated), and `enrichment_status`. A leader's email is their first `valid` one, else the first not known to be `invalid`, else the first. JSON Lines has one company per line with every field. Fields the later stages have not filled in yet are empty, so export after the task ends.


### `company_pause`, `company_resume`, `company_cancel`: Control a Task

```bash
scripts/desearch.py company_pause 5b33f3ee-168b-4780-9c8e-63a626781872
scripts/desearch.py company_resume 5b33f3ee-168b-4780-9c8e-63a626781872
scripts/desearch.py company_cancel 5b33f3ee-168b-4780-9c8e-63a626781872
```

- **pause:** a queued task pauses at once; a running one finishes its current batch first (`pausing`, then `paused`). Companies delivered so far stay available. A task paused for more than 7 days is cancelled.
- **resume:** continues a paused task where it stopped. It is not charged again.
- **cancel:** stops the task for good. You pay only for the companies it already delivered (nothing if it had not started), and the rest of the reservation is returned. Delivered companies stay available for 30 days. Cannot be undone.

**Response:** the task. `409` means the action does not apply to the task's current status; the body is `{ detail, task }` with the task as it is now.


### `company_tasks`: List Your Tasks

Company Search and Company Enrich tasks, newest first. People Search tasks are not listed here.

```bash
scripts/desearch.py company_tasks
scripts/desearch.py company_tasks --type enrich --status running,paused
scripts/desearch.py company_tasks --metadata campaign=q4 --metadata workspace_id=ws_42
```

**Options:**
| Option | Description |
|--------|-------------|
| `--type` | `search` or `enrich` |
| `--status` | Comma-separated statuses, e.g. `running,paused` |
| `--limit`, `-n` | Tasks per page, 1 to 100 (API default 20) |
| `--cursor` | `next_cursor` from the previous page. Keep the same filters when you page. |
| `--metadata` | `key=value`, repeatable (up to 3). Only tasks whose `metadata` has exactly these labels; a task must match all of them. |

**Response:** `{ tasks: Task[], next_cursor }`

### Errors
| Status | Meaning |
|--------|---------|
| 400 | Unknown type, status, or cursor, or an invalid metadata filter |
| 401 | Missing or invalid API key |
| 402 | Balance cannot cover the reservation |
| 404 | Task not found. A People Search task ID is a 404 here (use `desearch-people-search` for it), and a company task ID is a 404 there. |
| 409 | Pause, resume, or cancel does not apply to the task's current status |
| 410 | Results expired, 30 days after the task ended |
| 422 | Invalid request body or parameters, for example a domain that is not a public host name |
| 429 | Too many of your People Search and Company Search tasks are already queued, running, or paused |

Error bodies are JSON with a `detail` field. A `409` from pause, resume, or cancel also includes the current `task`. The CLI prints the body as returned. Input it can check locally (query length, `count` and `--min-score` ranges, roles, requirements, more than 20 countries, no domains or more than 200, metadata labels, task ID format, statuses, export format) is rejected before any request is sent.

## Resources
- [Company Search guide](https://www.desearch.ai/docs/guide/apis/company-search)
- [API Reference](https://desearch.ai/docs/api-reference)
- [Pricing](https://desearch.ai/pricing)
- [Desearch Console](https://console.desearch.ai)

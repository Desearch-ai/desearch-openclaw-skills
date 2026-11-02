---
name: desearch-threads-search
description: Search public Threads in real time. Find posts by keyword and date, find accounts by name, read a profile and its latest posts, and get one post with its replies.
metadata: {"clawdbot":{"emoji":"🧵","homepage":"https://desearch.ai","requires":{"env":["DESEARCH_API_KEY"]}}}
---

# Threads Search By Desearch

Real-time public Threads data: keyword search, account search, profiles, a profile's latest posts, and single posts with their replies. Public data only.

## Setup

1. Get an API key from https://console.desearch.ai
2. Set environment variable: `export DESEARCH_API_KEY='your-key-here'`

## Pricing

Every command is one request, billed at $2.07 per 1,000 requests, including an empty result. A `404` and a `422` are not charged.

## No Pagination

Threads commands return everything in one response and take no cursor:

- `threads_search` returns one batch of posts (often 10 to 20); Threads offers no further pages. Narrow the query or the dates to get different posts.
- `threads_profile_posts` returns the latest 20-30 posts, which is all Threads shows publicly.

Lists are printed as plain JSON arrays.

## Common Fields

### Post
| Field | Type | Description |
|-------|------|-------------|
| `id` | string\|null | Post ID |
| `code` | string\|null | Shortcode from the post URL. Pass it to `threads_post`. |
| `url` | string\|null | `https://www.threads.com/@{username}/post/{code}` |
| `text` | string\|null | Post text |
| `createdAt` | string\|null | ISO time |
| `author` | User\|null | `{id, username, fullName, avatar, verified}` |
| `likes`, `replies`, `reposts`, `quotes`, `reshares`, `views` | int\|null | Counts |
| `images`, `videos` | string[]\|null | Media URLs |

Fields a result does not report can be missing or `null`; treat them as unknown, not zero.

## Commands

### `threads_search`: Search Posts

```bash
scripts/desearch.py threads_search "bittensor"
scripts/desearch.py threads_search "bittensor" --start-date 2026-01-01 --end-date 2026-10-30
```

**Options:**
| Option | Description |
|--------|-------------|
| `--start-date` | Only posts on or after this date (YYYY-MM-DD) |
| `--end-date` | Only posts on or before this date (YYYY-MM-DD) |

**Response:** `Post[]`


### `threads_search_users`: Search Accounts

```bash
scripts/desearch.py threads_search_users zuck
```

The query is a username or name, up to 100 characters.

**Response:** `User[]`


### `threads_profile`: Retrieve Profile

```bash
scripts/desearch.py threads_profile zuck
```

The leading `@` is optional.

**Response:** `{ id, username, url, fullName, bio, avatar, followers, verified, isPrivate, isThreadsOnly, links }`


### `threads_profile_posts`: Profile Posts

```bash
scripts/desearch.py threads_profile_posts zuck
```

**Response:** `Post[]` (the latest 20-30)


### `threads_post`: Retrieve Post

```bash
scripts/desearch.py threads_post DK-BydcJHkF
scripts/desearch.py threads_post "https://www.threads.com/@zuck/post/DK-BydcJHkF"
```

Takes the post URL or its shortcode.

**Response:** `Post` plus `comments` (`Post[]`, the public replies returned with it) and `threadItems` (`Post[]`, the author's own continuation posts in the same thread).

### Errors
| Status | Meaning |
|--------|---------|
| 401 | Missing or invalid API key |
| 402 | Balance depleted |
| 404 | Profile or post not found (not charged) |
| 422 | Invalid parameters (not charged) |
| 429 | Too many requests |

Error bodies are JSON with a `detail` field and are printed as returned.

## Resources
- [API Reference](https://desearch.ai/docs/api-reference)
- [Desearch Console](https://console.desearch.ai)

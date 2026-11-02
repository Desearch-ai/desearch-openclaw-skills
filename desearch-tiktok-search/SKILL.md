---
name: desearch-tiktok-search
description: Search public TikTok in real time. Find posts by keyword or hashtag, read a creator's profile and recent posts, get one post and its comments, and list trending posts by region. List commands return one page at a time with a cursor for the next page.
metadata: {"clawdbot":{"emoji":"🎵","homepage":"https://desearch.ai","requires":{"env":["DESEARCH_API_KEY"]}}}
---

# TikTok Search By Desearch

Real-time public TikTok data: keyword and hashtag search, creator profiles and their posts, post details, comments, and trending posts. Public data only; download and no-watermark media URLs are not exposed.

## Setup

1. Get an API key from https://console.desearch.ai
2. Set environment variable: `export DESEARCH_API_KEY='your-key-here'`

## Pagination

`tiktok_search`, `tiktok_profile_posts`, `tiktok_comments`, and `tiktok_hashtag` return one page:

```json
{
  "results": [ ... ],
  "next_cursor": "eyJ2IjoxLCJyb3V0ZSI6..."
}
```

For the next page, run the same command with the same target (query, username, video ID, or hashtag) plus `--cursor <next_cursor>`. `next_cursor` is `null` on the last page; stop there.

```bash
scripts/desearch.py tiktok_hashtag ai --count 20
scripts/desearch.py tiktok_hashtag ai --count 20 --cursor "eyJ2IjoxLCJyb3V0ZSI6..."
```

- The cursor is opaque. Send it back exactly as printed; never build or edit one.
- A cursor works only for the command and target that returned it, for 24 hours. Any other value returns `422` and is not charged.
- `--count` is a maximum. Each request reads one provider page and returns at most `--count` items from it; items past `--count` on that page are skipped, not carried to the next page. To page through everything without gaps, use `--count 100`. The charge settles to the items returned. Keep going until `next_cursor` is `null`.
- Posts already returned on the previous page are left out of the next one and are not charged again.

`tiktok_trending` returns a plain list and does not page.

## Common Fields

### Post
| Field | Type | Description |
|-------|------|-------------|
| `id` | string | TikTok video ID. Pass it to `tiktok_post` or `tiktok_comments`. |
| `providerId` | string\|null | Opaque upstream ID, when present |
| `url` | string\|null | `https://www.tiktok.com/@{username}/video/{id}` |
| `text` | string\|null | Caption |
| `createTime` | string\|null | Post time |
| `author` | Author\|null | See Author below |
| `stats` | object\|null | `{playCount, digCount, commentCount, shareCount, collectCount}`; `digCount` is likes |
| `music` | object | `{id, title, authorName}`. Omitted on hashtag and trending posts. |
| `hashtags` | string[] | Hashtags; empty when none |
| `mentions` | string[] | Mentioned handles; empty when none |
| `videoDuration`, `videoWidth`, `videoHeight` | int\|null | Video size and duration |
| `thumbnailUrl`, `mediaUrl` | string\|null | Cover image and video URL |

### Author
| Field | Type | Description |
|-------|------|-------------|
| `id` | string\|null | User ID |
| `username` | string\|null | Handle without `@` |
| `nickname` | string\|null | Display name |
| `avatar` | string\|null | Avatar URL |
| `verified` | bool\|null | Verified badge |
| `followers`, `following` | int\|null | Follower and following counts |
| `heart` | int\|null | Total likes received |

Fields a post does not report can be missing or `null`; treat them as unknown, not zero.

## Commands

### `tiktok_search`: Search Posts

```bash
scripts/desearch.py tiktok_search "home espresso" --count 10
scripts/desearch.py tiktok_search "home espresso" --count 10 --cursor "<next_cursor>"
```

**Options:**
| Option | Description |
|--------|-------------|
| `--count`, `-n` | Maximum posts on this page, 1 to 100 (API default 10) |
| `--cursor` | `next_cursor` from the previous page |
| `--sort` | Sort option, passed to the provider when it supports one. A cursor only works with the same `--sort`. |

**Response:** `{ results: Post[], next_cursor }`. Only repeats of the previous page are removed, so a post from an earlier page can reappear.


### `tiktok_post`: Retrieve Post by ID

```bash
scripts/desearch.py tiktok_post 7620891413932166433
```

**Response:** `Post`


### `tiktok_profile`: Retrieve Profile

```bash
scripts/desearch.py tiktok_profile tiktok
```

**Response:** `Profile`: the Author fields plus `bio`, `videoCount` (posts), and `digCount` (likes given).


### `tiktok_profile_posts`: Profile Posts

Public posts from a creator.

```bash
scripts/desearch.py tiktok_profile_posts tiktok --count 20
scripts/desearch.py tiktok_profile_posts tiktok --count 20 --cursor "<next_cursor>"
```

**Options:**
| Option | Description |
|--------|-------------|
| `--count`, `-n` | Maximum posts on this page, 1 to 100 (API default 20) |
| `--cursor` | `next_cursor` from the previous page |

**Response:** `{ results: Post[], next_cursor }`


### `tiktok_comments`: Post Comments

```bash
scripts/desearch.py tiktok_comments 7620891413932166433 --count 20
```

**Options:** `--count`, `-n` (1 to 100, API default 20) and `--cursor`, as above.

**Response:** `{ results: Comment[], next_cursor }`. A comment is `{ id, videoId, text, createTime, author: Author, likes, replies }`.


### `tiktok_hashtag`: Hashtag Posts

```bash
scripts/desearch.py tiktok_hashtag ai --count 20
```

The leading `#` is optional. **Options:** `--count`, `-n` (1 to 100, API default 20) and `--cursor`, as above.

**Response:** `{ results: Post[], next_cursor }`. Only repeats of the previous page are removed, so a post from an earlier page can reappear.


### `tiktok_trending`: Trending Posts

```bash
scripts/desearch.py tiktok_trending --region US --count 10
```

**Options:**
| Option | Description |
|--------|-------------|
| `--region` | Two-letter region code (API default `US`) |
| `--count`, `-n` | Maximum posts, 1 to 100 (API default 20) |

**Response:** `Post[]`. Trending does not page.

### Errors
| Status | Meaning |
|--------|---------|
| 401 | Missing or invalid API key |
| 402 | Balance depleted |
| 422 | Invalid parameters, or a cursor that is expired or came from another command or target (not charged) |
| 429 | Too many requests |

Error bodies are JSON with a `detail` field and are printed as returned.

## Resources
- [API Reference](https://desearch.ai/docs/api-reference)
- [Desearch Console](https://console.desearch.ai)

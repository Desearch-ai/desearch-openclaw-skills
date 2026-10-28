---
name: desearch-instagram-search
description: Search public Instagram profiles by keyword, and read profiles, their recent posts, single posts, post comments, and hashtag posts in real time. List commands return one page at a time with a cursor for the next page.
metadata: {"clawdbot":{"emoji":"📸","homepage":"https://desearch.ai","requires":{"env":["DESEARCH_API_KEY"]}}}
---

# Instagram Search By Desearch

Real-time public Instagram data: profile search, profiles and their posts, single posts, comments, and hashtag posts. Public data only; private accounts, login-only surfaces, and download-only media are not exposed.

## Setup

1. Get an API key from https://console.desearch.ai
2. Set environment variable: `export DESEARCH_API_KEY='your-key-here'`

## Pagination

`instagram_profile_posts`, `instagram_comments`, and `instagram_hashtag` return one page:

```json
{
  "results": [ ... ],
  "next_cursor": "eyJ2IjoxLCJyb3V0ZSI6..."
}
```

For the next page, run the same command with the same target (username, shortcode, or hashtag) plus `--cursor <next_cursor>`. `next_cursor` is `null` on the last page; stop there.

```bash
scripts/desearch.py instagram_profile_posts instagram --count 12
scripts/desearch.py instagram_profile_posts instagram --count 12 --cursor "eyJ2IjoxLCJyb3V0ZSI6..."
```

- The cursor is opaque. Send it back exactly as printed; never build or edit one.
- A cursor works only for the command and target that returned it, for 24 hours. Any other value returns `422` and is not charged.
- `--count` is a maximum. Each request reads one provider page and returns at most `--count` items from it; items past `--count` on that page are skipped, not carried to the next page. A profile's posts come about 12 per page. To page through everything without gaps, use `--count 100`. The charge settles to the items returned. Keep going until `next_cursor` is `null`.
- Items already returned on the previous page are left out of the next one and are not charged again.

`instagram_search` returns a plain list and does not page; it has no `--cursor`.

## Common Fields

### Post
| Field | Type | Description |
|-------|------|-------------|
| `id` | string\|null | Media ID |
| `shortcode` | string\|null | Code in the post URL. Pass it to `instagram_comments` or `instagram_media`. |
| `url` | string\|null | `https://www.instagram.com/p/{shortcode}/` |
| `caption` | string\|null | Caption |
| `createTime` | string\|null | Post time |
| `mediaType` | string\|null | `image`, `video`, or `carousel` |
| `mediaUrl`, `thumbnailUrl` | string\|null | Media and thumbnail URLs |
| `author` | Profile\|null | See Profile below |
| `stats` | object\|null | `{likeCount, commentCount, viewCount, playCount}` |
| `hashtags`, `mentions` | string[] | Empty when none |
| `children` | array | Items of a carousel post |

### Profile
| Field | Type | Description |
|-------|------|-------------|
| `id` | string\|null | User ID |
| `username` | string\|null | Handle without `@` |
| `fullName` | string\|null | Display name |
| `biography` | string\|null | Bio |
| `avatar` | string\|null | Avatar URL |
| `verified` | bool\|null | Verified badge |
| `private` | bool\|null | Private account |
| `followers`, `following` | int | Exact counts. Omitted when the provider does not give one. |
| `postsCount` | int | Total posts. Omitted when unknown. |
| `externalUrl` | string\|null | Link in bio |
| `category` | string\|null | Business category |

Fields a record does not report can be missing or `null`; treat them as unknown, not zero.

## Commands

### `instagram_search`: Search Profiles

```bash
scripts/desearch.py instagram_search "coffee roasters" --count 10
```

**Options:**
| Option | Description |
|--------|-------------|
| `--count`, `-n` | Maximum results, 1 to 100 (API default 10) |

**Response:** a list of `{ id, type, username, title, url, avatar, followers }`. `type` is `profile`, `hashtag`, or `media`; `followers` is omitted when unknown. Use `instagram_hashtag` to find posts.


### `instagram_media`: Retrieve a Post

Accepts a shortcode, a media ID, or a public post URL.

```bash
scripts/desearch.py instagram_media DeuOR-CjKE9
scripts/desearch.py instagram_media "https://www.instagram.com/p/DeuOR-CjKE9/"
```

**Response:** `Post`


### `instagram_profile`: Retrieve Profile

```bash
scripts/desearch.py instagram_profile instagram
```

**Response:** `Profile`


### `instagram_profile_posts`: Profile Posts

```bash
scripts/desearch.py instagram_profile_posts instagram --count 12
```

**Options:**
| Option | Description |
|--------|-------------|
| `--count`, `-n` | Maximum posts on this page, 1 to 100 (API default 20) |
| `--cursor` | `next_cursor` from the previous page |

**Response:** `{ results: Post[], next_cursor }`


### `instagram_comments`: Post Comments

Takes the post **shortcode** (`DeuOR-CjKE9` in `https://www.instagram.com/p/DeuOR-CjKE9/`) or the post URL, from which the CLI reads the shortcode. Numeric media IDs return `404`.

```bash
scripts/desearch.py instagram_comments DeuOR-CjKE9 --count 20
scripts/desearch.py instagram_comments "https://www.instagram.com/p/DeuOR-CjKE9/"
```

**Options:** `--count`, `-n` (1 to 100, API default 20) and `--cursor`, as above.

**Response:** `{ results: Comment[], next_cursor }`. A comment is `{ id, mediaId, text, createTime, author: Profile, likes, replies }`.


### `instagram_hashtag`: Hashtag Posts

```bash
scripts/desearch.py instagram_hashtag ai --count 20
```

The leading `#` is optional. **Options:** `--count`, `-n` (1 to 100, API default 20) and `--cursor`, as above.

**Response:** `{ results: Post[], next_cursor }`

### Errors
| Status | Meaning |
|--------|---------|
| 401 | Missing or invalid API key |
| 402 | Balance depleted |
| 404 | No post found for this shortcode |
| 422 | Invalid parameters, or a cursor that is expired or came from another command or target (not charged) |
| 429 | Too many requests |

Error bodies are JSON with a `detail` field and are printed as returned.

## Resources
- [API Reference](https://desearch.ai/docs/api-reference)
- [Desearch Console](https://console.desearch.ai)

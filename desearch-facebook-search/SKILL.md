---
name: desearch-facebook-search
description: Search the public Meta Ad Library by keyword or hashtag, and read public Facebook pages and profiles, their posts, single posts, and post comments in real time. List commands return one page at a time with a cursor for the next page.
metadata: {"clawdbot":{"emoji":"📘","homepage":"https://desearch.ai","requires":{"env":["DESEARCH_API_KEY"]}}}
---

# Facebook Search By Desearch

Real-time public Facebook data: Meta Ad Library search, public pages and profiles, their posts, single posts, and comments. Public data only.

Keyword and hashtag search (`facebook_search`, `facebook_hashtag`) search **Meta Ad Library** records (ads), not organic posts. To read organic posts, start from a page with `facebook_profile_posts`.

## Setup

1. Get an API key from https://console.desearch.ai
2. Set environment variable: `export DESEARCH_API_KEY='your-key-here'`

## Pagination

`facebook_search`, `facebook_profile_posts`, `facebook_comments`, and `facebook_hashtag` return one page:

```json
{
  "results": [ ... ],
  "next_cursor": "eyJ2IjoxLCJyb3V0ZSI6..."
}
```

For the next page, run the same command with the same target (query, page, post ID, or hashtag) plus `--cursor <next_cursor>`. `next_cursor` is `null` on the last page; stop there.

```bash
scripts/desearch.py facebook_profile_posts facebook
scripts/desearch.py facebook_profile_posts facebook --cursor "eyJ2IjoxLCJyb3V0ZSI6..."
```

- The cursor is opaque. Send it back exactly as printed; never build or edit one.
- A cursor works only for the command and target that returned it, for 24 hours. Any other value returns `422` and is not charged.
- `--count` is a maximum. Each request reads one provider page and returns at most `--count` items from it; items past `--count` on that page are skipped, not carried to the next page. A provider page holds about 30 Ad Library records, 3 page posts, or about 10 comments. To page through everything without gaps, use `--count 100`. The charge settles to the items returned. Keep going until `next_cursor` is `null`.
- Items already returned on the previous page are left out of the next one and are not charged again.

## Common Fields

### Post
| Field | Type | Description |
|-------|------|-------------|
| `id` | string\|null | Post ID. Pass it to `facebook_post` or `facebook_comments`. |
| `url` | string\|null | Post URL, or the Ad Library URL for an ad |
| `text` | string\|null | Post or ad text |
| `createTime` | string\|null | Post time |
| `author` | Profile\|null | Page or profile that posted it; see Profile below |
| `stats` | object\|null | `{reactionCount, commentCount, shareCount, viewCount}` |
| `media` | array | `[{type, url, thumbnail, width, height}]` |
| `hashtags` | string[] | Hashtags; empty when none |

Ad Library records also carry:
| Field | Type | Description |
|-------|------|-------------|
| `headline` | string\|null | Ad headline |
| `linkUrl` | string\|null | Ad landing URL |
| `linkDescription` | string\|null | Ad link description |
| `cta` | string\|null | Call-to-action button text, or its type such as `SHOP_NOW` |
| `active` | bool | Whether the ad is running. Omitted when unknown. |
| `endDate` | string | Ad end date. Omitted when unknown. |
| `platforms` | string[] | Where the ad runs, such as `FACEBOOK` or `INSTAGRAM` |

### Profile
| Field | Type | Description |
|-------|------|-------------|
| `id` | string\|null | Page or profile ID |
| `username` | string\|null | Public handle |
| `name` | string\|null | Display name |
| `url` | string\|null | Page URL |
| `avatar` | string\|null | Avatar URL |
| `verified` | bool\|null | Verified badge |
| `bio` | string\|null | About text |
| `category` | string\|null | Page category |
| `followers`, `likes` | int\|null | Follower and page-like counts |

Fields a record does not report can be missing or `null`; treat them as unknown, not zero.

## Commands

### `facebook_search`: Search the Meta Ad Library

```bash
scripts/desearch.py facebook_search "running shoes" --count 10
scripts/desearch.py facebook_search "running shoes" --cursor "<next_cursor>"
```

**Options:**
| Option | Description |
|--------|-------------|
| `--count`, `-n` | Maximum ads on this page, 1 to 100 (API default 10) |
| `--cursor` | `next_cursor` from the previous page |

**Response:** `{ results: Post[], next_cursor }`


### `facebook_post`: Retrieve Post by ID

```bash
scripts/desearch.py facebook_post 1525856912919657
```

**Response:** `Post`


### `facebook_profile`: Retrieve Page or Profile

Accepts a numeric ID, a username, or a vanity handle.

```bash
scripts/desearch.py facebook_profile facebook
```

**Response:** `Profile`


### `facebook_profile_posts`: Page or Profile Posts

```bash
scripts/desearch.py facebook_profile_posts facebook
scripts/desearch.py facebook_profile_posts facebook --cursor "<next_cursor>"
```

**Options:**
| Option | Description |
|--------|-------------|
| `--count`, `-n` | Maximum posts on this page, 1 to 100 (API default 20). The provider returns 3 posts per page. |
| `--cursor` | `next_cursor` from the previous page |

**Response:** `{ results: Post[], next_cursor }`


### `facebook_comments`: Post Comments

```bash
scripts/desearch.py facebook_comments 1525856912919657
```

**Options:** `--count`, `-n` (1 to 100, API default 20; the provider returns about 10 per page) and `--cursor`, as above.

**Response:** `{ results: Comment[], next_cursor }`. A comment is `{ id, postId, text, createTime, author: Profile, likes, replies }`.


### `facebook_hashtag`: Ad Library Records for a Hashtag

Runs the same Meta Ad Library search as `facebook_search` for a keyword or hashtag. Organic hashtag feeds are not available.

```bash
scripts/desearch.py facebook_hashtag ai --count 20
```

The leading `#` is optional. **Options:** `--count`, `-n` (1 to 100, API default 20) and `--cursor`, as above.

**Response:** `{ results: Post[], next_cursor }`

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

---
name: desearch-reddit-search
description: Search public Reddit in real time. Find posts across all subreddits by keyword, read a subreddit's metadata and posts, and get one post and its comment tree. List commands return one page at a time with a cursor for the next page.
metadata: {"clawdbot":{"emoji":"👽","homepage":"https://desearch.ai","requires":{"env":["DESEARCH_API_KEY"]}}}
---

# Reddit Search By Desearch

Real-time public Reddit data: keyword search across all subreddits, subreddit metadata, subreddit posts with Reddit's sort and time filters, single posts, and comment trees. Public data only.

## Setup

1. Get an API key from https://console.desearch.ai
2. Set environment variable: `export DESEARCH_API_KEY='your-key-here'`

## Pricing

Every command is one request, billed at $2.07 per 1,000 requests, including a page with no results. A `404` and a `422` are not charged.

## Pagination

`reddit_search`, `reddit_subreddit_posts`, and `reddit_comments` return one page:

```json
{
  "results": [ ... ],
  "next_cursor": "eyJ2IjoxLCJyb3V0ZSI6..."
}
```

For the next page, run the same command with the same target (query and filters, subreddit and sort, or post) plus `--cursor <next_cursor>`. `next_cursor` is `null` on the last page; stop there.

```bash
scripts/desearch.py reddit_subreddit_posts AskReddit --sort top --timeframe week
scripts/desearch.py reddit_subreddit_posts AskReddit --sort top --timeframe week --cursor "eyJ2IjoxLCJyb3V0ZSI6..."
```

- The cursor is opaque. Send it back exactly as printed; never build or edit one.
- A cursor works only for the command and target that returned it, for 24 hours. Any other value returns `422` and is not charged.
- Each request reads one Reddit page, so page sizes vary. A later page can occasionally come back empty; that page is billed like any other.

## IDs and Names

- Post commands take a post ID (`1q6pxwn`, with or without `t3_`) or the post's full URL.
- Subreddit names are case-sensitive: `AskReddit`, not `askreddit`. A leading `r/` is optional.

## Common Fields

### Post
| Field | Type | Description |
|-------|------|-------------|
| `id` | string\|null | Post ID. Pass it to `reddit_post` or `reddit_comments`. |
| `name` | string\|null | Reddit fullname (`t3_` + id) |
| `title`, `text` | string\|null | Title, and body of a text post |
| `author`, `subreddit` | string\|null | Author username and subreddit name |
| `url` | string\|null | Reddit permalink |
| `linkUrl` | string\|null | Outbound link of a link post, when different from `url` |
| `score`, `upvotes`, `commentCount` | int\|null | Counts |
| `upvoteRatio` | float\|null | Share of upvotes |
| `createdAt` | string\|null | ISO time |
| `flair` | string\|null | Post flair |
| `isVideo`, `over18`, `locked`, `archived` | bool\|null | Flags |
| `subredditSubscribers` | int\|null | Subreddit size |

Fields a result does not report can be missing or `null`; treat them as unknown, not zero.

## Commands

### `reddit_search`: Search Posts

```bash
scripts/desearch.py reddit_search "bittensor"
scripts/desearch.py reddit_search "bittensor" --sort top --timeframe month
```

**Options:**
| Option | Description |
|--------|-------------|
| `--sort` | `relevance`, `new`, `top`, or `comment_count` |
| `--timeframe` | `all`, `day`, `week`, `month`, or `year` |
| `--cursor` | `next_cursor` from the previous page. Works only with the same query and filters. |

**Response:** `{ results: Post[], next_cursor }`


### `reddit_subreddit`: Retrieve Subreddit

```bash
scripts/desearch.py reddit_subreddit AskReddit
```

**Response:** `{ id, name, url, description, rules, weeklyActiveUsers, weeklyContributions, icon, header, createdAt, advertiserCategory, submitText }`


### `reddit_subreddit_posts`: Subreddit Posts

```bash
scripts/desearch.py reddit_subreddit_posts AskReddit --sort new
scripts/desearch.py reddit_subreddit_posts AskReddit --sort top --timeframe week
```

**Options:**
| Option | Description |
|--------|-------------|
| `--sort` | `best`, `hot`, `new`, `top`, or `rising` |
| `--timeframe` | `all`, `day`, `week`, `month`, or `year`. Applies to `top`; ignored with another sort; without `--sort` it means `top`. |
| `--cursor` | `next_cursor` from the previous page |

**Response:** `{ results: Post[], next_cursor }`


### `reddit_post`: Retrieve Post

```bash
scripts/desearch.py reddit_post 1q6pxwn
```

**Response:** `Post`, without comments. Use `reddit_comments` for those.


### `reddit_comments`: Post Comments

```bash
scripts/desearch.py reddit_comments 1q6pxwn
```

**Options:** `--cursor`, as above.

**Response:** `{ results: Comment[], next_cursor }`. Comments are a tree of top-level comments with the replies Reddit loaded alongside them. A comment is `{ id, name, postId, parentId, author, text, score, createdAt, url, depth, replies: Comment[], hasMoreReplies }`; `depth` is 0 for a top-level comment and `hasMoreReplies` is `true` when Reddit has more replies than were loaded.

### Errors
| Status | Meaning |
|--------|---------|
| 401 | Missing or invalid API key |
| 402 | Balance depleted |
| 404 | Subreddit or post not found (not charged) |
| 422 | Invalid parameters, or a cursor that is expired or came from another command or target (not charged) |
| 429 | Too many requests |

Error bodies are JSON with a `detail` field and are printed as returned.

## Resources
- [API Reference](https://desearch.ai/docs/api-reference)
- [Desearch Console](https://console.desearch.ai)

---
name: desearch-x-search
description: Search X (Twitter) in real time. Find posts by keyword, user, or hashtag. Get a user's timeline, replies, retweeters, or fetch specific posts by ID or URL. Supports advanced filters like date range, language, engagement thresholds, and media type.
metadata: {"clawdbot":{"emoji":"𝕏","homepage":"https://desearch.ai","requires":{"env":["DESEARCH_API_KEY"]}}}
---

# X (Twitter) Search By Desearch

Real-time X/Twitter search and monitoring. Search posts, track users, get timelines, replies, and retweeters with powerful filtering.

## Setup

1. Get an API key from https://console.desearch.ai
2. Set environment variable: `export DESEARCH_API_KEY='your-key-here'`

## Usage

```bash
# Search X posts by keyword
scripts/desearch.py x "Bittensor TAO" --sort Latest --count 10

# Search with filters
scripts/desearch.py x "AI news" --user elonmusk --start-date 2025-01-01
scripts/desearch.py x "crypto" --min-likes 100 --verified --lang en

# Get a specific post by ID
scripts/desearch.py x_post 1892527552029499853

# Fetch multiple posts by URL
scripts/desearch.py x_urls "https://x.com/user/status/123" "https://x.com/user/status/456"

# Search posts by a specific user
scripts/desearch.py x_user elonmusk --query "AI" --count 10

# Get a user's timeline
scripts/desearch.py x_timeline elonmusk --count 20

# Get retweeters of a post
scripts/desearch.py x_retweeters 1982770537081532854

# Get a user's replies
scripts/desearch.py x_replies elonmusk --count 10

# Get replies to a specific post
scripts/desearch.py x_post_replies 1234567890 --count 10
```

## Commands

| Command | Description |
|---------|-------------|
| `x` | Search X posts with advanced filters (dates, engagement, media type) |
| `x_post` | Retrieve a single post by its ID |
| `x_urls` | Fetch multiple posts by their URLs |
| `x_user` | Search posts by a specific username |
| `x_timeline` | Get a user's recent timeline posts |
| `x_retweeters` | Get users who retweeted a post |
| `x_replies` | Get a user's replies |
| `x_post_replies` | Get replies to a specific post |

## Options

| Option | Description | Applies to |
|--------|-------------|------------|
| `--count`, `-n` | Number of results (default: 10, max: 100) | Most commands |
| `--sort` | Sort order: `Top` or `Latest` | `x` |
| `--user`, `-u` | Filter by X username | `x` |
| `--start-date` | Start date UTC (YYYY-MM-DD) | `x` |
| `--end-date` | End date UTC (YYYY-MM-DD) | `x` |
| `--lang` | Language code (e.g., `en`, `es`, `fr`) | `x` |
| `--verified` | Filter for verified users | `x` |
| `--blue-verified` | Filter for blue checkmark users | `x` |
| `--is-quote` | Only tweets with quotes | `x` |
| `--is-video` | Only tweets with videos | `x` |
| `--is-image` | Only tweets with images | `x` |
| `--min-retweets` | Minimum retweet count | `x` |
| `--min-replies` | Minimum reply count | `x` |
| `--min-likes` | Minimum like count | `x` |
| `--query`, `-q` | Additional search query filter | `x_user`, `x_replies`, `x_post_replies` |
| `--cursor` | Pagination cursor | `x_retweeters` |

## Examples

### Find trending discussion on a topic
```bash
scripts/desearch.py x "Bittensor" --sort Latest --count 20 --min-likes 5
```

### Monitor what a user is posting
```bash
scripts/desearch.py x_timeline elonmusk --count 20
```


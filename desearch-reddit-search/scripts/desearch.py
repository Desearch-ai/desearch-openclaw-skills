#!/usr/bin/env python3
"""Desearch Reddit Search CLI - Public Reddit search, subreddits, posts, and comments.

List commands print one page as {"results": [...], "next_cursor": "..."}.
Pass next_cursor back unchanged with --cursor for the next page; it is null
on the last page.

Usage:
    desearch reddit_search "<query>" [--sort S] [--timeframe T] [--cursor C]
    desearch reddit_subreddit <name>
    desearch reddit_subreddit_posts <name> [--sort S] [--timeframe T] [--cursor C]
    desearch reddit_post <post_id_or_url>
    desearch reddit_comments <post_id_or_url> [--cursor C]

Environment:
    DESEARCH_API_KEY - Required API key from desearch.ai
    DESEARCH_BASE_URL - Optional API base URL (default https://api.desearch.ai)
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

DESEARCH_BASE = "https://api.desearch.ai"

# List routes return a JSON array and put the cursor for the next page in this
# response header. The header is absent on the last page.
NEXT_CURSOR_HEADER = "x-desearch-next-cursor"

COMMANDS = [
    "reddit_search",
    "reddit_subreddit",
    "reddit_subreddit_posts",
    "reddit_post",
    "reddit_comments",
]

SEARCH_SORTS = ["relevance", "new", "top", "comment_count"]
SUBREDDIT_SORTS = ["best", "hot", "new", "top", "rising"]
TIMEFRAMES = ["all", "day", "week", "month", "year"]


def get_api_key() -> str:
    key = os.environ.get("DESEARCH_API_KEY")
    if not key:
        print("Error: DESEARCH_API_KEY environment variable not set", file=sys.stderr)
        print("Get your key at https://console.desearch.ai", file=sys.stderr)
        sys.exit(1)
    return key


def api_base() -> str:
    return (os.environ.get("DESEARCH_BASE_URL") or DESEARCH_BASE).rstrip("/")


def api_request(
    method: str,
    path: str,
    params: dict = None,
    body: dict = None,
    paged: bool = False,
) -> dict | list | str:
    """Call the API and return the parsed body.

    With ``paged=True`` a JSON array body is returned as
    ``{"results": [...], "next_cursor": <x-desearch-next-cursor or None>}``.
    The cursor is opaque and is passed on exactly as received.
    """
    api_key = get_api_key()
    url = f"{api_base()}{path}"

    if method == "GET" and params:
        filtered = {key: value for key, value in params.items() if value is not None}
        if filtered:
            url = f"{url}?{urlencode(filtered, doseq=True)}"

    headers = {
        "Authorization": api_key,
        "Content-Type": "application/json",
        "User-Agent": "Desearch-OpenClaw/1.0",
    }
    data = json.dumps(body).encode() if method == "POST" and body else None

    try:
        request = Request(url, data=data, headers=headers, method=method)
        with urlopen(request, timeout=60) as response:
            raw = response.read().decode()
            try:
                result = json.loads(raw)
            except json.JSONDecodeError:
                return raw
            if paged and isinstance(result, list):
                return {
                    "results": result,
                    "next_cursor": response.headers.get(NEXT_CURSOR_HEADER) or None,
                }
            return result
    except HTTPError as error:
        error_body = error.read().decode() if error.fp else ""
        try:
            return json.loads(error_body)
        except json.JSONDecodeError:
            return {
                "error": f"HTTP {error.code}: {error.reason}",
                "details": error_body,
            }
    except URLError as error:
        return {"error": f"Connection failed: {error.reason}"}
    except Exception as error:
        return {"error": str(error)}


# Argument types


def required_text(value: str) -> str:
    text = value.strip()
    if not text:
        raise argparse.ArgumentTypeError("must not be empty")
    return text


def query_text(value: str) -> str:
    text = required_text(value)
    if len(text) > 500:
        raise argparse.ArgumentTypeError("must be at most 500 characters")
    return text


def path_segment(value: str) -> str:
    # Encode every reserved character, "/" included, so an ID or URL is one segment.
    return quote(value, safe="")


def subreddit_name(value: str) -> str:
    name = value.strip()
    for prefix in ("/r/", "r/"):
        if name.lower().startswith(prefix):
            name = name[len(prefix) :]
            break
    return required_text(name.strip("/"))


# Commands


def cmd_reddit_search(args):
    body = {"query": args.query}
    for key, value in (
        ("sort", args.sort),
        ("timeframe", args.timeframe),
        ("cursor", args.cursor or None),
    ):
        if value is not None:
            body[key] = value
    return api_request("POST", "/desearch/reddit/search", body=body, paged=True)


def cmd_reddit_subreddit(args):
    return api_request("GET", f"/desearch/reddit/subreddit/{path_segment(args.name)}")


def cmd_reddit_subreddit_posts(args):
    return api_request(
        "GET",
        f"/desearch/reddit/subreddit/{path_segment(args.name)}/posts",
        params={
            "sort": args.sort,
            "timeframe": args.timeframe,
            "cursor": args.cursor or None,
        },
        paged=True,
    )


def cmd_reddit_post(args):
    return api_request("GET", f"/desearch/reddit/post/{path_segment(args.id)}")


def cmd_reddit_comments(args):
    return api_request(
        "GET",
        f"/desearch/reddit/comments/{path_segment(args.post_id)}",
        params={"cursor": args.cursor or None},
        paged=True,
    )


COMMAND_HANDLERS = {
    "reddit_search": cmd_reddit_search,
    "reddit_subreddit": cmd_reddit_subreddit,
    "reddit_subreddit_posts": cmd_reddit_subreddit_posts,
    "reddit_post": cmd_reddit_post,
    "reddit_comments": cmd_reddit_comments,
}


def add_cursor(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--cursor",
        help="next_cursor from the previous page, sent back unchanged",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Desearch Reddit Search CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    commands = parser.add_subparsers(dest="command", metavar="command", required=True)

    search = commands.add_parser(
        "reddit_search", help="Search public Reddit posts across all subreddits"
    )
    search.add_argument("query", type=query_text, help="Keyword or phrase")
    search.add_argument("--sort", choices=SEARCH_SORTS, help="Result order")
    search.add_argument(
        "--timeframe", choices=TIMEFRAMES, help="Only posts from this window"
    )
    add_cursor(search)

    subreddit = commands.add_parser("reddit_subreddit", help="A subreddit's metadata")
    subreddit.add_argument(
        "name",
        type=subreddit_name,
        help="Subreddit name, case-sensitive (r/ optional), e.g. AskReddit",
    )

    posts = commands.add_parser("reddit_subreddit_posts", help="Posts in a subreddit")
    posts.add_argument(
        "name",
        type=subreddit_name,
        help="Subreddit name, case-sensitive (r/ optional), e.g. AskReddit",
    )
    posts.add_argument("--sort", choices=SUBREDDIT_SORTS, help="Post order")
    posts.add_argument(
        "--timeframe",
        choices=TIMEFRAMES,
        help="Time window for top; ignored with another sort, means top without --sort",
    )
    add_cursor(posts)

    post = commands.add_parser("reddit_post", help="One Reddit post, without comments")
    post.add_argument(
        "id", type=required_text, help="Post ID (t3_ optional) or the post URL"
    )

    comments = commands.add_parser(
        "reddit_comments", help="Comments on a Reddit post, as a tree"
    )
    comments.add_argument(
        "post_id", type=required_text, help="Post ID (t3_ optional) or the post URL"
    )
    add_cursor(comments)

    return parser


def main(argv: list[str] | None = None):
    parser = build_parser()
    args = parser.parse_args(argv)

    handler = COMMAND_HANDLERS[args.command]
    results = handler(args)

    if isinstance(results, str):
        print(results)
    else:
        print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()

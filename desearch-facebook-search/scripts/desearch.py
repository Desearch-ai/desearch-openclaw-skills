#!/usr/bin/env python3
"""Desearch Facebook Search CLI - Meta Ad Library search plus public Facebook pages, posts, and comments.

List commands print one page as {"results": [...], "next_cursor": "..."}.
Pass next_cursor back unchanged with --cursor for the next page; it is null
on the last page.

Usage:
    desearch facebook_search "<query>" [--count N] [--cursor C]
    desearch facebook_post <post_id>
    desearch facebook_profile <profile_id_or_handle>
    desearch facebook_profile_posts <profile_id_or_handle> [--count N] [--cursor C]
    desearch facebook_comments <post_id> [--count N] [--cursor C]
    desearch facebook_hashtag <tag> [--count N] [--cursor C]

Environment:
    DESEARCH_API_KEY - Required API key from desearch.ai
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
    "facebook_search",
    "facebook_post",
    "facebook_profile",
    "facebook_profile_posts",
    "facebook_comments",
    "facebook_hashtag",
]


def get_api_key() -> str:
    key = os.environ.get("DESEARCH_API_KEY")
    if not key:
        print("Error: DESEARCH_API_KEY environment variable not set", file=sys.stderr)
        print("Get your key at https://console.desearch.ai", file=sys.stderr)
        sys.exit(1)
    return key


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
    url = f"{DESEARCH_BASE}{path}"

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


def bounded_int(minimum: int, maximum: int):
    def parse(value: str) -> int:
        number = int(value)
        if not minimum <= number <= maximum:
            raise argparse.ArgumentTypeError(f"must be between {minimum} and {maximum}")
        return number

    return parse


def required_text(value: str) -> str:
    text = value.strip()
    if not text:
        raise argparse.ArgumentTypeError("must not be empty")
    return text


def hashtag(value: str) -> str:
    return required_text(value.strip().lstrip("#"))


def path_segment(value: str) -> str:
    # Encode every reserved character, "/" included, so an ID is one segment.
    return quote(value, safe="")


def page_params(args) -> dict:
    return {"count": args.count, "cursor": args.cursor or None}


# Commands


def cmd_facebook_search(args):
    body = {"query": args.query}
    if args.count is not None:
        body["count"] = args.count
    if args.cursor:
        body["cursor"] = args.cursor
    return api_request("POST", "/desearch/facebook/search", body=body, paged=True)


def cmd_facebook_post(args):
    return api_request("GET", f"/desearch/facebook/post/{path_segment(args.id)}")


def cmd_facebook_profile(args):
    return api_request(
        "GET", f"/desearch/facebook/profile/{path_segment(args.profile_id)}"
    )


def cmd_facebook_profile_posts(args):
    return api_request(
        "GET",
        f"/desearch/facebook/profile/{path_segment(args.profile_id)}/posts",
        params=page_params(args),
        paged=True,
    )


def cmd_facebook_comments(args):
    return api_request(
        "GET",
        f"/desearch/facebook/comments/{path_segment(args.post_id)}",
        params=page_params(args),
        paged=True,
    )


def cmd_facebook_hashtag(args):
    return api_request(
        "GET",
        f"/desearch/facebook/hashtag/{path_segment(args.tag)}",
        params=page_params(args),
        paged=True,
    )


COMMAND_HANDLERS = {
    "facebook_search": cmd_facebook_search,
    "facebook_post": cmd_facebook_post,
    "facebook_profile": cmd_facebook_profile,
    "facebook_profile_posts": cmd_facebook_profile_posts,
    "facebook_comments": cmd_facebook_comments,
    "facebook_hashtag": cmd_facebook_hashtag,
}


def add_page_options(parser: argparse.ArgumentParser, default_count: int) -> None:
    parser.add_argument(
        "--count",
        "-n",
        type=bounded_int(1, 100),
        help=f"Maximum results on this page (1-100, API default {default_count}). "
        "The page can be smaller.",
    )
    parser.add_argument(
        "--cursor",
        help="next_cursor from the previous page, sent back unchanged",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Desearch Facebook Search CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    commands = parser.add_subparsers(dest="command", metavar="command", required=True)

    search = commands.add_parser(
        "facebook_search", help="Search public Meta Ad Library records"
    )
    search.add_argument("query", type=required_text, help="Keyword, phrase, or hashtag")
    add_page_options(search, 10)

    post = commands.add_parser("facebook_post", help="One public Facebook post by ID")
    post.add_argument("id", type=required_text, help="Facebook post/media ID")

    profile = commands.add_parser(
        "facebook_profile", help="A public Facebook profile or page"
    )
    profile.add_argument(
        "profile_id", type=required_text, help="Profile/page ID or public handle"
    )

    profile_posts = commands.add_parser(
        "facebook_profile_posts", help="Public posts from a Facebook profile or page"
    )
    profile_posts.add_argument(
        "profile_id", type=required_text, help="Profile/page ID or public handle"
    )
    add_page_options(profile_posts, 20)

    comments = commands.add_parser(
        "facebook_comments", help="Public comments on a Facebook post"
    )
    comments.add_argument("post_id", type=required_text, help="Facebook post/media ID")
    add_page_options(comments, 20)

    tag = commands.add_parser(
        "facebook_hashtag", help="Meta Ad Library records for a keyword or hashtag"
    )
    tag.add_argument("tag", type=hashtag, help="Hashtag or keyword (# optional)")
    add_page_options(tag, 20)

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

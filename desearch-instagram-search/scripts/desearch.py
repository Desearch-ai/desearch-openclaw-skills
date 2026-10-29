#!/usr/bin/env python3
"""Desearch Instagram Search CLI - Public Instagram profiles, posts, comments, and hashtags.

List commands print one page as {"results": [...], "next_cursor": "..."}.
Pass next_cursor back unchanged with --cursor for the next page; it is null
on the last page. instagram_search returns a plain list and does not page.

Usage:
    desearch instagram_search "<query>" [--count N]
    desearch instagram_media <shortcode_id_or_url>
    desearch instagram_profile <username>
    desearch instagram_profile_posts <username> [--count N] [--cursor C]
    desearch instagram_comments <shortcode_or_post_url> [--count N] [--cursor C]
    desearch instagram_hashtag <tag> [--count N] [--cursor C]

Environment:
    DESEARCH_API_KEY - Required API key from desearch.ai
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

DESEARCH_BASE = "https://api.desearch.ai"

# List routes return a JSON array and put the cursor for the next page in this
# response header. The header is absent on the last page.
NEXT_CURSOR_HEADER = "x-desearch-next-cursor"

COMMANDS = [
    "instagram_search",
    "instagram_media",
    "instagram_profile",
    "instagram_profile_posts",
    "instagram_comments",
    "instagram_hashtag",
]

# instagram.com/p/<code>/, /reel/<code>/, /tv/<code>/, optionally after a username.
POST_URL_SHORTCODE = re.compile(
    r"instagram\.com/(?:[^/?#]+/)?(?:p|reel|reels|tv)/([^/?#]+)"
)


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


def username(value: str) -> str:
    return required_text(value.strip().lstrip("@"))


def hashtag(value: str) -> str:
    return required_text(value.strip().lstrip("#"))


def shortcode(value: str) -> str:
    """The post shortcode, also when given a post URL."""
    text = required_text(value)
    match = POST_URL_SHORTCODE.search(text)
    return match.group(1) if match else text


def path_segment(value: str) -> str:
    # Encode every reserved character, "/" included, so an ID or URL is one segment.
    return quote(value, safe="")


def page_params(args) -> dict:
    return {"count": args.count, "cursor": args.cursor or None}


# Commands


def cmd_instagram_search(args):
    body = {"query": args.query}
    if args.count is not None:
        body["count"] = args.count
    return api_request("POST", "/desearch/instagram/search", body=body)


def cmd_instagram_media(args):
    return api_request("GET", f"/desearch/instagram/media/{path_segment(args.id)}")


def cmd_instagram_profile(args):
    return api_request(
        "GET", f"/desearch/instagram/profile/{path_segment(args.username)}"
    )


def cmd_instagram_profile_posts(args):
    return api_request(
        "GET",
        f"/desearch/instagram/profile/{path_segment(args.username)}/posts",
        params=page_params(args),
        paged=True,
    )


def cmd_instagram_comments(args):
    return api_request(
        "GET",
        f"/desearch/instagram/comments/{path_segment(args.shortcode)}",
        params=page_params(args),
        paged=True,
    )


def cmd_instagram_hashtag(args):
    return api_request(
        "GET",
        f"/desearch/instagram/hashtag/{path_segment(args.tag)}",
        params=page_params(args),
        paged=True,
    )


COMMAND_HANDLERS = {
    "instagram_search": cmd_instagram_search,
    "instagram_media": cmd_instagram_media,
    "instagram_profile": cmd_instagram_profile,
    "instagram_profile_posts": cmd_instagram_profile_posts,
    "instagram_comments": cmd_instagram_comments,
    "instagram_hashtag": cmd_instagram_hashtag,
}


def add_count(parser: argparse.ArgumentParser, default_count: int) -> None:
    parser.add_argument(
        "--count",
        "-n",
        type=bounded_int(1, 100),
        help=f"Maximum results (1-100, API default {default_count}). "
        "The page can be smaller.",
    )


def add_page_options(parser: argparse.ArgumentParser, default_count: int) -> None:
    add_count(parser, default_count)
    parser.add_argument(
        "--cursor",
        help="next_cursor from the previous page, sent back unchanged",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Desearch Instagram Search CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    commands = parser.add_subparsers(dest="command", metavar="command", required=True)

    search = commands.add_parser(
        "instagram_search", help="Search public Instagram profiles"
    )
    search.add_argument(
        "query", type=required_text, help="Keyword, username, or phrase"
    )
    # Instagram search returns one page; the API rejects any cursor.
    add_count(search, 10)

    media = commands.add_parser("instagram_media", help="One public Instagram post")
    media.add_argument(
        "id", type=required_text, help="Post shortcode, media ID, or public post URL"
    )

    profile = commands.add_parser("instagram_profile", help="An Instagram profile")
    profile.add_argument(
        "username", type=username, help="Instagram username (@ optional)"
    )

    profile_posts = commands.add_parser(
        "instagram_profile_posts", help="Recent posts from an Instagram profile"
    )
    profile_posts.add_argument(
        "username", type=username, help="Instagram username (@ optional)"
    )
    add_page_options(profile_posts, 20)

    comments = commands.add_parser(
        "instagram_comments", help="Public comments on an Instagram post"
    )
    comments.add_argument(
        "shortcode",
        type=shortcode,
        help="Post shortcode (e.g. DeuOR-CjKE9) or post URL",
    )
    add_page_options(comments, 20)

    tag = commands.add_parser("instagram_hashtag", help="Instagram posts for a hashtag")
    tag.add_argument("tag", type=hashtag, help="Hashtag (# optional)")
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

#!/usr/bin/env python3
"""Desearch Threads Search CLI - Public Threads posts, accounts, profiles, and replies.

Threads commands do not page: a search returns one batch of posts and a
profile's posts are the latest 20-30 that Threads shows publicly. Lists are
printed as plain JSON arrays.

Usage:
    desearch threads_search "<query>" [--start-date YYYY-MM-DD] [--end-date YYYY-MM-DD]
    desearch threads_search_users "<query>"
    desearch threads_profile <username>
    desearch threads_profile_posts <username>
    desearch threads_post <post_url_or_shortcode>

Environment:
    DESEARCH_API_KEY - Required API key from desearch.ai
    DESEARCH_BASE_URL - Optional API base URL (default https://api.desearch.ai)
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import date
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

DESEARCH_BASE = "https://api.desearch.ai"

COMMANDS = [
    "threads_search",
    "threads_search_users",
    "threads_profile",
    "threads_profile_posts",
    "threads_post",
]


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
) -> dict | list | str:
    """Call the API and return the parsed body."""
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
                return json.loads(raw)
            except json.JSONDecodeError:
                return raw
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


def user_query(value: str) -> str:
    text = required_text(value)
    if len(text) > 100:
        raise argparse.ArgumentTypeError("must be at most 100 characters")
    return text


def username(value: str) -> str:
    return required_text(value.strip().lstrip("@"))


def iso_date(value: str) -> str:
    text = value.strip()
    try:
        date.fromisoformat(text)
    except ValueError:
        raise argparse.ArgumentTypeError(
            "must be a date in YYYY-MM-DD format"
        ) from None
    if len(text) != 10:
        raise argparse.ArgumentTypeError("must be a date in YYYY-MM-DD format")
    return text


# Commands


def cmd_threads_search(args):
    body = {"query": args.query}
    if args.start_date:
        body["start_date"] = args.start_date
    if args.end_date:
        body["end_date"] = args.end_date
    return api_request("POST", "/desearch/threads/search", body=body)


def cmd_threads_search_users(args):
    return api_request(
        "POST", "/desearch/threads/search/users", body={"query": args.query}
    )


def cmd_threads_profile(args):
    return api_request(
        "GET", f"/desearch/threads/profile/{path_segment(args.username)}"
    )


def cmd_threads_profile_posts(args):
    return api_request(
        "GET", f"/desearch/threads/profile/{path_segment(args.username)}/posts"
    )


def cmd_threads_post(args):
    return api_request("GET", f"/desearch/threads/post/{path_segment(args.id)}")


COMMAND_HANDLERS = {
    "threads_search": cmd_threads_search,
    "threads_search_users": cmd_threads_search_users,
    "threads_profile": cmd_threads_profile,
    "threads_profile_posts": cmd_threads_profile_posts,
    "threads_post": cmd_threads_post,
}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Desearch Threads Search CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    commands = parser.add_subparsers(dest="command", metavar="command", required=True)

    search = commands.add_parser("threads_search", help="Search public Threads posts")
    search.add_argument("query", type=query_text, help="Keyword or phrase")
    search.add_argument(
        "--start-date",
        dest="start_date",
        type=iso_date,
        help="Only posts on or after this date (YYYY-MM-DD)",
    )
    search.add_argument(
        "--end-date",
        dest="end_date",
        type=iso_date,
        help="Only posts on or before this date (YYYY-MM-DD)",
    )

    users = commands.add_parser(
        "threads_search_users", help="Search public Threads accounts"
    )
    users.add_argument("query", type=user_query, help="Username or name")

    profile = commands.add_parser("threads_profile", help="A Threads profile")
    profile.add_argument(
        "username", type=username, help="Threads username (@ optional)"
    )

    profile_posts = commands.add_parser(
        "threads_profile_posts", help="Latest public posts of a Threads account"
    )
    profile_posts.add_argument(
        "username", type=username, help="Threads username (@ optional)"
    )

    post = commands.add_parser("threads_post", help="One Threads post with its replies")
    post.add_argument("id", type=required_text, help="Post URL or shortcode")

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

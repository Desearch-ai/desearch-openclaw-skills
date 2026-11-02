#!/usr/bin/env python3
"""Desearch Search API CLI - Ranked web pages, each with the passage that best matches the query.

Usage:
    desearch search "<query>" [options]

Environment:
    DESEARCH_API_KEY - Required API key from desearch.ai
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
import sys
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

DESEARCH_BASE = "https://api.desearch.ai"

MODES = ["fast", "balanced"]
COUNTS = [10, 15, 20]


def get_api_key() -> str:
    key = os.environ.get("DESEARCH_API_KEY")
    if not key:
        print("Error: DESEARCH_API_KEY environment variable not set", file=sys.stderr)
        print("Get your key at https://console.desearch.ai", file=sys.stderr)
        sys.exit(1)
    return key


def api_request(
    method: str, path: str, params: dict = None, body: dict = None
) -> dict | str:
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


def search_query(value: str) -> str:
    text = value.strip()
    if not 1 <= len(text) <= 2000:
        raise argparse.ArgumentTypeError("query must be 1 to 2000 characters")
    return text


def iso_date(value: str) -> str:
    try:
        return datetime.date.fromisoformat(value).isoformat()
    except ValueError as error:
        raise argparse.ArgumentTypeError("date must be YYYY-MM-DD") from error


def build_search_body(args) -> dict:
    """Request body for POST /search. Options left unset use the API defaults."""
    body = {"query": args.query}
    if args.mode is not None:
        body["mode"] = args.mode
    if args.count is not None:
        body["count"] = args.count
    if args.start_date is not None:
        body["start_date"] = args.start_date
    if args.end_date is not None:
        body["end_date"] = args.end_date
    if args.no_highlights:
        body["highlights"] = False
    if args.page_text:
        body["page_text"] = True
    return body


def cmd_search(args):
    return api_request("POST", "/search", body=build_search_body(args))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Desearch Search API CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("command", choices=["search"], help="Command to execute")
    parser.add_argument("query", type=search_query, help="Search query")
    parser.add_argument(
        "--mode",
        choices=MODES,
        help="fast returns results sooner; balanced (API default) favors relevance",
    )
    parser.add_argument(
        "--count",
        "-n",
        type=int,
        choices=COUNTS,
        help="Number of results: 10 (API default), 15, or 20",
    )
    parser.add_argument(
        "--start-date",
        type=iso_date,
        help="Only pages published on or after this date (YYYY-MM-DD)",
    )
    parser.add_argument(
        "--end-date",
        type=iso_date,
        help="Only pages published on or before this date (YYYY-MM-DD)",
    )
    parser.add_argument(
        "--no-highlights",
        action="store_true",
        help="Leave out the passage that best matches the query",
    )
    parser.add_argument(
        "--page-text",
        action="store_true",
        help="Include the full text of each page",
    )
    return parser


def main(argv: list[str] | None = None):
    parser = build_parser()
    args = parser.parse_args(argv)
    results = cmd_search(args)

    if isinstance(results, str):
        print(results)
    else:
        print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()

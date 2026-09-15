#!/usr/bin/env python3
"""Desearch Extract CLI - Extract content from a public webpage URL.

Usage:
    desearch extract "<url>" [options]

Environment:
    DESEARCH_API_KEY - Required API key from desearch.ai
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

DESEARCH_BASE = "https://api.desearch.ai"


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


def wait_milliseconds(value: str) -> int:
    wait = int(value)
    if not 0 <= wait <= 30000:
        raise argparse.ArgumentTypeError("wait must be between 0 and 30000")
    return wait


def cmd_extract(args):
    params = {
        "url": args.url,
        "format": args.output_format,
        "js": "true" if args.js else "false",
        "wait": args.wait,
    }
    return api_request("GET", "/web/extract", params=params)


def main():
    parser = argparse.ArgumentParser(
        description="Desearch Extract CLI - Extract content from any webpage",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("command", choices=["extract"], help="Command to execute")
    parser.add_argument("url", help="Public URL to extract")
    parser.add_argument(
        "--format",
        dest="output_format",
        choices=["text", "html"],
        default="text",
        help="Output format (default: text)",
    )
    parser.add_argument(
        "--js",
        action="store_true",
        help="Render JavaScript before extracting content",
    )
    parser.add_argument(
        "--wait",
        type=wait_milliseconds,
        help="Extra post-load wait in milliseconds (0-30000)",
    )

    args = parser.parse_args()
    results = cmd_extract(args)

    if isinstance(results, str):
        print(results)
    else:
        print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Desearch People Search CLI - Find people and creators on X, YouTube, LinkedIn, and TikTok.

Starting a search is billed and runs in the background (usually 1 to 5 minutes).
Every other command is free.

Usage:
    desearch people_search <platform> "<query>" [options]    Start a billed search
    desearch people_task <task_id>                           Read status, progress, and cost
    desearch people_wait <task_id> [--interval S] [--timeout S]
    desearch people_results <task_id> [--cursor C] [--limit N] [--all]
    desearch people_export <task_id> [--format csv|jsonl] [--output FILE] [filters]
    desearch people_pause | people_resume | people_cancel <task_id>
    desearch people_tasks [--platform P] [--status S1,S2] [--limit N] [--cursor C]
    desearch people_profiles <platform> [--query Q] [--sort S] [filters]
    desearch people_profiles_export <platform> [--format csv|jsonl] [--output FILE] [filters]

Platforms: x, youtube, linkedin, tiktok

Environment:
    DESEARCH_API_KEY - Required API key from desearch.ai
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import uuid
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

DESEARCH_BASE = "https://api.desearch.ai"

PLATFORMS = ["x", "youtube", "linkedin", "tiktok"]

COMMANDS = [
    "people_search",
    "people_task",
    "people_wait",
    "people_results",
    "people_export",
    "people_pause",
    "people_resume",
    "people_cancel",
    "people_tasks",
    "people_profiles",
    "people_profiles_export",
]

# Filters each platform accepts inside the search request `filters` object.
# The API rejects any other key with HTTP 422, so the CLI checks them before
# the billed call.
PLATFORM_FILTERS = {
    "x": (
        "min_followers",
        "max_followers",
        "verified_only",
        "countries",
        "keywords",
        "exclude_keywords",
    ),
    "youtube": (
        "min_subscribers",
        "max_subscribers",
        "countries",
        "require_contact",
        "keywords",
        "exclude_keywords",
    ),
    "linkedin": (
        "min_followers",
        "max_followers",
        "countries",
        "keywords",
        "exclude_keywords",
    ),
    "tiktok": (
        "min_followers",
        "max_followers",
        "require_contact",
        "keywords",
        "exclude_keywords",
    ),
}

SEARCH_FILTER_NAMES = (
    "min_followers",
    "max_followers",
    "min_subscribers",
    "max_subscribers",
    "verified_only",
    "require_contact",
    "countries",
    "keywords",
    "exclude_keywords",
)

TASK_STATUSES = [
    "queued",
    "running",
    "pausing",
    "paused",
    "cancelling",
    "completed",
    "partial",
    "failed",
    "cancelled",
    "expired",
]

# A task in one of these statuses does not change again.
ENDED_STATUSES = {"completed", "partial", "failed", "cancelled", "expired"}

PROFILE_SORTS = ["score", "recent", "audience"]

HAS_CHANNELS = ["email", "website", "x", "linkedin", "instagram", "youtube", "tiktok"]

# Only X and TikTok people carry a verified flag; other platforms return HTTP 400.
VERIFIED_PLATFORMS = {"x", "tiktok"}

CONTROL_ACTIONS = {
    "people_pause": "pause",
    "people_resume": "resume",
    "people_cancel": "cancel",
}


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
    headers: dict = None,
    parse_json: bool = True,
) -> dict | list | str:
    api_key = get_api_key()
    url = f"{DESEARCH_BASE}{path}"

    if method == "GET" and params:
        filtered = {key: value for key, value in params.items() if value is not None}
        if filtered:
            url = f"{url}?{urlencode(filtered, doseq=True)}"

    request_headers = {
        "Authorization": api_key,
        "Content-Type": "application/json",
        "User-Agent": "Desearch-OpenClaw/1.0",
    }
    if headers:
        request_headers.update(headers)
    data = json.dumps(body).encode() if method == "POST" and body else None

    try:
        request = Request(url, data=data, headers=request_headers, method=method)
        with urlopen(request, timeout=60) as response:
            raw = response.read().decode()
            if not parse_json:
                return raw
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


def bounded_int(minimum: int, maximum: int | None = None):
    def parse(value: str) -> int:
        number = int(value)
        if maximum is None and number < minimum:
            raise argparse.ArgumentTypeError(f"must be {minimum} or more")
        if maximum is not None and not minimum <= number <= maximum:
            raise argparse.ArgumentTypeError(
                f"must be between {minimum} and {maximum}"
            )
        return number

    return parse


def search_query(value: str) -> str:
    text = value.strip()
    if not 3 <= len(text) <= 1000:
        raise argparse.ArgumentTypeError("query must be 3 to 1000 characters")
    return text


def comma_list(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def choice_list(choices: list[str]):
    def parse(value: str) -> list[str]:
        items = comma_list(value)
        unknown = [item for item in items if item not in choices]
        if unknown:
            raise argparse.ArgumentTypeError(
                f"unknown value(s) {', '.join(unknown)}; use {', '.join(choices)}"
            )
        return items

    return parse


def task_id_type(value: str) -> str:
    try:
        return str(uuid.UUID(value))
    except ValueError as error:
        raise argparse.ArgumentTypeError(
            "task_id must be the UUID returned by people_search"
        ) from error


def task_path(task_id: str, suffix: str = "") -> str:
    return f"/desearch/people/tasks/{quote(task_id, safe='')}{suffix}"


# Request builders


def build_search_body(args) -> dict:
    """Request body for POST /desearch/people/search/{platform}.

    Raises ValueError when a filter does not apply to the chosen platform, so a
    bad request never reaches the billed route.
    """
    allowed = PLATFORM_FILTERS[args.platform]
    filters = {}
    for name in SEARCH_FILTER_NAMES:
        value = getattr(args, name, None)
        if value is None or value is False or value == []:
            continue
        if name not in allowed:
            flags = ", ".join(f"--{item.replace('_', '-')}" for item in allowed)
            raise ValueError(
                f"--{name.replace('_', '-')} is not a {args.platform} filter. "
                f"{args.platform} filters: {flags}"
            )
        filters[name] = value

    body = {"query": args.query}
    if getattr(args, "count", None) is not None:
        body["count"] = args.count
    if getattr(args, "min_score", None) is not None:
        body["min_score"] = args.min_score
    if getattr(args, "exclude", None):
        body["exclude"] = args.exclude
    if filters:
        body["filters"] = filters
    return body


def library_filters(args) -> dict:
    """Filters shared by GET /desearch/people/profiles and the task export."""
    params = {}
    if getattr(args, "has", None):
        params["has"] = ",".join(args.has)
    for name in ("min_audience", "max_audience", "min_score", "location"):
        value = getattr(args, name, None)
        if value is not None:
            params[name] = value
    if getattr(args, "verified", False):
        params["verified"] = "true"
    return params


# Commands


def cmd_people_search(args):
    try:
        body = build_search_body(args)
    except ValueError as error:
        return {"error": str(error)}

    idempotency_key = args.idempotency_key or str(uuid.uuid4())
    print(
        f"Starting a billed {args.platform} People Search with Idempotency-Key "
        f"{idempotency_key}. To retry this exact search without a second charge, "
        f"pass --idempotency-key {idempotency_key}",
        file=sys.stderr,
    )
    return api_request(
        "POST",
        f"/desearch/people/search/{args.platform}",
        body=body,
        headers={"Idempotency-Key": idempotency_key},
    )


def cmd_people_task(args):
    return api_request("GET", task_path(args.task_id))


def cmd_people_wait(args):
    deadline = time.monotonic() + args.timeout
    while True:
        task = api_request("GET", task_path(args.task_id))
        if not isinstance(task, dict) or "status" not in task:
            return task
        status = task["status"]
        if status in ENDED_STATUSES or status == "paused":
            return task
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return {
                "error": (
                    f"Still {status} after {args.timeout} seconds. The search keeps "
                    "running; call people_wait or people_task again later."
                ),
                "task": task,
            }
        print(
            f"status={status} stage={task.get('stage')} "
            f"found={task.get('result_count')}/{task.get('count')}",
            file=sys.stderr,
        )
        time.sleep(min(args.interval, remaining))


def cmd_people_results(args):
    params = {"cursor": args.cursor, "limit": args.limit}
    page = api_request("GET", task_path(args.task_id, "/results"), params=params)
    if not args.all:
        return page

    results = []
    while isinstance(page, dict) and isinstance(page.get("results"), list):
        results.extend(page["results"])
        if not page.get("has_more") or not page.get("next_cursor"):
            break
        params = {"cursor": page["next_cursor"], "limit": args.limit}
        page = api_request("GET", task_path(args.task_id, "/results"), params=params)

    if not isinstance(page, dict) or "results" not in page:
        return page
    return {**page, "results": results}


def save_export(result, args):
    """Return an export body, or write it to --output; API errors pass through."""
    if not isinstance(result, str):
        return result

    # A JSON body is an API error (for example 410 after results expire).
    try:
        parsed = json.loads(result)
    except json.JSONDecodeError:
        parsed = None
    if isinstance(parsed, dict) and ("detail" in parsed or "error" in parsed):
        return parsed

    if args.output:
        path = Path(args.output)
        path.write_text(result, encoding="utf-8")
        return {
            "saved": str(path),
            "format": args.export_format,
            "bytes": len(result.encode("utf-8")),
        }
    return result


def cmd_people_export(args):
    params = {"format": args.export_format, **library_filters(args)}
    result = api_request(
        "GET",
        task_path(args.task_id, "/export"),
        params=params,
        parse_json=False,
    )
    return save_export(result, args)


def cmd_people_control(args):
    action = CONTROL_ACTIONS[args.command]
    return api_request("POST", task_path(args.task_id, f"/{action}"))


def cmd_people_tasks(args):
    params = {
        "platform": args.platform,
        "status": ",".join(args.status) if args.status else None,
        "limit": args.limit,
        "cursor": args.cursor,
    }
    return api_request("GET", "/desearch/people/tasks", params=params)


def cmd_people_profiles(args):
    if getattr(args, "verified", False) and args.platform not in VERIFIED_PLATFORMS:
        return {"error": "--verified works only on x and tiktok"}
    params = {
        "platform": args.platform,
        "q": args.query,
        "sort": args.sort,
        "limit": args.limit,
        "cursor": args.cursor,
        **library_filters(args),
    }
    return api_request("GET", "/desearch/people/profiles", params=params)


def cmd_people_profiles_export(args):
    if getattr(args, "verified", False) and args.platform not in VERIFIED_PLATFORMS:
        return {"error": "--verified works only on x and tiktok"}
    params = {
        "platform": args.platform,
        "format": args.export_format,
        "q": args.query,
        "sort": args.sort,
        **library_filters(args),
    }
    result = api_request(
        "GET",
        "/desearch/people/profiles/export",
        params=params,
        parse_json=False,
    )
    return save_export(result, args)


COMMAND_HANDLERS = {
    "people_search": cmd_people_search,
    "people_task": cmd_people_task,
    "people_wait": cmd_people_wait,
    "people_results": cmd_people_results,
    "people_export": cmd_people_export,
    "people_pause": cmd_people_control,
    "people_resume": cmd_people_control,
    "people_cancel": cmd_people_control,
    "people_tasks": cmd_people_tasks,
    "people_profiles": cmd_people_profiles,
    "people_profiles_export": cmd_people_profiles_export,
}


def add_library_filters(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--has",
        type=choice_list(HAS_CHANNELS),
        help="Comma-separated channels every person must have: "
        + ", ".join(HAS_CHANNELS),
    )
    parser.add_argument(
        "--min-audience",
        type=bounded_int(0),
        help="Minimum followers (subscribers on YouTube)",
    )
    parser.add_argument(
        "--max-audience",
        type=bounded_int(0),
        help="Maximum followers (subscribers on YouTube)",
    )
    parser.add_argument(
        "--min-score", type=bounded_int(0, 100), help="Minimum fit score (0-100)"
    )
    parser.add_argument("--location", help="Text in the location, e.g. 'united states'")
    parser.add_argument(
        "--verified",
        action="store_true",
        help="Only verified accounts (X and TikTok only)",
    )


def add_export_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--format",
        dest="export_format",
        choices=["csv", "jsonl"],
        default="csv",
        help="Export format (default: csv)",
    )
    parser.add_argument("--output", "-o", help="Write the export to this file")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Desearch People Search CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    commands = parser.add_subparsers(dest="command", metavar="command", required=True)

    search = commands.add_parser(
        "people_search", help="Start a billed People Search (returns a task_id)"
    )
    search.add_argument("platform", choices=PLATFORMS)
    search.add_argument(
        "query", type=search_query, help="Who you are looking for, in plain language"
    )
    search.add_argument(
        "--count",
        "-n",
        type=bounded_int(5, 200),
        help="People to find (5-200, API default 25). This many are reserved.",
    )
    search.add_argument(
        "--min-score", type=bounded_int(0, 100), help="Minimum fit score (0-100)"
    )
    search.add_argument(
        "--exclude", type=comma_list, help="Comma-separated handles to leave out"
    )
    search.add_argument(
        "--idempotency-key",
        help="Reuse the key from a previous attempt so a retry is not charged again",
    )
    search.add_argument(
        "--min-followers", type=bounded_int(0), help="x, linkedin, tiktok"
    )
    search.add_argument(
        "--max-followers", type=bounded_int(0), help="x, linkedin, tiktok"
    )
    search.add_argument("--min-subscribers", type=bounded_int(0), help="youtube")
    search.add_argument("--max-subscribers", type=bounded_int(0), help="youtube")
    search.add_argument(
        "--verified-only",
        action="store_true",
        help="Only verified or X Premium accounts (x)",
    )
    search.add_argument(
        "--require-contact",
        action="store_true",
        help="Only creators with a public email or contact link (youtube, tiktok)",
    )
    search.add_argument(
        "--countries",
        type=comma_list,
        help="Comma-separated countries to prefer, e.g. US,GB (x, youtube, linkedin)",
    )
    search.add_argument(
        "--keywords",
        type=comma_list,
        help="Comma-separated words that should appear in posts, videos, or bios",
    )
    search.add_argument(
        "--exclude-keywords",
        type=comma_list,
        help="Comma-separated words; leave out people who mention them",
    )

    task = commands.add_parser("people_task", help="Status, progress, and cost of a task")
    task.add_argument("task_id", type=task_id_type)

    wait = commands.add_parser(
        "people_wait", help="Poll a task until it ends or is paused"
    )
    wait.add_argument("task_id", type=task_id_type)
    wait.add_argument(
        "--interval",
        type=bounded_int(2, 300),
        default=10,
        help="Seconds between polls (default: 10)",
    )
    wait.add_argument(
        "--timeout",
        type=bounded_int(10, 3600),
        default=600,
        help="Seconds to wait before giving up (default: 600)",
    )

    results = commands.add_parser(
        "people_results", help="Read the people a task found, one page at a time"
    )
    results.add_argument("task_id", type=task_id_type)
    results.add_argument("--cursor", help="next_cursor from the previous page")
    results.add_argument(
        "--limit",
        "-n",
        type=bounded_int(1, 500),
        help="People per page (1-500, API default 100)",
    )
    results.add_argument(
        "--all",
        action="store_true",
        help="Follow next_cursor until every person found so far is returned",
    )

    export = commands.add_parser(
        "people_export", help="Download a task's people as CSV or JSON Lines"
    )
    export.add_argument("task_id", type=task_id_type)
    add_export_options(export)
    add_library_filters(export)

    for name, action in CONTROL_ACTIONS.items():
        control = commands.add_parser(name, help=f"{action.capitalize()} a task")
        control.add_argument("task_id", type=task_id_type)

    tasks = commands.add_parser("people_tasks", help="List your People Search tasks")
    tasks.add_argument("--platform", choices=PLATFORMS)
    tasks.add_argument(
        "--status",
        type=choice_list(TASK_STATUSES),
        help="Comma-separated statuses, e.g. running,paused",
    )
    tasks.add_argument(
        "--limit", "-n", type=bounded_int(1, 100), help="Tasks per page (1-100)"
    )
    tasks.add_argument("--cursor", help="next_cursor from the previous page")

    profiles = commands.add_parser(
        "people_profiles", help="Everyone your searches found on one platform"
    )
    profiles.add_argument("platform", choices=PLATFORMS)
    profiles.add_argument(
        "--query", "-q", help="Text in the name, handle, bio, or location"
    )
    profiles.add_argument(
        "--sort", choices=PROFILE_SORTS, help="score (API default), recent, or audience"
    )
    profiles.add_argument(
        "--limit", "-n", type=bounded_int(1, 200), help="People per page (1-200)"
    )
    profiles.add_argument("--cursor", help="next_cursor from the previous page")
    add_library_filters(profiles)

    profiles_export = commands.add_parser(
        "people_profiles_export",
        help="Download everyone people_profiles lists as CSV or JSON Lines",
    )
    profiles_export.add_argument("platform", choices=PLATFORMS)
    profiles_export.add_argument(
        "--query", "-q", help="Text in the name, handle, bio, or location"
    )
    profiles_export.add_argument(
        "--sort", choices=PROFILE_SORTS, help="score (API default), recent, or audience"
    )
    add_export_options(profiles_export)
    add_library_filters(profiles_export)

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

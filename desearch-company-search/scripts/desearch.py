#!/usr/bin/env python3
"""Desearch Company Search CLI - Find companies and their public contacts and leaders.

Company Search finds companies on the web from a description; Company Enrich reads the
domains you send. Starting either is billed and runs in the background for several
minutes. Every other command is free.

Usage:
    desearch company_search "<query>" [options]                  Start a billed search
    desearch company_enrich [domain ...] [--file FILE] [options]  Start a billed enrichment
    desearch company_task <task_id>                               Read status, progress, and cost
    desearch company_wait <task_id> [--interval S] [--timeout S]
    desearch company_results <task_id> [--cursor C] [--limit N] [--all]
    desearch company_export <task_id> [--format csv|jsonl] [--output FILE]
    desearch company_pause | company_resume | company_cancel <task_id>
    desearch company_tasks [--type search|enrich] [--status S1,S2] [--metadata K=V]

Environment:
    DESEARCH_API_KEY - Required API key from desearch.ai
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import uuid
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode, urlsplit
from urllib.request import Request, urlopen

DESEARCH_BASE = "https://api.desearch.ai"

COMMANDS = [
    "company_search",
    "company_enrich",
    "company_task",
    "company_wait",
    "company_results",
    "company_export",
    "company_pause",
    "company_resume",
    "company_cancel",
    "company_tasks",
]

ROLES = [
    "ceo",
    "founder",
    "cto",
    "cfo",
    "coo",
    "cmo",
    "president",
    "owner",
    "managing_director",
]

REQUIREMENTS = ["email", "phone", "linkedin", "leader", "leader_email"]

TASK_TYPES = ["search", "enrich"]

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

CONTROL_ACTIONS = {
    "company_pause": "pause",
    "company_resume": "resume",
    "company_cancel": "cancel",
}

COUNTRIES_MAX = 20
DOMAINS_MAX = 200
METADATA_MAX_KEYS = 10
METADATA_FILTERS_MAX = 3
METADATA_VALUE_MAX = 200
METADATA_KEY_RE = re.compile(r"[a-z0-9_.-]{1,40}")
METADATA_KEY_RULE = "1-40 characters of a-z, 0-9, '_', '.' or '-'"

SCHEME_RE = re.compile(r"^[a-z][a-z0-9+.-]*://", re.IGNORECASE)
DOMAIN_SEPARATORS = re.compile(r"[\s,;]+")


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
    text = " ".join(value.split())
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
        if not items:
            raise argparse.ArgumentTypeError(f"use one or more of {', '.join(choices)}")
        return items

    return parse


def metadata_item(value: str) -> tuple[str, str]:
    """`key=value` for --metadata. Keys follow the API's rule; values are kept as given."""
    key, separator, item = value.partition("=")
    key = key.strip()
    if not separator:
        raise argparse.ArgumentTypeError("use key=value, e.g. campaign=q4")
    if not METADATA_KEY_RE.fullmatch(key):
        raise argparse.ArgumentTypeError(
            f"metadata key {key[:50]!r} is not allowed: keys are {METADATA_KEY_RULE}"
        )
    if len(item) > METADATA_VALUE_MAX:
        raise argparse.ArgumentTypeError(
            f"metadata value of {key!r} is longer than {METADATA_VALUE_MAX} characters"
        )
    return key, item


def task_id_type(value: str) -> str:
    try:
        return str(uuid.UUID(value))
    except ValueError as error:
        raise argparse.ArgumentTypeError(
            "task_id must be the UUID returned by company_search or company_enrich"
        ) from error


def task_path(task_id: str, suffix: str = "") -> str:
    return f"/desearch/companies/tasks/{quote(task_id, safe='')}{suffix}"


# Request builders


def metadata_dict(pairs, maximum: int, noun: str = "labels") -> dict:
    """--metadata key=value pairs as a dict. Raises ValueError for a repeated key or too many."""
    labels = {}
    for key, value in pairs or []:
        if key in labels:
            raise ValueError(f"--metadata {key} is given more than once")
        labels[key] = value
    if len(labels) > maximum:
        raise ValueError(f"At most {maximum} --metadata {noun} (got {len(labels)})")
    return labels


def add_enrichment_options(body: dict, args) -> None:
    """roles, infer_emails, verify_emails: sent only when they differ from the API defaults."""
    if getattr(args, "roles", None):
        body["roles"] = args.roles
    if getattr(args, "no_infer_emails", False):
        body["infer_emails"] = False
    if getattr(args, "no_verify_emails", False):
        body["verify_emails"] = False


def build_search_body(args) -> dict:
    """Request body for POST /desearch/companies/search.

    Raises ValueError for input the API would reject, so a bad request never
    reaches the billed route.
    """
    body = {"query": args.query}
    if getattr(args, "count", None) is not None:
        body["count"] = args.count
    if getattr(args, "min_score", None) is not None:
        body["min_score"] = args.min_score
    if getattr(args, "exclude", None):
        body["exclude"] = args.exclude
    add_enrichment_options(body, args)

    filters = {}
    countries = getattr(args, "countries", None)
    if countries:
        if len(countries) > COUNTRIES_MAX:
            raise ValueError(
                f"--countries takes at most {COUNTRIES_MAX} countries (got {len(countries)})"
            )
        filters["countries"] = countries
    if getattr(args, "require", None):
        filters["require"] = args.require
    if filters:
        body["filters"] = filters

    metadata = metadata_dict(getattr(args, "metadata", None), METADATA_MAX_KEYS)
    if metadata:
        body["metadata"] = metadata
    return body


def domain_key(value: str) -> str:
    """The host a domain or URL names, lowercased and without `www.`, as the API reduces it.

    Used only to drop duplicates before the billed call; the API does the real
    normalization and rejects anything that is not a public domain.
    """
    text = value.strip()
    candidate = text if SCHEME_RE.match(text) else "https://" + text.lstrip("/")
    try:
        host = urlsplit(candidate).hostname or ""
    except ValueError:
        host = ""
    host = host.rstrip(".").lower()
    if host.startswith("www.") and "." in host[len("www."):]:
        host = host[len("www."):]
    return host or text.lower()


def split_domains(text: str) -> list[str]:
    """Domains in a line or argument, separated by commas, semicolons, or whitespace."""
    return [item for item in DOMAIN_SEPARATORS.split(text) if item]


def read_domain_file(path: str) -> list[str]:
    """One domain or URL per line (commas also separate them). Lines starting with # are skipped."""
    try:
        if path == "-":
            text = sys.stdin.read()
        else:
            text = Path(path).read_text(encoding="utf-8")
    except OSError as error:
        raise ValueError(f"Cannot read {path}: {error.strerror or error}") from error
    domains = []
    for line in text.splitlines():
        if line.strip().startswith("#"):
            continue
        domains.extend(split_domains(line))
    return domains


def collect_domains(args) -> list[str]:
    """Domains from the arguments and --file, duplicates dropped, in order.

    Raises ValueError when there are none or more than the API takes in one task.
    """
    values = []
    for item in getattr(args, "domains", None) or []:
        values.extend(split_domains(item))
    if getattr(args, "file", None):
        values.extend(read_domain_file(args.file))

    domains, seen = [], set()
    for value in values:
        key = domain_key(value)
        if key in seen:
            continue
        seen.add(key)
        domains.append(value)

    if not domains:
        raise ValueError(
            "Give at least one domain, as arguments or with --file (one per line)"
        )
    if len(domains) > DOMAINS_MAX:
        raise ValueError(
            f"{len(domains)} domains: Company Enrich takes at most {DOMAINS_MAX} per task. "
            "Split them into several tasks."
        )
    return domains


def build_enrich_body(args) -> dict:
    """Request body for POST /desearch/companies/enrich. Raises ValueError like build_search_body."""
    body = {"domains": collect_domains(args)}
    add_enrichment_options(body, args)
    metadata = metadata_dict(getattr(args, "metadata", None), METADATA_MAX_KEYS)
    if metadata:
        body["metadata"] = metadata
    return body


# Commands


def start_task(path: str, body: dict, idempotency_key: str | None, what: str):
    key = idempotency_key or str(uuid.uuid4())
    print(
        f"Starting a billed {what} with Idempotency-Key {key}. To retry this exact "
        f"task without a second charge, pass --idempotency-key {key}",
        file=sys.stderr,
    )
    return api_request("POST", path, body=body, headers={"Idempotency-Key": key})


def cmd_company_search(args):
    try:
        body = build_search_body(args)
    except ValueError as error:
        return {"error": str(error)}
    return start_task(
        "/desearch/companies/search", body, args.idempotency_key, "Company Search"
    )


def cmd_company_enrich(args):
    try:
        body = build_enrich_body(args)
    except ValueError as error:
        return {"error": str(error)}
    count = len(body["domains"])
    what = f"Company Enrich of {count} domain{'s' if count != 1 else ''}"
    return start_task("/desearch/companies/enrich", body, args.idempotency_key, what)


def cmd_company_task(args):
    return api_request("GET", task_path(args.task_id))


def progress_line(task: dict) -> str:
    line = (
        f"status={task.get('status')} stage={task.get('stage')} "
        f"delivered={task.get('result_count')}/{task.get('count')}"
    )
    progress = task.get("progress")
    enrichment = progress.get("enrichment") if isinstance(progress, dict) else None
    if isinstance(enrichment, dict) and enrichment.get("complete") is not None:
        line += f" fully_enriched={enrichment['complete']}"
    return line


def cmd_company_wait(args):
    deadline = time.monotonic() + args.timeout
    while True:
        task = api_request("GET", task_path(args.task_id))
        if not isinstance(task, dict) or "status" not in task:
            return task
        status = task["status"]
        # A running task in stage `enriching` has published every company but is
        # still filling some in, so keep waiting until it ends.
        if status in ENDED_STATUSES or status == "paused":
            return task
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return {
                "error": (
                    f"Still {status} (stage {task.get('stage')}) after {args.timeout} "
                    "seconds. The task keeps running; call company_wait or "
                    "company_task again later."
                ),
                "task": task,
            }
        print(progress_line(task), file=sys.stderr)
        time.sleep(min(args.interval, remaining))


def cmd_company_results(args):
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


def cmd_company_export(args):
    result = api_request(
        "GET",
        task_path(args.task_id, "/export"),
        params={"format": args.export_format},
        parse_json=False,
    )
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


def cmd_company_control(args):
    action = CONTROL_ACTIONS[args.command]
    return api_request("POST", task_path(args.task_id, f"/{action}"))


def cmd_company_tasks(args):
    try:
        metadata = metadata_dict(
            getattr(args, "metadata", None), METADATA_FILTERS_MAX, "filters"
        )
    except ValueError as error:
        return {"error": str(error)}
    params = {
        "type": args.task_type,
        "status": ",".join(args.status) if args.status else None,
        "limit": args.limit,
        "cursor": args.cursor,
        **{f"metadata.{key}": value for key, value in metadata.items()},
    }
    return api_request("GET", "/desearch/companies/tasks", params=params)


COMMAND_HANDLERS = {
    "company_search": cmd_company_search,
    "company_enrich": cmd_company_enrich,
    "company_task": cmd_company_task,
    "company_wait": cmd_company_wait,
    "company_results": cmd_company_results,
    "company_export": cmd_company_export,
    "company_pause": cmd_company_control,
    "company_resume": cmd_company_control,
    "company_cancel": cmd_company_control,
    "company_tasks": cmd_company_tasks,
}


def add_enrichment_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--roles",
        type=choice_list(ROLES),
        help="Comma-separated leaders to look for: "
        + ", ".join(ROLES)
        + " (API default: ceo,founder,cto,cfo)",
    )
    parser.add_argument(
        "--no-infer-emails",
        action="store_true",
        help="Do not guess leaders' emails from the company's address pattern",
    )
    parser.add_argument(
        "--no-verify-emails",
        action="store_true",
        help="Skip the email checks (finishes sooner; emails have no verification)",
    )
    parser.add_argument(
        "--metadata",
        type=metadata_item,
        action="append",
        metavar="KEY=VALUE",
        help=f"Your own label for the task, repeatable (up to {METADATA_MAX_KEYS})",
    )
    parser.add_argument(
        "--idempotency-key",
        help="Reuse the key from a previous attempt so a retry is not charged again",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Desearch Company Search CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    commands = parser.add_subparsers(dest="command", metavar="command", required=True)

    search = commands.add_parser(
        "company_search", help="Start a billed Company Search (returns a task_id)"
    )
    search.add_argument(
        "query",
        type=search_query,
        help="The companies you are looking for, in plain language",
    )
    search.add_argument(
        "--count",
        "-n",
        type=bounded_int(5, 200),
        help="Companies to deliver (5-200, API default 25). This many are reserved.",
    )
    search.add_argument(
        "--min-score", type=bounded_int(0, 100), help="Minimum fit score (0-100)"
    )
    search.add_argument(
        "--exclude",
        type=comma_list,
        help="Comma-separated domains or URLs to leave out (up to 1,000)",
    )
    search.add_argument(
        "--countries",
        type=comma_list,
        help=f"Comma-separated ISO codes or country names, e.g. DE,AT (up to {COUNTRIES_MAX})",
    )
    search.add_argument(
        "--require",
        type=choice_list(REQUIREMENTS),
        help="Comma-separated; only deliver companies that have all of: "
        + ", ".join(REQUIREMENTS),
    )
    add_enrichment_arguments(search)

    enrich = commands.add_parser(
        "company_enrich", help="Start a billed Company Enrich of your domains"
    )
    enrich.add_argument(
        "domains",
        nargs="*",
        help="Domains or URLs, e.g. acme.com https://www.beta.io/about",
    )
    enrich.add_argument(
        "--file",
        "-f",
        help="File with one domain or URL per line (# starts a comment line; - reads stdin)",
    )
    add_enrichment_arguments(enrich)

    task = commands.add_parser("company_task", help="Status, progress, and cost of a task")
    task.add_argument("task_id", type=task_id_type)

    wait = commands.add_parser(
        "company_wait", help="Poll a task until it ends or is paused"
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
        default=1200,
        help="Seconds to wait before giving up (default: 1200)",
    )

    results = commands.add_parser(
        "company_results", help="Read the companies a task delivered, one page at a time"
    )
    results.add_argument("task_id", type=task_id_type)
    results.add_argument("--cursor", help="next_cursor from the previous page")
    results.add_argument(
        "--limit",
        "-n",
        type=bounded_int(1, 500),
        help="Companies per page (1-500, API default 100)",
    )
    results.add_argument(
        "--all",
        action="store_true",
        help="Follow next_cursor until every company delivered so far is returned",
    )

    export = commands.add_parser(
        "company_export", help="Download a task's companies as CSV or JSON Lines"
    )
    export.add_argument("task_id", type=task_id_type)
    export.add_argument(
        "--format",
        dest="export_format",
        choices=["csv", "jsonl"],
        default="csv",
        help="Export format (default: csv)",
    )
    export.add_argument("--output", "-o", help="Write the export to this file")

    for name, action in CONTROL_ACTIONS.items():
        control = commands.add_parser(name, help=f"{action.capitalize()} a task")
        control.add_argument("task_id", type=task_id_type)

    tasks = commands.add_parser(
        "company_tasks", help="List your Company Search and Company Enrich tasks"
    )
    tasks.add_argument(
        "--type", dest="task_type", choices=TASK_TYPES, help="search or enrich"
    )
    tasks.add_argument(
        "--status",
        type=choice_list(TASK_STATUSES),
        help="Comma-separated statuses, e.g. running,paused",
    )
    tasks.add_argument(
        "--limit", "-n", type=bounded_int(1, 100), help="Tasks per page (1-100)"
    )
    tasks.add_argument("--cursor", help="next_cursor from the previous page")
    tasks.add_argument(
        "--metadata",
        type=metadata_item,
        action="append",
        metavar="KEY=VALUE",
        help=f"Only tasks with this metadata label, repeatable (up to {METADATA_FILTERS_MAX})",
    )

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

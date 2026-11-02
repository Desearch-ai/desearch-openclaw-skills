#!/usr/bin/env python3
"""Live smoke test for the YouTube, Reddit, and Threads skills.

It runs each skill's CLI against the real API, so it spends a small amount of
balance: every command runs once (about 23 requests at $2.07 per 1,000, about
$0.05 in total), and each list command that returns a next_cursor is run once
more with it. A failed call is retried once, because the upstream provider
occasionally returns a 503 or an empty second page; a call that passes only on
the retry is reported with the first error.

The key is read from the environment variable named by --key-env (default
DESEARCH_API_KEY) or, when unset, from ~/.config/desearch/e2e.env. It is passed
to the CLI as DESEARCH_API_KEY and is never printed.

Usage:
    DESEARCH_API_KEY='your-key-here' python3 scripts/e2e-youtube-reddit-threads.py
    python3 scripts/e2e-youtube-reddit-threads.py --base-url https://api-dev.desearch.ai --key-env DESEARCH_DEV_API_KEY

Prints one line per call, `PASS name` or `FAIL name: error`, and exits 1 when
any call failed (2 when the key is not set).
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
ENV_FILE = Path.home() / ".config" / "desearch" / "e2e.env"

TIMEOUT_SECONDS = 120

VIDEO_ID = "dQw4w9WgXcQ"
CHANNEL = "@MrBeast"
SUBREDDIT = "AskReddit"
REDDIT_POST_ID = "1q6pxwn"
THREADS_USER = "zuck"
THREADS_POST_CODE = "DK-BydcJHkF"


def read_env_file(name: str) -> str | None:
    if not ENV_FILE.exists():
        return None
    for line in ENV_FILE.read_text().splitlines():
        key, _, value = line.strip().partition("=")
        if key == name and value:
            return value.strip().strip("'\"")
    return None


class Smoke:
    def __init__(self, env: dict):
        self.env = env
        self.failures = 0
        self.calls = 0

    def run_cli(self, skill: str, argv: list[str]):
        """Run one skill command. Return (parsed output, error message or None)."""
        script = REPO_ROOT / skill / "scripts" / "desearch.py"
        self.calls += 1
        try:
            process = subprocess.run(
                [sys.executable, str(script), *argv],
                capture_output=True,
                text=True,
                timeout=TIMEOUT_SECONDS,
                check=False,
                env=self.env,
            )
        except subprocess.TimeoutExpired:
            return None, f"no response after {TIMEOUT_SECONDS} seconds"
        if process.returncode != 0:
            detail = (process.stderr or process.stdout).strip().splitlines()
            return None, f"exit {process.returncode}: {detail[-1] if detail else ''}"
        try:
            return json.loads(process.stdout), None
        except json.JSONDecodeError:
            return process.stdout, None

    def call(self, name: str, skill: str, argv: list[str], check):
        data, error = self.run_cli(skill, argv)
        error = error or problem(data, check)
        if error:
            first_error = error
            data, error = self.run_cli(skill, argv)
            error = error or problem(data, check)
            if error:
                self.failures += 1
                print(f"FAIL {name}: {error} (first try: {first_error})", flush=True)
                return None
            print(f"PASS {name} (on retry; first try: {first_error})", flush=True)
            return data
        print(f"PASS {name}{describe(data)}", flush=True)
        return data

    def page(self, name: str, skill: str, argv: list[str]):
        """A list call, then one more page when a cursor comes back."""
        data = self.call(name, skill, argv, "page")
        cursor = data.get("next_cursor") if data else None
        if cursor:
            self.call(f"{name} next page", skill, [*argv, "--cursor", cursor], "page")
        return data


def describe(data) -> str:
    if isinstance(data, dict) and isinstance(data.get("results"), list):
        more = "yes" if data.get("next_cursor") else "no"
        return f" ({len(data['results'])} items, next_cursor={more})"
    if isinstance(data, list):
        return f" ({len(data)} items)"
    return ""


def problem(data, check) -> str | None:
    """Why the output is not what a working command prints, or None."""
    if isinstance(data, dict) and ("error" in data or "detail" in data):
        return json.dumps(data)[:300]
    if check == "page":
        if not isinstance(data, dict) or not isinstance(data.get("results"), list):
            return f"expected {{results, next_cursor}}, got {str(data)[:200]}"
        if "next_cursor" not in data:
            return "next_cursor missing from the output"
    elif check == "list":
        if not isinstance(data, list):
            return f"expected a list, got {str(data)[:200]}"
    elif isinstance(check, dict):
        if not isinstance(data, dict):
            return f"expected an object, got {str(data)[:200]}"
        for key, expected in check.items():
            value = data.get(key)
            if expected is list:
                if not isinstance(value, list) or not value:
                    return f"expected a non-empty `{key}` list, got {str(value)[:200]}"
            elif expected is str:
                if not isinstance(value, str) or not value:
                    return f"expected `{key}` in the output, got {str(data)[:200]}"
            elif value != expected:
                return f"expected `{key}` == {expected!r}, got {value!r}"
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--base-url", default="https://api.desearch.ai")
    parser.add_argument("--key-env", default="DESEARCH_API_KEY")
    args = parser.parse_args()

    key = os.environ.get(args.key_env) or read_env_file(args.key_env)
    if not key:
        print(f"{args.key_env} is not set", file=sys.stderr)
        return 2

    env = {**os.environ, "DESEARCH_API_KEY": key, "DESEARCH_BASE_URL": args.base_url}
    smoke = Smoke(env)
    print(f"Base URL: {args.base_url}", flush=True)

    # YouTube
    youtube = "desearch-youtube-search"
    smoke.page(
        "youtube_search",
        youtube,
        ["youtube_search", "bittensor", "--type", "videos"],
    )
    smoke.call("youtube_video", youtube, ["youtube_video", VIDEO_ID], {"id": VIDEO_ID})
    smoke.call(
        "youtube_video (URL)",
        youtube,
        ["youtube_video", f"https://youtu.be/{VIDEO_ID}"],
        {"id": VIDEO_ID},
    )
    smoke.call(
        "youtube_transcript",
        youtube,
        ["youtube_transcript", VIDEO_ID, "--language", "en"],
        {"text": str, "segments": list},
    )
    smoke.page("youtube_comments", youtube, ["youtube_comments", VIDEO_ID])
    smoke.call(
        "youtube_channel", youtube, ["youtube_channel", CHANNEL], {"handle": "MrBeast"}
    )
    smoke.page("youtube_channel_videos", youtube, ["youtube_channel_videos", CHANNEL])

    # Reddit
    reddit = "desearch-reddit-search"
    smoke.page("reddit_search", reddit, ["reddit_search", "bittensor"])
    smoke.call(
        "reddit_subreddit",
        reddit,
        ["reddit_subreddit", SUBREDDIT],
        {"name": SUBREDDIT},
    )
    smoke.page(
        "reddit_subreddit_posts",
        reddit,
        ["reddit_subreddit_posts", SUBREDDIT, "--sort", "top", "--timeframe", "week"],
    )
    smoke.call(
        "reddit_post",
        reddit,
        ["reddit_post", REDDIT_POST_ID],
        {"id": REDDIT_POST_ID},
    )
    smoke.page("reddit_comments", reddit, ["reddit_comments", REDDIT_POST_ID])

    # Threads (no pagination)
    threads = "desearch-threads-search"
    smoke.call("threads_search", threads, ["threads_search", "bittensor"], "list")
    smoke.call(
        "threads_search_users",
        threads,
        ["threads_search_users", THREADS_USER],
        "list",
    )
    smoke.call(
        "threads_profile",
        threads,
        ["threads_profile", THREADS_USER],
        {"username": THREADS_USER},
    )
    smoke.call(
        "threads_profile_posts",
        threads,
        ["threads_profile_posts", THREADS_USER],
        "list",
    )
    smoke.call(
        "threads_post",
        threads,
        ["threads_post", THREADS_POST_CODE],
        {"code": THREADS_POST_CODE},
    )
    smoke.call(
        "threads_post (URL)",
        threads,
        ["threads_post", f"https://www.threads.com/@zuck/post/{THREADS_POST_CODE}"],
        {"code": THREADS_POST_CODE},
    )

    print(
        f"{smoke.calls} requests, {smoke.failures} failed checks",
        flush=True,
    )
    return 1 if smoke.failures else 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""Live smoke test for the commands added for full Desearch API coverage.

It runs each skill's CLI against the real API with DESEARCH_API_KEY, so it
spends a small amount of balance. Every new command runs once with a small
count (2 on social lists; x_trends and search use their minimums, 30 and 10).
Each social list command that returns a next_cursor is run once more with it.

Nothing here starts a People Search job: people_profiles_export reads the free
library of people your earlier searches already found.

Usage:
    DESEARCH_API_KEY='your-key-here' python3 scripts/e2e-full-coverage.py

Prints one line per call, `PASS name` or `FAIL name: error`, and exits 1 when
any call failed (2 when DESEARCH_API_KEY is not set).
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

TIMEOUT_SECONDS = 180


def run_cli(skill: str, argv: list[str]):
    """Run one skill command. Return (parsed output, error message or None)."""
    script = REPO_ROOT / skill / "scripts" / "desearch.py"
    try:
        process = subprocess.run(
            [sys.executable, str(script), *argv],
            capture_output=True,
            text=True,
            timeout=TIMEOUT_SECONDS,
            check=False,
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


def problem(data, expect: str) -> str | None:
    """Why the output is not what a working command prints, or None."""
    if isinstance(data, dict) and ("error" in data or "detail" in data):
        return json.dumps(data)[:300]
    if expect == "page":
        if not isinstance(data, dict) or not isinstance(data.get("results"), list):
            return f"expected {{results, next_cursor}}, got {str(data)[:200]}"
        if "next_cursor" not in data:
            return "next_cursor missing from the output"
    elif expect == "list":
        if not isinstance(data, list):
            return f"expected a list, got {str(data)[:200]}"
    elif expect == "object":
        if not isinstance(data, dict) or not data:
            return f"expected an object, got {str(data)[:200]}"
    elif isinstance(expect, tuple):
        key, kind = expect
        if not isinstance(data, dict) or not isinstance(data.get(key), kind):
            return f"expected `{key}` in the output, got {str(data)[:200]}"
    return None


class Smoke:
    def __init__(self):
        self.failures = 0

    def fail(self, name: str, message: str) -> None:
        self.failures += 1
        print(f"FAIL {name}: {message}", flush=True)

    def call(self, name: str, skill: str, argv: list[str], expect):
        data, error = run_cli(skill, argv)
        error = error or problem(data, expect)
        if error:
            self.fail(name, error)
            return None
        print(f"PASS {name}", flush=True)
        return data

    def page(self, name: str, skill: str, argv: list[str]):
        """A social list call, then one more page when a cursor comes back."""
        data = self.call(name, skill, argv, "page")
        cursor = data.get("next_cursor") if data else None
        if cursor:
            self.call(f"{name} next page", skill, [*argv, "--cursor", cursor], "page")
        return data


def first(page, key: str) -> str | None:
    for item in (page or {}).get("results") or []:
        if isinstance(item, dict) and item.get(key):
            return str(item[key])
    return None


def main() -> int:
    if not os.environ.get("DESEARCH_API_KEY"):
        print("DESEARCH_API_KEY is not set", file=sys.stderr)
        return 2

    smoke = Smoke()

    # X trends (minimum count is 30)
    smoke.call(
        "x_trends",
        "desearch-x-search",
        ["x_trends", "1", "--count", "30"],
        ("trends", list),
    )

    # Search API (minimum count is 10)
    smoke.call(
        "search",
        "desearch-search-api",
        ["search", "What is Bittensor?", "--mode", "fast", "--count", "10"],
        ("results", list),
    )

    # People Search profiles library export (free; starts no search)
    with tempfile.TemporaryDirectory() as directory:
        smoke.call(
            "people_profiles_export",
            "desearch-people-search",
            [
                "people_profiles_export",
                "x",
                "--format",
                "jsonl",
                "--output",
                str(Path(directory) / "people.jsonl"),
            ],
            ("saved", str),
        )

    # TikTok
    tiktok = "desearch-tiktok-search"
    smoke.page("tiktok_search", tiktok, ["tiktok_search", "ai", "--count", "2"])
    smoke.call("tiktok_profile", tiktok, ["tiktok_profile", "tiktok"], "object")
    posts = smoke.page(
        "tiktok_profile_posts",
        tiktok,
        ["tiktok_profile_posts", "tiktok", "--count", "2"],
    )
    video_id = first(posts, "id")
    if video_id:
        smoke.call("tiktok_post", tiktok, ["tiktok_post", video_id], "object")
        smoke.page(
            "tiktok_comments", tiktok, ["tiktok_comments", video_id, "--count", "2"]
        )
    else:
        smoke.fail("tiktok_post", "no video id from tiktok_profile_posts")
        smoke.fail("tiktok_comments", "no video id from tiktok_profile_posts")
    smoke.page("tiktok_hashtag", tiktok, ["tiktok_hashtag", "ai", "--count", "2"])
    smoke.call(
        "tiktok_trending",
        tiktok,
        ["tiktok_trending", "--region", "US", "--count", "2"],
        "list",
    )

    # Facebook
    facebook = "desearch-facebook-search"
    smoke.page("facebook_search", facebook, ["facebook_search", "ai", "--count", "2"])
    smoke.call("facebook_profile", facebook, ["facebook_profile", "facebook"], "object")
    posts = smoke.page(
        "facebook_profile_posts",
        facebook,
        ["facebook_profile_posts", "facebook", "--count", "2"],
    )
    post_id = first(posts, "id")
    if post_id:
        smoke.call("facebook_post", facebook, ["facebook_post", post_id], "object")
        smoke.page(
            "facebook_comments",
            facebook,
            ["facebook_comments", post_id, "--count", "2"],
        )
    else:
        smoke.fail("facebook_post", "no post id from facebook_profile_posts")
        smoke.fail("facebook_comments", "no post id from facebook_profile_posts")
    smoke.page("facebook_hashtag", facebook, ["facebook_hashtag", "ai", "--count", "2"])

    # Instagram
    instagram = "desearch-instagram-search"
    smoke.call(
        "instagram_search",
        instagram,
        ["instagram_search", "instagram", "--count", "2"],
        "list",
    )
    smoke.call(
        "instagram_profile", instagram, ["instagram_profile", "instagram"], "object"
    )
    posts = smoke.page(
        "instagram_profile_posts",
        instagram,
        ["instagram_profile_posts", "instagram", "--count", "2"],
    )
    shortcode = first(posts, "shortcode")
    if shortcode:
        smoke.call(
            "instagram_media", instagram, ["instagram_media", shortcode], "object"
        )
        smoke.page(
            "instagram_comments",
            instagram,
            ["instagram_comments", shortcode, "--count", "2"],
        )
    else:
        smoke.fail("instagram_media", "no shortcode from instagram_profile_posts")
        smoke.fail("instagram_comments", "no shortcode from instagram_profile_posts")
    smoke.page(
        "instagram_hashtag", instagram, ["instagram_hashtag", "ai", "--count", "2"]
    )

    return 1 if smoke.failures else 0


if __name__ == "__main__":
    sys.exit(main())

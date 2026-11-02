#!/usr/bin/env python3
"""Desearch YouTube Search CLI - Public YouTube search, videos, transcripts, comments, and channels.

List commands print one page as {"results": [...], "next_cursor": "..."}.
Pass next_cursor back unchanged with --cursor for the next page; it is null
on the last page.

Usage:
    desearch youtube_search "<query>" [--type T] [--upload-date D] [--sort-by S] [--duration L] [--cursor C]
    desearch youtube_video <video_id_or_url>
    desearch youtube_transcript <video_id_or_url> [--language CODE]
    desearch youtube_comments <video_id_or_url> [--order top|newest] [--cursor C]
    desearch youtube_channel <handle_or_channel_id>
    desearch youtube_channel_videos <handle_or_channel_id> [--sort latest|popular] [--cursor C]

Environment:
    DESEARCH_API_KEY - Required API key from desearch.ai
    DESEARCH_BASE_URL - Optional API base URL (default https://api.desearch.ai)
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
    "youtube_search",
    "youtube_video",
    "youtube_transcript",
    "youtube_comments",
    "youtube_channel",
    "youtube_channel_videos",
]

SEARCH_TYPES = ["videos", "shorts", "channels", "playlists"]
UPLOAD_DATES = ["today", "this_week", "this_month", "this_year"]
SEARCH_SORTS = ["relevance", "popular"]
DURATIONS = ["under_3_min", "between_3_and_20_min", "over_20_min"]
COMMENT_ORDERS = ["top", "newest"]
CHANNEL_VIDEO_SORTS = ["latest", "popular"]


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


def language_code(value: str) -> str:
    code = value.strip()
    if not re.fullmatch(r"[A-Za-z]{2,3}(-[A-Za-z0-9]{2,4})?", code):
        raise argparse.ArgumentTypeError(
            "language must be a code such as en, es or pt-BR"
        )
    return code


def path_segment(value: str) -> str:
    # Encode every reserved character, "/" included, so an ID or URL is one segment.
    return quote(value, safe="")


# Commands


def cmd_youtube_search(args):
    body = {"query": args.query}
    for key, value in (
        ("type", args.type),
        ("upload_date", args.upload_date),
        ("sort_by", args.sort_by),
        ("duration", args.duration),
        ("cursor", args.cursor or None),
    ):
        if value is not None:
            body[key] = value
    return api_request("POST", "/desearch/youtube/search", body=body, paged=True)


def cmd_youtube_video(args):
    return api_request("GET", f"/desearch/youtube/video/{path_segment(args.id)}")


def cmd_youtube_transcript(args):
    return api_request(
        "GET",
        f"/desearch/youtube/transcript/{path_segment(args.video_id)}",
        params={"language": args.language},
    )


def cmd_youtube_comments(args):
    return api_request(
        "GET",
        f"/desearch/youtube/comments/{path_segment(args.video_id)}",
        params={"order": args.order, "cursor": args.cursor or None},
        paged=True,
    )


def cmd_youtube_channel(args):
    return api_request("GET", f"/desearch/youtube/channel/{path_segment(args.handle)}")


def cmd_youtube_channel_videos(args):
    return api_request(
        "GET",
        f"/desearch/youtube/channel/{path_segment(args.handle)}/videos",
        params={"sort": args.sort, "cursor": args.cursor or None},
        paged=True,
    )


COMMAND_HANDLERS = {
    "youtube_search": cmd_youtube_search,
    "youtube_video": cmd_youtube_video,
    "youtube_transcript": cmd_youtube_transcript,
    "youtube_comments": cmd_youtube_comments,
    "youtube_channel": cmd_youtube_channel,
    "youtube_channel_videos": cmd_youtube_channel_videos,
}


def add_cursor(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--cursor",
        help="next_cursor from the previous page, sent back unchanged",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Desearch YouTube Search CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    commands = parser.add_subparsers(dest="command", metavar="command", required=True)

    search = commands.add_parser(
        "youtube_search", help="Search YouTube videos, Shorts, channels, and playlists"
    )
    search.add_argument("query", type=query_text, help="Keyword or phrase")
    search.add_argument(
        "--type", choices=SEARCH_TYPES, help="Only this kind of result (default mixed)"
    )
    search.add_argument(
        "--upload-date",
        dest="upload_date",
        choices=UPLOAD_DATES,
        help="Only videos uploaded in this window",
    )
    search.add_argument(
        "--sort-by", dest="sort_by", choices=SEARCH_SORTS, help="Result order"
    )
    search.add_argument(
        "--duration",
        choices=DURATIONS,
        help="Video length filter; applies to videos, not Shorts",
    )
    add_cursor(search)

    video = commands.add_parser("youtube_video", help="One YouTube video or Short")
    video.add_argument("id", type=required_text, help="Video or Short ID, or its URL")

    transcript = commands.add_parser(
        "youtube_transcript", help="Captions of a YouTube video as text and segments"
    )
    transcript.add_argument(
        "video_id", type=required_text, help="Video or Short ID, or its URL"
    )
    transcript.add_argument(
        "--language",
        type=language_code,
        help="Caption language code, e.g. en (default YouTube's default track)",
    )

    comments = commands.add_parser(
        "youtube_comments", help="Top-level comments on a YouTube video"
    )
    comments.add_argument("video_id", type=required_text, help="Video ID or its URL")
    comments.add_argument("--order", choices=COMMENT_ORDERS, help="Comment order")
    add_cursor(comments)

    channel = commands.add_parser("youtube_channel", help="A YouTube channel")
    channel.add_argument(
        "handle", type=required_text, help="Channel handle (@ optional) or channel ID"
    )

    channel_videos = commands.add_parser(
        "youtube_channel_videos", help="Videos uploaded by a YouTube channel"
    )
    channel_videos.add_argument(
        "handle", type=required_text, help="Channel handle (@ optional) or channel ID"
    )
    channel_videos.add_argument(
        "--sort",
        choices=CHANNEL_VIDEO_SORTS,
        help="Video order (API default latest)",
    )
    add_cursor(channel_videos)

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

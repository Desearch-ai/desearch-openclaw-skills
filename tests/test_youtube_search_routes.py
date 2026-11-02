import contextlib
import email.message
import importlib.util
import io
import json
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError

REPO_ROOT = Path(__file__).resolve().parents[1]

VIDEO_ID = "dQw4w9WgXcQ"


def load_script(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class FakeResponse:
    def __init__(self, body, headers=None):
        self.body = body
        self.headers = email.message.Message()
        for name, value in (headers or {}).items():
            self.headers[name] = value

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def read(self):
        return self.body.encode()


class YouTubeSearchRouteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.script = load_script(
            "desearch_youtube_search_script",
            REPO_ROOT / "desearch-youtube-search" / "scripts" / "desearch.py",
        )

    def run_cli(self, argv, response=None):
        with (
            patch.object(
                self.script,
                "api_request",
                return_value=response if response is not None else [],
            ) as request,
            contextlib.redirect_stdout(io.StringIO()) as stdout,
        ):
            self.script.main(argv)
        return request, stdout.getvalue()

    def send(self, argv, responses, env=None):
        """Run the CLI against a fake HTTP layer; return (sent requests, printed JSON)."""
        sent = []
        queue = list(responses)

        def fake_urlopen(request, timeout):
            sent.append(request)
            response = queue.pop(0)
            if isinstance(response, Exception):
                raise response
            return response

        environ = {"DESEARCH_API_KEY": "test-key", **(env or {})}
        with (
            patch.dict(self.script.os.environ, environ),
            patch.object(self.script, "urlopen", side_effect=fake_urlopen),
            contextlib.redirect_stdout(io.StringIO()) as stdout,
        ):
            if "DESEARCH_BASE_URL" not in environ:
                self.script.os.environ.pop("DESEARCH_BASE_URL", None)
            self.script.main(argv)
        return sent, json.loads(stdout.getvalue())

    def assert_rejected(self, bad_argvs):
        for argv in bad_argvs:
            with self.subTest(argv=argv):
                with (
                    patch.object(self.script, "api_request") as request,
                    contextlib.redirect_stderr(io.StringIO()),
                    self.assertRaises(SystemExit) as exit_info,
                ):
                    self.script.main(argv)

                self.assertEqual(exit_info.exception.code, 2)
                request.assert_not_called()

    def test_every_command_calls_its_route(self):
        cases = [
            (
                [
                    "youtube_search",
                    "bittensor",
                    "--type",
                    "videos",
                    "--upload-date",
                    "this_month",
                    "--sort-by",
                    "popular",
                    "--duration",
                    "over_20_min",
                    "--cursor",
                    "CUR",
                ],
                ("POST", "/desearch/youtube/search"),
                {
                    "body": {
                        "query": "bittensor",
                        "type": "videos",
                        "upload_date": "this_month",
                        "sort_by": "popular",
                        "duration": "over_20_min",
                        "cursor": "CUR",
                    },
                    "paged": True,
                },
            ),
            (
                ["youtube_search", "bittensor"],
                ("POST", "/desearch/youtube/search"),
                {"body": {"query": "bittensor"}, "paged": True},
            ),
            (
                ["youtube_video", VIDEO_ID],
                ("GET", f"/desearch/youtube/video/{VIDEO_ID}"),
                {},
            ),
            (
                ["youtube_transcript", VIDEO_ID, "--language", "en"],
                ("GET", f"/desearch/youtube/transcript/{VIDEO_ID}"),
                {"params": {"language": "en"}},
            ),
            (
                ["youtube_comments", VIDEO_ID, "--order", "newest", "--cursor", "CUR"],
                ("GET", f"/desearch/youtube/comments/{VIDEO_ID}"),
                {"params": {"order": "newest", "cursor": "CUR"}, "paged": True},
            ),
            (
                ["youtube_channel", "@MrBeast"],
                ("GET", "/desearch/youtube/channel/%40MrBeast"),
                {},
            ),
            (
                [
                    "youtube_channel_videos",
                    "UCX6OQ3DkcsbYNE6H8uQQuVA",
                    "--sort",
                    "popular",
                ],
                ("GET", "/desearch/youtube/channel/UCX6OQ3DkcsbYNE6H8uQQuVA/videos"),
                {"params": {"sort": "popular", "cursor": None}, "paged": True},
            ),
        ]
        self.assertEqual({argv[0] for argv, _, _ in cases}, set(self.script.COMMANDS))
        for argv, call_args, call_kwargs in cases:
            with self.subTest(argv=argv):
                request, stdout = self.run_cli(argv)
                request.assert_called_once_with(*call_args, **call_kwargs)
                self.assertEqual(json.loads(stdout), [])

    def test_video_urls_are_sent_as_one_encoded_segment(self):
        request, _ = self.run_cli(["youtube_video", "https://youtu.be/dQw4w9WgXcQ?t=1"])
        request.assert_called_once_with(
            "GET",
            "/desearch/youtube/video/https%3A%2F%2Fyoutu.be%2FdQw4w9WgXcQ%3Ft%3D1",
        )

    def test_list_output_includes_the_next_cursor_header(self):
        page = [{"id": "c1", "text": "comment"}]
        sent, printed = self.send(
            ["youtube_comments", VIDEO_ID, "--cursor", "PAGE-1"],
            [FakeResponse(json.dumps(page), {"X-Desearch-Next-Cursor": "PAGE-2.sig"})],
        )

        self.assertEqual(printed, {"results": page, "next_cursor": "PAGE-2.sig"})
        request = sent[0]
        self.assertEqual(request.get_method(), "GET")
        self.assertEqual(
            request.full_url,
            f"https://api.desearch.ai/desearch/youtube/comments/{VIDEO_ID}?cursor=PAGE-1",
        )
        self.assertEqual(request.get_header("Authorization"), "test-key")

    def test_next_cursor_is_null_on_the_last_page(self):
        _, printed = self.send(
            ["youtube_channel_videos", "@MrBeast"], [FakeResponse("[]")]
        )
        self.assertEqual(printed, {"results": [], "next_cursor": None})

    def test_search_sends_the_cursor_in_the_body(self):
        sent, printed = self.send(
            ["youtube_search", "bittensor", "--cursor", "opaque/+=="],
            [FakeResponse("[]", {"x-desearch-next-cursor": "NEXT"})],
        )

        self.assertEqual(printed["next_cursor"], "NEXT")
        request = sent[0]
        self.assertEqual(request.get_method(), "POST")
        self.assertEqual(
            request.full_url, "https://api.desearch.ai/desearch/youtube/search"
        )
        self.assertEqual(
            json.loads(request.data), {"query": "bittensor", "cursor": "opaque/+=="}
        )

    def test_base_url_can_be_overridden(self):
        sent, _ = self.send(
            ["youtube_transcript", VIDEO_ID],
            [FakeResponse('{"videoId": "dQw4w9WgXcQ"}')],
            env={"DESEARCH_BASE_URL": "https://api-dev.desearch.ai/"},
        )
        self.assertEqual(
            sent[0].full_url,
            f"https://api-dev.desearch.ai/desearch/youtube/transcript/{VIDEO_ID}",
        )

    def test_errors_and_single_objects_are_not_wrapped(self):
        error = HTTPError(
            f"https://api.desearch.ai/desearch/youtube/transcript/{VIDEO_ID}",
            404,
            "Not Found",
            email.message.Message(),
            io.BytesIO(b'{"detail": "Not found"}'),
        )
        _, printed = self.send(["youtube_transcript", VIDEO_ID], [error])
        self.assertEqual(printed, {"detail": "Not found"})

        video = {"id": VIDEO_ID, "views": 1}
        _, printed = self.send(
            ["youtube_video", VIDEO_ID], [FakeResponse(json.dumps(video))]
        )
        self.assertEqual(printed, video)

    def test_cli_rejects_bad_input_before_any_request(self):
        self.assert_rejected(
            [
                ["youtube_search", " "],
                ["youtube_search", "x" * 501],
                ["youtube_search", "ai", "--type", "movies"],
                ["youtube_search", "ai", "--duration", "short"],
                ["youtube_search", "ai", "--upload-date", "yesterday"],
                ["youtube_transcript", VIDEO_ID, "--language", "english"],
                ["youtube_comments", VIDEO_ID, "--order", "oldest"],
                ["youtube_channel_videos", "@MrBeast", "--sort", "oldest"],
                ["youtube_video", " "],
                ["youtube_video", VIDEO_ID, "--cursor", "CUR"],
                ["youtube_shorts", "ai"],
            ]
        )


if __name__ == "__main__":
    unittest.main()

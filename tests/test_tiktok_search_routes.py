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

VIDEO_ID = "7620891413932166433"


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


class TikTokSearchRouteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.script = load_script(
            "desearch_tiktok_search_script",
            REPO_ROOT / "desearch-tiktok-search" / "scripts" / "desearch.py",
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

    def send(self, argv, responses):
        """Run the CLI against a fake HTTP layer; return (sent requests, printed JSON)."""
        sent = []
        queue = list(responses)

        def fake_urlopen(request, timeout):
            sent.append(request)
            response = queue.pop(0)
            if isinstance(response, Exception):
                raise response
            return response

        with (
            patch.dict(self.script.os.environ, {"DESEARCH_API_KEY": "test-key"}),
            patch.object(self.script, "urlopen", side_effect=fake_urlopen),
            contextlib.redirect_stdout(io.StringIO()) as stdout,
        ):
            self.script.main(argv)
        return sent, json.loads(stdout.getvalue())

    def test_every_command_calls_its_route(self):
        cases = [
            (
                [
                    "tiktok_search",
                    "ai agents",
                    "--count",
                    "5",
                    "--cursor",
                    "CUR",
                    "--sort",
                    "relevance",
                ],
                ("POST", "/desearch/tiktok/search"),
                {
                    "body": {
                        "query": "ai agents",
                        "count": 5,
                        "cursor": "CUR",
                        "sort": "relevance",
                    },
                    "paged": True,
                },
            ),
            (
                ["tiktok_search", "ai agents"],
                ("POST", "/desearch/tiktok/search"),
                {"body": {"query": "ai agents"}, "paged": True},
            ),
            (
                ["tiktok_post", VIDEO_ID],
                ("GET", f"/desearch/tiktok/post/{VIDEO_ID}"),
                {},
            ),
            (
                ["tiktok_profile", "@tiktok"],
                ("GET", "/desearch/tiktok/profile/tiktok"),
                {},
            ),
            (
                ["tiktok_profile_posts", "tiktok", "--count", "3", "--cursor", "CUR"],
                ("GET", "/desearch/tiktok/profile/tiktok/posts"),
                {"params": {"count": 3, "cursor": "CUR"}, "paged": True},
            ),
            (
                ["tiktok_comments", VIDEO_ID, "-n", "2"],
                ("GET", f"/desearch/tiktok/comments/{VIDEO_ID}"),
                {"params": {"count": 2, "cursor": None}, "paged": True},
            ),
            (
                ["tiktok_hashtag", "#ai"],
                ("GET", "/desearch/tiktok/hashtag/ai"),
                {"params": {"count": None, "cursor": None}, "paged": True},
            ),
            (
                ["tiktok_trending", "--region", "gb", "--count", "5"],
                ("GET", "/desearch/tiktok/trending"),
                {"params": {"region": "GB", "count": 5}},
            ),
            (
                ["tiktok_trending"],
                ("GET", "/desearch/tiktok/trending"),
                {"params": {"region": None, "count": None}},
            ),
        ]
        self.assertEqual({argv[0] for argv, _, _ in cases}, set(self.script.COMMANDS))
        for argv, call_args, call_kwargs in cases:
            with self.subTest(argv=argv):
                request, stdout = self.run_cli(argv)
                request.assert_called_once_with(*call_args, **call_kwargs)
                self.assertEqual(json.loads(stdout), [])

    def test_path_values_are_url_encoded_as_one_segment(self):
        request, _ = self.run_cli(["tiktok_post", "a/b c?"])
        request.assert_called_once_with("GET", "/desearch/tiktok/post/a%2Fb%20c%3F")

        request, _ = self.run_cli(["tiktok_hashtag", "#café"])
        self.assertEqual(
            request.call_args.args[1], "/desearch/tiktok/hashtag/caf%C3%A9"
        )

    def test_list_output_includes_the_next_cursor_header(self):
        page = [{"id": VIDEO_ID, "text": "caption"}]
        sent, printed = self.send(
            ["tiktok_hashtag", "ai", "--count", "2", "--cursor", "PAGE-1"],
            [FakeResponse(json.dumps(page), {"X-Desearch-Next-Cursor": "PAGE-2.sig"})],
        )

        self.assertEqual(printed, {"results": page, "next_cursor": "PAGE-2.sig"})
        request = sent[0]
        self.assertEqual(request.get_method(), "GET")
        self.assertEqual(
            request.full_url,
            "https://api.desearch.ai/desearch/tiktok/hashtag/ai?count=2&cursor=PAGE-1",
        )
        self.assertEqual(request.get_header("Authorization"), "test-key")

    def test_next_cursor_is_null_on_the_last_page(self):
        _, printed = self.send(["tiktok_profile_posts", "tiktok"], [FakeResponse("[]")])
        self.assertEqual(printed, {"results": [], "next_cursor": None})

    def test_search_sends_the_cursor_in_the_body(self):
        sent, printed = self.send(
            ["tiktok_search", "ai", "--cursor", "opaque/+=="],
            [FakeResponse("[]", {"x-desearch-next-cursor": "NEXT"})],
        )

        self.assertEqual(printed["next_cursor"], "NEXT")
        request = sent[0]
        self.assertEqual(request.get_method(), "POST")
        self.assertEqual(
            request.full_url, "https://api.desearch.ai/desearch/tiktok/search"
        )
        self.assertEqual(
            json.loads(request.data), {"query": "ai", "cursor": "opaque/+=="}
        )

    def test_cursor_is_sent_back_unchanged(self):
        cursor = "eyJ2IjoxfQ.c2ln-_=="
        sent, _ = self.send(
            ["tiktok_comments", VIDEO_ID, "--cursor", cursor], [FakeResponse("[]")]
        )
        query = sent[0].full_url.split("?", 1)[1]
        self.assertIn("cursor=eyJ2IjoxfQ.c2ln-_%3D%3D", query)

    def test_errors_and_single_objects_are_not_wrapped(self):
        error = HTTPError(
            "https://api.desearch.ai/desearch/tiktok/hashtag/ai",
            422,
            "Unprocessable Entity",
            email.message.Message(),
            io.BytesIO(b'{"detail": "Invalid request parameters"}'),
        )
        _, printed = self.send(["tiktok_hashtag", "ai", "--cursor", "stale"], [error])
        self.assertEqual(printed, {"detail": "Invalid request parameters"})

        profile = {"username": "tiktok", "followers": 1}
        _, printed = self.send(
            ["tiktok_profile", "tiktok"], [FakeResponse(json.dumps(profile))]
        )
        self.assertEqual(printed, profile)

    def test_trending_prints_the_plain_list(self):
        page = [{"id": VIDEO_ID}]
        _, printed = self.send(["tiktok_trending"], [FakeResponse(json.dumps(page))])
        self.assertEqual(printed, page)

    def test_cli_rejects_bad_input_before_any_request(self):
        bad_argvs = [
            ["tiktok_search", "ai", "--count", "0"],
            ["tiktok_hashtag", "ai", "--count", "101"],
            ["tiktok_trending", "--region", "USA"],
            ["tiktok_trending", "--cursor", "CUR"],
            ["tiktok_profile", "@"],
            ["tiktok_post", " "],
            ["tiktok_videos", "tiktok"],
        ]
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


if __name__ == "__main__":
    unittest.main()

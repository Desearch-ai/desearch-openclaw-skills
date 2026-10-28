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

SHORTCODE = "DeuOR-CjKE9"


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


class InstagramSearchRouteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.script = load_script(
            "desearch_instagram_search_script",
            REPO_ROOT / "desearch-instagram-search" / "scripts" / "desearch.py",
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
                ["instagram_search", "desearch", "--count", "5"],
                ("POST", "/desearch/instagram/search"),
                {"body": {"query": "desearch", "count": 5}},
            ),
            (
                ["instagram_media", SHORTCODE],
                ("GET", f"/desearch/instagram/media/{SHORTCODE}"),
                {},
            ),
            (
                ["instagram_profile", "@instagram"],
                ("GET", "/desearch/instagram/profile/instagram"),
                {},
            ),
            (
                [
                    "instagram_profile_posts",
                    "instagram",
                    "--count",
                    "3",
                    "--cursor",
                    "CUR",
                ],
                ("GET", "/desearch/instagram/profile/instagram/posts"),
                {"params": {"count": 3, "cursor": "CUR"}, "paged": True},
            ),
            (
                ["instagram_comments", SHORTCODE, "-n", "2"],
                ("GET", f"/desearch/instagram/comments/{SHORTCODE}"),
                {"params": {"count": 2, "cursor": None}, "paged": True},
            ),
            (
                ["instagram_hashtag", "#ai"],
                ("GET", "/desearch/instagram/hashtag/ai"),
                {"params": {"count": None, "cursor": None}, "paged": True},
            ),
        ]
        self.assertEqual({argv[0] for argv, _, _ in cases}, set(self.script.COMMANDS))
        for argv, call_args, call_kwargs in cases:
            with self.subTest(argv=argv):
                request, stdout = self.run_cli(argv)
                request.assert_called_once_with(*call_args, **call_kwargs)
                self.assertEqual(json.loads(stdout), [])

    def test_media_accepts_a_post_url_as_one_encoded_segment(self):
        request, _ = self.run_cli(
            ["instagram_media", f"https://www.instagram.com/p/{SHORTCODE}/"]
        )
        request.assert_called_once_with(
            "GET",
            "/desearch/instagram/media/"
            f"https%3A%2F%2Fwww.instagram.com%2Fp%2F{SHORTCODE}%2F",
        )

    def test_comments_take_the_shortcode_from_a_post_url(self):
        urls = [
            f"https://www.instagram.com/p/{SHORTCODE}/",
            f"https://instagram.com/reel/{SHORTCODE}?igsh=abc",
            f"https://www.instagram.com/someone/p/{SHORTCODE}/",
            SHORTCODE,
        ]
        for value in urls:
            with self.subTest(value=value):
                request, _ = self.run_cli(["instagram_comments", value])
                self.assertEqual(
                    request.call_args.args,
                    ("GET", f"/desearch/instagram/comments/{SHORTCODE}"),
                )

    def test_list_output_includes_the_next_cursor_header(self):
        page = [{"shortcode": SHORTCODE, "caption": "caption text"}]
        sent, printed = self.send(
            ["instagram_hashtag", "ai", "--count", "2", "--cursor", "PAGE-1"],
            [FakeResponse(json.dumps(page), {"X-Desearch-Next-Cursor": "PAGE-2.sig"})],
        )

        self.assertEqual(printed, {"results": page, "next_cursor": "PAGE-2.sig"})
        request = sent[0]
        self.assertEqual(request.get_method(), "GET")
        self.assertEqual(
            request.full_url,
            "https://api.desearch.ai/desearch/instagram/hashtag/ai?count=2&cursor=PAGE-1",
        )
        self.assertEqual(request.get_header("Authorization"), "test-key")

    def test_next_cursor_is_null_on_the_last_page(self):
        _, printed = self.send(["instagram_comments", SHORTCODE], [FakeResponse("[]")])
        self.assertEqual(printed, {"results": [], "next_cursor": None})

    def test_search_prints_the_plain_list_and_sends_no_cursor(self):
        page = [{"type": "profile", "username": "instagram"}]
        sent, printed = self.send(
            ["instagram_search", "instagram"], [FakeResponse(json.dumps(page))]
        )

        self.assertEqual(printed, page)
        request = sent[0]
        self.assertEqual(request.get_method(), "POST")
        self.assertEqual(
            request.full_url, "https://api.desearch.ai/desearch/instagram/search"
        )
        self.assertEqual(json.loads(request.data), {"query": "instagram"})

    def test_errors_and_single_objects_are_not_wrapped(self):
        error = HTTPError(
            f"https://api.desearch.ai/desearch/instagram/comments/{SHORTCODE}",
            404,
            "Not Found",
            email.message.Message(),
            io.BytesIO(b'{"detail": "No post found for this shortcode"}'),
        )
        _, printed = self.send(["instagram_comments", SHORTCODE], [error])
        self.assertEqual(printed, {"detail": "No post found for this shortcode"})

        profile = {"username": "instagram", "followers": 1}
        _, printed = self.send(
            ["instagram_profile", "instagram"], [FakeResponse(json.dumps(profile))]
        )
        self.assertEqual(printed, profile)

    def test_cli_rejects_bad_input_before_any_request(self):
        bad_argvs = [
            ["instagram_search", "ai", "--cursor", "CUR"],
            ["instagram_search", "ai", "--count", "0"],
            ["instagram_hashtag", "ai", "--count", "101"],
            ["instagram_profile", "@"],
            ["instagram_comments", " "],
            ["instagram_trending"],
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

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

POST_ID = "1525856912919657"


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


class FacebookSearchRouteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.script = load_script(
            "desearch_facebook_search_script",
            REPO_ROOT / "desearch-facebook-search" / "scripts" / "desearch.py",
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
                ["facebook_search", "running shoes", "--count", "5", "--cursor", "CUR"],
                ("POST", "/desearch/facebook/search"),
                {
                    "body": {"query": "running shoes", "count": 5, "cursor": "CUR"},
                    "paged": True,
                },
            ),
            (
                ["facebook_search", "running shoes"],
                ("POST", "/desearch/facebook/search"),
                {"body": {"query": "running shoes"}, "paged": True},
            ),
            (
                ["facebook_post", POST_ID],
                ("GET", f"/desearch/facebook/post/{POST_ID}"),
                {},
            ),
            (
                ["facebook_profile", "facebook"],
                ("GET", "/desearch/facebook/profile/facebook"),
                {},
            ),
            (
                [
                    "facebook_profile_posts",
                    "facebook",
                    "--count",
                    "3",
                    "--cursor",
                    "CUR",
                ],
                ("GET", "/desearch/facebook/profile/facebook/posts"),
                {"params": {"count": 3, "cursor": "CUR"}, "paged": True},
            ),
            (
                ["facebook_comments", POST_ID, "-n", "10"],
                ("GET", f"/desearch/facebook/comments/{POST_ID}"),
                {"params": {"count": 10, "cursor": None}, "paged": True},
            ),
            (
                ["facebook_hashtag", "#ai"],
                ("GET", "/desearch/facebook/hashtag/ai"),
                {"params": {"count": None, "cursor": None}, "paged": True},
            ),
        ]
        self.assertEqual({argv[0] for argv, _, _ in cases}, set(self.script.COMMANDS))
        for argv, call_args, call_kwargs in cases:
            with self.subTest(argv=argv):
                request, stdout = self.run_cli(argv)
                request.assert_called_once_with(*call_args, **call_kwargs)
                self.assertEqual(json.loads(stdout), [])

    def test_path_values_are_url_encoded_as_one_segment(self):
        request, _ = self.run_cli(["facebook_post", "pfbid/02 x"])
        request.assert_called_once_with("GET", "/desearch/facebook/post/pfbid%2F02%20x")

        request, _ = self.run_cli(["facebook_comments", "100/posts/200"])
        self.assertEqual(
            request.call_args.args[1], "/desearch/facebook/comments/100%2Fposts%2F200"
        )

    def test_list_output_includes_the_next_cursor_header(self):
        page = [{"id": POST_ID, "text": "Post text"}]
        sent, printed = self.send(
            [
                "facebook_profile_posts",
                "facebook",
                "--count",
                "3",
                "--cursor",
                "PAGE-1",
            ],
            [FakeResponse(json.dumps(page), {"X-Desearch-Next-Cursor": "PAGE-2.sig"})],
        )

        self.assertEqual(printed, {"results": page, "next_cursor": "PAGE-2.sig"})
        request = sent[0]
        self.assertEqual(request.get_method(), "GET")
        self.assertEqual(
            request.full_url,
            "https://api.desearch.ai/desearch/facebook/profile/facebook/posts?count=3&cursor=PAGE-1",
        )
        self.assertEqual(request.get_header("Authorization"), "test-key")

    def test_next_cursor_is_null_on_the_last_page(self):
        _, printed = self.send(["facebook_comments", POST_ID], [FakeResponse("[]")])
        self.assertEqual(printed, {"results": [], "next_cursor": None})

    def test_search_sends_the_cursor_in_the_body(self):
        sent, printed = self.send(
            ["facebook_search", "running", "--cursor", "opaque/+=="],
            [FakeResponse("[]", {"x-desearch-next-cursor": "NEXT"})],
        )

        self.assertEqual(printed, {"results": [], "next_cursor": "NEXT"})
        request = sent[0]
        self.assertEqual(request.get_method(), "POST")
        self.assertEqual(
            request.full_url, "https://api.desearch.ai/desearch/facebook/search"
        )
        self.assertEqual(
            json.loads(request.data), {"query": "running", "cursor": "opaque/+=="}
        )

    def test_errors_and_single_objects_are_not_wrapped(self):
        error = HTTPError(
            "https://api.desearch.ai/desearch/facebook/hashtag/ai",
            422,
            "Unprocessable Entity",
            email.message.Message(),
            io.BytesIO(b'{"detail": "Invalid request parameters"}'),
        )
        _, printed = self.send(["facebook_hashtag", "ai", "--cursor", "stale"], [error])
        self.assertEqual(printed, {"detail": "Invalid request parameters"})

        post = {"id": POST_ID, "text": "Post text"}
        _, printed = self.send(
            ["facebook_post", POST_ID], [FakeResponse(json.dumps(post))]
        )
        self.assertEqual(printed, post)

    def test_cli_rejects_bad_input_before_any_request(self):
        bad_argvs = [
            ["facebook_search", "ai", "--count", "0"],
            ["facebook_comments", POST_ID, "--count", "101"],
            ["facebook_profile", " "],
            ["facebook_hashtag", "#"],
            ["facebook_post", POST_ID, "--cursor", "CUR"],
            ["facebook_trending"],
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

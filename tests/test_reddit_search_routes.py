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

POST_ID = "1q6pxwn"


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


class RedditSearchRouteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.script = load_script(
            "desearch_reddit_search_script",
            REPO_ROOT / "desearch-reddit-search" / "scripts" / "desearch.py",
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
                    "reddit_search",
                    "bittensor",
                    "--sort",
                    "top",
                    "--timeframe",
                    "week",
                    "--cursor",
                    "CUR",
                ],
                ("POST", "/desearch/reddit/search"),
                {
                    "body": {
                        "query": "bittensor",
                        "sort": "top",
                        "timeframe": "week",
                        "cursor": "CUR",
                    },
                    "paged": True,
                },
            ),
            (
                ["reddit_search", "bittensor"],
                ("POST", "/desearch/reddit/search"),
                {"body": {"query": "bittensor"}, "paged": True},
            ),
            (
                ["reddit_subreddit", "r/AskReddit"],
                ("GET", "/desearch/reddit/subreddit/AskReddit"),
                {},
            ),
            (
                [
                    "reddit_subreddit_posts",
                    "AskReddit",
                    "--sort",
                    "top",
                    "--timeframe",
                    "week",
                    "--cursor",
                    "CUR",
                ],
                ("GET", "/desearch/reddit/subreddit/AskReddit/posts"),
                {
                    "params": {"sort": "top", "timeframe": "week", "cursor": "CUR"},
                    "paged": True,
                },
            ),
            (
                ["reddit_subreddit_posts", "/r/AskReddit/"],
                ("GET", "/desearch/reddit/subreddit/AskReddit/posts"),
                {
                    "params": {"sort": None, "timeframe": None, "cursor": None},
                    "paged": True,
                },
            ),
            (
                ["reddit_post", POST_ID],
                ("GET", f"/desearch/reddit/post/{POST_ID}"),
                {},
            ),
            (
                ["reddit_comments", f"t3_{POST_ID}", "--cursor", "CUR"],
                ("GET", f"/desearch/reddit/comments/t3_{POST_ID}"),
                {"params": {"cursor": "CUR"}, "paged": True},
            ),
        ]
        self.assertEqual({argv[0] for argv, _, _ in cases}, set(self.script.COMMANDS))
        for argv, call_args, call_kwargs in cases:
            with self.subTest(argv=argv):
                request, stdout = self.run_cli(argv)
                request.assert_called_once_with(*call_args, **call_kwargs)
                self.assertEqual(json.loads(stdout), [])

    def test_subreddit_name_keeps_its_case(self):
        request, _ = self.run_cli(["reddit_subreddit", "R/WorldNews"])
        request.assert_called_once_with("GET", "/desearch/reddit/subreddit/WorldNews")

    def test_post_urls_are_sent_as_one_encoded_segment(self):
        url = f"https://www.reddit.com/r/webscraping/comments/{POST_ID}/"
        request, _ = self.run_cli(["reddit_comments", url])
        self.assertEqual(
            request.call_args.args[1],
            "/desearch/reddit/comments/https%3A%2F%2Fwww.reddit.com%2Fr%2Fwebscraping"
            f"%2Fcomments%2F{POST_ID}%2F",
        )

    def test_list_output_includes_the_next_cursor_header(self):
        page = [{"id": POST_ID, "title": "post"}]
        sent, printed = self.send(
            [
                "reddit_subreddit_posts",
                "AskReddit",
                "--sort",
                "new",
                "--cursor",
                "PAGE-1",
            ],
            [FakeResponse(json.dumps(page), {"X-Desearch-Next-Cursor": "PAGE-2.sig"})],
        )

        self.assertEqual(printed, {"results": page, "next_cursor": "PAGE-2.sig"})
        self.assertEqual(
            sent[0].full_url,
            "https://api.desearch.ai/desearch/reddit/subreddit/AskReddit/posts"
            "?sort=new&cursor=PAGE-1",
        )
        self.assertEqual(sent[0].get_header("Authorization"), "test-key")

    def test_next_cursor_is_null_on_the_last_page(self):
        _, printed = self.send(["reddit_comments", POST_ID], [FakeResponse("[]")])
        self.assertEqual(printed, {"results": [], "next_cursor": None})

    def test_search_sends_the_cursor_in_the_body(self):
        sent, printed = self.send(
            ["reddit_search", "bittensor", "--cursor", "opaque/+=="],
            [FakeResponse("[]", {"x-desearch-next-cursor": "NEXT"})],
        )

        self.assertEqual(printed["next_cursor"], "NEXT")
        request = sent[0]
        self.assertEqual(request.get_method(), "POST")
        self.assertEqual(
            request.full_url, "https://api.desearch.ai/desearch/reddit/search"
        )
        self.assertEqual(
            json.loads(request.data), {"query": "bittensor", "cursor": "opaque/+=="}
        )

    def test_base_url_can_be_overridden(self):
        sent, _ = self.send(
            ["reddit_post", POST_ID],
            [FakeResponse('{"id": "1q6pxwn"}')],
            env={"DESEARCH_BASE_URL": "https://api-dev.desearch.ai"},
        )
        self.assertEqual(
            sent[0].full_url,
            f"https://api-dev.desearch.ai/desearch/reddit/post/{POST_ID}",
        )

    def test_errors_and_single_objects_are_not_wrapped(self):
        error = HTTPError(
            "https://api.desearch.ai/desearch/reddit/search",
            422,
            "Unprocessable Entity",
            email.message.Message(),
            io.BytesIO(b'{"detail": "Invalid request parameters"}'),
        )
        _, printed = self.send(["reddit_search", "ai", "--cursor", "stale"], [error])
        self.assertEqual(printed, {"detail": "Invalid request parameters"})

        subreddit = {"name": "AskReddit", "weeklyActiveUsers": 1}
        _, printed = self.send(
            ["reddit_subreddit", "AskReddit"], [FakeResponse(json.dumps(subreddit))]
        )
        self.assertEqual(printed, subreddit)

    def test_cli_rejects_bad_input_before_any_request(self):
        self.assert_rejected(
            [
                ["reddit_search", " "],
                ["reddit_search", "x" * 501],
                ["reddit_search", "ai", "--sort", "hot"],
                ["reddit_search", "ai", "--timeframe", "hour"],
                ["reddit_subreddit", "r/"],
                ["reddit_subreddit_posts", "AskReddit", "--sort", "relevance"],
                ["reddit_post", " "],
                ["reddit_post", POST_ID, "--cursor", "CUR"],
                ["reddit_user", "spez"],
            ]
        )


if __name__ == "__main__":
    unittest.main()

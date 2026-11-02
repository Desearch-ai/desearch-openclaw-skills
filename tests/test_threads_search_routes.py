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

POST_CODE = "DK-BydcJHkF"


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


class ThreadsSearchRouteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.script = load_script(
            "desearch_threads_search_script",
            REPO_ROOT / "desearch-threads-search" / "scripts" / "desearch.py",
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
                    "threads_search",
                    "bittensor",
                    "--start-date",
                    "2026-01-01",
                    "--end-date",
                    "2026-10-30",
                ],
                ("POST", "/desearch/threads/search"),
                {
                    "body": {
                        "query": "bittensor",
                        "start_date": "2026-01-01",
                        "end_date": "2026-10-30",
                    }
                },
            ),
            (
                ["threads_search", "bittensor"],
                ("POST", "/desearch/threads/search"),
                {"body": {"query": "bittensor"}},
            ),
            (
                ["threads_search_users", "zuck"],
                ("POST", "/desearch/threads/search/users"),
                {"body": {"query": "zuck"}},
            ),
            (
                ["threads_profile", "@zuck"],
                ("GET", "/desearch/threads/profile/zuck"),
                {},
            ),
            (
                ["threads_profile_posts", "zuck"],
                ("GET", "/desearch/threads/profile/zuck/posts"),
                {},
            ),
            (
                ["threads_post", POST_CODE],
                ("GET", f"/desearch/threads/post/{POST_CODE}"),
                {},
            ),
        ]
        self.assertEqual({argv[0] for argv, _, _ in cases}, set(self.script.COMMANDS))
        for argv, call_args, call_kwargs in cases:
            with self.subTest(argv=argv):
                request, stdout = self.run_cli(argv)
                request.assert_called_once_with(*call_args, **call_kwargs)
                self.assertEqual(json.loads(stdout), [])

    def test_post_urls_are_sent_as_one_encoded_segment(self):
        request, _ = self.run_cli(
            ["threads_post", f"https://www.threads.com/@zuck/post/{POST_CODE}"]
        )
        request.assert_called_once_with(
            "GET",
            "/desearch/threads/post/https%3A%2F%2Fwww.threads.com%2F%40zuck%2Fpost%2F"
            + POST_CODE,
        )

    def test_lists_are_printed_plain_and_never_page(self):
        posts = [{"code": POST_CODE, "text": "post"}]
        sent, printed = self.send(
            ["threads_profile_posts", "zuck"],
            [FakeResponse(json.dumps(posts), {"x-desearch-next-cursor": "IGNORED"})],
        )
        self.assertEqual(printed, posts)
        self.assertEqual(
            sent[0].full_url,
            "https://api.desearch.ai/desearch/threads/profile/zuck/posts",
        )
        self.assertEqual(sent[0].get_header("Authorization"), "test-key")

        sent, printed = self.send(["threads_search", "bittensor"], [FakeResponse("[]")])
        self.assertEqual(printed, [])
        self.assertEqual(sent[0].get_method(), "POST")
        self.assertEqual(json.loads(sent[0].data), {"query": "bittensor"})

    def test_base_url_can_be_overridden(self):
        sent, _ = self.send(
            ["threads_search_users", "zuck"],
            [FakeResponse("[]")],
            env={"DESEARCH_BASE_URL": "https://api-dev.desearch.ai"},
        )
        self.assertEqual(
            sent[0].full_url,
            "https://api-dev.desearch.ai/desearch/threads/search/users",
        )

    def test_errors_and_single_objects_are_not_wrapped(self):
        error = HTTPError(
            f"https://api.desearch.ai/desearch/threads/post/{POST_CODE}",
            404,
            "Not Found",
            email.message.Message(),
            io.BytesIO(b"not json"),
        )
        _, printed = self.send(["threads_post", POST_CODE], [error])
        self.assertEqual(
            printed, {"error": "HTTP 404: Not Found", "details": "not json"}
        )

        post = {"code": POST_CODE, "comments": [], "threadItems": []}
        _, printed = self.send(
            ["threads_post", POST_CODE], [FakeResponse(json.dumps(post))]
        )
        self.assertEqual(printed, post)

    def test_cli_rejects_bad_input_before_any_request(self):
        self.assert_rejected(
            [
                ["threads_search", " "],
                ["threads_search", "x" * 501],
                ["threads_search", "ai", "--start-date", "2026/01/01"],
                ["threads_search", "ai", "--end-date", "2026-13-01"],
                ["threads_search", "ai", "--cursor", "CUR"],
                ["threads_search_users", "x" * 101],
                ["threads_profile", "@"],
                ["threads_profile_posts", "zuck", "--count", "5"],
                ["threads_post", " "],
                ["threads_hashtag", "ai"],
            ]
        )


if __name__ == "__main__":
    unittest.main()

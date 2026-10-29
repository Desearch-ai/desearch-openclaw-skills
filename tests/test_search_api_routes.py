import contextlib
import importlib.util
import io
import json
import unittest
from pathlib import Path
from unittest.mock import patch


REPO_ROOT = Path(__file__).resolve().parents[1]


def load_script(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class FakeResponse:
    def __init__(self, body):
        self.body = body

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def read(self):
        return self.body.encode()


class SearchApiRouteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.script = load_script(
            "desearch_search_api_script",
            REPO_ROOT / "desearch-search-api" / "scripts" / "desearch.py",
        )

    def run_cli(self, argv, response=None):
        with (
            patch.object(
                self.script, "api_request", return_value=response or {"results": []}
            ) as request,
            contextlib.redirect_stdout(io.StringIO()) as stdout,
        ):
            self.script.main(argv)
        return request, json.loads(stdout.getvalue())

    def test_search_sends_only_the_query_by_default(self):
        request, _ = self.run_cli(["search", "What is Bittensor?"])
        request.assert_called_once_with(
            "POST", "/search", body={"query": "What is Bittensor?"}
        )

    def test_search_sends_every_option(self):
        request, _ = self.run_cli(
            [
                "search",
                "  bittensor subnets  ",
                "--mode",
                "fast",
                "--count",
                "20",
                "--start-date",
                "2026-01-01",
                "--end-date",
                "2026-06-30",
                "--no-highlights",
                "--page-text",
            ]
        )
        request.assert_called_once_with(
            "POST",
            "/search",
            body={
                "query": "bittensor subnets",
                "mode": "fast",
                "count": 20,
                "start_date": "2026-01-01",
                "end_date": "2026-06-30",
                "highlights": False,
                "page_text": True,
            },
        )

    def test_search_prints_the_response(self):
        response = {
            "results": [
                {
                    "url": "https://docs.bittensor.com/",
                    "title": "Bittensor Docs",
                    "published_date": "2026-01-15",
                    "highlights": ["Bittensor is an open network..."],
                }
            ],
            "cost_usd": 0.01,
            "usage_count": 1,
            "service": "Search API",
            "currency": "USD",
        }
        _, printed = self.run_cli(["search", "bittensor"], response)
        self.assertEqual(printed, response)

    def test_api_request_posts_json_to_the_search_route(self):
        sent = []

        def fake_urlopen(request, timeout):
            sent.append(request)
            return FakeResponse('{"results": []}')

        with (
            patch.dict(self.script.os.environ, {"DESEARCH_API_KEY": "test-key"}),
            patch.object(self.script, "urlopen", side_effect=fake_urlopen),
            contextlib.redirect_stdout(io.StringIO()) as stdout,
        ):
            self.script.main(["search", "bittensor", "--count", "15"])

        self.assertEqual(json.loads(stdout.getvalue()), {"results": []})
        request = sent[0]
        self.assertEqual(request.full_url, "https://api.desearch.ai/search")
        self.assertEqual(request.get_method(), "POST")
        self.assertEqual(request.get_header("Authorization"), "test-key")
        self.assertEqual(json.loads(request.data), {"query": "bittensor", "count": 15})

    def test_cli_rejects_bad_input_before_any_request(self):
        bad_argvs = [
            ["search", "   "],
            ["search", "x" * 2001],
            ["search", "bittensor", "--count", "12"],
            ["search", "bittensor", "--mode", "slow"],
            ["search", "bittensor", "--start-date", "01/02/2026"],
            ["web", "bittensor"],
        ]
        for argv in bad_argvs:
            with self.subTest(argv=argv[:3]):
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

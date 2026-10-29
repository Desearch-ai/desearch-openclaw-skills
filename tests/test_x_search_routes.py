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


TRENDS = {
    "trends": [{"name": "#AI", "query": "%23AI", "rank": 1}],
    "woeid": {"name": "Worldwide", "id": 1},
}


class XTrendsRouteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.script = load_script(
            "desearch_x_search_script",
            REPO_ROOT / "desearch-x-search" / "scripts" / "desearch.py",
        )

    def run_cli(self, argv, response=None):
        with (
            patch.object(
                self.script, "api_request", return_value=response or TRENDS
            ) as request,
            contextlib.redirect_stdout(io.StringIO()) as stdout,
        ):
            self.script.main(argv)
        return request, json.loads(stdout.getvalue())

    def test_trends_sends_woeid_and_count(self):
        request, printed = self.run_cli(["x_trends", "23424977", "--count", "50"])

        request.assert_called_once_with(
            "GET", "/twitter/trends", params={"woeid": 23424977, "count": 50}
        )
        self.assertEqual(printed, TRENDS)

    def test_trends_leaves_count_to_the_api_default(self):
        request, _ = self.run_cli(["x_trends", "1"])
        request.assert_called_once_with(
            "GET", "/twitter/trends", params={"woeid": 1, "count": None}
        )

    def test_trends_rejects_bad_input_before_any_request(self):
        cases = [
            (["x_trends", "worldwide"], "numeric WOEID"),
            (["x_trends", "1", "--count", "29"], "between 30 and 100"),
            (["x_trends", "1", "--count", "101"], "between 30 and 100"),
        ]
        for argv, message in cases:
            with self.subTest(argv=argv):
                with (
                    patch.object(self.script, "api_request") as request,
                    contextlib.redirect_stdout(io.StringIO()) as stdout,
                ):
                    self.script.main(argv)

                request.assert_not_called()
                self.assertIn(message, json.loads(stdout.getvalue())["error"])

    def test_trends_request_url(self):
        sent = []

        def fake_urlopen(request, timeout):
            sent.append(request)
            return FakeResponse(json.dumps(TRENDS))

        with (
            patch.dict(self.script.os.environ, {"DESEARCH_API_KEY": "test-key"}),
            patch.object(self.script, "urlopen", side_effect=fake_urlopen),
            contextlib.redirect_stdout(io.StringIO()) as stdout,
        ):
            self.script.main(["x_trends", "1", "--count", "30"])

        self.assertEqual(json.loads(stdout.getvalue()), TRENDS)
        request = sent[0]
        self.assertEqual(
            request.full_url, "https://api.desearch.ai/twitter/trends?woeid=1&count=30"
        )
        self.assertEqual(request.get_method(), "GET")
        self.assertEqual(request.get_header("Authorization"), "test-key")

    def test_existing_commands_still_parse(self):
        request, _ = self.run_cli(
            ["x_post", "1892527552029499853"], response={"id": "1"}
        )
        request.assert_called_once_with(
            "GET", "/twitter/post", params={"id": "1892527552029499853"}
        )


if __name__ == "__main__":
    unittest.main()

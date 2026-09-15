import importlib.util
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch


REPO_ROOT = Path(__file__).resolve().parents[1]


def load_script(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ExtractRouteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.extract_script = load_script(
            "desearch_extract_script",
            REPO_ROOT / "desearch-extract" / "scripts" / "desearch.py",
        )
        cls.crawl_script = load_script(
            "desearch_crawl_script",
            REPO_ROOT / "desearch-crawl" / "scripts" / "desearch.py",
        )

    def test_new_skill_calls_canonical_extract_route(self):
        args = SimpleNamespace(
            url="https://desearch.ai",
            output_format="text",
            js=True,
            wait=250,
        )
        with patch.object(
            self.extract_script, "api_request", return_value="content"
        ) as request:
            result = self.extract_script.cmd_extract(args)

        self.assertEqual(result, "content")
        request.assert_called_once_with(
            "GET",
            "/web/extract",
            params={
                "url": "https://desearch.ai",
                "format": "text",
                "js": "true",
                "wait": 250,
            },
        )

    def test_legacy_skill_keeps_calling_crawl_route(self):
        args = SimpleNamespace(
            url="https://desearch.ai",
            crawl_format="html",
        )
        with patch.object(
            self.crawl_script, "api_request", return_value="content"
        ) as request:
            result = self.crawl_script.cmd_crawl(args)

        self.assertEqual(result, "content")
        request.assert_called_once_with(
            "GET",
            "/web/crawl",
            params={"url": "https://desearch.ai", "format": "html"},
        )


if __name__ == "__main__":
    unittest.main()

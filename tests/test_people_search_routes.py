import contextlib
import importlib.util
import io
import json
import tempfile
import unittest
import uuid
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch


REPO_ROOT = Path(__file__).resolve().parents[1]

TASK_ID = "5b33f3ee-168b-4780-9c8e-63a626781872"


def load_script(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def search_args(**overrides):
    values = {
        "platform": "x",
        "query": "Indie hackers building in public who share their MRR",
        "count": None,
        "min_score": None,
        "exclude": None,
        "idempotency_key": None,
        "min_followers": None,
        "max_followers": None,
        "min_subscribers": None,
        "max_subscribers": None,
        "verified_only": False,
        "require_contact": False,
        "countries": None,
        "keywords": None,
        "exclude_keywords": None,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def library_args(**overrides):
    values = {
        "has": None,
        "min_audience": None,
        "max_audience": None,
        "min_score": None,
        "location": None,
        "verified": False,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


class PeopleSearchRouteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.script = load_script(
            "desearch_people_search_script",
            REPO_ROOT / "desearch-people-search" / "scripts" / "desearch.py",
        )

    def run_quietly(self, handler, args):
        with contextlib.redirect_stderr(io.StringIO()) as stderr:
            result = handler(args)
        return result, stderr.getvalue()

    def test_search_posts_body_filters_and_idempotency_key(self):
        args = search_args(
            count=10,
            min_score=70,
            exclude=["already_contacted"],
            idempotency_key="retry-key-1",
            min_followers=1000,
            verified_only=True,
            countries=["US", "GB"],
            keywords=["MRR"],
        )
        task = {"task_id": TASK_ID, "status": "queued", "reserved_cost_usd": 0.4}
        with patch.object(self.script, "api_request", return_value=task) as request:
            result, stderr = self.run_quietly(self.script.cmd_people_search, args)

        self.assertEqual(result, task)
        request.assert_called_once_with(
            "POST",
            "/desearch/people/search/x",
            body={
                "query": "Indie hackers building in public who share their MRR",
                "count": 10,
                "min_score": 70,
                "exclude": ["already_contacted"],
                "filters": {
                    "min_followers": 1000,
                    "verified_only": True,
                    "countries": ["US", "GB"],
                    "keywords": ["MRR"],
                },
            },
            headers={"Idempotency-Key": "retry-key-1"},
        )
        self.assertIn("retry-key-1", stderr)

    def test_search_without_filters_sends_only_query(self):
        args = search_args(platform="linkedin", query="Heads of growth at fintech startups")
        with patch.object(self.script, "api_request", return_value={}) as request:
            self.run_quietly(self.script.cmd_people_search, args)

        method, path = request.call_args.args
        self.assertEqual((method, path), ("POST", "/desearch/people/search/linkedin"))
        self.assertEqual(
            request.call_args.kwargs["body"],
            {"query": "Heads of growth at fintech startups"},
        )

    def test_search_generates_an_idempotency_key_when_none_is_given(self):
        args = search_args(platform="tiktok", query="Skincare creators")
        with patch.object(self.script, "api_request", return_value={}) as request:
            _, stderr = self.run_quietly(self.script.cmd_people_search, args)

        key = request.call_args.kwargs["headers"]["Idempotency-Key"]
        self.assertEqual(str(uuid.UUID(key)), key)
        self.assertIn(key, stderr)

    def test_search_rejects_another_platforms_filter_before_the_billed_call(self):
        cases = [
            ("youtube", {"verified_only": True}, "--verified-only"),
            ("x", {"min_subscribers": 1000}, "--min-subscribers"),
            ("linkedin", {"require_contact": True}, "--require-contact"),
            ("tiktok", {"countries": ["US"]}, "--countries"),
        ]
        for platform, overrides, flag in cases:
            with self.subTest(platform=platform, flag=flag):
                args = search_args(platform=platform, **overrides)
                with patch.object(self.script, "api_request") as request:
                    result, _ = self.run_quietly(self.script.cmd_people_search, args)

                request.assert_not_called()
                self.assertIn(flag, result["error"])
                self.assertIn(platform, result["error"])

    def test_youtube_search_uses_subscriber_filters(self):
        args = search_args(
            platform="youtube",
            query="Home espresso reviewers",
            min_subscribers=10000,
            max_subscribers=500000,
            require_contact=True,
        )
        with patch.object(self.script, "api_request", return_value={}) as request:
            self.run_quietly(self.script.cmd_people_search, args)

        self.assertEqual(
            request.call_args.kwargs["body"]["filters"],
            {
                "min_subscribers": 10000,
                "max_subscribers": 500000,
                "require_contact": True,
            },
        )

    def test_task_reads_one_task(self):
        args = SimpleNamespace(task_id=TASK_ID)
        with patch.object(self.script, "api_request", return_value={}) as request:
            self.script.cmd_people_task(args)

        request.assert_called_once_with("GET", f"/desearch/people/tasks/{TASK_ID}")

    def test_wait_polls_until_the_task_ends(self):
        args = SimpleNamespace(task_id=TASK_ID, interval=5, timeout=600)
        responses = [
            {"task_id": TASK_ID, "status": "queued", "result_count": 0, "count": 10},
            {"task_id": TASK_ID, "status": "running", "result_count": 4, "count": 10},
            {"task_id": TASK_ID, "status": "completed", "result_count": 9, "count": 10},
        ]
        with patch.object(
            self.script, "api_request", side_effect=responses
        ) as request, patch.object(self.script.time, "sleep") as sleep:
            result, _ = self.run_quietly(self.script.cmd_people_wait, args)

        self.assertEqual(result["status"], "completed")
        self.assertEqual(request.call_count, 3)
        self.assertEqual(sleep.call_count, 2)

    def test_wait_stops_when_the_task_is_paused(self):
        args = SimpleNamespace(task_id=TASK_ID, interval=5, timeout=600)
        with patch.object(
            self.script, "api_request", return_value={"status": "paused"}
        ), patch.object(self.script.time, "sleep") as sleep:
            result, _ = self.run_quietly(self.script.cmd_people_wait, args)

        self.assertEqual(result["status"], "paused")
        sleep.assert_not_called()

    def test_wait_returns_api_errors_without_polling_again(self):
        args = SimpleNamespace(task_id=TASK_ID, interval=5, timeout=600)
        error = {"detail": "Task not found"}
        with patch.object(
            self.script, "api_request", return_value=error
        ) as request, patch.object(self.script.time, "sleep"):
            result, _ = self.run_quietly(self.script.cmd_people_wait, args)

        self.assertEqual(result, error)
        request.assert_called_once()

    def test_wait_gives_up_after_the_timeout(self):
        args = SimpleNamespace(task_id=TASK_ID, interval=10, timeout=30)
        clock = iter([0, 0, 10, 20, 31])
        with patch.object(
            self.script, "api_request", return_value={"status": "running"}
        ), patch.object(self.script.time, "sleep"), patch.object(
            self.script.time, "monotonic", side_effect=lambda: next(clock)
        ):
            result, _ = self.run_quietly(self.script.cmd_people_wait, args)

        self.assertIn("Still running after 30 seconds", result["error"])
        self.assertEqual(result["task"], {"status": "running"})

    def test_results_reads_one_page(self):
        args = SimpleNamespace(task_id=TASK_ID, cursor="0", limit=50, all=False)
        page = {"results": [{"handle": "a"}], "next_cursor": "1", "has_more": False}
        with patch.object(self.script, "api_request", return_value=page) as request:
            result = self.script.cmd_people_results(args)

        self.assertEqual(result, page)
        request.assert_called_once_with(
            "GET",
            f"/desearch/people/tasks/{TASK_ID}/results",
            params={"cursor": "0", "limit": 50},
        )

    def test_results_all_follows_next_cursor(self):
        args = SimpleNamespace(task_id=TASK_ID, cursor=None, limit=2, all=True)
        pages = [
            {
                "task_id": TASK_ID,
                "status": "completed",
                "results": [{"handle": "a"}, {"handle": "b"}],
                "next_cursor": "2",
                "has_more": True,
            },
            {
                "task_id": TASK_ID,
                "status": "completed",
                "results": [{"handle": "c"}],
                "next_cursor": "3",
                "has_more": False,
            },
        ]
        with patch.object(self.script, "api_request", side_effect=pages) as request:
            result = self.script.cmd_people_results(args)

        self.assertEqual([p["handle"] for p in result["results"]], ["a", "b", "c"])
        self.assertEqual(result["next_cursor"], "3")
        self.assertFalse(result["has_more"])
        self.assertEqual(
            request.call_args_list[1].kwargs["params"], {"cursor": "2", "limit": 2}
        )

    def test_export_writes_csv_to_a_file(self):
        csv_text = "handle,name\nexample,Example Person\n"
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "people.csv"
            args = SimpleNamespace(
                task_id=TASK_ID,
                export_format="csv",
                output=str(output),
                **vars(library_args(has=["email", "website"], min_audience=1000)),
            )
            with patch.object(
                self.script, "api_request", return_value=csv_text
            ) as request:
                result = self.script.cmd_people_export(args)

            self.assertEqual(output.read_text(encoding="utf-8"), csv_text)

        self.assertEqual(result["format"], "csv")
        self.assertEqual(result["bytes"], len(csv_text.encode("utf-8")))
        request.assert_called_once_with(
            "GET",
            f"/desearch/people/tasks/{TASK_ID}/export",
            params={"format": "csv", "has": "email,website", "min_audience": 1000},
            parse_json=False,
        )

    def test_export_returns_api_errors_instead_of_writing_them(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "people.jsonl"
            args = SimpleNamespace(
                task_id=TASK_ID,
                export_format="jsonl",
                output=str(output),
                **vars(library_args()),
            )
            error_body = json.dumps({"detail": "Results expired"})
            with patch.object(self.script, "api_request", return_value=error_body):
                result = self.script.cmd_people_export(args)

            self.assertFalse(output.exists())

        self.assertEqual(result, {"detail": "Results expired"})

    def test_control_commands_post_to_their_action_route(self):
        for command, action in [
            ("people_pause", "pause"),
            ("people_resume", "resume"),
            ("people_cancel", "cancel"),
        ]:
            with self.subTest(command=command):
                args = SimpleNamespace(command=command, task_id=TASK_ID)
                with patch.object(
                    self.script, "api_request", return_value={}
                ) as request:
                    self.script.cmd_people_control(args)

                request.assert_called_once_with(
                    "POST", f"/desearch/people/tasks/{TASK_ID}/{action}"
                )

    def test_tasks_lists_with_filters(self):
        args = SimpleNamespace(
            platform="x", status=["running", "paused"], limit=20, cursor=None
        )
        with patch.object(self.script, "api_request", return_value={}) as request:
            self.script.cmd_people_tasks(args)

        request.assert_called_once_with(
            "GET",
            "/desearch/people/tasks",
            params={
                "platform": "x",
                "status": "running,paused",
                "limit": 20,
                "cursor": None,
            },
        )

    def test_profiles_library_sends_filters(self):
        args = SimpleNamespace(
            platform="tiktok",
            query="skincare",
            sort="audience",
            limit=100,
            cursor="abc",
            **vars(
                library_args(
                    has=["email", "instagram"],
                    min_audience=1000,
                    max_audience=500000,
                    min_score=60,
                    location="united states",
                    verified=True,
                )
            ),
        )
        with patch.object(self.script, "api_request", return_value={}) as request:
            self.script.cmd_people_profiles(args)

        request.assert_called_once_with(
            "GET",
            "/desearch/people/profiles",
            params={
                "platform": "tiktok",
                "q": "skincare",
                "sort": "audience",
                "limit": 100,
                "cursor": "abc",
                "has": "email,instagram",
                "min_audience": 1000,
                "max_audience": 500000,
                "min_score": 60,
                "location": "united states",
                "verified": "true",
            },
        )

    def test_profiles_rejects_verified_on_platforms_without_it(self):
        for platform in ["youtube", "linkedin"]:
            with self.subTest(platform=platform):
                args = SimpleNamespace(
                    platform=platform,
                    query=None,
                    sort=None,
                    limit=None,
                    cursor=None,
                    **vars(library_args(verified=True)),
                )
                with patch.object(self.script, "api_request") as request:
                    result = self.script.cmd_people_profiles(args)

                request.assert_not_called()
                self.assertIn("--verified", result["error"])

    def test_profiles_export_sends_search_filters_and_writes_a_file(self):
        jsonl = '{"handle": "a"}\n{"handle": "b"}\n'
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "library.jsonl"
            args = SimpleNamespace(
                platform="x",
                export_format="jsonl",
                output=str(output),
                query="founder",
                sort="audience",
                **vars(
                    library_args(
                        has=["email"], min_score=70, location="united states", verified=True
                    )
                ),
            )
            with patch.object(self.script, "api_request", return_value=jsonl) as request:
                result = self.script.cmd_people_profiles_export(args)

            self.assertEqual(output.read_text(encoding="utf-8"), jsonl)

        self.assertEqual(
            result,
            {"saved": str(output), "format": "jsonl", "bytes": len(jsonl.encode("utf-8"))},
        )
        request.assert_called_once_with(
            "GET",
            "/desearch/people/profiles/export",
            params={
                "platform": "x",
                "format": "jsonl",
                "q": "founder",
                "sort": "audience",
                "has": "email",
                "min_score": 70,
                "location": "united states",
                "verified": "true",
            },
            parse_json=False,
        )

    def test_profiles_export_prints_csv_and_passes_api_errors_through(self):
        args = SimpleNamespace(
            platform="youtube",
            export_format="csv",
            output=None,
            query=None,
            sort=None,
            **vars(library_args()),
        )
        csv_text = "handle,name\nexample,Example Person\n"
        with patch.object(self.script, "api_request", return_value=csv_text) as request:
            self.assertEqual(self.script.cmd_people_profiles_export(args), csv_text)
        self.assertEqual(
            request.call_args.kwargs["params"],
            {"platform": "youtube", "format": "csv", "q": None, "sort": None},
        )

        error = {"detail": "Unknown platform"}
        with patch.object(self.script, "api_request", return_value=json.dumps(error)):
            self.assertEqual(self.script.cmd_people_profiles_export(args), error)

    def test_profiles_export_rejects_verified_on_platforms_without_it(self):
        args = SimpleNamespace(
            platform="linkedin",
            export_format="csv",
            output=None,
            query=None,
            sort=None,
            **vars(library_args(verified=True)),
        )
        with patch.object(self.script, "api_request") as request:
            result = self.script.cmd_people_profiles_export(args)

        request.assert_not_called()
        self.assertIn("--verified", result["error"])

    def test_cli_parses_a_profiles_export(self):
        csv_text = "handle\nexample\n"
        argv = [
            "people_profiles_export",
            "tiktok",
            "--query",
            "skincare",
            "--has",
            "email,instagram",
            "--min-audience",
            "1000",
        ]
        with patch.object(
            self.script, "api_request", return_value=csv_text
        ) as request, contextlib.redirect_stdout(io.StringIO()) as stdout:
            self.script.main(argv)

        self.assertEqual(stdout.getvalue(), csv_text + "\n")
        request.assert_called_once_with(
            "GET",
            "/desearch/people/profiles/export",
            params={
                "platform": "tiktok",
                "format": "csv",
                "q": "skincare",
                "sort": None,
                "has": "email,instagram",
                "min_audience": 1000,
            },
            parse_json=False,
        )

    def test_api_request_sends_idempotency_header_and_can_skip_json_parsing(self):
        class FakeResponse:
            def __init__(self, body):
                self.body = body

            def __enter__(self):
                return self

            def __exit__(self, *exc):
                return False

            def read(self):
                return self.body.encode()

        sent = []

        def fake_urlopen(request, timeout):
            sent.append(request)
            return FakeResponse('{"handle": "only-one-person"}')

        with patch.dict(
            self.script.os.environ, {"DESEARCH_API_KEY": "test-key"}
        ), patch.object(self.script, "urlopen", side_effect=fake_urlopen):
            raw = self.script.api_request(
                "POST",
                "/desearch/people/search/x",
                body={"query": "Indie hackers"},
                headers={"Idempotency-Key": "key-1"},
                parse_json=False,
            )

        self.assertEqual(raw, '{"handle": "only-one-person"}')
        request = sent[0]
        self.assertEqual(
            request.full_url, "https://api.desearch.ai/desearch/people/search/x"
        )
        self.assertEqual(request.get_method(), "POST")
        self.assertEqual(request.get_header("Idempotency-key"), "key-1")
        self.assertEqual(request.get_header("Authorization"), "test-key")
        self.assertEqual(json.loads(request.data), {"query": "Indie hackers"})

    def test_cli_parses_a_search_and_prints_json(self):
        task = {"task_id": TASK_ID, "status": "queued"}
        argv = [
            "people_search",
            "youtube",
            "Home espresso reviewers",
            "--count",
            "20",
            "--min-subscribers",
            "10000",
            "--countries",
            "US, GB",
            "--idempotency-key",
            "cli-key",
        ]
        with patch.object(
            self.script, "api_request", return_value=task
        ) as request, contextlib.redirect_stdout(
            io.StringIO()
        ) as stdout, contextlib.redirect_stderr(io.StringIO()):
            self.script.main(argv)

        self.assertEqual(json.loads(stdout.getvalue()), task)
        request.assert_called_once_with(
            "POST",
            "/desearch/people/search/youtube",
            body={
                "query": "Home espresso reviewers",
                "count": 20,
                "filters": {"min_subscribers": 10000, "countries": ["US", "GB"]},
            },
            headers={"Idempotency-Key": "cli-key"},
        )

    def test_cli_rejects_bad_input_before_any_request(self):
        bad_argvs = [
            ["people_search", "x", "Indie hackers", "--count", "3"],
            ["people_search", "x", "ab"],
            ["people_search", "facebook", "Indie hackers"],
            ["people_task", "not-a-task-id"],
            ["people_profiles", "x", "--has", "email,phone"],
            ["people_tasks", "--status", "running,sleeping"],
            ["people_export", TASK_ID, "--format", "xlsx"],
            ["people_profiles_export", "facebook"],
            ["people_profiles_export", "x", "--format", "xlsx"],
            ["people_profiles_export", "x", "--sort", "followers"],
            ["people_profiles_export", "x", "--limit", "10"],
        ]
        for argv in bad_argvs:
            with self.subTest(argv=argv):
                with patch.object(
                    self.script, "api_request"
                ) as request, contextlib.redirect_stderr(
                    io.StringIO()
                ), self.assertRaises(SystemExit) as exit_info:
                    self.script.main(argv)

                self.assertEqual(exit_info.exception.code, 2)
                request.assert_not_called()


if __name__ == "__main__":
    unittest.main()

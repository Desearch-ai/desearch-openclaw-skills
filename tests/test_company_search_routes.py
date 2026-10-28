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
from urllib.error import HTTPError, URLError


REPO_ROOT = Path(__file__).resolve().parents[1]

TASK_ID = "5b33f3ee-168b-4780-9c8e-63a626781872"


def load_script(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def search_args(**overrides):
    values = {
        "query": "Series A fintech startups in Berlin building payment infrastructure",
        "count": None,
        "min_score": None,
        "exclude": None,
        "countries": None,
        "require": None,
        "roles": None,
        "no_infer_emails": False,
        "no_verify_emails": False,
        "metadata": None,
        "idempotency_key": None,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def enrich_args(**overrides):
    values = {
        "domains": [],
        "file": None,
        "roles": None,
        "no_infer_emails": False,
        "no_verify_emails": False,
        "metadata": None,
        "idempotency_key": None,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def tasks_args(**overrides):
    values = {
        "task_type": None,
        "status": None,
        "limit": None,
        "cursor": None,
        "metadata": None,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


class FakeResponse:
    def __init__(self, body: str):
        self.body = body

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def read(self):
        return self.body.encode()


def http_error(code: int, body: str, reason: str = "Error") -> HTTPError:
    return HTTPError(
        "https://api.desearch.ai/x", code, reason, hdrs=None, fp=io.BytesIO(body.encode())
    )


class CompanySearchRouteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.script = load_script(
            "desearch_company_search_script",
            REPO_ROOT / "desearch-company-search" / "scripts" / "desearch.py",
        )

    def run_quietly(self, handler, args):
        with contextlib.redirect_stderr(io.StringIO()) as stderr:
            result = handler(args)
        return result, stderr.getvalue()

    def run_cli(self, argv):
        with contextlib.redirect_stdout(
            io.StringIO()
        ) as stdout, contextlib.redirect_stderr(io.StringIO()) as stderr:
            self.script.main(argv)
        return stdout.getvalue(), stderr.getvalue()

    # company_search

    def test_search_posts_body_filters_and_idempotency_key(self):
        args = search_args(
            count=25,
            min_score=60,
            exclude=["stripe.com", "https://www.adyen.com/"],
            countries=["DE"],
            require=["email", "leader"],
            roles=["ceo", "founder", "cto", "cfo"],
            no_infer_emails=True,
            no_verify_emails=True,
            metadata=[("campaign", "q4"), ("workspace_id", "ws_42")],
            idempotency_key="retry-key-1",
        )
        task = {"task_id": TASK_ID, "status": "queued", "reserved_cost_usd": 2.25}
        with patch.object(self.script, "api_request", return_value=task) as request:
            result, stderr = self.run_quietly(self.script.cmd_company_search, args)

        self.assertEqual(result, task)
        request.assert_called_once_with(
            "POST",
            "/desearch/companies/search",
            body={
                "query": "Series A fintech startups in Berlin building payment infrastructure",
                "count": 25,
                "min_score": 60,
                "exclude": ["stripe.com", "https://www.adyen.com/"],
                "roles": ["ceo", "founder", "cto", "cfo"],
                "infer_emails": False,
                "verify_emails": False,
                "filters": {"countries": ["DE"], "require": ["email", "leader"]},
                "metadata": {"campaign": "q4", "workspace_id": "ws_42"},
            },
            headers={"Idempotency-Key": "retry-key-1"},
        )
        self.assertIn("retry-key-1", stderr)
        self.assertIn("billed Company Search", stderr)

    def test_search_without_options_sends_only_query(self):
        args = search_args(query="Robotics startups in Munich")
        with patch.object(self.script, "api_request", return_value={}) as request:
            self.run_quietly(self.script.cmd_company_search, args)

        method, path = request.call_args.args
        self.assertEqual((method, path), ("POST", "/desearch/companies/search"))
        # API defaults (count 25, default roles, infer and verify emails) are not sent.
        self.assertEqual(
            request.call_args.kwargs["body"], {"query": "Robotics startups in Munich"}
        )

    def test_search_generates_an_idempotency_key_when_none_is_given(self):
        args = search_args()
        with patch.object(self.script, "api_request", return_value={}) as request:
            _, stderr = self.run_quietly(self.script.cmd_company_search, args)

        key = request.call_args.kwargs["headers"]["Idempotency-Key"]
        self.assertEqual(str(uuid.UUID(key)), key)
        self.assertIn(f"--idempotency-key {key}", stderr)

    def test_search_rejects_bad_input_before_the_billed_call(self):
        cases = [
            ({"countries": [f"C{i}" for i in range(21)]}, "--countries"),
            ({"metadata": [("campaign", "q4"), ("campaign", "q1")]}, "more than once"),
            ({"metadata": [(f"k{i}", "v") for i in range(11)]}, "At most 10"),
        ]
        for overrides, message in cases:
            with self.subTest(message=message):
                args = search_args(**overrides)
                with patch.object(self.script, "api_request") as request:
                    result, _ = self.run_quietly(self.script.cmd_company_search, args)

                request.assert_not_called()
                self.assertIn(message, result["error"])

    # company_enrich

    def test_enrich_posts_domains_from_arguments_and_file(self):
        with tempfile.TemporaryDirectory() as directory:
            domain_file = Path(directory) / "domains.txt"
            domain_file.write_text(
                "# companies from the trade fair\n"
                "gamma.de\n"
                "\n"
                "delta.com, epsilon.io\n"
                "https://WWW.ACME.com/contact\n",
                encoding="utf-8",
            )
            args = enrich_args(
                domains=["acme.com", "https://www.beta.io/about"],
                file=str(domain_file),
                roles=["ceo", "cto"],
                no_verify_emails=True,
                metadata=[("campaign", "q4")],
                idempotency_key="enrich-key",
            )
            task = {"task_id": TASK_ID, "status": "queued", "count": 5}
            with patch.object(
                self.script, "api_request", return_value=task
            ) as request:
                result, stderr = self.run_quietly(self.script.cmd_company_enrich, args)

        self.assertEqual(result, task)
        request.assert_called_once_with(
            "POST",
            "/desearch/companies/enrich",
            body={
                # The duplicate https://WWW.ACME.com/contact is dropped: one reservation per company.
                "domains": [
                    "acme.com",
                    "https://www.beta.io/about",
                    "gamma.de",
                    "delta.com",
                    "epsilon.io",
                ],
                "roles": ["ceo", "cto"],
                "verify_emails": False,
                "metadata": {"campaign": "q4"},
            },
            headers={"Idempotency-Key": "enrich-key"},
        )
        self.assertIn("Company Enrich of 5 domains", stderr)
        self.assertIn("enrich-key", stderr)

    def test_enrich_reads_domains_from_stdin(self):
        args = enrich_args(file="-")
        with patch.object(
            self.script.sys, "stdin", io.StringIO("acme.com\nbeta.io\n")
        ), patch.object(self.script, "api_request", return_value={}) as request:
            _, stderr = self.run_quietly(self.script.cmd_company_enrich, args)

        body = request.call_args.kwargs["body"]
        self.assertEqual(body, {"domains": ["acme.com", "beta.io"]})
        key = request.call_args.kwargs["headers"]["Idempotency-Key"]
        self.assertEqual(str(uuid.UUID(key)), key)
        self.assertIn(key, stderr)

    def test_enrich_rejects_bad_input_before_the_billed_call(self):
        cases = [
            (enrich_args(), "at least one domain"),
            (enrich_args(domains=[" , "]), "at least one domain"),
            (
                enrich_args(domains=[f"company{i}.com" for i in range(201)]),
                "at most 200",
            ),
            (enrich_args(file="/nonexistent/domains.txt"), "Cannot read"),
            (
                enrich_args(
                    domains=["acme.com"], metadata=[("a", "1"), ("a", "2")]
                ),
                "more than once",
            ),
        ]
        for args, message in cases:
            with self.subTest(message=message):
                with patch.object(self.script, "api_request") as request:
                    result, _ = self.run_quietly(self.script.cmd_company_enrich, args)

                request.assert_not_called()
                self.assertIn(message, result["error"])

    def test_enrich_accepts_200_unique_domains_after_dropping_duplicates(self):
        domains = [f"company{i}.com" for i in range(200)]
        args = enrich_args(domains=domains + ["https://www.company0.com/"])
        with patch.object(self.script, "api_request", return_value={}) as request:
            self.run_quietly(self.script.cmd_company_enrich, args)

        self.assertEqual(request.call_args.kwargs["body"]["domains"], domains)

    def test_domain_key_matches_the_api_normalization(self):
        cases = {
            "Acme.com": "acme.com",
            "https://www.acme.com/about?x=1": "acme.com",
            "www.acme.co.uk": "acme.co.uk",
            "acme.com.": "acme.com",
            "http://acme.com:8080/": "acme.com",
            "www.io": "www.io",
        }
        for value, key in cases.items():
            with self.subTest(value=value):
                self.assertEqual(self.script.domain_key(value), key)

    # company_task / company_wait

    def test_task_reads_one_task(self):
        args = SimpleNamespace(task_id=TASK_ID)
        with patch.object(self.script, "api_request", return_value={}) as request:
            self.script.cmd_company_task(args)

        request.assert_called_once_with("GET", f"/desearch/companies/tasks/{TASK_ID}")

    def test_wait_keeps_polling_while_the_task_is_enriching(self):
        args = SimpleNamespace(task_id=TASK_ID, interval=5, timeout=600)
        responses = [
            {"status": "queued", "stage": None, "result_count": 0, "count": 25},
            {"status": "running", "stage": "processing", "result_count": 10, "count": 25},
            {
                "status": "running",
                "stage": "enriching",
                "result_count": 25,
                "count": 25,
                "progress": {"enrichment": {"published": 25, "complete": 18}},
            },
            {"status": "completed", "stage": None, "result_count": 25, "count": 25},
        ]
        with patch.object(
            self.script, "api_request", side_effect=responses
        ) as request, patch.object(self.script.time, "sleep") as sleep:
            result, stderr = self.run_quietly(self.script.cmd_company_wait, args)

        self.assertEqual(result["status"], "completed")
        self.assertEqual(request.call_count, 4)
        self.assertEqual(sleep.call_count, 3)
        for call in request.call_args_list:
            self.assertEqual(call.args, ("GET", f"/desearch/companies/tasks/{TASK_ID}"))
        self.assertIn("stage=enriching delivered=25/25 fully_enriched=18", stderr)

    def test_wait_stops_when_the_task_is_paused(self):
        args = SimpleNamespace(task_id=TASK_ID, interval=5, timeout=600)
        with patch.object(
            self.script, "api_request", return_value={"status": "paused"}
        ), patch.object(self.script.time, "sleep") as sleep:
            result, _ = self.run_quietly(self.script.cmd_company_wait, args)

        self.assertEqual(result["status"], "paused")
        sleep.assert_not_called()

    def test_wait_returns_api_errors_without_polling_again(self):
        args = SimpleNamespace(task_id=TASK_ID, interval=5, timeout=600)
        error = {"detail": "Task not found"}
        with patch.object(
            self.script, "api_request", return_value=error
        ) as request, patch.object(self.script.time, "sleep"):
            result, _ = self.run_quietly(self.script.cmd_company_wait, args)

        self.assertEqual(result, error)
        request.assert_called_once()

    def test_wait_gives_up_after_the_timeout(self):
        args = SimpleNamespace(task_id=TASK_ID, interval=10, timeout=30)
        clock = iter([0, 0, 10, 20, 31])
        running = {"status": "running", "stage": "enriching"}
        with patch.object(
            self.script, "api_request", return_value=running
        ), patch.object(self.script.time, "sleep"), patch.object(
            self.script.time, "monotonic", side_effect=lambda: next(clock)
        ):
            result, _ = self.run_quietly(self.script.cmd_company_wait, args)

        self.assertIn("Still running (stage enriching) after 30 seconds", result["error"])
        self.assertEqual(result["task"], running)

    # company_results

    def test_results_reads_one_page(self):
        args = SimpleNamespace(task_id=TASK_ID, cursor="0", limit=50, all=False)
        page = {"results": [{"domain": "acme.com"}], "next_cursor": "1", "has_more": False}
        with patch.object(self.script, "api_request", return_value=page) as request:
            result = self.script.cmd_company_results(args)

        self.assertEqual(result, page)
        request.assert_called_once_with(
            "GET",
            f"/desearch/companies/tasks/{TASK_ID}/results",
            params={"cursor": "0", "limit": 50},
        )

    def test_results_all_follows_next_cursor(self):
        args = SimpleNamespace(task_id=TASK_ID, cursor=None, limit=2, all=True)
        pages = [
            {
                "task_id": TASK_ID,
                "status": "running",
                "results": [{"domain": "acme.com"}, {"domain": "beta.io"}],
                "next_cursor": "2",
                "has_more": True,
            },
            {
                "task_id": TASK_ID,
                "status": "running",
                "results": [{"domain": "gamma.de"}],
                "next_cursor": "3",
                "has_more": False,
            },
        ]
        with patch.object(self.script, "api_request", side_effect=pages) as request:
            result = self.script.cmd_company_results(args)

        self.assertEqual(
            [c["domain"] for c in result["results"]], ["acme.com", "beta.io", "gamma.de"]
        )
        self.assertEqual(result["next_cursor"], "3")
        self.assertFalse(result["has_more"])
        self.assertEqual(
            request.call_args_list[0].kwargs["params"], {"cursor": None, "limit": 2}
        )
        self.assertEqual(
            request.call_args_list[1].kwargs["params"], {"cursor": "2", "limit": 2}
        )

    def test_results_all_returns_an_expired_error_as_is(self):
        args = SimpleNamespace(task_id=TASK_ID, cursor=None, limit=None, all=True)
        error = {"detail": "Results expired 30 days after the task ended"}
        with patch.object(self.script, "api_request", return_value=error):
            result = self.script.cmd_company_results(args)

        self.assertEqual(result, error)

    # company_export

    def test_export_writes_csv_to_a_file(self):
        csv_text = "domain,name,url\nacme.com,Acme,https://acme.com/\n"
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "companies.csv"
            args = SimpleNamespace(
                task_id=TASK_ID, export_format="csv", output=str(output)
            )
            with patch.object(
                self.script, "api_request", return_value=csv_text
            ) as request:
                result = self.script.cmd_company_export(args)

            self.assertEqual(output.read_text(encoding="utf-8"), csv_text)

        self.assertEqual(result["format"], "csv")
        self.assertEqual(result["bytes"], len(csv_text.encode("utf-8")))
        request.assert_called_once_with(
            "GET",
            f"/desearch/companies/tasks/{TASK_ID}/export",
            params={"format": "csv"},
            parse_json=False,
        )

    def test_export_prints_jsonl_without_an_output_file(self):
        jsonl = '{"domain": "acme.com"}\n{"domain": "beta.io"}\n'
        args = SimpleNamespace(task_id=TASK_ID, export_format="jsonl", output=None)
        with patch.object(self.script, "api_request", return_value=jsonl) as request:
            result = self.script.cmd_company_export(args)

        self.assertEqual(result, jsonl)
        self.assertEqual(request.call_args.kwargs["params"], {"format": "jsonl"})

    def test_export_returns_api_errors_instead_of_writing_them(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "companies.jsonl"
            args = SimpleNamespace(
                task_id=TASK_ID, export_format="jsonl", output=str(output)
            )
            error_body = json.dumps({"detail": "Results expired"})
            with patch.object(self.script, "api_request", return_value=error_body):
                result = self.script.cmd_company_export(args)

            self.assertFalse(output.exists())

        self.assertEqual(result, {"detail": "Results expired"})

    # company_pause / company_resume / company_cancel

    def test_control_commands_post_to_their_action_route(self):
        for command, action in [
            ("company_pause", "pause"),
            ("company_resume", "resume"),
            ("company_cancel", "cancel"),
        ]:
            with self.subTest(command=command):
                args = SimpleNamespace(command=command, task_id=TASK_ID)
                with patch.object(
                    self.script, "api_request", return_value={}
                ) as request:
                    self.script.cmd_company_control(args)

                request.assert_called_once_with(
                    "POST", f"/desearch/companies/tasks/{TASK_ID}/{action}"
                )

    def test_control_409_prints_the_detail_and_current_task(self):
        conflict = {
            "detail": "Only paused tasks can be resumed.",
            "task": {"task_id": TASK_ID, "status": "running"},
        }
        sent = []

        def fake_urlopen(request, timeout):
            sent.append(request)
            raise http_error(409, json.dumps(conflict), "Conflict")

        with patch.dict(
            self.script.os.environ, {"DESEARCH_API_KEY": "test-key"}
        ), patch.object(self.script, "urlopen", side_effect=fake_urlopen):
            stdout, _ = self.run_cli(["company_resume", TASK_ID])

        self.assertEqual(json.loads(stdout), conflict)
        self.assertEqual(sent[0].get_method(), "POST")
        self.assertEqual(
            sent[0].full_url,
            f"https://api.desearch.ai/desearch/companies/tasks/{TASK_ID}/resume",
        )
        self.assertIsNone(sent[0].data)

    # company_tasks

    def test_tasks_lists_with_filters_and_metadata(self):
        args = tasks_args(
            task_type="enrich",
            status=["running", "paused"],
            limit=50,
            cursor="abc",
            metadata=[("campaign", "q4"), ("workspace_id", "ws_42")],
        )
        with patch.object(self.script, "api_request", return_value={}) as request:
            self.script.cmd_company_tasks(args)

        request.assert_called_once_with(
            "GET",
            "/desearch/companies/tasks",
            params={
                "type": "enrich",
                "status": "running,paused",
                "limit": 50,
                "cursor": "abc",
                "metadata.campaign": "q4",
                "metadata.workspace_id": "ws_42",
            },
        )

    def test_tasks_without_filters_sends_no_values(self):
        with patch.object(self.script, "api_request", return_value={}) as request:
            self.script.cmd_company_tasks(tasks_args())

        request.assert_called_once_with(
            "GET",
            "/desearch/companies/tasks",
            params={"type": None, "status": None, "limit": None, "cursor": None},
        )

    def test_tasks_rejects_more_than_three_metadata_filters(self):
        args = tasks_args(metadata=[(f"k{i}", "v") for i in range(4)])
        with patch.object(self.script, "api_request") as request:
            result = self.script.cmd_company_tasks(args)

        request.assert_not_called()
        self.assertIn("At most 3 --metadata filters", result["error"])

    # api_request

    def test_api_request_sends_idempotency_header_and_can_skip_json_parsing(self):
        sent = []

        def fake_urlopen(request, timeout):
            sent.append(request)
            return FakeResponse('{"task_id": "only-one-task"}')

        with patch.dict(
            self.script.os.environ, {"DESEARCH_API_KEY": "test-key"}
        ), patch.object(self.script, "urlopen", side_effect=fake_urlopen):
            raw = self.script.api_request(
                "POST",
                "/desearch/companies/enrich",
                body={"domains": ["acme.com"]},
                headers={"Idempotency-Key": "key-1"},
                parse_json=False,
            )

        self.assertEqual(raw, '{"task_id": "only-one-task"}')
        request = sent[0]
        self.assertEqual(
            request.full_url, "https://api.desearch.ai/desearch/companies/enrich"
        )
        self.assertEqual(request.get_method(), "POST")
        self.assertEqual(request.get_header("Idempotency-key"), "key-1")
        self.assertEqual(request.get_header("Authorization"), "test-key")
        self.assertEqual(json.loads(request.data), {"domains": ["acme.com"]})

    def test_api_request_encodes_metadata_filters_in_the_query_string(self):
        sent = []

        def fake_urlopen(request, timeout):
            sent.append(request)
            return FakeResponse('{"tasks": [], "next_cursor": null}')

        with patch.dict(
            self.script.os.environ, {"DESEARCH_API_KEY": "test-key"}
        ), patch.object(self.script, "urlopen", side_effect=fake_urlopen):
            result = self.script.api_request(
                "GET",
                "/desearch/companies/tasks",
                params={
                    "type": "search",
                    "status": None,
                    "metadata.campaign": "q4 launch",
                },
            )

        self.assertEqual(result, {"tasks": [], "next_cursor": None})
        self.assertEqual(
            sent[0].full_url,
            "https://api.desearch.ai/desearch/companies/tasks"
            "?type=search&metadata.campaign=q4+launch",
        )
        self.assertEqual(sent[0].get_method(), "GET")
        self.assertIsNone(sent[0].data)

    def test_api_request_returns_error_bodies(self):
        cases = [
            (
                http_error(402, '{"detail": "Company Search needs account credits."}'),
                {"detail": "Company Search needs account credits."},
            ),
            (
                http_error(502, "<html>Bad Gateway</html>", "Bad Gateway"),
                {"error": "HTTP 502: Bad Gateway", "details": "<html>Bad Gateway</html>"},
            ),
            (
                URLError("timed out"),
                {"error": "Connection failed: timed out"},
            ),
        ]
        for raised, expected in cases:
            with self.subTest(expected=expected):
                with patch.dict(
                    self.script.os.environ, {"DESEARCH_API_KEY": "test-key"}
                ), patch.object(self.script, "urlopen", side_effect=raised):
                    result = self.script.api_request("GET", f"/desearch/companies/tasks/{TASK_ID}")

                self.assertEqual(result, expected)

    def test_missing_api_key_exits_before_any_request(self):
        with patch.dict(self.script.os.environ, {}, clear=True), patch.object(
            self.script, "urlopen"
        ) as opener, contextlib.redirect_stderr(io.StringIO()) as stderr, self.assertRaises(
            SystemExit
        ) as exit_info:
            self.script.api_request("GET", "/desearch/companies/tasks")

        self.assertEqual(exit_info.exception.code, 1)
        opener.assert_not_called()
        self.assertIn("DESEARCH_API_KEY", stderr.getvalue())

    # CLI

    def test_cli_parses_a_search_and_prints_json(self):
        task = {"task_id": TASK_ID, "status": "queued"}
        argv = [
            "company_search",
            "  Series A fintech startups   in Berlin ",
            "--count",
            "30",
            "--min-score",
            "60",
            "--exclude",
            "stripe.com, adyen.com",
            "--countries",
            "DE, AT",
            "--require",
            "email,leader_email",
            "--roles",
            "ceo,managing_director",
            "--no-infer-emails",
            "--metadata",
            "campaign=q4",
            "--metadata",
            "note=a=b",
            "--idempotency-key",
            "cli-key",
        ]
        with patch.object(self.script, "api_request", return_value=task) as request:
            stdout, _ = self.run_cli(argv)

        self.assertEqual(json.loads(stdout), task)
        request.assert_called_once_with(
            "POST",
            "/desearch/companies/search",
            body={
                "query": "Series A fintech startups in Berlin",
                "count": 30,
                "min_score": 60,
                "exclude": ["stripe.com", "adyen.com"],
                "roles": ["ceo", "managing_director"],
                "infer_emails": False,
                "filters": {"countries": ["DE", "AT"], "require": ["email", "leader_email"]},
                "metadata": {"campaign": "q4", "note": "a=b"},
            },
            headers={"Idempotency-Key": "cli-key"},
        )

    def test_cli_parses_an_enrich_and_prints_json(self):
        task = {"task_id": TASK_ID, "status": "queued", "count": 2}
        argv = [
            "company_enrich",
            "acme.com,beta.io",
            "acme.com",
            "--no-verify-emails",
            "--idempotency-key",
            "cli-enrich",
        ]
        with patch.object(self.script, "api_request", return_value=task) as request:
            stdout, stderr = self.run_cli(argv)

        self.assertEqual(json.loads(stdout), task)
        request.assert_called_once_with(
            "POST",
            "/desearch/companies/enrich",
            body={"domains": ["acme.com", "beta.io"], "verify_emails": False},
            headers={"Idempotency-Key": "cli-enrich"},
        )
        self.assertIn("Company Enrich of 2 domains", stderr)

    def test_cli_routes_every_free_command(self):
        cases = [
            (["company_task", TASK_ID], ("GET", f"/desearch/companies/tasks/{TASK_ID}"), {}),
            (
                ["company_results", TASK_ID, "--limit", "500", "--cursor", "7"],
                ("GET", f"/desearch/companies/tasks/{TASK_ID}/results"),
                {"params": {"cursor": "7", "limit": 500}},
            ),
            (
                ["company_export", TASK_ID, "--format", "jsonl"],
                ("GET", f"/desearch/companies/tasks/{TASK_ID}/export"),
                {"params": {"format": "jsonl"}, "parse_json": False},
            ),
            (
                ["company_export", TASK_ID],
                ("GET", f"/desearch/companies/tasks/{TASK_ID}/export"),
                {"params": {"format": "csv"}, "parse_json": False},
            ),
            (["company_pause", TASK_ID], ("POST", f"/desearch/companies/tasks/{TASK_ID}/pause"), {}),
            (["company_resume", TASK_ID], ("POST", f"/desearch/companies/tasks/{TASK_ID}/resume"), {}),
            (["company_cancel", TASK_ID], ("POST", f"/desearch/companies/tasks/{TASK_ID}/cancel"), {}),
            (
                ["company_tasks", "--type", "search", "--status", "completed", "-n", "5",
                 "--metadata", "campaign=q4"],
                ("GET", "/desearch/companies/tasks"),
                {
                    "params": {
                        "type": "search",
                        "status": "completed",
                        "limit": 5,
                        "cursor": None,
                        "metadata.campaign": "q4",
                    }
                },
            ),
        ]
        for argv, call_args, call_kwargs in cases:
            with self.subTest(argv=argv):
                with patch.object(self.script, "api_request", return_value={}) as request:
                    self.run_cli(argv)

                request.assert_called_once_with(*call_args, **call_kwargs)

    def test_cli_wait_uses_the_default_interval_and_timeout(self):
        parsed = self.script.build_parser().parse_args(["company_wait", TASK_ID])
        self.assertEqual((parsed.interval, parsed.timeout), (10, 1200))

    def test_cli_rejects_bad_input_before_any_request(self):
        bad_argvs = [
            ["company_search", "Robotics startups", "--count", "3"],
            ["company_search", "Robotics startups", "--count", "201"],
            ["company_search", "Robotics startups", "--min-score", "101"],
            ["company_search", "ab"],
            ["company_search", "Robotics startups", "--roles", "ceo,intern"],
            ["company_search", "Robotics startups", "--require", "email,fax"],
            ["company_search", "Robotics startups", "--metadata", "campaign"],
            ["company_search", "Robotics startups", "--metadata", "Campaign=q4"],
            ["company_search", "Robotics startups", "--metadata", "note=" + "x" * 201],
            ["company_enrich", "acme.com", "--roles", ","],
            ["company_task", "not-a-task-id"],
            ["company_wait", TASK_ID, "--timeout", "5"],
            ["company_results", TASK_ID, "--limit", "501"],
            ["company_tasks", "--status", "running,sleeping"],
            ["company_tasks", "--type", "people"],
            ["company_tasks", "--limit", "101"],
            ["company_export", TASK_ID, "--format", "xlsx"],
            ["people_search", "x", "Indie hackers"],
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

    def test_cli_prints_local_errors_without_any_request(self):
        with patch.object(self.script, "api_request") as request:
            stdout, _ = self.run_cli(["company_enrich"])

        request.assert_not_called()
        self.assertIn("at least one domain", json.loads(stdout)["error"])


if __name__ == "__main__":
    unittest.main()

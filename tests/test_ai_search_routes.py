import contextlib
import importlib.util
import io
import json
import unittest
from pathlib import Path
from unittest.mock import patch


class AiSearchRouteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        path = Path(__file__).resolve().parents[1] / 'desearch-ai-search/scripts/desearch.py'
        spec = importlib.util.spec_from_file_location('ai_search_script', path)
        cls.script = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.script)

    def run_cli(self, argv):
        response = {'search': [{'link': 'https://docs.bittensor.com/'}]}
        with (patch.object(self.script, 'api_request', return_value=response) as request,
              contextlib.redirect_stdout(io.StringIO()) as stdout,
              contextlib.redirect_stderr(io.StringIO()) as stderr):
            self.script.main(argv)
        self.assertEqual(json.loads(stdout.getvalue()), response)
        return request, stderr.getvalue()

    def test_default_and_explicit_sources_match_the_approved_example(self):
        for options in ([], ['--tools', 'web,twitter']):
            with self.subTest(options=options):
                request, _ = self.run_cli(['ai_search', 'What is Bittensor?'] + options)
                request.assert_called_once_with('POST', '/desearch/ai/search', body={
                    'prompt': 'What is Bittensor?', 'tools': ['web', 'twitter'], 'streaming': False})

    def test_supported_single_source_and_existing_filters(self):
        for tool in ('web', 'twitter'):
            request, _ = self.run_cli(['ai_search', 'bittensor', '--tools', tool,
                                       '--count', '15', '--date-filter', 'PAST_WEEK'])
            request.assert_called_once_with('POST', '/desearch/ai/search', body={
                'prompt': 'bittensor', 'tools': [tool], 'streaming': False,
                'result_count': 15, 'date_filter': 'PAST_WEEK'})

    def test_web_compatibility_uses_search_api_query_without_ai_fields(self):
        for options, extra in (([], {}), (['--tools', 'web', '--count', '15'], {'count': 15})):
            request, warning = self.run_cli(['ai_web', 'machine learning papers'] + options)
            request.assert_called_once_with('POST', '/search', body={
                'query': 'machine learning papers', **extra})
            self.assertEqual(warning.strip(), self.script.WEB_GUIDANCE)

    def test_x_route_is_preserved(self):
        request, _ = self.run_cli(['ai_x', 'crypto market trends', '--count', '20'])
        request.assert_called_once_with('POST', '/desearch/ai/search/links/twitter',
                                        body={'prompt': 'crypto market trends', 'count': 20})

    def test_unsupported_sources_and_ignored_options_never_reach_http(self):
        bad = [['ai_search', 'query', '--tools', value] for value in
               ('youtube', 'reddit', 'arxiv', 'hackernews', 'wikipedia', 'web,youtube', '', 'web,')]
        bad += [['ai_web', 'query', '--tools', 'twitter'],
                ['ai_web', 'query', '--tools', 'web,twitter'],
                ['ai_web', 'query', '--count', '1'],
                ['ai_x', 'query', '--tools', 'web'],
                ['ai_web', 'query', '--date-filter', 'PAST_WEEK']]
        for argv in bad:
            with self.subTest(argv=argv), patch.object(self.script, 'api_request') as request:
                with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as error:
                    self.script.main(argv)
                self.assertEqual(error.exception.code, 2)
                request.assert_not_called()

    def test_missing_key_does_not_reach_http(self):
        with patch.dict(self.script.os.environ, {}, clear=True), patch.object(self.script, 'urlopen') as request:
            with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as error:
                self.script.main(['ai_search', 'query'])
            self.assertEqual(error.exception.code, 1)
            request.assert_not_called()


if __name__ == '__main__':
    unittest.main()

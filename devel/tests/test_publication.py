"""Public verification must reject stale or mixed Pages generations (#18)."""
import contextlib
import hashlib
import io
import json
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
import urllib.error

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import control

SHA = 'a' * 40
KEY = 'b' * 64
HTML = b'<html>current build</html>'


class PublicationTests(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict(os.environ, {'SOURCE_SHA': SHA, 'RECIPE': KEY,
                                          'GITHUB_RUN_ID': '10', 'GITHUB_RUN_ATTEMPT': '2',
                                          'GH_TOKEN': 'must-not-be-sent-to-pages'})
        self.env.start()
        self.addCleanup(self.env.stop)
        self.metadata = {'sha': SHA, 'recipe': KEY, 'run_id': '10', 'attempt': '2',
                         'index_sha256': hashlib.sha256(HTML).hexdigest()}

    def test_matching_metadata_and_html_pass(self):
        with patch.object(control, 'public_file', side_effect=[json.dumps(self.metadata), HTML]) as read:
            self.assertEqual(control.verify_once(), self.metadata)
        self.assertEqual([c.args[0] for c in read.call_args_list], ['build.json', 'index.html'])

    def test_each_stale_identity_field_fails_with_observed_values(self):
        for key in ('sha', 'recipe', 'run_id', 'attempt'):
            stale = dict(self.metadata, **{key: 'old'})
            with self.subTest(key=key), patch.object(control, 'public_file', return_value=json.dumps(stale)) as read:
                with self.assertRaisesRegex(ValueError, 'expected=.*observed=.*old'):
                    control.verify_once()
                self.assertEqual(read.call_count, 1)

    def test_new_metadata_cannot_mask_stale_html(self):
        with patch.object(control, 'public_file', side_effect=[json.dumps(self.metadata), b'<html>old</html>']):
            with self.assertRaisesRegex(ValueError, 'Published HTML mismatch'):
                control.verify_once()

    def test_invalid_metadata_or_missing_hash_fails_closed(self):
        for value in ('not json', '[]', json.dumps({k: v for k, v in self.metadata.items() if k != 'index_sha256'})):
            with self.subTest(value=value), patch.object(control, 'public_file', return_value=value):
                with self.assertRaises(ValueError):
                    control.verify_once()

    def test_propagation_can_recover_without_republishing(self):
        with patch.object(control, 'verify_once', side_effect=[ValueError('old generation'), self.metadata]) as verify, patch.object(control.time, 'sleep') as sleep, patch.object(control, 'summary') as summary, contextlib.redirect_stdout(io.StringIO()):
            control.verify(attempts=3, interval=10)
        self.assertEqual(verify.call_count, 2)
        sleep.assert_called_once_with(10)
        summary.assert_called_once()

    def test_transport_and_json_errors_are_bounded_and_retryable(self):
        errors = [urllib.error.HTTPError('https://example.invalid', 503, 'Unavailable', {}, None),
                  TimeoutError('timeout'), json.JSONDecodeError('invalid', '', 0), self.metadata]
        with patch.object(control, 'verify_once', side_effect=errors), patch.object(control.time, 'sleep') as sleep, patch.object(control, 'summary'), contextlib.redirect_stdout(io.StringIO()):
            control.verify(attempts=4)
        self.assertEqual(sleep.call_count, 3)

    def test_persistent_staleness_fails_and_never_records_success(self):
        with patch.object(control, 'verify_once', side_effect=ValueError('old generation')) as verify, patch.object(control.time, 'sleep') as sleep, patch.object(control, 'summary') as summary, contextlib.redirect_stdout(io.StringIO()):
            with self.assertRaisesRegex(SystemExit, 'did not match'):
                control.verify(attempts=3)
        self.assertEqual(verify.call_count, 3)
        self.assertEqual(sleep.call_count, 2)
        summary.assert_not_called()

    def test_public_requests_are_unique_revalidated_and_unauthenticated(self):
        with patch.object(control.urllib.request, 'urlopen') as open_url:
            open_url.return_value.__enter__.return_value.read.return_value = b'{}'
            control.public_file('build.json')
            control.public_file('build.json')
        requests = [call.args[0] for call in open_url.call_args_list]
        self.assertNotEqual(requests[0].full_url, requests[1].full_url)
        for request in requests:
            self.assertTrue(request.full_url.startswith(control.SITE + 'build.json?verify='))
            self.assertEqual(request.get_header('Cache-control'), 'no-cache')
            self.assertNotIn('Authorization', request.headers)

    def test_public_response_size_is_bounded(self):
        with patch.object(control.urllib.request, 'urlopen') as open_url:
            open_url.return_value.__enter__.return_value.read.return_value = b'x' * (2 * 1024 * 1024 + 1)
            with self.assertRaisesRegex(ValueError, 'exceeds controller limit'):
                control.public_file('index.html')


if __name__ == '__main__':
    unittest.main()

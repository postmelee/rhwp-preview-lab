import datetime as dt
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import control
spec = importlib.util.spec_from_file_location('preview_site', Path(__file__).resolve().parents[1] / 'site.py')
site = importlib.util.module_from_spec(spec)
spec.loader.exec_module(site)
SHA = 'a' * 40
KEY = 'b' * 64
NOW = dt.datetime(2026, 9, 17, tzinfo=dt.timezone.utc)


class DecisionTests(unittest.TestCase):
    def record(self, state, seconds=10):
        timestamp = (NOW - dt.timedelta(seconds=seconds)).isoformat()
        return {'payload': {'source_sha': SHA, 'recipe': KEY}, 'created_at': timestamp,
                'latest_status': {'state': state, 'created_at': timestamp}}

    def decide(self, published=None, latest=None, force=False, key=KEY, sha=SHA):
        return control.decision(sha, key, published, latest, NOW, force)[0]

    def test_first_publication(self):
        self.assertTrue(self.decide())

    def test_unchanged_skips(self):
        self.assertFalse(self.decide({'sha': SHA, 'recipe': KEY}))

    def test_source_and_recipe_changes_build(self):
        self.assertTrue(self.decide({'sha': 'c' * 40, 'recipe': KEY}))
        self.assertTrue(self.decide({'sha': SHA, 'recipe': 'c' * 64}))

    def test_failures_wait_one_hour(self):
        for state in ('failure', 'error', 'pending', 'in_progress'):
            with self.subTest(state=state):
                self.assertFalse(self.decide(latest=self.record(state, 3599)))
                self.assertTrue(self.decide(latest=self.record(state, 3600)))

    def test_interrupted_before_status_recovers(self):
        record = self.record('pending')
        record['latest_status'] = None
        self.assertFalse(self.decide(latest=record))
        record['created_at'] = (NOW - dt.timedelta(hours=2)).isoformat()
        self.assertTrue(self.decide(latest=record))

    def test_new_sha_ignores_previous_failure(self):
        self.assertTrue(self.decide(latest=self.record('failure'), sha='c' * 40))

    def test_force_unchanged_and_failure(self):
        self.assertTrue(self.decide({'sha': SHA, 'recipe': KEY}, self.record('failure'), True))

    def test_unknown_public_state_does_not_rebuild_success(self):
        with self.assertRaises(ValueError):
            self.decide(latest=self.record('success'))

    def test_serialized_payload(self):
        record = self.record('failure')
        record['payload'] = json.dumps(record['payload'])
        self.assertFalse(self.decide(latest=record))

    def test_bad_metadata_fails_closed(self):
        with self.assertRaises(ValueError):
            self.decide({'sha': 'nope', 'recipe': KEY})
        with self.assertRaises(KeyError):
            self.decide({})

    def test_obsolete_harness_skips_before_creating_record(self):
        with patch.object(control, 'current_harness', return_value=False), patch.object(control, 'api') as api, patch.object(control, 'output') as output, patch.object(control, 'summary'):
            control.gate()
        api.assert_not_called()
        output.assert_called_once_with({'build': False})

    def test_site_error_does_not_create_record(self):
        with patch.object(control, 'current_harness', return_value=True), patch.object(control, 'api', return_value={'sha': SHA}) as api, patch.object(control, 'request', side_effect=TimeoutError), patch.dict(os.environ, {'GITHUB_RUN_ID': '1'}):
            with self.assertRaises(TimeoutError):
                control.gate()
        self.assertEqual(api.call_count, 1)


class StaticTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.dist = self.root / 'rhwp-studio/dist'
        self.dist.mkdir(parents=True)
        (self.dist / 'index.html').write_text('<html><body></body></html>')
        (self.dist / 'test.wasm').write_bytes(b'\0asm\x01\0\0\0')
        with patch.dict(os.environ, {'GITHUB_RUN_ID': '1', 'GITHUB_RUN_ATTEMPT': '2'}):
            site.stamp(self.root, SHA)

    def validate(self, sha=SHA):
        return site.validate(self.dist, sha, control.recipe(), '1', '2')

    def test_valid_static_provenance(self):
        self.assertEqual(self.validate()['source_sha'], SHA)
        self.assertIn('data-source-sha="' + SHA, (self.dist / 'index.html').read_text())

    def test_other_run_sha_rejected(self):
        with self.assertRaises(ValueError):
            self.validate('c' * 40)

    def test_symlink_rejected(self):
        (self.dist / 'linked.js').symlink_to('/etc/passwd')
        with self.assertRaises(ValueError):
            self.validate()

    def test_sample_corpus_rejected(self):
        (self.dist / 'samples').mkdir()
        (self.dist / 'samples/a.txt').write_text('private sample')
        with self.assertRaises(ValueError):
            self.validate()

    def test_pwa_rejected(self):
        (self.dist / 'sw.js').write_text('')
        with self.assertRaises(ValueError):
            self.validate()

    def test_bad_wasm_rejected(self):
        (self.dist / 'test.wasm').write_bytes(b'not wasm')
        with self.assertRaises(ValueError):
            self.validate()

    def test_size_limit(self):
        with (self.dist / 'large.js').open('wb') as target:
            target.truncate(50 * 1024 * 1024 + 1)
        with self.assertRaises(ValueError):
            self.validate()


if __name__ == '__main__':
    unittest.main()

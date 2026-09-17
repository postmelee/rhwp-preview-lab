import datetime as dt
import importlib.util
import json
import os
from pathlib import Path
import sys
import subprocess
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
        with patch.object(control, 'current_harness', return_value=True), patch.object(control, 'api', return_value={'object': {'sha': SHA}}) as api, patch.object(control, 'request', side_effect=TimeoutError), patch.dict(os.environ, {'GITHUB_RUN_ID': '1'}):
            with self.assertRaises(TimeoutError):
                control.gate()
        self.assertEqual(api.call_count, 1)


class ControllerFlowTests(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict(os.environ, {'GITHUB_SHA': 'c' * 40, 'GITHUB_RUN_ID': '10',
                                          'GITHUB_RUN_ATTEMPT': '2', 'FORCE': 'false'})
        self.env.start()
        self.addCleanup(self.env.stop)

    def test_no_change_creates_no_deployment(self):
        with patch.object(control, 'current_harness', return_value=True), patch.object(control, 'recipe', return_value=KEY), patch.object(control, 'request', return_value={'sha': SHA, 'recipe': KEY}), patch.object(control, 'api', side_effect=[{'object': {'sha': SHA}}, []]) as api, patch.object(control, 'output') as output, patch.object(control, 'summary'):
            control.gate()
        self.assertEqual(api.call_count, 2)
        output.assert_called_once_with({'build': False, 'sha': SHA, 'recipe': KEY})

    def test_changed_source_records_exact_run_before_build(self):
        with patch.object(control, 'current_harness', return_value=True), patch.object(control, 'recipe', return_value=KEY), patch.object(control, 'request', return_value=None), patch.object(control, 'api', side_effect=[{'object': {'sha': SHA}}, [], {'id': 42}, {}]) as api, patch.object(control, 'output') as output, patch.object(control, 'summary'):
            control.gate()
        body = api.call_args_list[2].args[1]
        self.assertFalse(body['auto_merge'])
        self.assertEqual(body['required_contexts'], [])
        self.assertEqual(body['payload'], {'source_sha': SHA, 'recipe': KEY, 'run_id': '10', 'attempt': '2'})
        output.assert_called_once_with({'build': True, 'sha': SHA, 'recipe': KEY, 'deployment': 42})
        self.assertEqual(api.call_args_list[3].args[1]['state'], 'in_progress')

    def test_finalizer_rejects_another_run(self):
        record = {'environment': control.ENVIRONMENT,
                  'payload': {'source_sha': SHA, 'recipe': KEY, 'run_id': '11', 'attempt': '2'}}
        with patch.dict(os.environ, {'SOURCE_SHA': SHA, 'RECIPE': KEY, 'DEPLOYMENT_ID': '42', 'PUBLISH_RESULT': 'success'}), patch.object(control, 'api', return_value=record) as api:
            with self.assertRaises(ValueError):
                control.finish()
        self.assertEqual(api.call_count, 1)

    def test_failed_or_skipped_publication_is_not_success(self):
        record = {'environment': control.ENVIRONMENT,
                  'payload': {'source_sha': SHA, 'recipe': KEY, 'run_id': '10', 'attempt': '2'}}
        for result in ('failure', 'skipped', 'cancelled', 'success'):
            with self.subTest(result=result), patch.dict(os.environ, {'SOURCE_SHA': SHA, 'RECIPE': KEY, 'DEPLOYMENT_ID': '42', 'PUBLISH_RESULT': result}), patch.object(control, 'api', return_value=record), patch.object(control, 'set_status') as status:
                control.finish()
                self.assertEqual(status.call_args.args[1], 'success' if result == 'success' else 'failure')


class PrepareTests(unittest.TestCase):
    def test_project_base_and_only_distributable_fonts(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            subprocess.run(['git', 'init', '-q', directory], check=True)
            subprocess.run(['git', '-C', directory, '-c', 'user.name=Test', '-c', 'user.email=test@example.invalid', 'commit', '-q', '--allow-empty', '-m', 'fixture'], check=True)
            sha = subprocess.check_output(['git', '-C', directory, 'rev-parse', 'HEAD'], text=True).strip()
            public = root / 'rhwp-studio/public'
            public.mkdir(parents=True)
            fonts = root / 'assets/fonts'
            fonts.mkdir(parents=True)
            (fonts / 'font.woff2').write_bytes(b'font')
            (public / 'fonts').symlink_to(fonts, target_is_directory=True)
            (public / 'samples').mkdir()
            (public / 'samples/private.hwp').write_bytes(b'private')
            (public / 'outside.txt').symlink_to('/etc/passwd')
            site.prepare(root, sha)
            prepared = root / 'rhwp-studio/.devel-public'
            self.assertEqual((prepared / 'fonts/font.woff2').read_bytes(), b'font')
            self.assertFalse((prepared / 'samples').exists())
            self.assertFalse((prepared / 'outside.txt').exists())
            self.assertIn("base:'/rhwp-preview-lab/'", (root / 'rhwp-studio/vite.devel.config.ts').read_text())

    def test_wrong_checkout_rejected_before_writing(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(site.subprocess, 'check_output', return_value='c' * 40):
            with self.assertRaises(ValueError):
                site.prepare(directory, SHA)
            self.assertFalse((Path(directory) / 'rhwp-studio').exists())


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

import importlib.util
import json
from http.client import IncompleteRead
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import footer
spec = importlib.util.spec_from_file_location('preview_site_footer', Path(__file__).resolve().parents[1] / 'site.py')
site = importlib.util.module_from_spec(spec)
spec.loader.exec_module(site)
SHA, PARENT, OTHER = 'a' * 40, 'b' * 40, 'c' * 40


def pull(sha=SHA):
    return {'number': 7367, 'title': 'fix: <layout> "title" & text', 'merged_at': '2026-09-23T06:00:00Z',
            'merge_commit_sha': sha, 'base': {'ref': 'devel', 'repo': {'full_name': 'edwardkim/rhwp'}}}


class FooterTests(unittest.TestCase):
    def test_kst_crosses_midnight_and_year(self):
        self.assertEqual(footer.kst_time('2026-12-31T15:00:00+00:00'), '2027-01-01 00:00:00 KST')
        self.assertEqual(footer.kst_time('2026-09-23T06:50:39.444050+00:00'), '2026-09-23 15:50:39 KST')

    def test_exact_merge_one_request_and_canonical_link(self):
        pr = pull()
        pr['html_url'] = 'https://untrusted.invalid/'
        with patch.object(footer, 'public_json', return_value=[pr]) as api:
            result = footer.find_last_pr(SHA)
        self.assertEqual(api.call_count, 1)
        self.assertEqual(result['commits_after'], 0)
        self.assertEqual(result['url'], 'https://github.com/edwardkim/rhwp/pull/7367')
        self.assertEqual(result['merge_sha'], SHA)

    def test_rejects_open_wrong_sha_branch_and_repository(self):
        for field, value in [('merged_at', None), ('merge_commit_sha', OTHER),
                             ('base', {'ref': 'main', 'repo': {'full_name': 'edwardkim/rhwp'}}),
                             ('base', {'ref': 'devel', 'repo': {'full_name': 'someone/rhwp'}})]:
            pr = pull()
            pr[field] = value
            with self.subTest(field=field, value=value), patch.object(footer, 'public_json', side_effect=[[pr], {'sha': SHA, 'parents': []}]):
                self.assertIsNone(footer.find_last_pr(SHA))

    def test_first_parent_only_and_commits_after(self):
        with patch.object(footer, 'public_json', side_effect=[[], {'sha': SHA, 'parents': [{'sha': PARENT}, {'sha': OTHER}]}, [pull(PARENT)]]) as api:
            result = footer.find_last_pr(SHA)
        self.assertEqual(result['commits_after'], 1)
        self.assertEqual(result['merge_sha'], PARENT)
        self.assertIn(PARENT, api.call_args_list[2].args[0])

    def test_ambiguous_or_truncated_results_are_unknown(self):
        for prs in [[pull(), pull()], [pull()] * 100]:
            with patch.object(footer, 'public_json', return_value=prs) as api:
                self.assertIsNone(footer.find_last_pr(SHA))
                self.assertEqual(api.call_count, 1)

    def test_error_and_malformed_response_do_not_fail_build(self):
        for response in [None, {}, [None], [{'base': None}]]:
            with patch.object(footer, 'public_json', return_value=response):
                self.assertIsNone(footer.find_last_pr(SHA))
        for error in [TimeoutError(), OSError(), ValueError(), IncompleteRead(b"partial")]:
            with patch.object(footer, 'public_json', side_effect=error):
                self.assertIsNone(footer.find_last_pr(SHA))

    def test_invalid_number_and_title_are_unknown(self):
        for field, value in [('number', True), ('number', 0), ('number', '1'), ('title', None)]:
            pr = pull()
            pr[field] = value
            with patch.object(footer, 'public_json', return_value=[pr]):
                self.assertIsNone(footer.find_last_pr(SHA))

    def test_wrong_commit_identity_is_unknown(self):
        with patch.object(footer, 'public_json', side_effect=[[], {'sha': OTHER, 'parents': [{'sha': PARENT}]}]):
            self.assertIsNone(footer.find_last_pr(SHA))

    def test_history_scan_is_bounded(self):
        def response(path, deadline):
            if '/pulls?' in path:
                return []
            sha = path.rsplit('/', 1)[1]
            return {'sha': sha, 'parents': [{'sha': f'{int(sha, 16) + 1:040x}'}]}
        with patch.object(footer, 'public_json', side_effect=response) as api:
            self.assertIsNone(footer.find_last_pr('0' * 40))
        self.assertEqual(api.call_count, 39)  # 20 candidates and 19 first-parent reads.

    def test_http_budget_and_no_credentials(self):
        with patch.object(footer.time, 'monotonic', return_value=10), patch.object(footer.urllib.request, 'urlopen') as open_url:
            with self.assertRaises(TimeoutError):
                footer.public_json('commits/test', 9)
            open_url.assert_not_called()
            open_url.return_value.__enter__.return_value.read.return_value = b'{}'
            footer.public_json('commits/test', 12)
            request = open_url.call_args.args[0]
            self.assertNotIn('Authorization', request.headers)
            self.assertEqual(open_url.call_args.kwargs['timeout'], 2)

    def test_response_limit(self):
        with patch.object(footer.time, 'monotonic', return_value=10), patch.object(footer.urllib.request, 'urlopen') as open_url:
            open_url.return_value.__enter__.return_value.read.return_value = b'x' * (1024 * 1024 + 1)
            with self.assertRaises(ValueError):
                footer.public_json('commits/test', 12)

    def test_stamp_keeps_utc_sha_and_escapes_title(self):
        with patch.object(footer, 'public_json', return_value=[pull()]):
            pr = footer.find_last_pr(SHA)
        with tempfile.TemporaryDirectory() as directory:
            dist = Path(directory) / 'rhwp-studio/dist'
            dist.mkdir(parents=True)
            index = dist / 'index.html'
            index.write_text('<body><div id="studio-root"></div></body>')
            with patch.object(site, 'find_last_pr', return_value=pr), patch.dict(os.environ, {'GITHUB_RUN_ID': '1', 'GITHUB_RUN_ATTEMPT': '1'}):
                site.stamp(directory, SHA)
            metadata = json.loads((dist / 'build.json').read_text())
            html = index.read_text()
            self.assertTrue(metadata['built_at'].endswith('+00:00'))
            self.assertEqual(metadata['sha'], SHA)
            self.assertEqual(metadata['last_pr']['number'], 7367)
            self.assertIn('PR #7367', html)
            self.assertIn('fix: &lt;layout&gt; &quot;title&quot; &amp; text', html)
            self.assertIn('datetime="' + metadata['built_at'] + '"', html)
            self.assertIn(footer.kst_time(metadata['built_at']), html)
            self.assertIn('height:calc(100vh - 24px)', html)
            self.assertIn('id="preview-relative-time"', html)

    def test_stamp_unknown_pr_still_has_sha_time_and_status(self):
        with tempfile.TemporaryDirectory() as directory:
            dist = Path(directory) / 'rhwp-studio/dist'
            dist.mkdir(parents=True)
            index = dist / 'index.html'
            index.write_text('<body></body>')
            with patch.object(site, 'find_last_pr', return_value=None), patch.dict(os.environ, {'GITHUB_RUN_ID': '1', 'GITHUB_RUN_ATTEMPT': '1'}):
                site.stamp(directory, SHA)
            html = index.read_text()
            self.assertIn('PR 미확인', html)
            self.assertIn(SHA, html)
            self.assertIn('갱신 상태·실패 로그', html)
            self.assertIn('KST</time>', html)


if __name__ == '__main__':
    unittest.main()

"""Optional build metadata. Public API failures must not block publication."""
import datetime as dt
import json
import time
import urllib.request
from zoneinfo import ZoneInfo

from control import UPSTREAM, valid_sha


def kst_time(iso):
    return dt.datetime.fromisoformat(iso).astimezone(ZoneInfo('Asia/Seoul')).strftime('%Y-%m-%d %H:%M:%S KST')


def public_json(path, deadline):
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise TimeoutError('PR lookup budget exhausted')
    request = urllib.request.Request(f'https://api.github.com/repos/{UPSTREAM}/{path}', headers={
        'Accept': 'application/vnd.github+json', 'User-Agent': 'rhwp-preview-footer',
        'X-GitHub-Api-Version': '2022-11-28',
    })
    with urllib.request.urlopen(request, timeout=min(3, remaining)) as response:
        raw = response.read(1024 * 1024 + 1)
    if len(raw) > 1024 * 1024 or time.monotonic() > deadline:
        raise ValueError('PR lookup response exceeds budget')
    return json.loads(raw)


def find_last_pr(source_sha):
    """Match merged devel PRs on the exact first-parent chain, never live HEAD."""
    sha = valid_sha(source_sha)
    deadline = time.monotonic() + 20
    try:
        for distance in range(20):
            pulls = public_json(f'commits/{sha}/pulls?per_page=100', deadline)
            # Do not choose from a potentially truncated/ambiguous result.
            if not isinstance(pulls, list) or len(pulls) >= 100:
                return None
            matches = [p for p in pulls if p.get('merged_at') and p.get('merge_commit_sha') == sha
                       and p.get('base', {}).get('ref') == 'devel'
                       and (p.get('base', {}).get('repo') or {}).get('full_name') == UPSTREAM]
            if matches:
                if len(matches) != 1:
                    return None
                pr = matches[0]
                if type(pr.get('number')) is not int or pr['number'] < 1 or not isinstance(pr.get('title'), str):
                    return None
                return {'number': pr['number'], 'title': pr['title'], 'merge_sha': sha,
                        'commits_after': distance, 'url': f"https://github.com/{UPSTREAM}/pull/{pr['number']}"}
            if distance == 19:
                break
            # Git commit endpoint omits large file diffs and keeps this lookup small.
            commit = public_json(f'git/commits/{sha}', deadline)
            if commit['sha'] != sha:
                return None
            parents = commit['parents']
            if not parents:
                break
            sha = valid_sha(parents[0]['sha'])
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        print('PR metadata unavailable; publishing SHA and build time without a PR label.')
    return None

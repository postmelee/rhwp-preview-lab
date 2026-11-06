"""Trusted polling controller. No upstream code is imported or executed here."""
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import time
import urllib.error
import urllib.request
import uuid

REPO = 'postmelee/rhwp-preview-lab'
UPSTREAM = 'edwardkim/rhwp'
ENVIRONMENT = 'devel-preview-build'
SITE = 'https://postmelee.github.io/rhwp-preview-lab/'
COOLDOWN = 3600
ROOT = Path(__file__).resolve().parent.parent


def recipe():
    digest = hashlib.sha256()
    paths = [ROOT / '.github/workflows/devel-pages.yml', *sorted((ROOT / 'devel').glob('*.*'))]
    for path in paths:
        digest.update(path.relative_to(ROOT).as_posix().encode() + b'\0' + path.read_bytes())
    return digest.hexdigest()


def request(url, body=None, token=None, missing=False, method=None):
    headers = {'Accept': 'application/vnd.github+json', 'User-Agent': 'rhwp-devel-preview'}
    if token:
        headers['Authorization'] = f'Bearer {token}'
    data = None if body is None else json.dumps(body).encode()
    if data is not None:
        headers['Content-Type'] = 'application/json'
    try:
        with urllib.request.urlopen(urllib.request.Request(url, data, headers, method=method), timeout=25) as response:
            raw = response.read(2 * 1024 * 1024 + 1)
            if len(raw) > 2 * 1024 * 1024:
                raise ValueError('response exceeds controller limit')
            return json.loads(raw) if raw else None
    except urllib.error.HTTPError as error:
        if missing and error.code == 404:
            return None
        raise


def api(path, body=None, method=None):
    return request('https://api.github.com/' + path, body, os.environ['GH_TOKEN'], method=method)


def valid_sha(sha):
    if not isinstance(sha, str) or not re.fullmatch('[0-9a-f]{40}', sha):
        raise ValueError('invalid source SHA')
    return sha


def decision(sha, key, published, latest, now, force=False):
    valid_sha(sha)
    if published is not None:
        valid_sha(published['sha'])
        if not re.fullmatch('[0-9a-f]{64}', published['recipe']):
            raise ValueError('invalid published recipe')
    if force:
        return True, 'manual force'
    if published and (published['sha'], published['recipe']) == (sha, key):
        return False, 'already published'
    if latest:
        payload = latest['payload']
        if isinstance(payload, str):
            payload = json.loads(payload)
        if (payload.get('source_sha'), payload.get('recipe')) == (sha, key):
            status = latest.get('latest_status')
            state = status['state'] if status else 'pending'
            timestamp = status['created_at'] if status else latest['created_at']
            age = (now - dt.datetime.fromisoformat(timestamp.replace('Z', '+00:00'))).total_seconds()
            if state == 'success' and published is None:
                raise ValueError('successful publication exists but public metadata is missing')
            if state != 'success' and age < COOLDOWN:
                return False, 'retry cooldown / unfinished attempt lease'
    return True, 'new source or recipe / retry due'


def output(values):
    with open(os.environ['GITHUB_OUTPUT'], 'a') as target:
        for name, value in values.items():
            target.write(f'{name}={str(value).lower() if isinstance(value, bool) else value}\n')


def summary(message):
    print(message)
    if os.environ.get('GITHUB_STEP_SUMMARY'):
        with open(os.environ['GITHUB_STEP_SUMMARY'], 'a') as target:
            target.write(message + '\n')


def current_harness():
    return api(f'repos/{REPO}/git/ref/heads/main')['object']['sha'] == os.environ['GITHUB_SHA']


def gate():
    if not current_harness():
        output({'build': False})
        summary('Skipped: workflow revision is no longer current main.')
        return
    sha = valid_sha(api(f'repos/{UPSTREAM}/git/ref/heads/devel')['object']['sha'])
    key = recipe()
    # Do not send the GitHub token to the public Pages host.
    published = request(SITE + 'build.json?poll=' + os.environ['GITHUB_RUN_ID'], missing=True)
    records = api(f'repos/{REPO}/deployments?environment={ENVIRONMENT}&per_page=1')
    latest = records[0] if records else None
    if latest:
        statuses = api(f'repos/{REPO}/deployments/{latest["id"]}/statuses?per_page=1')
        latest['latest_status'] = statuses[0] if statuses else None
    build, reason = decision(sha, key, published, latest, dt.datetime.now(dt.timezone.utc),
                             os.environ.get('FORCE') == 'true')
    values = {'build': build, 'sha': sha, 'recipe': key}
    if build:
        deployment = api(f'repos/{REPO}/deployments', {
            'ref': os.environ['GITHUB_SHA'], 'auto_merge': False, 'required_contexts': [],
            'environment': ENVIRONMENT, 'transient_environment': True, 'production_environment': False,
            'description': f'devel {sha[:12]}',
            'payload': {'source_sha': sha, 'recipe': key, 'run_id': os.environ['GITHUB_RUN_ID'],
                        'attempt': os.environ['GITHUB_RUN_ATTEMPT']}})
        values['deployment'] = deployment['id']
        # Output first: the finalizer can mark a failure even if status creation fails.
        output(values)
        set_status(deployment['id'], 'in_progress', 'Building and validating exact upstream devel')
    else:
        output(values)
    summary(f'### devel preview\nSource: `{sha}`\n\n{reason}. Build: **{build}**.')


def set_status(deployment, state, description):
    if not str(deployment).isdigit():
        raise ValueError('invalid deployment id')
    api(f'repos/{REPO}/deployments/{deployment}/statuses', {
        'state': state, 'description': description, 'auto_inactive': False,
        'log_url': f'https://github.com/{REPO}/actions/runs/{os.environ["GITHUB_RUN_ID"]}',
        'environment_url': SITE})


def cleanup_pages_artifact():
    run_id = os.environ['GITHUB_RUN_ID']
    artifacts = api(f'repos/{REPO}/actions/runs/{run_id}/artifacts?per_page=100')['artifacts']
    for artifact in artifacts:
        if artifact['name'] == 'github-pages' and not artifact['expired']:
            artifact_id = artifact['id']
            if not str(artifact_id).isdigit():
                raise ValueError('invalid artifact id')
            api(f'repos/{REPO}/actions/artifacts/{artifact_id}', method='DELETE')


def finish():
    deployment = os.environ['DEPLOYMENT_ID']
    expected = (os.environ['SOURCE_SHA'], os.environ['RECIPE'], os.environ['GITHUB_RUN_ID'], os.environ['GITHUB_RUN_ATTEMPT'])
    record = api(f'repos/{REPO}/deployments/{deployment}')
    payload = record['payload']
    if isinstance(payload, str):
        payload = json.loads(payload)
    actual = tuple(str(payload[k]) for k in ('source_sha', 'recipe', 'run_id', 'attempt'))
    if record['environment'] != ENVIRONMENT or actual != expected:
        raise ValueError('deployment ownership mismatch')
    success = os.environ.get('PUBLISH_RESULT') == 'success'
    set_status(deployment, 'success' if success else 'failure',
               'Pages deployment verified' if success else 'Attempt failed or was cancelled; inspect published SHA and logs')
    cleanup_pages_artifact()


def public_file(path):
    # Each observation is independent of a previous failed verification request.
    # Never send the GitHub token to Pages.
    url = SITE + path + '?verify=' + uuid.uuid4().hex
    headers = {'User-Agent': 'rhwp-devel-preview', 'Cache-Control': 'no-cache', 'Pragma': 'no-cache'}
    with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=10) as response:
        data = response.read(2 * 1024 * 1024 + 1)
        if len(data) > 2 * 1024 * 1024:
            raise ValueError('public response exceeds controller limit')
        return data


def verify_once():
    expected = dict(zip(('sha', 'recipe', 'run_id', 'attempt'),
                        (os.environ['SOURCE_SHA'], os.environ['RECIPE'],
                         os.environ['GITHUB_RUN_ID'], os.environ['GITHUB_RUN_ATTEMPT'])))
    metadata = json.loads(public_file('build.json'))
    if not isinstance(metadata, dict):
        raise ValueError('public metadata is not an object')
    actual = {key: str(metadata.get(key)) for key in expected}
    if actual != expected:
        raise ValueError(f'Published metadata mismatch: expected={json.dumps(expected)} observed={json.dumps(actual)}')
    expected_hash = metadata.get('index_sha256')
    if not isinstance(expected_hash, str) or not re.fullmatch('[0-9a-f]{64}', expected_hash):
        raise ValueError('public metadata is missing a valid index_sha256')
    actual_hash = hashlib.sha256(public_file('index.html')).hexdigest()
    if actual_hash != expected_hash:
        raise ValueError(f'Published HTML mismatch: expected={expected_hash} observed={actual_hash}')
    return metadata


def verify(attempts=12, interval=10):
    for number in range(1, attempts + 1):
        try:
            metadata = verify_once()
        except (ValueError, OSError, urllib.error.URLError) as error:
            print(f'Public verification {number}/{attempts}: {error}', flush=True)
            if number < attempts:
                time.sleep(interval)
        else:
            summary(f'Published metadata and HTML verified: {SITE} — `{metadata["sha"]}`')
            return
    raise SystemExit('Public files did not match this run within the propagation window')


if __name__ == '__main__':
    command = sys.argv[1]
    if command == 'gate':
        gate()
    elif command == 'resolve':
        output({'sha': valid_sha(api(f'repos/{UPSTREAM}/git/ref/heads/devel')['object']['sha']), 'recipe': recipe()})
    elif command == 'guard':
        if not current_harness():
            raise SystemExit('Refusing publication from an obsolete workflow revision')
    elif command == 'finish':
        finish()
    elif command == 'verify':
        verify()
    else:
        raise SystemExit('unknown controller command')

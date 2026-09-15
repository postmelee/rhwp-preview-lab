"""GitHub-only stage 2 adapter. Deliberately has no hosting credentials/API."""
import base64, json, os, pathlib, re, subprocess
from policy import select_run, validate_zip

REPO = os.environ['GITHUB_REPOSITORY']
ROOT = f'repos/{REPO}'
MARKER = '<!-- rhwp-preview-lab:v1 -->'


def api(path, body=None, raw=False, method=None):
    args = ['gh', 'api', path]
    if body is not None:
        args += ['--method', method or 'POST', '--input', '-']
    data = subprocess.check_output(args, input=json.dumps(body).encode() if body is not None else None)
    return data if raw else json.loads(data)


def pages(path, key=None):
    result = []
    for n in range(1, 11):
        page = api(path + ('&' if '?' in path else '?') + f'per_page=100&page={n}')
        items = page[key] if key else page
        result += items
        if len(items) < 100:
            return result
    raise ValueError('pagination limit; refuse incomplete evidence')


def pull(number):
    return api(f'{ROOT}/pulls/{number}')


def target_sha(number):
    if number:
        pr = pull(number)
        if pr['state'] != 'open' or pr['base']['ref'] != 'devel' or pr['base']['repo']['full_name'] != REPO:
            raise ValueError('PR closed or wrong base')
        return pr['head']['sha']
    return api(f'{ROOT}/git/ref/heads/devel')['object']['sha']


def content(path, ref):
    value = api(f'{ROOT}/contents/{path}?ref={ref}')
    return base64.b64decode(value['content'])


def bot_comment(number):
    matches = [c for c in pages(f'{ROOT}/issues/{number}/comments') if c['user']['login'] == 'github-actions[bot]' and c['body'].startswith(MARKER)]
    if len(matches) > 1:
        raise ValueError('duplicate bot comments')
    return matches[0] if matches else None


def comment(number, body):
    previous = bot_comment(number)
    if previous:
        if previous['body'] != body:
            api(f"{ROOT}/issues/comments/{previous['id']}", {'body':body}, method='PATCH')
    else:
        api(f'{ROOT}/issues/{number}/comments', {'body':body})


def reconcile(number):
    sha = target_sha(number)
    evidence = []
    event = 'pull_request' if number else 'push'
    workflows = ['ci.yml', 'quality.yml'] if number else ['ci.yml']
    for filename in workflows:
        # Bind privilege-free build workflow to the trusted default branch definition.
        if content(f'.github/workflows/{filename}', sha) != pathlib.Path(f'.github/workflows/{filename}').read_bytes():
            raise ValueError('unreviewed build workflow change')
        workflow = api(f'{ROOT}/actions/workflows/{filename}')
        runs = pages(f"{ROOT}/actions/workflows/{workflow['id']}/runs?head_sha={sha}&event={event}", 'workflow_runs')
        if number:
            pr = pull(number)
            runs = [r for r in runs if r.get('head_repository', {}).get('id') == pr['head']['repo']['id'] and r['head_branch'] == pr['head']['ref']]
        else:
            runs = [r for r in runs if r['head_branch'] == 'devel']
        run = select_run(runs, sha, event, workflow['id'])
        jobs = pages(f"{ROOT}/actions/runs/{run['id']}/attempts/{run['run_attempt']}/jobs", 'jobs')
        expected = 'build' if filename == 'ci.yml' else 'quality'
        if len(jobs) != 1 or jobs[0]['name'] != expected or jobs[0]['conclusion'] != 'success':
            raise ValueError('missing or skipped required job')
        evidence.append(run)
    ci = evidence[0]
    artifacts = pages(f"{ROOT}/actions/runs/{ci['id']}/artifacts", 'artifacts')
    found = [a for a in artifacts if a['name'] == f"static-{sha}-{ci['run_attempt']}" and not a['expired']]
    if len(found) != 1 or found[0]['size_in_bytes'] > 100 * 1024 * 1024:
        raise ValueError('missing, duplicate, or oversized artifact')
    artifact = found[0]
    data = api(f"{ROOT}/actions/artifacts/{artifact['id']}/zip", raw=True)
    verified = validate_zip(data, sha, ci['id'], ci['run_attempt'])
    if artifact.get('digest') != 'sha256:' + verified['sha256']:
        raise ValueError('GitHub artifact digest mismatch')
    if target_sha(number) != sha:
        raise ValueError('stale head before publish')
    # Recheck live attempts: a rerun started during validation must revoke this evidence.
    for run in evidence:
        current = api(f"{ROOT}/actions/runs/{run['id']}")
        if (current['run_attempt'], current['status'], current['conclusion']) != (run['run_attempt'], 'completed', 'success'):
            raise ValueError('CI attempt changed during validation')
    result = {'target': f'pr-{number}' if number else 'devel', 'sha':sha, 'state':'verified-not-hosted', 'artifact_id':artifact['id'], 'runs':[{'id':r['id'],'attempt':r['run_attempt'],'url':r['html_url']} for r in evidence], **verified}
    if number:
        body = f"{MARKER}\n## 미리보기 시험 — 호스팅 미설정\n\n검증한 PR head: `{sha}`\n\n필수 CI와 정적 artifact 검증 통과. 실제 배포는 아직 없습니다.\n\n[검증 산출물]({ci['html_url']}) · [수동 재검증](https://github.com/{REPO}/actions/workflows/preview.yml)\n\nPR head 열기 / 비교 기준 열기 / 현재 devel 열기는 Cloudflare 연결 후 제공됩니다.\n\n<!-- verified-sha:{sha} -->"
        if target_sha(number) != sha:
            raise ValueError('stale head immediately before comment')
        comment(number, body)
    return result


def main():
    event = json.loads(pathlib.Path(os.environ['GITHUB_EVENT_PATH']).read_text())
    event_name = os.environ['GITHUB_EVENT_NAME']
    prefix = []
    if event_name == 'pull_request_target':
        number = event['pull_request']['number']
        if pull(number)['state'] == 'closed':
            comment(number, f'{MARKER}\n## 미리보기 시험 종료\n\nPR이 닫혔습니다. 실제 호스팅 자원은 생성하지 않았습니다.')
        prefix.append({'target':f'pr-{number}', 'state':'closed-event-reconciled'})
    elif event_name == 'workflow_dispatch':
        value = event.get('inputs', {}).get('pr', '0')
        if not re.fullmatch(r'\d{1,8}', value):
            raise ValueError('invalid PR number')
        if int(value):
            target_sha(int(value))
    else:
        run = api(f"{ROOT}/actions/runs/{event['workflow_run']['id']}")
        if run['event'] not in ('pull_request', 'push'):
            return [{'state':'ignored-event'}]
    # GitHub keeps at most one pending concurrency member. Any surviving event
    # must therefore reconcile every current request, including devel.
    requests = pages(f'{ROOT}/pulls?state=all&base=devel')
    for pr in requests:
        if pr['state'] == 'closed' and bot_comment(pr['number']):
            if pull(pr['number'])['state'] == 'closed':
                comment(pr['number'], f'{MARKER}\n## 미리보기 시험 종료\n\nPR이 닫혔습니다. 실제 호스팅 자원은 생성하지 않았습니다.')
    numbers = [0] + [p['number'] for p in requests if p['state'] == 'open']
    results = prefix
    for number in numbers:
        try:
            results.append(reconcile(number))
        except ValueError as e:
            results.append({'target':f'pr-{number}' if number else 'devel', 'state':'blocked', 'reason':str(e)})
            # Preserve last verified SHA but visibly mark it as stale after failed CI.
            if number and pull(number)['state'] == 'open':
                previous = bot_comment(number)
                old = re.search(r'<!-- verified-sha:([a-f0-9]{40}) -->', previous['body']) if previous else None
                last = old.group(1) if old else '없음'
                body = f'{MARKER}\n## 미리보기 시험 — 게시 보류\n\n현재 head: `{target_sha(number)}`\n\n사유: {e}\n\n이전 검증 SHA: `{last}`. 현재 head의 성공 증거로 사용하지 않습니다.\n\n호스팅 미설정.'
                if old:
                    body += f'\n\n<!-- verified-sha:{last} -->'
                comment(number, body)
    return results


if __name__ == '__main__':
    results = main()
    pathlib.Path('verification.json').write_text(json.dumps(results, indent=2)+'\n')
    with open(os.environ['GITHUB_STEP_SUMMARY'], 'a') as f:
        f.write('## GitHub-only preview verification\n\n```json\n'+json.dumps(results, indent=2)+'\n```\n')
    print(json.dumps(results))

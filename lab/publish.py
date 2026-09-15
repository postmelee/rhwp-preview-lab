"""Trusted CI gate and Pages lifecycle controller for the isolated lab."""
import base64, json, os, pathlib, re, subprocess
from policy import select_run, validate_zip
from hosting import Pages, meta, latest_pointers, branch as branch_name

from approval import fork, grant, enforce

HOST = None
APPROVAL = None

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


def permission(actor):
    if not re.fullmatch(r'[A-Za-z0-9-]+', actor):
        raise ValueError('invalid approval actor')
    return api(f'{ROOT}/collaborators/{actor}/permission')['permission']


def approval_guard(number, sha):
    if number:
        enforce(pull(number), number, sha, APPROVAL, permission)


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
    approval_guard(number, sha)
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
    def guard():
        approval_guard(number, sha)
        if target_sha(number) != sha:
            raise ValueError('stale head before publish')
        for run in evidence:
            current = api(f"{ROOT}/actions/runs/{run['id']}")
            if (current['run_attempt'], current['status'], current['conclusion']) != (run['run_attempt'], 'completed', 'success'):
                raise ValueError('CI attempt changed during validation')
    guard()
    result = {'target': f'pr-{number}' if number else 'devel', 'sha':sha, 'state':'verified-not-hosted', 'artifact_id':artifact['id'], 'runs':[{'id':r['id'],'attempt':r['run_attempt'],'url':r['html_url']} for r in evidence], **verified}
    if number and fork(pull(number)):
        result['approval'] = APPROVAL
    if HOST:
        baseline = None
        if number:
            deployments = HOST.deployments()
            previous = latest_pointers(deployments).get(f'pr-{number}')
            if previous:
                base_id = meta(previous).get('baseline')
                baseline = next((d for d in deployments if d['id'] == base_id), None)
            else:
                base_sha = pull(number)['base']['sha']
                # Only assets actually selected by a verified devel pointer qualify.
                base_ids = {meta(d)['asset'] for d in deployments if meta(d) and meta(d)['kind'] == 'pointer' and branch_name(d) == 'devel' and meta(d)['sha'] == base_sha}
                baseline = next((d for d in deployments if d['id'] in base_ids), None)
            if not baseline:
                raise ValueError('pinned PR base has no verified devel deployment')
        asset = HOST.asset(data, sha, verified)
        pointer, url = HOST.pointer(result['target'], asset, baseline, guard, external=bool(number and fork(pull(number))))
        result.update(state='hosted', url=url, immutable_url=asset['url'], deployment_id=pointer['id'], asset_id=asset['id'])
        if baseline:
            result.update(base_sha=meta(baseline)['sha'], baseline_id=baseline['id'], baseline_url=baseline['url'])
        guard()
        if number:
            body = f"{MARKER}\n## PR 미리보기\n\n검증한 PR head: `{sha}`\n\n[PR head 열기]({url}) · [검증 버전 고유 링크]({asset['url']}) · [비교 기준 열기]({baseline['url']}) · [현재 devel 열기](https://{HOST.domain})\n\n비교 기준 SHA: `{meta(baseline)['sha']}` (이 미리보기 수명 동안 고정)\n\n[CI 산출물]({ci['html_url']}) · [수동 재검증](https://github.com/{REPO}/actions/workflows/preview.yml)\n\n<!-- verified-sha:{sha} -->"
            if fork(pull(number)):
                body += '\n\n외부 기여 코드 미리보기입니다. 민감한 문서를 열거나 로그인 정보를 입력하지 마세요. 게시 승인은 코드 안전성 보증이 아닙니다.'
            comment(number, body)
    return result


def main():
    global HOST, APPROVAL
    APPROVAL = None
    event = json.loads(pathlib.Path(os.environ['GITHUB_EVENT_PATH']).read_text())
    event_name = os.environ['GITHUB_EVENT_NAME']
    prefix = []
    if event_name == 'pull_request_target':
        number = event['pull_request']['number']
        if pull(number)['state'] == 'closed':
            comment(number, f'{MARKER}\n## 미리보기 시험 종료\n\nPR이 닫혔습니다. 미리보기 링크 제공을 종료합니다. 관리 배포는 참조 확인 후 정리합니다.')
        prefix.append({'target':f'pr-{number}', 'state':'closed-event-reconciled'})
    elif event_name == 'workflow_dispatch':
        value = event.get('inputs', {}).get('pr', '0')
        if not re.fullmatch(r'\d{1,8}', value):
            raise ValueError('invalid PR number')
        if int(value):
            target_sha(int(value))
        approved_sha = event.get('inputs', {}).get('approve_sha', '')
        if approved_sha:
            if not int(value):
                raise ValueError('fork approval requires PR number')
            APPROVAL = grant(pull(int(value)), int(value), approved_sha,
                [os.environ.get('GITHUB_ACTOR', ''), os.environ.get('GITHUB_TRIGGERING_ACTOR', '')], permission)
    else:
        run = api(f"{ROOT}/actions/runs/{event['workflow_run']['id']}")
        if run['event'] not in ('pull_request', 'push'):
            return [{'state':'ignored-event'}]
    if os.environ.get('CLOUDFLARE_API_TOKEN'):
        HOST = Pages()
    # GitHub keeps at most one pending concurrency member. Any surviving event
    # must therefore reconcile every current request, including devel.
    requests = pages(f'{ROOT}/pulls?state=all&base=devel')
    for pr in requests:
        if pr['state'] == 'closed' and bot_comment(pr['number']):
            if pull(pr['number'])['state'] == 'closed':
                comment(pr['number'], f'{MARKER}\n## 미리보기 시험 종료\n\nPR이 닫혔습니다. 미리보기 링크 제공을 종료합니다. 관리 배포는 참조 확인 후 정리합니다.')
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
                preserved = ''
                if HOST:
                    prior = latest_pointers(HOST.deployments()).get(f'pr-{number}')
                    if prior:
                        m = meta(prior)
                        last = m['sha']
                        asset = HOST.api('/deployments/' + m['asset'])
                        preserved = f"\n\n[이전 정상 버전]({asset['url']}) · [현재 devel](https://{HOST.domain})"
                body = f'{MARKER}\n## 미리보기 시험 — 게시 보류\n\n현재 head: `{target_sha(number)}`\n\n사유: {e}\n\n[게시 승인/재검증](https://github.com/{REPO}/actions/workflows/preview.yml): fork는 PR 번호와 현재 전체 SHA를 approve_sha에 입력해야 합니다.\n\n이전 검증 SHA: `{last}`. 현재 head의 성공 증거로 사용하지 않습니다.{preserved}'
                if old:
                    body += f'\n\n<!-- verified-sha:{last} -->'
                comment(number, body)
    if HOST:
        snapshot = [(p['number'], p['state'], p['head']['sha']) for p in requests]
        def cleanup_guard():
            live = pages(f'{ROOT}/pulls?state=all&base=devel')
            if [(p['number'], p['state'], p['head']['sha']) for p in live] != snapshot:
                raise ValueError('requests changed before cleanup')
        try:
            # If a pointer upload failed or a head changed, retain every deployment
            # for retry; never sweep away the previous verified version.
            if any(r.get('state') == 'blocked' for r in results):
                results.append({'state': 'cleanup-deferred'})
            else:
                results.append({'state': 'cleanup', **HOST.cleanup([p['number'] for p in requests if p['state'] == 'open'], cleanup_guard)})
        except ValueError as e:
            results.append({'state': 'cleanup-blocked', 'reason': str(e)})
    return results


if __name__ == '__main__':
    results = main()
    pathlib.Path('verification.json').write_text(json.dumps(results, indent=2)+'\n')
    with open(os.environ['GITHUB_STEP_SUMMARY'], 'a') as f:
        f.write('## Pages preview verification\n\n```json\n'+json.dumps(results, indent=2)+'\n```\n')
    print(json.dumps(results))

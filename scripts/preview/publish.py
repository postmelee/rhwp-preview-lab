"""Trusted publisher. Artifact bytes are validated but never executed here."""
import io,json,os,pathlib,re,subprocess,zipfile
from hosting import Pages,meta,latest_pointers,NAMESPACE
from policy import validate_zip
from reuse import asset_for_sha
from recipe import fingerprint
from producer import current_run
ROOT='repos/'+os.environ['GITHUB_REPOSITORY']
MARKER='<!-- rhwp-studio-preview:v1 -->'

def api(path,body=None,raw=False,method=None):
    args=['gh','api',path]
    if body is not None: args+=['--method',method or 'POST','--input','-']
    data=subprocess.check_output(args,input=json.dumps(body).encode() if body is not None else None,timeout=30)
    return data if raw else json.loads(data)

def pages(path,key=None):
    result=[]
    for page in range(1,31):
        value=api(path+('&' if '?' in path else '?')+f'per_page=100&page={page}')
        values=value[key] if key else value
        result+=values
        if len(values)<100:return result
    raise ValueError('incomplete pagination')

def comment(number,body):
    found=[c for c in pages(f'{ROOT}/issues/{number}/comments') if c['user']['login']=='github-actions[bot]' and c['body'].startswith(MARKER)]
    if len(found)>1: raise ValueError('duplicate preview comments')
    if found:
        if found[0]['body']!=body:api(f"{ROOT}/issues/comments/{found[0]['id']}",{'body':body},method='PATCH')
    else:api(f'{ROOT}/issues/{number}/comments',{'body':body})

def current(number):
    output=subprocess.run(['node',str(pathlib.Path(__file__).with_name('gate.cjs')),os.environ['GITHUB_REPOSITORY'],str(number)],capture_output=True,text=True,timeout=420)
    request=json.loads(output.stdout)
    if not request.get('allowed'):raise ValueError(request.get('reason','CI gate unavailable'))
    return request

def main():
    number=int(os.environ['PREVIEW_PR']); sha=os.environ.get('SOURCE_SHA',''); base_sha=os.environ.get('SOURCE_BASE_SHA','')
    host=Pages()
    open_prs=pages(f'{ROOT}/pulls?state=open&base=devel')
    snapshot=[(p['number'],p['head']['sha']) for p in open_prs]
    def cleanup_guard():
        if [(p['number'],p['head']['sha']) for p in pages(f'{ROOT}/pulls?state=open&base=devel')]!=snapshot:raise ValueError('PR set changed before cleanup')
    if os.environ.get('PREVIEW_CLOSED')=='true':
        pr=api(f'{ROOT}/pulls/{number}')
        if pr['state']!='closed':raise ValueError('PR reopened')
        comment(number,MARKER+'\n## 미리보기 종료\n\nPR이 닫혀 미리보기 제공을 종료했습니다.')
        return {'state':'closed',**host.cleanup([p['number'] for p in open_prs],cleanup_guard)}
    if os.environ.get('PREVIEW_BLOCKED')=='true':
        if number:
            pr=api(f'{ROOT}/pulls/{number}')
            if pr['state']=='open':
                previous=latest_pointers(host.deployments()).get(f'pr-{number}')
                preserved=''
                if previous:
                    m=meta(previous); asset=host.api('/deployments/'+m['asset'])
                    preserved=f"\n\n이전 정상 SHA: `{m['sha']}` · [이전 정상 버전]({asset['url']})"
                comment(number,MARKER+f"\n## Studio 미리보기 — 게시 보류\n\n현재 head: `{pr['head']['sha']}`\n\nCI·빌드·게시 승인이 아직 충족되지 않았습니다. [실행/재생성](https://github.com/{os.environ['GITHUB_REPOSITORY']}/actions/workflows/studio-preview.yml)에서 확인하세요. fork는 PR 번호와 현재 전체 SHA 승인이 필요합니다."+preserved)
        return {'state':'blocked','reason':'CI/build/approval incomplete; previous deployments preserved'}
    producer_identity=None
    def guard():
        r=current(number)
        if r['sha']!=sha or r['base_sha']!=base_sha:raise ValueError('source changed before publication')
        if r.get('external'):
            if os.environ['GITHUB_EVENT_NAME']!='workflow_dispatch' or os.environ.get('APPROVE_SHA')!=sha:raise ValueError('fork current SHA approval required')
            for actor in {os.environ['GITHUB_ACTOR'],os.environ['GITHUB_TRIGGERING_ACTOR']}:
                if not re.fullmatch('[A-Za-z0-9-]+',actor) or api(f'{ROOT}/collaborators/{actor}/permission')['permission'] not in ('write','maintain','admin'):raise ValueError('maintainer permission required')
        if number:
            producer=current_run(ROOT,r,api,pages)
            if producer_identity and (str(producer['id']),str(producer['run_attempt']))!=producer_identity:raise ValueError('native PR build changed before publication')
        return r
    request=guard()
    if number:
        producer=current_run(ROOT,request,api,pages)
        producer_identity=(str(producer['id']),str(producer['run_attempt']))
    run=os.environ['GITHUB_RUN_ID'];attempt=os.environ['GITHUB_RUN_ATTEMPT']
    artifacts=pages(f'{ROOT}/actions/runs/{run}/artifacts','artifacts')
    def asset_for(source,trusted=False):
        previous=asset_for_sha(host.deployments(),source,trusted=trusted)
        if previous:
            body,_=host.read(host.url(previous['url'])+'/build.json')
            stamp=json.loads(body)
            if stamp.get('sha')!=source or stamp.get('profile')!='release' or stamp.get('pwa') is not False or stamp.get('recipe')!=fingerprint():raise ValueError('published build identity mismatch')
            return previous,{'reused_published_asset':previous['id']}
        source_run,source_attempt=producer_identity if number and not trusted else (run,attempt)
        source_artifacts=pages(f'{ROOT}/actions/runs/{source_run}/artifacts','artifacts') if source_run!=run else artifacts
        found=[a for a in source_artifacts if a['name']==f'studio-static-{source}-{source_attempt}' and not a['expired']]
        if len(found)!=1 or found[0]['size_in_bytes']>100*1024*1024:raise ValueError('artifact identity or size')
        a=found[0]; data=api(f"{ROOT}/actions/artifacts/{a['id']}/zip",raw=True)
        verified=validate_zip(data,source,source_run,source_attempt)
        if a.get('digest')!='sha256:'+verified['sha256']:raise ValueError('artifact digest mismatch')
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            if any(n.startswith('samples/') or n in ('sw.js','registerSW.js','manifest.webmanifest') for n in z.namelist()):raise ValueError('sample corpus or PWA included')
            if json.loads(z.read('build.json')).get('recipe')!=fingerprint():raise ValueError('build recipe mismatch')
        verified['recipe']=fingerprint()
        verified['producer']='trusted-source' if trusted else 'pull_request'
        return host.asset(data,source,verified),{'artifact_id':a['id'],**verified}
    baseline=None
    if number:
        previous=latest_pointers(host.deployments()).get(f'pr-{number}')
        if previous:
            baseline=host.api('/deployments/'+meta(previous)['baseline'])
        else:baseline,_=asset_for(base_sha,trusted=True)
    asset,verified=asset_for(sha,trusted=not number)
    pointer,url=host.pointer(f'pr-{number}' if number else 'devel',asset,baseline,guard,external=request.get('external',False))
    guard()
    if number:
        warning='\n\n외부 기여 코드입니다. 민감한 문서를 열거나 로그인 정보를 입력하지 마세요.' if request.get('external') else ''
        comment(number,MARKER+f"\n## Studio 미리보기\n\nPR head: `{sha}`\n\n[PR head 열기]({url}) · [비교 기준 열기]({baseline['url']}) · [현재 devel 열기](https://{NAMESPACE+'devel.' if NAMESPACE else ''}{host.domain})\n\n비교 기준: `{meta(baseline)['sha']}`\n\n[고유 버전]({asset['url']}) · [재생성/게시 승인](https://github.com/{os.environ['GITHUB_REPOSITORY']}/actions/workflows/studio-preview.yml)"+warning)
    return {**request,**verified,'state':'hosted','url':url,'immutable_url':asset['url'],'deployment_id':pointer['id'],'baseline_url':baseline['url'] if baseline else None,'cleanup':host.cleanup([p['number'] for p in open_prs],cleanup_guard)}

def run():
    try:
        result=main()
    except (ValueError,subprocess.SubprocessError) as e:
        result={'state':'blocked','reason':str(e)}
        pathlib.Path('studio-verification.json').write_text(json.dumps(result,indent=2)+'\n')
        raise
    pathlib.Path('studio-verification.json').write_text(json.dumps(result,indent=2)+'\n')
    with open(os.environ['GITHUB_STEP_SUMMARY'],'a') as f:f.write('```json\n'+json.dumps(result,indent=2)+'\n```\n')

if __name__=='__main__':run()

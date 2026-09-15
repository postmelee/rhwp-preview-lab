"""Trusted real-source probe; never executes the downloaded Studio artifact."""
import io,json,os,pathlib,subprocess,zipfile
import hosting
from policy import validate_zip
from publish import api,pages,ROOT

# The real Studio probe must not collect/delete the fixture controller's deployments.
hosting.PREFIX = 'rhwp-studio-probe:v1:'
number=int(os.environ['PREVIEW_PR'])
sha=os.environ['SOURCE_SHA']
run=os.environ.get('SOURCE_ARTIFACT_RUN',os.environ['GITHUB_RUN_ID']); attempt=os.environ.get('SOURCE_ARTIFACT_ATTEMPT',os.environ['GITHUB_RUN_ATTEMPT'])

def guard():
    raw=subprocess.check_output(['node','scripts/preview/gate.cjs','edwardkim/rhwp',str(number)],text=True)
    result=json.loads(raw)
    if not result['allowed'] or result['sha'] != sha or result['base_sha'] != os.environ.get('SOURCE_BASE_SHA',result['base_sha']):
        raise ValueError('source or CI changed before publish')
    if number:
        if os.environ.get('APPROVE_SHA') != sha:
            raise ValueError('real PR probe requires explicit current SHA approval')
        for actor in {os.environ['GITHUB_ACTOR'],os.environ['GITHUB_TRIGGERING_ACTOR']}:
            if api(f'{ROOT}/collaborators/{actor}/permission')['permission'] not in ('write','maintain','admin'):
                raise ValueError('probe approval requires maintainer')
    return result

request=guard()
artifacts=pages(f'{ROOT}/actions/runs/{run}/artifacts','artifacts')
def verified_asset(source_sha):
    found=[a for a in artifacts if a['name']==f'studio-static-{source_sha}-{attempt}' and not a['expired']]
    if len(found)!=1 or found[0]['size_in_bytes']>100*1024*1024: raise ValueError('artifact identity or size')
    a=found[0]; data=api(f"{ROOT}/actions/artifacts/{a['id']}/zip",raw=True)
    verified=validate_zip(data,source_sha,run,attempt)
    if a.get('digest')!='sha256:'+verified['sha256']: raise ValueError('artifact digest mismatch')
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        if any(n.startswith('samples/') or n in ('sw.js','registerSW.js','manifest.webmanifest') for n in z.namelist()):
            raise ValueError('sample corpus or PWA included')
    return a,data,verified

a,data,verified=verified_asset(sha)
host=hosting.Pages()
baseline=None
if number:
    _,base_data,base_verified=verified_asset(request['base_sha'])
    baseline=host.asset(base_data,request['base_sha'],base_verified)
asset=host.asset(data,sha,verified)
pointer,url=host.pointer(f'studio-pr-{number}' if number else 'studio-devel',asset,baseline,guard,external=bool(number))
guard()
# Keep all current real-source pointers and their referenced immutable assets.
deployments=host.deployments(); keep=set()
for p in hosting.latest_pointers(deployments).values():
    m=hosting.meta(p); keep.update([p['id'],m['asset']])
    if m.get('baseline'): keep.add(m['baseline'])
deleted=[]
for d in deployments:
    if hosting.meta(d) and d['id'] not in keep:
        guard()
        host.api('/deployments/'+d['id']+'?force=true',method='DELETE')
        deleted.append(d['id'])
remaining=host.deployments()
if set(deleted)&{d['id'] for d in remaining}: raise ValueError('cleanup unconfirmed')
result={**verified,**request,'run_id':run,'attempt':attempt,'artifact_id':a['id'],'state':'hosted','url':url,'immutable_url':asset['url'],'deployment_id':pointer['id'],'asset_id':asset['id'],'deleted':deleted,'remaining':len(remaining),'baseline_url':baseline['url'] if baseline else None}
pathlib.Path('studio-verification.json').write_text(json.dumps(result,indent=2)+'\n')
with open(os.environ['GITHUB_STEP_SUMMARY'],'a') as f:f.write('```json\n'+json.dumps(result,indent=2)+'\n```\n')

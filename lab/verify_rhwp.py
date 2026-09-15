import io,json,os,pathlib,zipfile
from publish import ROOT, api, pages
from policy import validate_zip
sha='769582fc856f162e57604b318d41414d7b026345'
run=os.environ['GITHUB_RUN_ID']; attempt=os.environ['GITHUB_RUN_ATTEMPT']
artifacts=pages(f'{ROOT}/actions/runs/{run}/artifacts','artifacts')
found=[a for a in artifacts if a['name']==f'rhwp-static-{attempt}' and not a['expired']]
assert len(found)==1 and found[0]['size_in_bytes']<=100*1024*1024
artifact=found[0]; data=api(f"{ROOT}/actions/artifacts/{artifact['id']}/zip",raw=True)
result=validate_zip(data,sha,run,attempt)
assert artifact['digest']=='sha256:'+result['sha256']
with zipfile.ZipFile(io.BytesIO(data)) as z:
    names=z.namelist()
    assert not any(n.startswith('samples/') or n in ('sw.js','registerSW.js','manifest.webmanifest') for n in names)
    result['wasm']=[{'path':f.filename,'bytes':f.file_size} for f in z.infolist() if f.filename.endswith('.wasm')]
result.update(source_sha=sha,run_id=run,attempt=attempt,artifact_id=artifact['id'],state='verified-not-hosted')
pathlib.Path('verification.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result))
with open(os.environ['GITHUB_STEP_SUMMARY'],'a') as f:f.write('```json\n'+json.dumps(result,indent=2)+'\n```\n')

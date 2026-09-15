"""Repackage inspected PR artifacts with the exact source's distributable fonts.
No PR source, JS, WASM, install hook or build script is executed in this job.
"""
import datetime,io,json,os,pathlib,shutil,zipfile
from publish import api,pages,ROOT
from policy import validate_zip
source_run='34949858736'
sha=os.environ['SOURCE_SHA']
if sha not in ('c0f80c0ac6eb249bf1fb82a8f954b7035e15bb53','769582fc856f162e57604b318d41414d7b026345'):
 raise ValueError('uninspected source')
run=api(f'{ROOT}/actions/runs/{source_run}')
if run['path']!='.github/workflows/studio-probe.yml' or not run['head_sha'].startswith('9286b0e') or run['run_attempt']!=1:raise ValueError('source run mismatch')
jobs=pages(f'{ROOT}/actions/runs/{source_run}/attempts/1/jobs','jobs')
if len([j for j in jobs if j['name']==f'build ({sha})' and j['conclusion']=='success'])!=1:raise ValueError('build not successful')
found=[a for a in pages(f'{ROOT}/actions/runs/{source_run}/artifacts','artifacts') if a['name']==f'studio-static-{sha}-1' and not a['expired']]
if len(found)!=1 or found[0]['size_in_bytes']>100*1024*1024:raise ValueError('artifact identity')
a=found[0];data=api(f"{ROOT}/actions/artifacts/{a['id']}/zip",raw=True)
v=validate_zip(data,sha,source_run,1)
if a.get('digest')!='sha256:'+v['sha256']:raise ValueError('artifact digest')
dist=pathlib.Path('repacked-dist');dist.mkdir()
with zipfile.ZipFile(io.BytesIO(data)) as z:
 for name in z.namelist():
  p=dist/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(z.read(name))
fonts=pathlib.Path('../source/assets/fonts')
if not fonts.is_dir() or fonts.is_symlink():raise ValueError('source fonts missing')
shutil.copytree(fonts,dist/'fonts',ignore=lambda path,names:[n for n in names if (pathlib.Path(path)/n).is_symlink()])
stamp=json.loads((dist/'build.json').read_text())
stamp.update(source_run_id=source_run,source_artifact_digest=v['sha256'],run_id=os.environ['GITHUB_RUN_ID'],attempt=os.environ['GITHUB_RUN_ATTEMPT'],packaged_at=datetime.datetime.now(datetime.timezone.utc).isoformat())
(dist/'build.json').write_text(json.dumps(stamp))
print(json.dumps({'source_sha':sha,'source_artifact_id':a['id'],'source_digest':v['sha256'],'font_files':len(list((dist/'fonts').rglob('*')))}))

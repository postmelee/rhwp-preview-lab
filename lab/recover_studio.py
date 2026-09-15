"""Bounded recovery for two explicitly inspected/authorized experiment runs."""
import os,runpy
from publish import api,pages,ROOT
# Do not generalize input artifact provenance from names alone. These run identities
# were created and inspected in this experiment; no arbitrary external run is accepted.
known={
 '34949552214':(0,'0c9e28a481e662ff3b1823cfb1814084a13eb58b','0c9e28a481e662ff3b1823cfb1814084a13eb58b','b1fbc9d'),
 '34949858736':(7118,'c0f80c0ac6eb249bf1fb82a8f954b7035e15bb53','769582fc856f162e57604b318d41414d7b026345','9286b0e'),
}
source=os.environ['SOURCE_RUN']
if source not in known:raise ValueError('not an inspected recovery run')
number,sha,base,harness=known[source]
r=api(f'{ROOT}/actions/runs/{source}')
if r['event']!='workflow_dispatch' or r['path']!='.github/workflows/studio-probe.yml' or not r['head_sha'].startswith(harness) or r['run_attempt']!=1:
 raise ValueError('source run identity changed')
jobs=pages(f'{ROOT}/actions/runs/{source}/attempts/1/jobs','jobs')
expected=['gate']+(['build'] if not number else [f'build ({sha})',f'build ({base})'])
for name in expected:
 found=[j for j in jobs if j['name']==name and j['conclusion']=='success']
 if len(found)!=1:raise ValueError('source build not successful')
os.environ.update(PREVIEW_PR=str(number),SOURCE_SHA=sha,SOURCE_BASE_SHA=base,APPROVE_SHA=sha if number else '',SOURCE_ARTIFACT_RUN=os.environ['GITHUB_RUN_ID'] if os.environ.get('REPACKED')=='true' else source,SOURCE_ARTIFACT_ATTEMPT=os.environ['GITHUB_RUN_ATTEMPT'] if os.environ.get('REPACKED')=='true' else '1')
runpy.run_path('lab/publish_studio.py',run_name='__main__')

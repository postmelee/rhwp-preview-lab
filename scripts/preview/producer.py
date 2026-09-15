"""Bind a PR artifact producer to the latest native pull_request run."""
from urllib.parse import quote
PATH='.github/workflows/studio-preview-build.yml'

def select_run(runs,request,workflow_id):
    matches=[r for r in runs if r.get('workflow_id')==workflow_id
        and r.get('path','').split('@')[0]==PATH and r.get('event')=='pull_request'
        and r.get('head_sha')==request['sha'] and r.get('head_branch')==request['head_branch']
        and r.get('head_repository',{}).get('id')==request['head_repository_id']]
    if not matches:raise ValueError('native PR build missing')
    run=max(matches,key=lambda r:(r['id'],r['run_attempt']))
    if run.get('status')!='completed' or run.get('conclusion')!='success':
        raise ValueError('latest native PR build not successful')
    return run

def current_run(root,request,api,pages):
    workflow=api(root+'/actions/workflows/studio-preview-build.yml')
    runs=pages(root+'/actions/runs?event=pull_request&branch='+quote(request['head_branch'],safe=''),'workflow_runs')
    run=select_run(runs,request,workflow['id'])
    fresh=api(root+'/actions/runs/'+str(run['id']))
    checked=select_run([fresh],request,workflow['id'])
    if checked['run_attempt']!=run['run_attempt']:raise ValueError('PR build rerun changed during read')
    return checked

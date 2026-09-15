"""Reuse only immutable assets already accepted by the trusted Pages publisher."""
import json,os
from recipe import fingerprint
from hosting import Pages,meta,latest_pointers

def asset_for_sha(deployments,sha,trusted=False):
    candidates=[d for d in deployments if meta(d) and meta(d)['kind']=='asset' and meta(d)['sha']==sha and meta(d).get('recipe')==fingerprint() and (not trusted or meta(d).get('producer')=='trusted-source') and d['latest_stage']['status']=='success']
    return max(candidates,key=lambda d:(d['created_on'],d['id'])) if candidates else None

def missing_sources(request,deployments):
    # PR head is built only in pull_request context, never workflow_run/main.
    shas=[] if request['number'] else [request['sha']]
    if request['number']:
        previous=latest_pointers(deployments).get(f"pr-{request['number']}")
        if not previous:shas.append(request['base_sha'])
    return [sha for sha in dict.fromkeys(shas) if not asset_for_sha(deployments,sha,trusted=True)]

if __name__=='__main__':
    request=json.load(open('preview-request.json'))
    builds=[]
    if request.get('allowed') and not request.get('closed'):
        builds=missing_sources(request,Pages().deployments())
    with open(os.environ['GITHUB_OUTPUT'],'a') as f:f.write('builds='+json.dumps(builds)+'\n')

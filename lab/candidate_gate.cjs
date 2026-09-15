'use strict';
const fs=require('node:fs');
const {execFileSync}=require('node:child_process');
const {pages}=require('../scripts/preview/gate.cjs');
const read=p=>JSON.parse(execFileSync('gh',['api',p],{encoding:'utf8',timeout:30000}));
async function inspect(repository,number,api=read) {
 if(repository!=='postmelee/rhwp-preview-lab')throw Error('lab-only CI adapter');
 const root='repos/'+repository;
 if(!number){const sha=api(root+'/git/ref/heads/devel').object.sha;return {allowed:true,repository,number,sha,base_sha:sha};}
 const pr=api(root+'/pulls/'+number);
 if(pr.state!=='open'||pr.base.ref!=='devel'||!pr.head.repo)throw Error('PR identity invalid');
 const result={repository,number,sha:pr.head.sha,base_sha:pr.base.sha,head_repository:pr.head.repo.full_name,head_repository_id:pr.head.repo.id,head_branch:pr.head.ref,external:pr.head.repo.id!==pr.base.repo.id,runs:[]};
 for(const [file,job] of [['ci.yml','build'],['quality.yml','quality']]) {
  const path='.github/workflows/'+file;
  const source=api(root+'/contents/'+path+'?ref='+pr.head.sha);
  if(Buffer.from(source.content,'base64').toString()!==fs.readFileSync(path,'utf8'))return {...result,allowed:false,reason:'CI definition changed'};
  const workflow=api(root+'/actions/workflows/'+file);
  const runs=pages(root+'/actions/runs?event=pull_request&branch='+encodeURIComponent(pr.head.ref),'workflow_runs',api).filter(r=>r.workflow_id===workflow.id&&r.head_sha===pr.head.sha&&r.head_repository?.id===pr.head.repo.id&&r.event==='pull_request');
  runs.sort((a,b)=>b.id-a.id||b.run_attempt-a.run_attempt);
  const latest=runs[0];
  if(!latest||latest.status!=='completed'||latest.conclusion!=='success')return {...result,allowed:false,reason:'Lab CI not successful:'+file};
  const jobs=pages(root+'/actions/runs/'+latest.id+'/attempts/'+latest.run_attempt+'/jobs','jobs',api);
  if(jobs.length!==1||jobs[0].name!==job||jobs[0].conclusion!=='success')return {...result,allowed:false,reason:'Lab required job missing'};
  result.runs.push({id:latest.id,attempt:latest.run_attempt,path});
 }
 const fresh=api(root+'/pulls/'+number);
 return {...result,allowed:fresh.state==='open'&&fresh.head.sha===pr.head.sha&&fresh.base.sha===pr.base.sha,reason:'strict-lab-ci-gate'};
}
module.exports={inspect};
if(require.main===module)inspect(process.argv[2],Number(process.argv[3])).then(r=>{console.log(JSON.stringify(r));if(!r.allowed)process.exitCode=2;}).catch(e=>{console.log(JSON.stringify({allowed:false,reason:e.message}));process.exitCode=2;});

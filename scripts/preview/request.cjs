'use strict';
const fs = require('node:fs');
const { execFileSync } = require('node:child_process');
const { inspect, pages, verifyPolicy } = require('./gate.cjs');
const read = path => JSON.parse(execFileSync('gh',['api',path],{encoding:'utf8',timeout:30000,maxBuffer:20*1024*1024}));
function resolve(event,type,repository,read) {
 let number=0, closed=false;
 if(type==='workflow_dispatch') {
  const value=event.inputs?.pr||'0';
  if(!/^\d{1,8}$/.test(value)) throw Error('invalid PR number');
  number=Number(value);
 } else if(type==='workflow_run') {
  const run=event.workflow_run;
  if(run.event!=='pull_request') return {allowed:false,reason:'unrelated-run'};
  const matches=pages(`repos/${repository}/pulls?state=open&base=devel`,null,read).filter(p=>p.head.sha===run.head_sha&&p.head.ref===run.head_branch&&p.head.repo?.id===run.head_repository?.id);
  if(matches.length!==1) return {allowed:false,reason:'stale-or-ambiguous-run'};
  number=matches[0].number;
 } else if(type==='pull_request_target') {
  number=event.pull_request.number;
  const pr=read(`repos/${repository}/pulls/${number}`);
  closed=pr.state==='closed'&&pr.base.ref==='devel';
  if(!closed) return {allowed:false,reason:'not-closed'};
 } else if(type!=='push'||event.ref!=='refs/heads/devel') return {allowed:false,reason:'unrelated-event'};
 if(closed) return {allowed:true,closed,number,sha:'',base_sha:'',builds:[]};
 return {number,closed:false};
}
async function main({inspectRequest=inspect,verify=verifyPolicy}={}) {
 const repository=process.env.GITHUB_REPOSITORY;
 const event=JSON.parse(fs.readFileSync(process.env.GITHUB_EVENT_PATH,'utf8'));
 const type=process.env.GITHUB_EVENT_NAME;
 const target=resolve(event,type,repository,read);
 if(target.allowed===false||target.closed)return target;
 const number=target.number;
 const request=await inspectRequest(repository,number,read);
 if(request.allowed&&number) verify(repository,request.base_sha,read);
 if(request.external && (type!=='workflow_dispatch'||event.inputs.approve_sha!==request.sha)) {
  request.allowed=false;request.reason='fork-awaiting-current-SHA-approval';
 }
 return {...request,closed:false,builds:request.allowed?[...new Set([request.sha,request.base_sha])]:[]};
}
function writeResult(r) {
 fs.writeFileSync('preview-request.json',JSON.stringify(r,null,2)+'\n');
 fs.appendFileSync(process.env.GITHUB_STEP_SUMMARY,`## Studio preview\n\n${r.reason||'closed'}\n\nSHA: ${r.sha||'n/a'}\n`);
 fs.appendFileSync(process.env.GITHUB_OUTPUT,Object.entries({allowed:String(r.allowed),closed:String(Boolean(r.closed)),pr:r.number||0,sha:r.sha||'',base_sha:r.base_sha||'',builds:JSON.stringify(r.builds||[])}).map(([k,v])=>`${k}=${v}\n`).join(''));
}
module.exports={resolve,main,writeResult};
if(require.main===module) main().then(writeResult).catch(e=>{fs.writeFileSync('preview-request.json',JSON.stringify({allowed:false,reason:e.message})+'\n');console.error(e.message);process.exitCode=1;});

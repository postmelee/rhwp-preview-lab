'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const {inspect, pages} = require('./gate.cjs');
const sha='a'.repeat(40), base='b'.repeat(40);
function source({files=[{filename:'README.md',status:'modified'}],runs=[],change=false}={}) {
 let calls=0;
 const pr={number:1,state:'open',changed_files:files.length,created_at:'2026-09-15T00:00:00Z',
  head:{sha,ref:'topic',repo:{id:2,full_name:'fork/rhwp'}},base:{sha:base,ref:'devel',repo:{id:1,full_name:'owner/rhwp'}}};
 return path=>{
  if(path.endsWith('/pulls/1')) {calls++;return change&&calls>1?{...pr,head:{...pr.head,sha:'c'.repeat(40)}}:pr;}
  if(path.includes('/files?'))return files;
  if(path.includes('/actions/runs?'))return {workflow_runs:runs};
  throw Error('unexpected '+path);
 };
}
test('trusted policy permits inapplicable workflow paths',async()=>assert.equal((await inspect('owner/rhwp',1,source())).allowed,true));
test('Rust change with missing CI is blocked',async()=>assert.equal((await inspect('owner/rhwp',1,source({files:[{filename:'src/lib.rs',status:'modified'}]}))).allowed,false));
test('new live head invalidates completed collection',async()=>assert.equal((await inspect('owner/rhwp',1,source({change:true}))).reason,'request-changed-during-gate'));
test('observed advisory failure blocks publish',async()=>{
 const r=await inspect('owner/rhwp',1,source({runs:[{id:4,workflow_id:8,head_sha:sha,head_repository:{id:2},name:'Adapter inter-diff',path:'.github/workflows/adapter.yml',status:'completed',conclusion:'failure'}]}));
 assert.equal(r.allowed,false);assert.match(r.reason,/observed-workflow/);
});
test('skipped housekeeping is not a failed test',async()=>assert.equal((await inspect('owner/rhwp',1,source({runs:[{id:4,workflow_id:8,head_sha:sha,head_repository:{id:2},name:'Cancel stale PR runs',path:'.github/workflows/cancel-stale-pr-runs.yml',status:'completed',conclusion:'skipped'}]}))).allowed,true));
test('latest failed rerun does not reuse old success',async()=>{
 const r={workflow_id:8,head_sha:sha,head_repository:{id:2},name:'Extra',path:'.github/workflows/extra.yml',status:'completed'};
 assert.equal((await inspect('owner/rhwp',1,source({runs:[{...r,id:8,run_attempt:1,conclusion:'success'},{...r,id:8,run_attempt:2,conclusion:'failure'}]}))).allowed,false);
});
test('incomplete pagination refuses partial evidence',()=>assert.throws(()=>pages('x',null,()=>Array(100).fill({})),/incomplete pagination/));
test('devel is a deployment build without duplicate PR CI',async()=>assert.equal((await inspect('owner/rhwp',0,()=>({object:{sha}}))).allowed,true));
test('invalid request cannot select an API or executable path',async()=>await assert.rejects(inspect('../other',1,()=>{}),/invalid request/));

test('trusted controller rejects a mismatched local policy module',()=>{
 const {verifyRuntime}=require('./gate.cjs');
 assert.throws(()=>verifyRuntime({'scripts/ci-impact-policy.cjs':'0'.repeat(40)},()=>Buffer.from('wrong policy')),/trusted-runtime-policy-drift/);
});
test('local canonical policy modules match the pinned runtime contract',()=>{
 const {verifyRuntime}=require('./gate.cjs');
 verifyRuntime(require('./trusted-policy.json'));
});

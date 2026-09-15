'use strict';
const test=require('node:test');
const assert=require('node:assert/strict');
const {resolve}=require('./request.cjs');
const repo='owner/rhwp',sha='a'.repeat(40);
test('only devel push selects deployment build',()=>{
 assert.equal(resolve({ref:'refs/heads/main'},'push',repo).allowed,false);
 assert.deepEqual(resolve({ref:'refs/heads/devel'},'push',repo),{number:0,closed:false});
});
test('dispatch cannot inject PR number',()=>assert.throws(()=>resolve({inputs:{pr:'1\nsha=bad'}},'workflow_dispatch',repo),/invalid PR/));
test('stale completion cannot select current PR',()=>assert.equal(resolve({workflow_run:{event:'pull_request',head_sha:sha,head_branch:'topic',head_repository:{id:2}}},'workflow_run',repo,()=>[{number:1,head:{sha:'b'.repeat(40),ref:'topic',repo:{id:2}}}]).allowed,false));
test('fork completion is bound to both repository id and branch',()=>{
 const run={event:'pull_request',head_sha:sha,head_branch:'topic',head_repository:{id:2}};
 const pr={number:1,head:{sha,ref:'topic',repo:{id:3}}};
 assert.equal(resolve({workflow_run:run},'workflow_run',repo,()=>[pr]).allowed,false);
 pr.head.repo.id=2;
 assert.deepEqual(resolve({workflow_run:run},'workflow_run',repo,()=>[pr]),{number:1,closed:false});
});
test('reopened PR invalidates an older close event',()=>assert.equal(resolve({pull_request:{number:1}},'pull_request_target',repo,()=>({state:'open',base:{ref:'devel'}})).allowed,false));
test('confirmed close skips source build',()=>assert.deepEqual(resolve({pull_request:{number:1}},'pull_request_target',repo,()=>({state:'closed',base:{ref:'devel'}})).builds,[]));

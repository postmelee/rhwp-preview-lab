'use strict';
// Executed from a trusted checkout only. GitHub data never selects executable code.
const fs = require('node:fs');
const path = require('node:path');
const {createHash}=require('node:crypto');
const { execFileSync } = require('node:child_process');
const { classifyChanges } = require('../ci-impact-classifier.cjs');
const { determinePolicy, auditPolicyRuns, selectLatestWorkflowRun, WORKFLOW_PATHS } = require('../ci-impact-policy.cjs');
const { collectWorkflowEvidence } = require('../ci-workflow-evidence.cjs');

function api(path) {
  return JSON.parse(execFileSync('gh', ['api', path], { encoding: 'utf8', timeout: 30000, maxBuffer: 20 * 1024 * 1024 }));
}
function pages(path, key, read = api) {
  const result = [];
  for (let page = 1; page <= 30; page++) {
    const value = read(`${path}${path.includes('?') ? '&' : '?'}per_page=100&page=${page}`);
    const items = key ? value[key] : value;
    if (!Array.isArray(items)) throw Error('invalid paginated response');
    result.push(...items);
    if (items.length < 100) return result;
  }
  throw Error('incomplete pagination');
}
function normalize(snapshot) {
  const r = snapshot.run;
  return { ...snapshot, run: {
    id: r.id, attempt: r.run_attempt, name: r.name, path: r.path.split('@')[0], event: r.event,
    status: r.status, conclusion: r.conclusion, headSha: r.head_sha, headBranch: r.head_branch,
    headRepository: r.head_repository?.full_name,
    pullNumbers: (r.pull_requests || []).map(p => p.number),
    baseShas: (r.pull_requests || []).map(p => p.base?.sha || ''),
  }};
}
function sameRequest(a, b) {
  return a.state === b.state && a.head.sha === b.head.sha && a.head.repo?.id === b.head.repo?.id
    && a.base.sha === b.base.sha && a.base.ref === b.base.ref;
}
async function inspect(repository, number, read = api) {
  if (!/^[A-Za-z0-9][A-Za-z0-9_.-]*\/[A-Za-z0-9][A-Za-z0-9_.-]*$/.test(repository) || !Number.isSafeInteger(number) || number < 0) throw Error('invalid request');
  const root = `repos/${repository}`;
  if (!number) {
    const sha = read(`${root}/git/ref/heads/devel`).object.sha;
    if (!/^[a-f0-9]{40}$/.test(sha)) throw Error('invalid devel SHA');
    return { allowed: true, repository, number, sha, base_sha: sha, reason: 'trusted-devel-deployment-build-only', runs: [] };
  }
  const pr = read(`${root}/pulls/${number}`);
  if (pr.state !== 'open' || pr.base.ref !== 'devel' || pr.base.repo.full_name !== repository || !pr.head.repo) throw Error('PR closed or identity unavailable');
  const files = pages(`${root}/pulls/${number}/files`, null, read);
  if (files.length !== pr.changed_files || files.length >= 3000) throw Error('incomplete changed files');
  const identity = { number, baseRef: pr.base.ref, baseSha: pr.base.sha, headSha: pr.head.sha,
    headBranch: pr.head.ref, headRepository: pr.head.repo.full_name, authorPermission: 'read', createdAt: pr.created_at };
  const input = { repository, pullRequest: identity, files, classification: classifyChanges({eventName:'pull_request', files}), controllerAvailable: true };
  const policy = determinePolicy(input);
  const runs = pages(`${root}/actions/runs?event=pull_request&branch=${encodeURIComponent(pr.head.ref)}`, 'workflow_runs', read);
  const workflows = {};
  const evidence = [];
  for (const [name, path] of Object.entries(WORKFLOW_PATHS)) {
    if (policy.expected_workflows[name] !== 'true') continue;
    const run = selectLatestWorkflowRun(runs, {name, path, pullNumber:number, ...identity});
    if (!run) continue;
    const snapshot = await collectWorkflowEvidence({run,
      getRun: async id => read(`${root}/actions/runs/${id}`),
      listJobs: async id => pages(`${root}/actions/runs/${id}/jobs?filter=latest`, 'jobs', read),
      maxAttempts:1, delayMs:0});
    workflows[name] = normalize(snapshot);
    evidence.push({name, id:run.id, attempt:snapshot.run.run_attempt, url:run.html_url});
  }
  const audit = auditPolicyRuns({...input, policy, workflows, currentHeadSha:pr.head.sha});
  // Advisory PR workflows are not required when absent, but an observed failure or
  // unfinished run must not be silently described as "all CI passed".
  const latest = new Map();
  const housekeeping = new Set(['.github/workflows/cancel-stale-pr-runs.yml']);
  for (const r of runs.filter(r => r.head_sha === pr.head.sha && r.head_repository?.id === pr.head.repo.id && !housekeeping.has(r.path?.split('@')[0]))) {
    const old = latest.get(r.workflow_id);
    if (!old || r.id > old.id || (r.id === old.id && r.run_attempt > old.run_attempt)) latest.set(r.workflow_id, r);
  }
  const extra = [...latest.values()].find(r => r.status !== 'completed' || r.conclusion !== 'success');
  const fresh = read(`${root}/pulls/${number}`);
  const reason = !sameRequest(pr, fresh) ? 'request-changed-during-gate' : extra ? `observed-workflow-not-success:${extra.name}:${extra.id}` : audit.reason;
  return {allowed: sameRequest(pr, fresh) && !extra && audit.publish === 'true' && audit.conclusion === 'success',
    repository, number, sha:pr.head.sha, base_sha:pr.base.sha, head_repository:pr.head.repo.full_name,
    head_repository_id:pr.head.repo.id, head_branch:pr.head.ref, external:pr.head.repo.id !== pr.base.repo.id, policy, audit, reason, runs:evidence};
}
function verifyRuntime(hashes,readFile=file=>fs.readFileSync(path.join(__dirname,'../..',file))) {
  for(const [file,expected] of Object.entries(hashes).filter(([file])=>file.startsWith('scripts/'))) {
    const bytes=readFile(file);
    const actual=createHash('sha1').update(Buffer.from(`blob ${bytes.length}\0`)).update(bytes).digest('hex');
    if(actual!==expected)throw Error(`trusted-runtime-policy-drift:${file}`);
  }
}
function verifyPolicy(repository, baseSha, read=api) {
  const hashes=JSON.parse(fs.readFileSync(path.join(__dirname,'trusted-policy.json'),'utf8'));
  verifyRuntime(hashes);
  for (const [file,hash] of Object.entries(hashes)) {
    if(read(`repos/${repository}/contents/${file}?ref=${baseSha}`).sha !== hash) throw Error(`trusted-policy-drift:${file}`);
  }
}
module.exports = {inspect, normalize, pages, sameRequest, verifyPolicy, verifyRuntime};
if (require.main === module) inspect(process.argv[2], Number(process.argv[3] || 0)).then(result => {
  if(result.number && result.allowed) verifyPolicy(result.repository,result.base_sha);
  process.stdout.write(JSON.stringify(result, null, 2)+'\n');
  if (!result.allowed) process.exitCode = 2;
}).catch(error => {process.stdout.write(JSON.stringify({allowed:false, reason:error.message})+'\n'); process.exitCode=2;});

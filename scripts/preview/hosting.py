"""Static-only Pages adapter. No artifact code is executed, even for probing."""
import hashlib
import io
import json
import os
import pathlib
import re
import subprocess
import tempfile
import time
import urllib.error
import urllib.request
import zipfile

NAMESPACE = os.environ.get('PREVIEW_NAMESPACE', '')
if NAMESPACE and not re.fullmatch('[a-z][a-z0-9-]{0,19}-', NAMESPACE):
    raise ValueError('invalid preview namespace')
PREFIX = 'rhwp-studio:v1:' + NAMESPACE
WRANGLER = pathlib.Path(__file__).resolve().parent / 'node_modules/.bin/wrangler'


def served_path(name):
    if name == 'index.html':
        return ''
    if name.endswith('/index.html'):
        return name[:-10]
    return name[:-5] if name.endswith('.html') else name


def meta(deployment):
    message = deployment.get('deployment_trigger', {}).get('metadata', {}).get('commit_message', '')
    if not message.startswith(PREFIX):
        return None
    value = json.loads(message[len(PREFIX):])
    if value.get('kind') not in ('asset', 'pointer'):
        raise ValueError('unknown managed deployment')
    return value


def branch(deployment):
    value = deployment['deployment_trigger']['metadata']['branch']
    return value[len(NAMESPACE):] if NAMESPACE and value.startswith(NAMESPACE) else value


def latest_pointers(deployments):
    pointers = {}
    for d in sorted(deployments, key=lambda x: (x['created_on'], x['id'])):
        m = meta(d)
        if m and m['kind'] == 'pointer' and d['latest_stage']['status'] == 'success':
            pointers[branch(d)] = d
    return pointers


def retained_ids(deployments, open_numbers, canonical):
    keep = {canonical} if canonical else set()
    for b, d in latest_pointers(deployments).items():
        if b == 'devel' or b in {f'pr-{n}' for n in open_numbers}:
            keep.add(d['id'])
            m = meta(d)
            keep.add(m['asset'])
            if m.get('baseline'):
                keep.add(m['baseline'])
    return keep


class Pages:
    def __init__(self):
        account = os.environ['CLOUDFLARE_ACCOUNT_ID']
        self.project = os.environ['CLOUDFLARE_PAGES_PROJECT']
        if not re.fullmatch(r'[a-z0-9](?:[a-z0-9-]{0,56}[a-z0-9])?', self.project) or not re.fullmatch('[a-f0-9]{32}', account):
            raise ValueError('invalid configured Pages destination')
        self.root = f'https://api.cloudflare.com/client/v4/accounts/{account}/pages/projects/{self.project}'
        self.creates = 0
        self.deleted = []
        self.info = self.api('')
        if self.info.get('source'):
            raise ValueError('expected Direct Upload project')
        self.domain = self.info['subdomain']
        if self.domain != self.project + '.pages.dev':
            raise ValueError('unexpected Pages domain')
        if self.info['production_branch'] != 'devel':
            raise ValueError('Pages project must have production branch devel')

    def api(self, path, body=None, method='GET'):
        req = urllib.request.Request(self.root + path,
            data=json.dumps(body).encode() if body is not None else None,
            headers={'Authorization': 'Bearer ' + os.environ['CLOUDFLARE_API_TOKEN'], 'Content-Type': 'application/json'}, method=method)
        try:
            with urllib.request.urlopen(req, timeout=30) as response:
                result = json.load(response)
        except urllib.error.HTTPError as e:
            # Report API status/code only, never arbitrary response/credentials.
            try:
                codes = [v.get('code') for v in json.loads(e.read()).get('errors', [])]
            except (ValueError, TypeError):
                codes = []
            raise ValueError(f'Pages API {method} failed: HTTP {e.code}, codes {codes}') from None
        if not result['success']:
            raise ValueError('Pages API unsuccessful')
        return result['result']

    def deployments(self):
        items = []
        for page in range(1, 11):
            batch = self.api(f'/deployments?per_page=20&page={page}')
            items.extend(batch)
            if len(batch) < 20:
                return items
        raise ValueError('Pages pagination overflow')

    def url(self, url):
        # No secrets ever accompany public static probes; reject redirects.
        from urllib.parse import urlsplit
        parts = urlsplit(url)
        if parts.scheme != 'https' or not (parts.hostname == self.domain or parts.hostname.endswith('.' + self.domain)) or parts.username or parts.port:
            raise ValueError('foreign deployment URL')
        return url.rstrip('/')

    def read(self, url):
        class NoRedirect(urllib.request.HTTPRedirectHandler):
            def redirect_request(self, *args, **kwargs):
                return None
        request = urllib.request.Request(self.url(url), headers={'Cache-Control': 'no-cache', 'User-Agent': 'rhwp-preview-lab/2 (+https://github.com/postmelee/rhwp-preview-lab)'})
        with urllib.request.build_opener(NoRedirect).open(request, timeout=30) as response:
            return response.read(25 * 1024 * 1024 + 1), response.headers.get_content_type()

    def probe(self, deployment, files):
        url = self.url(deployment['url'])
        print(json.dumps({"probe_url": url, "deployment_id": deployment["id"]}))
        # Bound propagation wait. Compare real bytes, not only trusted-looking metadata.
        for attempt in range(6):
            try:
                for name, data in files.items():
                    if name == '_headers':
                        continue  # Pages consumes this configuration instead of serving it.
                    actual, mime = self.read(url + '/' + served_path(name))
                    if actual != data:
                        raise ValueError('static bytes mismatch: ' + name)
                    if name.endswith('.wasm') and mime != 'application/wasm':
                        raise ValueError('WASM MIME mismatch')
                return
            except (OSError, ValueError) as e:
                if attempt == 5:
                    raise ValueError("public deployment probe failed: " + str(e)) from None
                time.sleep(3)

    def deploy(self, b, sha, metadata, files):
        message = PREFIX + json.dumps(metadata, separators=(',', ':'), sort_keys=True)
        items = self.deployments()
        candidates = [d for d in items if branch(d) == b and meta(d) == metadata and d['latest_stage']['status'] == 'success']
        # For pointers, reuse only the current one, never an old matching version.
        if metadata['kind'] == 'pointer':
            latest = latest_pointers(items).get(b)
            candidates = [latest] if latest and meta(latest) == metadata else []
        if candidates:
            result = max(candidates, key=lambda d: d['created_on'])
            self.probe(result, files)
            return result
        if self.creates >= 12 or sum(meta(d) is not None for d in items) >= 100:
            raise ValueError('preview deployment budget exceeded')
        self.creates += 1
        with tempfile.TemporaryDirectory(prefix='pages-static-') as folder:
            root = pathlib.Path(folder)
            dist = root / 'dist'
            dist.mkdir()
            for name, data in files.items():
                target = dist / name
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(data)
            # Isolated cwd: no functions/, package.json, .env, or Wrangler config discovery.
            env = {k: v for k, v in os.environ.items() if k in ('PATH', 'HOME', 'CLOUDFLARE_ACCOUNT_ID', 'CLOUDFLARE_API_TOKEN')}
            env.update(CI='true', WRANGLER_SEND_METRICS='false')
            command = [str(WRANGLER), 'pages', 'deploy', str(dist), '--project-name', self.project,
                       '--branch', NAMESPACE + b, '--commit-hash', sha, '--commit-message', message, '--commit-dirty=false']
            try:
                subprocess.run(command, cwd=root, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=180, check=True)
            except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
                # Upload may have succeeded despite a lost response. Requery below.
                pass
        candidates = [d for d in self.deployments() if branch(d) == b and meta(d) == metadata and d['latest_stage']['status'] == 'success']
        if not candidates:
            raise ValueError('Pages upload not confirmed')
        result = max(candidates, key=lambda d: d['created_on'])
        self.probe(result, files)
        return result

    def asset(self, data, sha, verified):
        # validate_zip was already applied by caller before this extraction.
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            files = {n: z.read(n) for n in z.namelist()}
        metadata = {'kind': 'asset', 'sha': sha, 'digest': verified['sha256'], 'recipe': verified['recipe'], 'producer': verified['producer']}
        return self.deploy('assets', sha, metadata, files)

    def pointer(self, target, asset, baseline, guard, external=False):
        m = meta(asset)
        value = {'kind': 'pointer', 'sha': m['sha'], 'asset': asset['id']}
        if external:
            value['external'] = True
        if baseline:
            value.update(baseline=baseline['id'], base_sha=meta(baseline)['sha'])
        url = self.url(asset['url'])
        files = {'index.html': ('<!doctype html><meta charset="utf-8"><meta http-equiv="refresh" content="0;url=' + url + '"><title>검증된 미리보기</title><a href="' + url + '">검증된 미리보기 열기</a>').encode(),
                 'preview.json': json.dumps(value, sort_keys=True).encode(),
                 '_headers': b'/*\n  Cache-Control: no-store\n  X-Robots-Tag: noindex\n'}
        if external:
            files['index.html'] = ('<!doctype html><meta charset="utf-8"><title>외부 기여 미리보기</title><h1>외부 기여 코드 미리보기</h1><p>이 PR의 코드는 검토 중입니다. 민감한 문서를 열거나 로그인 정보를 입력하지 마세요. 게시 승인은 코드 안전성 보증이 아닙니다.</p><p>SHA: ' + m['sha'] + '</p><a href="' + url + '" rel="noreferrer">이 버전 열기</a>').encode()
        guard()
        d = self.deploy(target, m['sha'], value, files)
        guard()
        aliases = d.get('aliases') or []
        expected = 'https://' + ('' if target == 'devel' and not NAMESPACE else NAMESPACE + target + '.') + self.domain
        if target == 'devel' and not NAMESPACE:
            current = self.api('')
            if current['canonical_deployment']['id'] != d['id']:
                raise ValueError('production pointer is not canonical')
        elif expected not in aliases:
            raise ValueError('branch alias not assigned')
        # Branch aliases propagate separately from the immutable deployment URL.
        self.probe({'url': expected, 'id': d['id']}, {'preview.json': files['preview.json']})
        return d, expected

    def cleanup(self, open_numbers, guard):
        items = self.deployments()
        canonical = (self.api('').get('canonical_deployment') or {}).get('id')
        keep = retained_ids(items, open_numbers, canonical)
        # Pointers first, assets second. Referenced assets are never deleted.
        obsolete = sorted([d for d in items if meta(d) and d['id'] not in keep], key=lambda d: meta(d)['kind'] == 'asset')
        for d in obsolete:
            guard()
            suffix = '?force=true' if d['environment'] != 'production' else ''
            self.api('/deployments/' + d['id'] + suffix, method='DELETE')
            self.deleted.append(d['id'])
        remaining = self.deployments()
        if set(self.deleted) & {d['id'] for d in remaining}:
            raise ValueError('deleted deployments still listed')
        return {'deleted': self.deleted, 'retained': sorted(keep), 'remaining': len(remaining)}

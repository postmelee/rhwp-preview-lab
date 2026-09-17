"""Disposable checkout adapter and bounded static artifact validation for Pages."""
import datetime as dt
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from control import recipe, valid_sha

BASE = '/rhwp-preview-lab/'
EXTENSIONS = {'.html', '.json', '.js', '.css', '.wasm', '.woff', '.woff2', '.ttf', '.otf',
              '.png', '.svg', '.jpg', '.jpeg', '.ico', '.txt', '.md', '.ts', '.webp'}


def prepare(source, sha):
    source = Path(source).resolve()
    valid_sha(sha)
    if subprocess.check_output(['git', '-C', str(source), 'rev-parse', 'HEAD'], text=True).strip() != sha:
        raise ValueError('checkout SHA mismatch')
    studio = source / 'rhwp-studio'
    public = studio / '.devel-public'
    public.mkdir()
    for entry in (studio / 'public').iterdir():
        if entry.name == 'samples':
            continue
        target = entry
        if entry.is_symlink():
            if entry.name != 'fonts' or entry.resolve() != (source / 'assets/fonts').resolve():
                continue
            target = entry.resolve()
        if not target.resolve().is_relative_to(source):
            raise ValueError('public asset escapes checkout')
        if target.is_dir():
            shutil.copytree(target, public / entry.name,
                            ignore=lambda directory, names: [n for n in names if (Path(directory) / n).is_symlink()])
        else:
            shutil.copyfile(target, public / entry.name)
    (studio / 'vite.devel.config.ts').write_text("""import config from './vite.config';
export default {...config, base:'/rhwp-preview-lab/', publicDir:'.devel-public',
  plugins:config.plugins.flat().filter(p=>!p.name.startsWith('vite-plugin-pwa'))};
""")


def stamp(source, sha):
    dist = Path(source) / 'rhwp-studio/dist'
    metadata = {'sha': valid_sha(sha), 'recipe': recipe(), 'profile': 'release', 'pwa': False,
                'run_id': os.environ['GITHUB_RUN_ID'], 'attempt': os.environ['GITHUB_RUN_ATTEMPT'],
                'built_at': dt.datetime.now(dt.timezone.utc).isoformat(), 'base': BASE}
    (dist / 'build.json').write_text(json.dumps(metadata))
    (dist / 'preview-status.js').write_bytes(Path(__file__).with_name('status.js').read_bytes())
    index = dist / 'index.html'
    html = index.read_text()
    if '</body>' not in html:
        raise ValueError('missing HTML body')
    banner = f'''<aside id="devel-preview-status" data-source-sha="{sha}" aria-label="Preview build" style="position:fixed;bottom:0;right:0;z-index:2147483647;background:#132235;color:white;font:11px monospace;padding:5px;max-width:90vw">
<a style="color:#bde0ff" href="https://github.com/edwardkim/rhwp/commit/{sha}" target="_blank" rel="noopener">devel {sha[:12]}</a> · {metadata['built_at']}
· <span id="preview-freshness">최신 여부 확인 중</span>
· <a style="color:#bde0ff" href="https://github.com/postmelee/rhwp-preview-lab/actions/workflows/devel-pages.yml" target="_blank" rel="noopener">갱신 상태·실패 로그</a></aside>
<script type="module" src="{BASE}preview-status.js"></script>'''
    index.write_text(html.replace('</body>', banner + '</body>'))


def validate(dist, sha, key, run_id, attempt):
    dist = Path(dist)
    files = []
    total = 0
    for path in dist.rglob('*'):
        rel = path.relative_to(dist)
        if path.is_symlink():
            raise ValueError('symlink in artifact')
        if path.is_dir():
            continue
        if not path.is_file() or path.suffix not in EXTENSIONS:
            raise ValueError(f'non-static asset: {rel}')
        if any(part in ('samples', 'node_modules', '.git') for part in rel.parts):
            raise ValueError('private or sample corpus in artifact')
        if path.name in ('sw.js', 'registerSW.js') or path.name.startswith('workbox-'):
            raise ValueError('service worker in preview')
        size = path.stat().st_size
        total += size
        if size > 50 * 1024 * 1024 or total > 100 * 1024 * 1024:
            raise ValueError('artifact size limit')
        files.append(rel.as_posix())
    if len(files) > 20000 or not {'index.html', 'build.json', 'preview-status.js'} <= set(files):
        raise ValueError('missing entry/provenance or too many files')
    metadata = json.loads((dist / 'build.json').read_text())
    if (metadata['sha'], metadata['recipe'], str(metadata['run_id']), str(metadata['attempt'])) != (sha, key, str(run_id), str(attempt)):
        raise ValueError('artifact provenance mismatch')
    if metadata.get('base') != BASE or metadata.get('profile') != 'release' or metadata.get('pwa') is not False:
        raise ValueError('incorrect build mode')
    wasm = [p for p in files if p.endswith('.wasm')]
    if not wasm:
        raise ValueError('missing WASM')
    for name in wasm:
        with (dist / name).open('rb') as source:
            if source.read(4) != b'\0asm':
                raise ValueError('invalid WASM magic')
    return {'files': len(files), 'bytes': total, 'wasm': wasm, 'source_sha': sha}


if __name__ == '__main__':
    command, source, sha = sys.argv[1:4]
    if command == 'prepare':
        prepare(source, sha)
    elif command == 'stamp':
        stamp(source, sha)
    elif command == 'validate':
        result = validate(source, sha, os.environ['RECIPE'], os.environ['GITHUB_RUN_ID'], os.environ['GITHUB_RUN_ATTEMPT'])
        print(json.dumps(result, indent=2))
    else:
        raise SystemExit('unknown adapter command')

"""Pure fail-closed rules; API adapters live in publish.py."""
import hashlib, io, json, re, stat, zipfile


def validate_zip(data, sha, run_id, attempt):
    if len(data) > 100 * 1024 * 1024:
        raise ValueError('archive too large')
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        files = z.infolist()
        if not files or len(files) > 20000:
            raise ValueError('file count')
        seen = set(); total = 0
        for f in files:
            name = f.filename
            if (name in seen or not name or name.startswith('/') or '\\' in name
                or any(p in ('', '.', '..') for p in name.split('/'))
                or any(p.lower() in ('functions', '_worker.js', '_routes.json') for p in name.split('/'))
                or not re.fullmatch(r'[A-Za-z0-9_./-]+', name)
                or stat.S_ISLNK(f.external_attr >> 16)):
                raise ValueError('unsafe archive path')
            seen.add(name); total += f.file_size
            if f.file_size > 25 * 1024 * 1024 or total > 100 * 1024 * 1024:
                raise ValueError('asset size limit')
            if name.rsplit('.', 1)[-1] not in ('html', 'json', 'js', 'css', 'wasm', 'woff', 'woff2', 'png', 'svg', 'jpg', 'ico', 'txt', 'md', 'ts'):
                raise ValueError('not an allowed static file')
        if not {'index.html', 'build.json'} <= seen:
            raise ValueError('missing entry or provenance')
        metadata = json.loads(z.read('build.json'))
        if (metadata.get('sha'), str(metadata.get('run_id')), str(metadata.get('attempt'))) != (sha, str(run_id), str(attempt)):
            raise ValueError('artifact provenance mismatch')
        # Read every member to verify CRC without extracting or executing it.
        for f in files:
            z.read(f)
        return {'files':len(files), 'bytes':total, 'sha256':hashlib.sha256(data).hexdigest()}

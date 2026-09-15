import json, os, pathlib, subprocess, time
case = json.loads(pathlib.Path('lab/case.json').read_text())
assert not case['fail_ci'], 'Intentional CI failure fixture'
time.sleep(min(90, max(0, int(case['delay_seconds']))))
sha = subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip()
assert sha == os.environ['SOURCE_SHA'], 'checkout is not the requested source SHA'
out = pathlib.Path('dist'); out.mkdir(exist_ok=True)
# Minimal valid WASM exports add(i32, i32) -> i32, independent of any private asset.
(out/'add.wasm').write_bytes(bytes.fromhex('0061736d0100000001070160027f7f017f030201000707010361646400000a09010700200020016a0b'))
(out/'build.json').write_text(json.dumps({'sha':sha, 'run_id':os.environ['GITHUB_RUN_ID'], 'attempt':os.environ['GITHUB_RUN_ATTEMPT'], 'message':case['message']}))
(out/'index.html').write_text('''<!doctype html><meta charset="utf-8"><title>rhwp preview lab</title><h1>PR head WASM 시험</h1><p id="sha"></p><p id="result">불러오는 중</p><script type="module">
const build = await (await fetch('./build.json')).json(); document.querySelector('#sha').textContent=build.sha;
const {instance}=await WebAssembly.instantiateStreaming(fetch('./add.wasm'));document.querySelector('#result').textContent='WASM 20 + 22 = '+instance.exports.add(20,22);
</script>''')

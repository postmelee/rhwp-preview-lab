"""Lab-only replacement of expensive product compilation; publisher is unchanged."""
import datetime,json,os,pathlib,subprocess,sys
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/'scripts/preview'))
from recipe import fingerprint
source=pathlib.Path(sys.argv[1]);sha=sys.argv[2]
assert subprocess.check_output(['git','-C',str(source),'rev-parse','HEAD'],text=True).strip()==sha
case=json.loads((source/'lab/case.json').read_text())
assert not case.get('fail_build',False),'Intentional native preview build failure'
out=source/'rhwp-studio/dist';out.mkdir(parents=True)
(out/'add.wasm').write_bytes(bytes.fromhex('0061736d0100000001070160027f7f017f030201000707010361646400000a09010700200020016a0b'))
(out/'build.json').write_text(json.dumps({'sha':sha,'run_id':os.environ['GITHUB_RUN_ID'],'attempt':os.environ['GITHUB_RUN_ATTEMPT'],'profile':'release','pwa':False,'recipe':fingerprint(),'built_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'fixture':True}))
(out/'index.html').write_text('''<!doctype html><meta charset="utf-8"><title>Candidate controller fixture</title><h1>Controller integration fixture</h1><pre id="build"></pre><p id="result"></p><script type="module">const b=await(await fetch('./build.json')).json();document.querySelector('#build').textContent=JSON.stringify(b);const {instance}=await WebAssembly.instantiateStreaming(fetch('./add.wasm'));document.querySelector('#result').textContent='WASM 20 + 22 = '+instance.exports.add(20,22);</script>''')

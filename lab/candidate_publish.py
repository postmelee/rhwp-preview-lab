"""Only CI adapter differs; production publisher/provenance/cleanup code is identical."""
import json,os,pathlib,subprocess,sys
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/'scripts/preview'))
import publish

def current(number):
    r=subprocess.run(['node','lab/candidate_gate.cjs',os.environ['GITHUB_REPOSITORY'],str(number)],capture_output=True,text=True,timeout=420)
    value=json.loads(r.stdout)
    if not value.get('allowed'):raise ValueError(value.get('reason','Lab CI blocked'))
    return value
publish.current=current
publish.run()

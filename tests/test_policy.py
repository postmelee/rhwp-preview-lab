import io,json,pathlib,stat,sys,unittest,zipfile
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/'lab'))
from policy import select_run,validate_zip
SHA='a'*40

def run(**kw):
    return dict(dict(id=1,run_attempt=1,head_sha=SHA,event='pull_request',workflow_id=4,status='completed',conclusion='success'),**kw)

def archive(extra=None,metadata=None):
    out=io.BytesIO()
    with zipfile.ZipFile(out,'w') as z:
        z.writestr('index.html','hello')
        z.writestr('build.json',json.dumps(metadata or dict(sha=SHA,run_id='1',attempt='1')))
        if extra:
            for name,data in extra:z.writestr(name,data)
    return out.getvalue()

class Policy(unittest.TestCase):
    def test_success(self):self.assertEqual(select_run([run()],SHA,'pull_request',4)['id'],1)
    def test_missing_and_wrong_identity(self):
        for rows in [[],[run(head_sha='b'*40)],[run(event='push')],[run(workflow_id=5)]]:
            with self.subTest(rows=rows),self.assertRaises(ValueError):select_run(rows,SHA,'pull_request',4)
    def test_newer_failure_does_not_fall_back(self):
        with self.assertRaises(ValueError):select_run([run(),run(id=2,conclusion='failure')],SHA,'pull_request',4)
    def test_pending_cancelled_skipped_neutral(self):
        for state in ['failure','cancelled','skipped','neutral',None]:
            with self.subTest(state=state),self.assertRaises(ValueError):select_run([run(conclusion=state)],SHA,'pull_request',4)
    def test_rerun_in_progress_revokes_prior_attempt(self):
        with self.assertRaises(ValueError):select_run([run(),run(run_attempt=2,status='in_progress',conclusion=None)],SHA,'pull_request',4)
    def test_archive(self):self.assertEqual(validate_zip(archive(),SHA,1,1)['files'],2)
    def test_wrong_source_and_attempt(self):
        for metadata in [dict(sha='b'*40,run_id='1',attempt='1'),dict(sha=SHA,run_id='1',attempt='2')]:
            with self.subTest(metadata=metadata),self.assertRaises(ValueError):validate_zip(archive(metadata=metadata),SHA,1,1)
    def test_paths(self):
        for name in ['../secret','/absolute','a/../../b','a\\b','functions/run.js','_worker.js','a/_worker.js','index.html','script.py']:
            with self.subTest(name=name),self.assertRaises(ValueError):validate_zip(archive([(name,'x')]),SHA,1,1)
    def test_symlink(self):
        info=zipfile.ZipInfo('link.txt');info.create_system=3;info.external_attr=(stat.S_IFLNK|0o777)<<16
        with self.assertRaises(ValueError):validate_zip(archive([(info,'/etc/passwd')]),SHA,1,1)
    def test_size(self):
        with self.assertRaises(ValueError):validate_zip(archive([('big.wasm',b'x'*(25*1024*1024+1))]),SHA,1,1)

if __name__=='__main__':unittest.main()

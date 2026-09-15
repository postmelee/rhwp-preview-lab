import io,json,pathlib,stat,sys,unittest,zipfile
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]))
from policy import validate_zip
SHA='a'*40

def archive(extra=None,metadata=None):
    out=io.BytesIO()
    with zipfile.ZipFile(out,'w') as z:
        z.writestr('index.html','hello')
        z.writestr('build.json',json.dumps(metadata or dict(sha=SHA,run_id='1',attempt='1')))
        if extra:
            for name,data in extra:z.writestr(name,data)
    return out.getvalue()

class Policy(unittest.TestCase):
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

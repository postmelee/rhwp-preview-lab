"""Invalidate asset reuse when the trusted build recipe or tool versions change."""
import hashlib,pathlib

def fingerprint():
    here=pathlib.Path(__file__).resolve().parent
    files=[here/'prepare.py', here/'recipe.py', here.parent.parent/'.github/workflows/studio-preview.yml', here.parent.parent/'.github/workflows/studio-preview-build.yml']
    digest=hashlib.sha256()
    for path in files:
        digest.update(path.name.encode()+b'\0'+path.read_bytes()+b'\0')
    return digest.hexdigest()

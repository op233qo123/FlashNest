#!/usr/bin/env python3
"""Exact reviewed WebAudio patch integrity; optional pinned-source apply/reverse."""
import argparse,hashlib,json,subprocess,tempfile
from pathlib import Path
HERE=Path(__file__).resolve().parent

def digest(data):return hashlib.sha256(data).hexdigest()
def check(source=None):
    if not __debug__:raise RuntimeError('Optimization disables validation')
    m=json.loads((HERE/'patch-manifest.json').read_text());p=HERE/'audio-lifecycle.patch'
    assert digest(p.read_bytes())==m['patchSHA256']
    assert m['sourcePin']=='89a7049965f3090e706265670df309a5128233ac'
    assert m['scope']==['web/src/audio.rs']
    s=p.read_text();assert s.count('--- a/')==s.count('+++ b/')==1
    assert '+++ b/web/src/audio.rs' in s
    assert '+        let buffer_handle = Rc::downgrade(&buffer);' in s
    assert '+        self.buffers.clear();' in s
    if source is not None:
        data=source.read_bytes();assert digest(data)==m['baseSHA256']
        assert hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest()==m['baseGitBlob']
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);target=root/'web/src/audio.rs';target.parent.mkdir(parents=True);target.write_bytes(data)
            subprocess.run(['git','apply','--check',str(p)],cwd=root,check=True)
            subprocess.run(['git','apply',str(p)],cwd=root,check=True)
            assert digest(target.read_bytes())==m['modifiedSHA256']
            modified=target.read_text()
            assert modified.index('self.buffers.clear();')<modified.index('let _ = self.context.close();')
            assert modified.count('scheduled.set_onended(None);')==3
            for x in ('let _ = self.context.resume();','let _ = self.context.suspend();','let _ = self.context.close();'):
                assert data.decode().count(x)==modified.count(x)==1
            assert 'spawn_local' not in modified and 'forget(' not in modified
            subprocess.run(['git','apply','--reverse',str(p)],cwd=root,check=True);assert target.read_bytes()==data
    print('PASS WebAudio patch integrity'+(' and exact source apply/reverse' if source else '')+'; not runtime evidence')
if __name__=='__main__':
    a=argparse.ArgumentParser();a.add_argument('--source-file',type=Path);check(a.parse_args().source_file)

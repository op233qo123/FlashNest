import hashlib,json,sys,zipfile
from pathlib import Path

def verify(root, approval):
    root=Path(root);a=json.loads(Path(approval).read_text())
    run=json.loads((root/'run.json').read_text());artifact=json.loads((root/'artifact.json').read_text())
    if a['repository']!='op233qo123/FlashNest' or run['id']!=a['runID'] or run['head_sha']!=a['buildCommit'] or run['conclusion']!='success' or run['status']!='completed':raise ValueError('Unapproved or failed build')
    if artifact['id']!=a['artifactID'] or artifact['workflow_run']['id']!=run['id'] or artifact['expired']:raise ValueError('Wrong artifact')
    if (root/'runtime.zip').stat().st_size != a['archiveBytes'] or a['archiveBytes'] > 128*1024*1024:raise ValueError('Artifact compressed size bound')
    data=(root/'runtime.zip').read_bytes()
    if hashlib.sha256(data).hexdigest()!=a['archiveSHA256'] or len(data)!=a['archiveBytes']:raise ValueError('Artifact bytes mismatch')
    dest=root/'extracted'
    if dest.exists():raise ValueError('Existing extraction destination')
    with zipfile.ZipFile(root/'runtime.zip') as z:
        names=set();total=0
        for entry in z.infolist():
            p=Path(entry.filename);total+=entry.file_size
            if p.is_absolute() or '..' in p.parts or '\\' in entry.filename or entry.filename.casefold() in names or (entry.external_attr>>16)&0o170000==0o120000:raise ValueError('Unsafe artifact member')
            names.add(entry.filename.casefold())
        if total>128*1024*1024 or len(names)>512:raise ValueError('Artifact expansion bounds')
        if z.testzip() is not None:raise ValueError('Artifact CRC failure')
        z.extractall(dest)
    helper=a['audioOperationSource'];hp=Path(helper['path'])
    if hp.is_absolute() or '..' in hp.parts or not hp.parts:raise ValueError('Invalid helper source path')
    if hashlib.sha256((dest/hp).read_bytes()).hexdigest()!=helper['sha256']:raise ValueError('Wrong actual helper source')
    for runtime in a['runtimes'].values():
        p=Path(runtime['directory'])
        if p.is_absolute() or '..' in p.parts or not p.parts:raise ValueError('Invalid runtime directory')
    return dest
if __name__=='__main__':verify(*sys.argv[1:])

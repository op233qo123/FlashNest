#!/usr/bin/env python3
"""Fetch only the locked official runtime; hash first, safely extract second."""
import hashlib, io, json, pathlib, shutil, tempfile, urllib.request, zipfile
ROOT=pathlib.Path(__file__).resolve().parents[1]
lock=json.loads((ROOT/'runtime.lock.json').read_text())
manifest=json.loads((ROOT/'runtime.files.json').read_text())
assert lock['url'].startswith('https://github.com/ruffle-rs/ruffle/releases/download/')
with urllib.request.urlopen(lock['url'],timeout=120) as response:
    archive=response.read(50*1024*1024+1)
if len(archive)>50*1024*1024: raise SystemExit('Runtime archive exceeds limit')
if hashlib.sha256(archive).hexdigest()!=lock['sha256']: raise SystemExit('Runtime hash mismatch: refusing extraction')
target=ROOT/'App/Resources/Web/runtime'
with tempfile.TemporaryDirectory(dir=ROOT) as tmp:
    staging=pathlib.Path(tmp)/'runtime'; staging.mkdir()
    with zipfile.ZipFile(io.BytesIO(archive)) as z:
        if sum(i.file_size for i in z.infolist())>100*1024*1024: raise SystemExit('Expanded runtime exceeds limit')
        for i in z.infolist():
            p=pathlib.PurePosixPath(i.filename)
            if p.is_absolute() or '..' in p.parts or '\\' in i.filename or (i.external_attr>>16)&0o170000==0o120000: raise SystemExit('Unsafe archive entry')
        z.extractall(staging)
    for name in ('ruffle.js','LICENSE_MIT','LICENSE_APACHE','package.json'):
        if not (staging/name).is_file(): raise SystemExit('Incomplete runtime')
    if json.loads((staging/'package.json').read_text())['version']!=lock['version']: raise SystemExit('Version mismatch')
    # The archive hash is authoritative; per-file checks also catch manifest drift.
    for path in staging.rglob('*'):
        if path.is_file():
            name=path.relative_to(staging).as_posix()
            if manifest.get(name)!=hashlib.sha256(path.read_bytes()).hexdigest():
                raise SystemExit('Runtime file manifest mismatch: '+name)
    # Overlay only verified upstream files. Keep separately maintained notices
    # supplied by the project; never delete their full license materials.
    target.mkdir(parents=True,exist_ok=True)
    shutil.copytree(staging,target,dirs_exist_ok=True)
print('Verified and bundled Ruffle '+lock['version'])

#!/usr/bin/env python3
"""Extract only the exact existing build-17 runtime to a fresh isolated directory."""
import argparse,hashlib,json,os,shutil,stat,tempfile,zipfile
from pathlib import Path
ARCHIVE_SHA='57d7eaed19edd006e2a33a9bfa816f22da8b1003becf3719dfca0c97cb38c4af'
PROVENANCE_SHA='73829617008e26ffe48bfc29e689c0a719641f6c9e93214b29f8ee3c6bfd22d5'
PIN='89a7049965f3090e706265670df309a5128233ac'
GUARD='de0acabdf957fccbc11966b67defd0a7f577cdc5a147db949e0a4f0e56c6331f'
PREFIX='frame-order-engine-candidate/'
def sha(b):return hashlib.sha256(b).hexdigest()
def validate_names(rows):
 assert len(rows)<=2000 and sum(i.file_size for i in rows)<=200*1024*1024
 seen=set()
 for i in rows:
  p=Path(i.filename);assert i.filename and not p.is_absolute() and '..' not in p.parts and '\\' not in i.filename
  assert i.filename not in seen and not stat.S_ISLNK(i.external_attr>>16);seen.add(i.filename)
  assert i.file_size<=64*1024*1024
 return seen

def prepare(archive,output):
 if not __debug__:raise RuntimeError('Do not disable assertions')
 archive=archive.resolve();assert archive.is_file() and archive.stat().st_size<=64*1024*1024
 assert sha(archive.read_bytes())==ARCHIVE_SHA,'Wrong immutable vendor archive'
 assert not output.exists() and not output.is_symlink(),'Output must be fresh'
 assert output.parent.is_dir();output=output.parent.resolve()/output.name
 temporary=Path(tempfile.mkdtemp(prefix='transition-runtime-',dir=output.parent))
 try:
  with zipfile.ZipFile(archive) as z:
   names=validate_names(z.infolist());raw=z.read(PREFIX+'provenance.json');assert sha(raw)==PROVENANCE_SHA
   provenance=json.loads(raw);assert provenance['upstreamCommit']==PIN and provenance['patchSHA256']==GUARD
   rows={n:r for n,r in provenance['files'].items() if n.startswith('runtime/')}
   actual={n[len(PREFIX):] for n in names if n.startswith(PREFIX+'runtime/') and not n.endswith('/')}
   assert actual==set(rows),'Runtime inventory mismatch'
   for n,r in rows.items():
    b=z.read(PREFIX+n);assert len(b)==r['bytes'] and sha(b)==r['sha256']
    target=temporary/n;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(b)
   (temporary/'provenance.json').write_bytes(raw)
  manifest={str(p.relative_to(temporary/'runtime')):sha(p.read_bytes()) for p in sorted((temporary/'runtime').rglob('*')) if p.is_file() and p.suffix in ('.js','.wasm')}
  assert 'ruffle.js' in manifest and len([n for n in manifest if n.endswith('.wasm')])==2
  data=(json.dumps(manifest,indent=2)+'\n').encode();(temporary/'runtime.browser-manifest.json').write_bytes(data)
  identity={'schema':1,'kind':'unchanged-existing-build17-queued-goto-runtime','upstreamCommit':PIN,'archiveSHA256':ARCHIVE_SHA,'provenanceSHA256':PROVENANCE_SHA,'runtimeManifestSHA256':sha(data),'guardPatchSHA256':GUARD,'productionModified':False}
  (temporary/'identity.json').write_text(json.dumps(identity,indent=2)+'\n');os.rename(temporary,output);return identity
 finally:
  if temporary.exists():shutil.rmtree(temporary)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('archive',type=Path);p.add_argument('output',type=Path);a=p.parse_args();print(json.dumps(prepare(a.archive,a.output),indent=2))

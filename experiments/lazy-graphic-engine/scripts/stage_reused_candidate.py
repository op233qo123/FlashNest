#!/usr/bin/env python3
"""Reuse the exact successful candidate engine; never rebuild or relabel its run."""
import argparse,json,zipfile,io,stat
from pathlib import Path,PurePosixPath
from stage_validation_runtime import ROOT,fetch,require,sha
from check_pipeline import check
def main(out):
 check();e=json.loads((ROOT/'candidate-reuse.json').read_text())['engine'];out=out.resolve()
 require(not out.exists(),'Fresh candidate staging required')
 data=fetch(e)
 with zipfile.ZipFile(io.BytesIO(data)) as z:
  rows=z.infolist();require(len(rows)<=5000 and sum(i.file_size for i in rows)<=402653184,'Oversized artifact')
  names=set()
  for i in rows:
   p=PurePosixPath(i.filename);require(i.filename not in names and not p.is_absolute() and '..' not in p.parts and '\\' not in i.filename and ':' not in i.filename and p.as_posix()==i.filename,'Unsafe/duplicate artifact path');names.add(i.filename)
   require(stat.S_IFMT(i.external_attr>>16) in (0,stat.S_IFREG) and i.file_size<=67108864,'Linked/nonregular artifact member')
  required='lazy-graphic-engine/'
  raw=z.read(required+'provenance.json');require(sha(raw)==e['provenanceSHA256'],'Provenance differs');receipt=json.loads(raw);require(receipt['sourceLockSHA256']==e['sourceLockSHA256'],'Candidate original source lock differs')
  require(receipt['run']['GITHUB_SHA']==e['sourceCommit'] and receipt['run']['GITHUB_RUN_ID']==str(e['runID']) and receipt['sourceSetSHA256']==e['sourceSetSHA256'],'Receipt source/run differs')
  invraw=z.read(required+'runtime-files.json');require(sha(invraw)==e['runtimeInventorySHA256']==receipt['runtimeInventorySHA256'],'Runtime inventory differs');inv=json.loads(invraw)
  require({n[len(required+'runtime/'):] for n in names if n.startswith(required+'runtime/')}==set(inv),'Extra/missing runtime')
  for rel,row in inv.items():
   b=z.read(required+'runtime/'+rel);require(len(b)==row['bytes'] and sha(b)==row['sha256'],'Runtime bytes differ')
  require(sorted(row['sha256'] for rel,row in inv.items() if rel.endswith('.wasm'))==sorted(e['wasmSHA256']),'WASM branch inventory differs')
  # Full correspondence and its pre/post source inventory are independently pinned
  # by the reviewed entire archive, plus the engine receipt; no code is executed here.
  require(z.read(required+'full-source-before.json')==z.read(required+'full-source-after.json'),'Engine source changed during build')
  require(sha(z.read(required+'full-source-before.json'))==receipt['fullSourceManifestSHA256'],'Full source manifest differs')
  corr=receipt['correspondence'];prefix=required+'source-correspondence/'
  require({n[len(prefix):] for n in names if n.startswith(prefix)}==set(corr),'Correspondence file set differs')
  for rel,row in corr.items():
   b=z.read(prefix+rel);require(len(b)==row['bytes'] and sha(b)==row['sha256'],'Correspondence bytes differ')
  archive=out.parent/'reused-candidate-archive.zip';require(not archive.exists(),'Existing archive staging must be inspected');archive.write_bytes(data)
  out.mkdir()
  for name in sorted(names):
   if name.startswith(required):
    target=out/name[len(required):];target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(z.read(name))
 print('Verified reused candidate original archive, original build run, complete source correspondence and runtime')
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args();main(a.output)

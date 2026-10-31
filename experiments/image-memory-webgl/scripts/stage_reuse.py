#!/usr/bin/env python3
"""Verify and stage exact prior engine bytes; never rebuild or infer visual acceptance."""
import argparse,hashlib,json,pathlib,shutil,stat,zipfile
P=pathlib.Path(__file__).resolve().parents[1];lock=json.loads((P/'reuse-lock.json').read_text())
p=argparse.ArgumentParser();p.add_argument('archive',type=pathlib.Path);p.add_argument('metadata',type=pathlib.Path);p.add_argument('out',type=pathlib.Path);a=p.parse_args()
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
m=json.loads(a.metadata.read_text());assert m['id']==lock['artifactID'] and not m['expired'];assert m['workflow_run']['id']==lock['runID'] and m['workflow_run']['head_sha']==lock['commit'];assert m['size_in_bytes']==lock['archiveBytes'] and m['digest']=='sha256:'+lock['archiveSHA256']
assert a.archive.stat().st_size==lock['archiveBytes'] and sha(a.archive)==lock['archiveSHA256']
assert not a.out.exists();a.out.mkdir(parents=True)
with zipfile.ZipFile(a.archive) as z:
 assert len(z.infolist())<1000 and sum(i.file_size for i in z.infolist())<268435456
 for i in z.infolist():
  path=pathlib.PurePosixPath(i.filename);assert not path.is_absolute() and '..' not in path.parts and not stat.S_ISLNK(i.external_attr>>16)
  if i.filename.startswith('image-memory-engines/'):
   dst=a.out/pathlib.Path(*path.parts[1:]);assert dst.resolve().is_relative_to(a.out.resolve())
   if i.is_dir():dst.mkdir(parents=True,exist_ok=True)
   else:dst.parent.mkdir(parents=True,exist_ok=True);dst.write_bytes(z.read(i))
for arm,expected in lock['engines'].items():
 root=a.out/arm
 for file,key in [('provenance.json','provenanceSHA256'),('source-before.json','sourceManifestSHA256'),('runtime-files.json','runtimeInventorySHA256')]:assert sha(root/file)==expected[key]
 r=json.loads((root/'provenance.json').read_text());assert r['run']['GITHUB_RUN_ID']==str(lock['runID']) and r['run']['GITHUB_SHA']==lock['commit'];assert r['variant']==arm
 inv=json.loads((root/'runtime-files.json').read_text());actual={f.relative_to(root/'runtime').as_posix() for f in (root/'runtime').rglob('*') if f.is_file()};assert actual==set(inv)
 for rel,row in inv.items():
  f=root/'runtime'/rel;assert f.stat().st_size==row['bytes'] and sha(f)==row['sha256']
print('PASS exact prior dual-engine archive; original browser run failed, no visual acceptance inferred')

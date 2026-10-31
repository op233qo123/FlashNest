#!/usr/bin/env python3
"""Reuse only the already verified baseline, never an experimental product engine."""
import hashlib,json,pathlib,sys,zipfile
ROOT=pathlib.Path(__file__).resolve().parents[1]
def sha(b):return hashlib.sha256(b).hexdigest()
def main(archive,metadata,destination):
 lock=json.loads((ROOT/'engine-lock.json').read_text()); meta=json.loads(metadata.read_text())
 assert meta['id']==lock['artifactId'] and not meta['expired']
 assert meta['workflow_run']['id']==lock['runId'] and meta['workflow_run']['head_sha']==lock['headSHA']
 assert meta['digest']=='sha256:'+lock['artifactSHA256']
 assert archive.stat().st_size==lock['artifactBytes'] and sha(archive.read_bytes())==lock['artifactSHA256']
 destination.mkdir(parents=True,exist_ok=False)
 with zipfile.ZipFile(archive) as z:
  assert len(z.namelist())==len(set(z.namelist()))
  prefix=lock['prefix']; prov=json.loads(z.read(prefix+'provenance.json'))
  assert prov==lock['baselineProvenance'] and prov['variant']=='baseline' and prov['coreJSTests']==63
  assert json.loads(z.read(prefix+'runtime-files.json'))==lock['runtimeFiles']
  expected=set(prefix+'runtime/'+n for n in lock['runtimeFiles'])
  actual=set(n for n in z.namelist() if n.startswith(prefix+'runtime/') and not n.endswith('/'))
  assert expected==actual
  for name,info in lock['runtimeFiles'].items():
   assert '/' not in name and '\\' not in name and name not in ('.','..')
   b=z.read(prefix+'runtime/'+name);assert len(b)==info['bytes'] and sha(b)==info['sha256'];(destination/name).write_bytes(b)
 receipt={'schema':'texture-lifetime-runtime-reuse-v1','artifactId':lock['artifactId'],'artifactSHA256':lock['artifactSHA256'],'sourceRun':lock['runId'],'sourceCommit':lock['headSHA'],'variant':'accepted-baseline-only','runtimeFiles':lock['runtimeFiles'],'noProductChanges':True}
 (destination.parent/'runtime-receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
if __name__=='__main__':main(*(pathlib.Path(x) for x in sys.argv[1:]))

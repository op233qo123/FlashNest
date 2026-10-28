#!/usr/bin/env python3
"""Materialize pinned baseline arms and final App; no source gate activation."""
import hashlib,json,shutil,subprocess,sys,zipfile,io
from pathlib import Path,PurePosixPath
from stage_validation_runtime import ROOT,fetch,require,sha

def dump(path,value):
 path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(value,indent=2,sort_keys=True)+'\n')
def inventory(root):
 result={}
 for f in sorted(root.rglob('*')):
  require(not f.is_symlink(),'Symlink forbidden')
  if f.is_file():result[f.relative_to(root).as_posix()]=sha(f.read_bytes())
 return result

def main():
 lock=json.loads((ROOT/'validation-lock.json').read_text());baseline=lock['historicalBaseline'];out=ROOT/'baseline-bundle'
 require(lock.get('dispatchAllowed') is True,'Unapproved validation binding')
 require(not out.exists(),'Existing baseline staging must be inspected')
 data=fetch(baseline)
 with zipfile.ZipFile(io.BytesIO(data)) as z:
  for role,prefix in [('sampling','audio-recovery-candidate/runtime/'),('historical','audio-recovery-baseline/runtime/')]:
   expected=baseline['runtimeFiles'][role]
   names=[n for n in z.namelist() if n.startswith(prefix) and not n.endswith('/')]
   require(len(names)==len(set(names)) and {n[len(prefix):] for n in names}==set(expected),'Baseline file set differs')
   for rel,row in expected.items():
    p=PurePosixPath(rel);require(p.name==rel and ':' not in rel and '\\' not in rel,'Unsafe baseline filename')
    raw=z.read(prefix+rel);require(len(raw)==row['bytes'] and sha(raw)==row['sha256'],'Baseline bytes differ')
    dest=out/role/'runtime'/rel;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(raw)
   if role=='sampling':
    # Preserve the original frozen serialization, not an equivalent JSON re-encoding.
    original=ROOT/'validation-bindings/sampling-baseline-runtime.files.json'
    require(json.loads(original.read_text())=={k:v['sha256'] for k,v in expected.items()},'Baseline string inventory differs')
    shutil.copyfile(original,out/role/'runtime.files.json')
   else:dump(out/role/'runtime-files.json',expected)
   source=ROOT/'validation-bindings'/role/'app-metadata'
   shutil.copytree(source,out/role/'app-metadata')
 template=ROOT/'validation-app-template';app=ROOT/'validation-app'
 require(not app.exists(),'Existing App staging must be inspected')
 require(inventory(template)==lock['appTemplateFiles'],'Final App template differs')
 shutil.copytree(template,app)
 old=app/'vendor/ruffle-audio-recovery-40614335019.zip';require(not old.exists(),'Template must not contain old binary archive')
 old.parent.mkdir(exist_ok=True);old.write_bytes(data)
 proof=ROOT/'validation-bindings/engine-acceptance.json'
 subprocess.run([sys.executable,str(ROOT/'runtime-consumer/prepare_app_runtime.py'),'--archive',str(ROOT/'staged-engine-archive.zip'),'--acceptance',str(proof),'--app',str(app)],check=True)
 require(inventory(app)==lock['appSourceManifest']['files'],'Materialized App differs from externally frozen complete inventory')
 dump(ROOT/'evidence/input-staging.json',{'passed':True,'engineSHA256':lock['engine']['sha256'],'baselineSHA256':baseline['sha256'],'appFiles':lock['appSourceManifest']['files'],'samplingGateEnabled':False})
 print('Exact delivered baseline, separate historical audio control and final gate-off App staged')
if __name__=='__main__':main()

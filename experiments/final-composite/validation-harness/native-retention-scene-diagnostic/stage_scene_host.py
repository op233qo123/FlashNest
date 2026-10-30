"""Exact staged host/UITest/body-observer overlay; no product source mutations."""
import hashlib,json,shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parent
TARGETS={'SamplingHost.swift':'Host/SamplingHost.swift','NativeSceneLoaderUITests.swift':'UITests/NativeSamplingUITests.swift'}
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def require(ok,why):
 if not ok:raise ValueError(why)
def inventory(root):
 out={}
 for p in sorted(Path(root).rglob('*')):
  require(not p.is_symlink(),'Linked input rejected')
  if p.is_file():out[p.relative_to(root).as_posix()]=sha(p)
 return out

def apply_overlay(app,sampling_root,fixture_root,fixture_package):
 app=Path(app);sampling_root=Path(sampling_root);fixture_root=Path(fixture_root);fixture_package=Path(fixture_package)
 before=inventory(app);base=app/'NativeSamplingValidation';original={}
 for source,rel in TARGETS.items():
  original[rel]=(base/rel).read_bytes();require(original[rel]==(sampling_root/rel).read_bytes(),'Original staged source differs: '+rel)
 observer=fixture_package/'observer.js';original['Host/sampling-probe.js']=(base/'Host/sampling-probe.js').read_bytes()
 require(original['Host/sampling-probe.js']==(sampling_root/'Host/sampling-probe.js').read_bytes(),'Original observer differs')
 original['SamplingIdentity.json']=(base/'SamplingIdentity.json').read_bytes();identity=json.loads(original['SamplingIdentity.json'])
 require(identity['arm']=='candidate','Candidate-only scene diagnostic')
 manifest_path=fixture_root/'manifest.json';manifest=json.loads(manifest_path.read_text())
 required={'retention/'+name+'.swf' for name in ('main-retain','main-drop','prefix-a','prefix-b','old','new')}
 require(set(manifest['files'])==required and set(inventory(fixture_root))==required|{'manifest.json'},'Exact six generated fixtures and manifest required')
 require(sum((fixture_root/name).stat().st_size for name in required)<=144*1024*1024,'Generated package exceeds144MiB')
 require(sum(row['actualDecodedBytes'] for row in manifest['files'].values())<=154*1024*1024,'Declared decoded package exceeds154MiB')
 for name,row in manifest['files'].items():require(sha(fixture_root/name)==row['sha256'] and (fixture_root/name).stat().st_size==row['compressedBytes'],'Generated fixture raw identity differs')
 dest=base/'SamplingFixtures/scene-cws';require(not dest.exists(),'Fresh fixture destination required')
 # Manifest bytes are independently regenerated/decoded by the fixture generator before staging.
 combined=original['Host/sampling-probe.js']+b'\n// Bounded scene body diagnostic; public synthetic SWF requests only.\n'+observer.read_bytes()
 for source,rel in TARGETS.items():(base/rel).write_bytes((ROOT/source).read_bytes())
 (base/'Host/sampling-probe.js').write_bytes(combined);shutil.copytree(fixture_root,dest)
 identity['baseSamplingIdentitySHA256']=hashlib.sha256(original['SamplingIdentity.json']).hexdigest()
 identity['baseObserverSHA256']=identity['observerSHA256'];identity['observerSHA256']=sha(base/'Host/sampling-probe.js')
 identity['sceneDiagnostic']={'fixtureManifestSHA256':sha(manifest_path),'hostSHA256':sha(base/'Host/SamplingHost.swift'),'testsSHA256':sha(base/'UITests/NativeSamplingUITests.swift'),'bodyObserverSHA256':sha(observer),'policy':'automatic','scale':'original','allowScriptAccess':'unchanged-false'}
 (base/'SamplingIdentity.json').write_text(json.dumps(identity,sort_keys=True)+'\n')
 after=inventory(app);expected=dict(before)
 for rel in original:expected['NativeSamplingValidation/'+rel]=sha(base/rel)
 for name,h in inventory(dest).items():expected['NativeSamplingValidation/SamplingFixtures/scene-cws/'+name]=h
 require(after==expected,'Unexpected staged file delta')
 inverse=dict(after)
 for name in list(inverse):
  if name.startswith('NativeSamplingValidation/SamplingFixtures/scene-cws/'):del inverse[name]
 for rel,data in original.items():inverse['NativeSamplingValidation/'+rel]=hashlib.sha256(data).hexdigest()
 require(inverse==before,'Staged exact inverse differs')
 require({p:h for p,h in after.items() if p.startswith('App/')}=={p:h for p,h in before.items() if p.startswith('App/')},'Scene overlay changed product App')
 return {'diagnosticOnly':True,'nativeAcceptance':False,'exactInverseVerified':True,'productAppUnchanged':True,'beforeFiles':before,'afterFiles':after,'inverseFiles':inverse,'identity':identity,'fixtureManifestSHA256':sha(manifest_path),'addedFiles':sorted(set(after)-set(before)),'changedFiles':{p:{'before':before[p],'after':after[p]} for p in before if before[p]!=after[p]}}

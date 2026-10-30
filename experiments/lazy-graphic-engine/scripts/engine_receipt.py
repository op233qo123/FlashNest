#!/usr/bin/env python3
"""Draft strict provenance adapter; never interprets a build as native acceptance."""
from pathlib import Path
import json,hashlib,shutil,argparse,os,subprocess,datetime
from check_contract import ROOT,check,digest
from source_snapshot import snapshot
p=argparse.ArgumentParser();p.add_argument('mode',choices=['prepare','package']);p.add_argument('source',type=Path);p.add_argument('out',type=Path);a=p.parse_args();s=a.source.resolve();out=a.out.resolve();lock=check(ROOT,'engine')
def verify():
 for rel,row in lock['modifiedSourceFiles'].items():
  f=s/rel
  if digest(f)!=row['sha256'] or f.stat().st_size!=row['bytes']:raise ValueError('Source changed: '+rel)
 for rel,h in lock['locks'].items():
  if digest(s/rel)!=h:raise ValueError('Lock changed: '+rel)
verify();identity=hashlib.sha256(json.dumps(lock['modifiedSourceFiles'],sort_keys=True,separators=(',',':')).encode()).hexdigest()
seal={'version_number':'0.7.1','version_name':'FlashNest composite experimental '+identity[:12],'version_channel':'flashnest-composite-experimental','build_date':'2026-10-07T18:55:35Z','commitHash':lock['upstreamCommit'],'version4':'0.7.1.0','firefox_extension_id':'flashnest-composite-experimental'}
if a.mode=='prepare':
 (out/'full-source-before.json').write_text(json.dumps(snapshot(s,lock['modifiedSourceFiles']),sort_keys=True,indent=2)+'\n')
 (s/'web/version_seal.json').write_text(json.dumps(seal,sort_keys=True)+'\n')
 receipt={'schemaVersion':1,'status':'ENGINE_ONLY_NATIVE_AND_VISUAL_GATES_PENDING','sourceLockSHA256':digest(ROOT/'source-lock.json'),'sourceSetSHA256':identity,'upstreamCommit':lock['upstreamCommit'],'sourceDateEpoch':lock['sourceDateEpoch'],'versionSeal':seal,'actualBuildStartedUTC':datetime.datetime.now(datetime.timezone.utc).isoformat(),'dualWasm':True,'jpegxr':True,'wasmOpt':True,'runtimeValidated':False,'nativeAcceptance':False,'physicalDeviceAcceptance':False,'run':{k:os.environ.get(k) for k in ['GITHUB_SHA','GITHUB_RUN_ID','GITHUB_RUN_ATTEMPT','ImageOS','ImageVersion']}}
 (out/'provenance.json').write_text(json.dumps(receipt,indent=2)+'\n');raise SystemExit(0)
before=json.loads((out/'full-source-before.json').read_text());after=snapshot(s,lock['modifiedSourceFiles'])
if before!=after:raise ValueError('Tracked/new source bytes or file set changed during build')
(out/'full-source-after.json').write_text(json.dumps(after,sort_keys=True,indent=2)+'\n')
receipt=json.loads((out/'provenance.json').read_text())
if receipt['sourceLockSHA256']!=digest(ROOT/'source-lock.json') or receipt['sourceSetSHA256']!=identity:raise ValueError('Source changed during build')
if (s/'web/version_seal.json').read_text()!=json.dumps(seal,sort_keys=True)+'\n':raise ValueError('Seal changed')
log=(out/'build.log').read_text()
for marker in ['Running wasm-opt on extensions','Running wasm-opt on vanilla']:
 if marker not in log:raise ValueError('Missing optimizer/flavor proof: '+marker)
raw=(out/'core-js.log').read_text();j=json.loads(raw[raw.index('{\n  "stats"'):]);stats=j['stats']
expected=json.loads((ROOT/'expected-js-titles.json').read_text())
if stats['pending'] or stats['failures'] or sorted(t['fullTitle'] for t in j['passes'])!=expected:raise ValueError('Core JS coverage changed/skipped')
runtime=s/'web/packages/selfhosted/dist'
if len(list(runtime.glob('*.wasm')))!=2 or len(list(runtime.glob('*.js.map')))<3 or not (runtime/'ruffle.js').is_file():raise ValueError('Incomplete runtime')
for name in ['LICENSE_MIT','LICENSE_APACHE']:
 if not (runtime/name).is_file():raise ValueError('Missing runtime license')
shutil.copytree(runtime,out/'runtime');inventory={}
for f in sorted((out/'runtime').rglob('*')):
 if f.is_symlink():raise ValueError('Runtime symlink')
 if f.is_file():inventory[str(f.relative_to(out/'runtime'))]={'sha256':digest(f),'bytes':f.stat().st_size}
(out/'runtime-files.json').write_text(json.dumps(inventory,indent=2)+'\n')
c=out/'source-correspondence';c.mkdir()
for rel in set(lock['modifiedSourceFiles'])|{'Cargo.lock','Cargo.toml','.cargo/config.toml','web/package-lock.json','web/package.json','web/version_seal.json','web/packages/core/tools/build_wasm.ts','LICENSE.md'}:
 f=s/rel;q=c/'source'/rel;q.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(f,q)
shutil.copytree(ROOT/'patches',c/'patches');shutil.copytree(ROOT/'scripts',c/'scripts');shutil.copyfile(ROOT/'source-lock.json',c/'source-lock.json')
# Preserve inherited accepted source-contract inputs required by candidate checker.
shutil.copyfile(ROOT/'base-source-lock.json',c/'base-source-lock.json')
(c/'reviews').mkdir(exist_ok=True)
shutil.copyfile(ROOT/'reviews/base-touch-engine-source-eligibility.json',c/'reviews/base-touch-engine-source-eligibility.json')
review_path=lock['productionGcReview']['path'];q=c/review_path;q.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/review_path,q)
# All complete notices supplied by the exact final App resource inventory, not from guessed package names.
app=Path(os.environ['APP_SOURCE']);web=app/'App/Resources/Web'
for rel in ['licenses','licenses.manifest.json','THIRD_PARTY_NOTICES.md','Ruffle-THIRD-PARTY-LICENSES.md','Ruffle-MODIFICATIONS.md']:
 f=web/rel;q=c/'licenses'/rel;q.parent.mkdir(parents=True,exist_ok=True)
 if f.is_dir():shutil.copytree(f,q)
 else:shutil.copyfile(f,q)
license_manifest=json.loads((web/'licenses.manifest.json').read_text())
for rel,h in license_manifest.items():
 f=web/rel
 if digest(f)!=h:raise ValueError('License content changed: '+rel)
 q=c/'licenses/bundled-Web'/rel;q.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(f,q)
receipt['licenseManifestSHA256']=digest(web/'licenses.manifest.json')
receipt['fullSourceManifestSHA256']=digest(out/'full-source-before.json');receipt['fullSourceFileCount']=len(before)
receipt['toolVersions']={key:subprocess.check_output(cmd,stderr=subprocess.STDOUT,text=True).strip() for key,cmd in {'rustc':['rustc','-vV'],'cargo':['cargo','--version'],'node':['node','--version'],'npm':['npm','--version'],'wasmBindgen':['wasm-bindgen','--version'],'wasmOpt':['wasm-opt','--version'],'clang':['clang-18','--version'],'java':['java','-version']}.items()}
receipt['runtimeInventorySHA256']=digest(out/'runtime-files.json');receipt['correspondence']={str(f.relative_to(c)):{'sha256':digest(f),'bytes':f.stat().st_size} for f in sorted(c.rglob('*')) if f.is_file()};receipt['completedUTC']=datetime.datetime.now(datetime.timezone.utc).isoformat();receipt['coreJSTests']=stats['passes'];receipt['reproducibility']='Pinned recipe/locks; independent clean-build byte identity NOT established'
(out/'provenance.json').write_text(json.dumps(receipt,indent=2)+'\n')
print('PASS exact dual-WASM engine receipt; native/final visual approval remains false')

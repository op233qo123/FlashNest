#!/usr/bin/env python3
"""Exact-source experimental pair receipt. No native/physical-device acceptance."""
import argparse,hashlib,json,os,pathlib,shutil,subprocess,sys
P=pathlib.Path(__file__).resolve().parents[1]
OLD=P.parent/'lazy-graphic-engine'
sys.path.insert(0,str(OLD/'scripts'))
from source_snapshot import snapshot
p=argparse.ArgumentParser();p.add_argument('mode',choices=['prepare','package']);p.add_argument('source',type=pathlib.Path);p.add_argument('out',type=pathlib.Path);p.add_argument('variant',choices=['baseline','candidate']);a=p.parse_args();s=a.source.resolve();out=a.out.resolve()
def digest(f):return hashlib.sha256(f.read_bytes()).hexdigest()
def save(f,v):f.write_text(json.dumps(v,sort_keys=True,indent=2)+'\n')
lock=json.loads((OLD/'source-lock.json').read_text());binding=json.loads((P/'source-binding.json').read_text());rows=dict(lock['modifiedSourceFiles'])
assert digest(P/'product.patch')==binding['patchSHA256']
if a.variant=='candidate':rows['render/src/utils.rs']=binding['candidate']
else:
 assert digest(s/'render/src/utils.rs')==binding['baseline']['sha256']
for rel,row in rows.items():
 f=s/rel;assert f.stat().st_size==row['bytes'] and digest(f)==row['sha256'],rel
for rel,h in lock['locks'].items():assert digest(s/rel)==h,rel
manifest=snapshot(s,rows)
identity=hashlib.sha256(json.dumps(lock['modifiedSourceFiles'],sort_keys=True,separators=(',',':')).encode()).hexdigest()
# Deliberately identical version metadata: isolate algorithm only, not build timestamp/identity.
seal={'version_number':'0.7.1','version_name':'FlashNest composite experimental '+identity[:12],'version_channel':'flashnest-composite-experimental','build_date':'2026-10-07T18:55:35Z','commitHash':lock['upstreamCommit'],'version4':'0.7.1.0','firefox_extension_id':'flashnest-composite-experimental'}
if a.mode=='prepare':
 save(out/'source-before.json',manifest);(s/'web/version_seal.json').write_text(json.dumps(seal,sort_keys=True)+'\n')
 save(out/'provenance.json',{'variant':a.variant,'upstreamCommit':lock['upstreamCommit'],'baseSourceLockSHA256':digest(OLD/'source-lock.json'),'bindingSHA256':digest(P/'source-binding.json'),'patchSHA256':binding['patchSHA256'],'sourceSHA256':digest(out/'source-before.json'),'run':{k:os.environ.get(k) for k in ['GITHUB_SHA','GITHUB_RUN_ID','GITHUB_RUN_ATTEMPT','ImageOS','ImageVersion']},'nativeAcceptance':False,'physicalDeviceAcceptance':False,'experimentalOnly':True})
else:
 assert manifest==json.loads((out/'source-before.json').read_text()),'Source changed during build'
 assert (s/'web/version_seal.json').read_text()==json.dumps(seal,sort_keys=True)+'\n'
 log=(out/'build.log').read_text();assert all(x in log for x in ['Running wasm-opt on extensions','Running wasm-opt on vanilla'])
 raw=(out/'core-js.log').read_text();j=json.loads(raw[raw.index('{\n  "stats"'):]);assert j['stats']['pending']==0 and j['stats']['failures']==0
 assert sorted(t['fullTitle'] for t in j['passes'])==json.loads((OLD/'expected-js-titles.json').read_text())
 runtime=s/'web/packages/selfhosted/dist';assert len(list(runtime.glob('*.wasm')))==2 and len(list(runtime.glob('*.js.map')))>=3 and (runtime/'ruffle.js').is_file()
 for name in ['LICENSE_MIT','LICENSE_APACHE']:assert (runtime/name).is_file()
 shutil.copytree(runtime,out/'runtime')
 inventory={str(f.relative_to(runtime)):{'bytes':f.stat().st_size,'sha256':digest(f)} for f in sorted(runtime.rglob('*')) if f.is_file()}
 save(out/'runtime-files.json',inventory)
 c=out/'source-correspondence';c.mkdir()
 for rel in set(rows)|{'Cargo.lock','Cargo.toml','.cargo/config.toml','web/package-lock.json','web/package.json','web/version_seal.json','web/packages/core/tools/build_wasm.ts','LICENSE.md'}:
  dst=c/rel;dst.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(s/rel,dst)
 shutil.copyfile(P/'product.patch',out/'product.patch');shutil.copyfile(P/'source-binding.json',out/'source-binding.json')
 r=json.loads((out/'provenance.json').read_text());r.update({'coreJSTests':j['stats']['passes'],'runtimeInventorySHA256':digest(out/'runtime-files.json'),'toolVersions':{k:subprocess.check_output(cmd,stderr=subprocess.STDOUT,text=True).strip() for k,cmd in {'rustc':['rustc','-vV'],'cargo':['cargo','--version'],'node':['node','--version'],'npm':['npm','--version'],'wasmBindgen':['wasm-bindgen','--version'],'wasmOpt':['wasm-opt','--version'],'clang':['clang-18','--version']}.items()}});save(out/'provenance.json',r)
print('PASS',a.mode,a.variant)

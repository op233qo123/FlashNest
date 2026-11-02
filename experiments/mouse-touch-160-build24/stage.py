#!/usr/bin/env python3
"""Explicit 1.6.0 overlay over a fully verified frozen unload-candidate stage."""
import argparse,hashlib,importlib.util,json,os,plistlib,shutil,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parent
BASE='cc6c4bf285a201d9c1a827140662c54606027d10'
SOURCE='9bc000e37695696f2427b25fe08efe4993bf22e5'
CASE='c4cad276f1a79caffd012bcfcb6eb260a9e3492f'
DELIVERED='9a93ade1c7dd79382a06ddcb7925282a2e7c5ea8'
RECIPE='experiments/longrun-ipa-156-build23'
FROZEN='experiments/loader-unload-ipa'
def need(ok,message):
 if not ok:raise ValueError(message)
def sha(b):return hashlib.sha256(b).hexdigest()
def read(p):return json.loads(Path(p).read_text())
def write(p,x):
 p=Path(p);p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(x,sort_keys=True,indent=2)+'\n')
def inventory(root):
 result={}
 for p in sorted(Path(root).rglob('*')):
  need(not p.is_symlink(),'Symlink forbidden: '+str(p))
  if p.is_file():result[p.relative_to(root).as_posix()]=sha(p.read_bytes())
 return result
def git_head(p):return subprocess.check_output(['git','-C',str(p),'rev-parse','HEAD'],text=True).strip()
def module(name,path):
 spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);sys.modules[name]=m;spec.loader.exec_module(m);return m
def frozen():
 checkout=Path(os.environ['FLASHNEST_DELIVERED_CHECKOUT']).resolve()
 need(git_head(checkout)==DELIVERED,'Frozen delivered checkout changed')
 m=module('mouse_frozen_unload_stage',checkout/FROZEN/'stage.py');m.config();return m

def config():
 c=read(ROOT/'inputs.json')
 need(c['version']=='1.6.0' and c['build']=='24' and c['deliveredCommit']==DELIVERED,'New recipe identity')
 need(c['formalRelease'] is False and c['runtimeChanged'] is False,'Experimental/no-engine-delta scope')
 need({p:h for p,h in inventory(ROOT).items() if p!='inputs.json'}==c['recipeFiles'],'Recipe closure mismatch')
 need(inventory(ROOT/'overlay')=={p:r['after'] for p,r in c['overlay'].items()},'Overlay bytes differ')
 for p in c['overlay']:
  need(not p.startswith(('App/Resources/Web/runtime/','vendor/')) and p not in ['runtime.lock.json','runtime.files.json'],'Runtime mutation forbidden')
 return c

def verify(app,expected):
 for p,h in expected.items():need((app/p).is_file() and not (app/p).is_symlink() and sha((app/p).read_bytes())==h,'Source changed: '+p)
 for folder in ['App','Tests','UITests']:
  actual=inventory(app/folder);wanted={p[len(folder)+1:]:h for p,h in expected.items() if p.startswith(folder+'/')}
  if folder=='App' and 'Info.plist' in actual and 'Info.plist' not in wanted:
   raw=(app/'App/Info.plist').read_bytes()
   normalized=raw.replace(b'<key>CFBundleVersion</key>\n\t<string>24</string>',b'<key>CFBundleVersion</key>\n\t<string>19</string>').replace(b'<key>CFBundleShortVersionString</key>\n\t<string>1.6.0</string>',b'<key>CFBundleShortVersionString</key>\n\t<string>1.5.6</string>')
   need(sha(normalized)=='b71b74d803b9a68e58a77e1043cbdcb07888606b513fecb8000651d73990085f','Generated Info differs beyond version/build');del actual['Info.plist']
  need(actual==wanted,'Source closure changed: '+folder)

def validate_stage(app,receipt,baseline):
 c=config();m=frozen();s=read(receipt);_,_,case=m.inherited(baseline);old,runtime=m.effective_inventory(case)
 before=read(receipt.parent/'unload-staging.json')
 need(sha((receipt.parent/'unload-staging.json').read_bytes())==s['frozenStageSHA256'],'Frozen stage receipt changed')
 need(before['effectiveSourceFiles']==old and before['runtimeFiles']==runtime,'Frozen source receipt identity')
 effective=dict(old)
 for p,row in c['overlay'].items():
  need(effective.get(p)==row['before'],'Overlay preimage differs: '+p);effective[p]=row['after']
 need(s['effectiveSourceFiles']==effective and s['runtimeFiles']==runtime,'New overlay receipt differs')
 need(s['head']==os.environ['GITHUB_SHA'] and s['runID']==os.environ['GITHUB_RUN_ID'],'Wrong current run')
 need(s['overlay']==c['overlay'] and s['recipeFiles']==c['recipeFiles'],'Overlay recipe changed')
 need(s['additionalNativeTests']==c['additionalNativeTests'] and s['additionalTestSourceFiles']==c['additionalTestSourceFiles'],'Native inventory differs')
 need(s['additionalUITests']==c['additionalUITests'] and s['additionalUITestSourceFiles']==c['additionalUITestSourceFiles'],'UI inventory differs')
 need(s['engineReuseSHA256']==before['engineReuseSHA256'] and sha((receipt.parent/'engine-reuse.json').read_bytes())==s['engineReuseSHA256'],'Engine reuse proof changed')
 need(s['cadenceInputsSHA256']==before['cadenceInputsSHA256'] and sha((receipt.parent/'cadence-inputs.json').read_bytes())==s['cadenceInputsSHA256'],'Cadence proof changed')
 need(inventory(app/'App/Resources/Web/runtime')==runtime and len(runtime)==12,'Exact engine closure differs')
 verify(app,effective)
 return s,effective,read(baseline/RECIPE/'inputs.json')

def stage(a):
 c=config();m=frozen();m.stage(a.baseline_checkout,a.source_checkout,a.case_checkout,a.engine_archive,a.engine_metadata,a.output)
 app=a.output/'app';prior,effective,_=m.validate_stage(app,a.output/'unload-staging.json',a.baseline_checkout)
 for p,row in c['overlay'].items():
  need(effective.get(p)==row['before'],'Overlay preimage differs: '+p)
  dest=app/p;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes((ROOT/'overlay'/p).read_bytes());effective[p]=row['after']
 s=dict(prior);s.update(kind='EXPERIMENTAL-MOUSE-TOUCH-160-24',version='1.6.0',build='24',frozenStageSHA256=sha((a.output/'unload-staging.json').read_bytes()),effectiveSourceFiles=effective,overlay=c['overlay'],recipeFiles=c['recipeFiles'],additionalNativeTests=c['additionalNativeTests'],additionalTestSourceFiles=c['additionalTestSourceFiles'],additionalUITests=c['additionalUITests'],additionalUITestSourceFiles=c['additionalUITestSourceFiles'],runtimeChanged=False,formalRelease=False)
 write(a.output/'mouse-staging.json',s);validate_stage(app,a.output/'mouse-staging.json',a.baseline_checkout)
 print('PASS exact frozen base plus explicit 1.6.0/24 overlay; runtime unchanged')
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('action',choices=['stage','verify','preflight'])
 for n in ['baseline-checkout','source-checkout','case-checkout','engine-archive','engine-metadata','output']:p.add_argument('--'+n,type=Path)
 a=p.parse_args()
 if a.action=='preflight':config();frozen()
 elif a.action=='stage':stage(a)
 else:validate_stage(a.output/'app',a.output/'mouse-staging.json',a.baseline_checkout)

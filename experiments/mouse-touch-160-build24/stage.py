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
 need(c['version']=='1.6.0' and c['build']=='26' and c['deliveredCommit']==DELIVERED,'New recipe identity')
 need(c['formalRelease'] is False and c['runtimeChanged'] is False,'Experimental/no-engine-delta scope')
 debug=plistlib.loads((ROOT/'overlay/App/Info-Debug.plist').read_bytes())
 need(debug['CFBundleVersion']==c['build'] and debug['CFBundleShortVersionString']==c['version'],'Debug version differs from package identity')
 project=(ROOT/'overlay/project.yml').read_text()
 for key,value in [('CFBundleVersion',c['build']),('CURRENT_PROJECT_VERSION',c['build']),('CFBundleShortVersionString',c['version']),('MARKETING_VERSION',c['version'])]:
  need((key+": '"+value+"'") in project,'Project version differs: '+key)
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
   normalized=raw.replace(b'<key>CFBundleVersion</key>\n\t<string>26</string>',b'<key>CFBundleVersion</key>\n\t<string>19</string>').replace(b'<key>CFBundleShortVersionString</key>\n\t<string>1.6.0</string>',b'<key>CFBundleShortVersionString</key>\n\t<string>1.5.6</string>')
   need(sha(normalized)=='b71b74d803b9a68e58a77e1043cbdcb07888606b513fecb8000651d73990085f','Generated Info differs beyond version/build');del actual['Info.plist']
  need(actual==wanted,'Source closure changed: '+folder)

def validate_stage(app,receipt,baseline):
 c=config();s=read(receipt);parent=receipt.parent
 manifest=read(ROOT/'recovery-manifest.json');r=read(parent/'recovery-staging.json')
 need(s['kind']=='EXPERIMENTAL-MOUSE-TOUCH-160-26-RECOVERED','Explicit recovered source identity')
 need(s['recoveryReceiptSHA256']==sha((parent/'recovery-staging.json').read_bytes()),'Recovery receipt changed')
 need(r['recoveryManifestSHA256']==sha((ROOT/'recovery-manifest.json').read_bytes()),'Recovery manifest changed')
 need(r['kind']=='EXPLICIT-RECOVERED-SOURCE-BASELINE' and r['legacyStageExecuted'] is False,'Recovery cannot claim legacy staging')
 need(r['recoveryScriptSHA256']==sha((ROOT/'recovery_stage.py').read_bytes()),'Recovery producer changed')
 need(r['materialSources']==manifest['materials'],'Recovery material sources differ')
 effective=manifest['effectiveSourceFiles'];original=manifest['originalEffectiveSourceFiles'];removed=manifest['removedFiles']
 need(removed=={'vendor/ruffle-audio-recovery-40614335019.zip':'3befcb048669c074a017e2bfb6d3ccc283028ef90d7960695bbf0964a2634e9a'},'Unexpected recovery removal')
 need(len(original)==230 and len(effective)==229 and {p:h for p,h in original.items() if p not in removed}==effective and all(original.get(p)==h for p,h in removed.items()),'Recovered source differs beyond declared historical ZIP')
 need(r['effectiveSourceFiles']==effective and r['originalEffectiveSourceFiles']==original and r['removedFiles']==removed,'Recovery source declaration mismatch')
 need(s['effectiveSourceFiles']==effective and s['runtimeFiles']==r['runtimeFiles'],'Mouse recovery identity mismatch')
 for row in [s,r]:need(row['head']==os.environ['GITHUB_SHA'] and row['runID']==os.environ['GITHUB_RUN_ID'],'Wrong recovery current run')
 need(s['overlay']==c['overlay'] and s['recipeFiles']==c['recipeFiles'],'Overlay recipe changed')
 for key in ['additionalNativeTests','additionalTestSourceFiles','additionalUITests','additionalUITestSourceFiles']:need(s[key]==c[key],'Test inventory differs: '+key)
 for filename,key in [('engine-reuse.json','engineReuseSHA256'),('cadence-inputs.json','cadenceInputsSHA256')]:
  need(s[key]==r[key]==sha((parent/filename).read_bytes()),'Recovery runtime proof changed: '+filename)
 reuse=read(parent/'engine-reuse.json');cadence=read(parent/'cadence-inputs.json')
 need(reuse['consumerHead']==s['head'] and reuse['consumerRunID']==s['runID'] and reuse['engineBuildExecutedThisRun'] is False,'Engine reuse current-run identity')
 need(cadence['head']==s['head'] and cadence['runID']==s['runID'] and cadence['runtimeFiles']==s['runtimeFiles']==reuse['runtimeFiles'],'Cadence/runtime identity')
 need(inventory(app/'App/Resources/Web/runtime')==s['runtimeFiles'] and len(s['runtimeFiles'])==12,'Exact engine closure differs')
 need(not (app/next(iter(removed))).exists(),'Removed historical archive unexpectedly present')
 verify(app,effective)
 need(git_head(baseline)==BASE,'Frozen validator checkout identity')
 return s,effective,read(baseline/RECIPE/'inputs.json')

def stage(a):
 c=config();delivered=Path(os.environ['FLASHNEST_DELIVERED_CHECKOUT']).resolve()
 need(git_head(delivered)==DELIVERED,'Frozen delivered checkout changed')
 recovery=module('mouse_recovery_stage',ROOT/'recovery_stage.py')
 recovery.stage(a.baseline_checkout,a.source_checkout,a.case_checkout,delivered,a.engine_archive,a.engine_metadata,a.output)
 r=read(a.output/'recovery-staging.json');s=dict(r)
 s.update(kind='EXPERIMENTAL-MOUSE-TOUCH-160-26-RECOVERED',version='1.6.0',build='26',recoveryReceiptSHA256=sha((a.output/'recovery-staging.json').read_bytes()),overlay=c['overlay'],recipeFiles=c['recipeFiles'],runtimeChanged=False,formalRelease=False)
 for key in ['additionalNativeTests','additionalTestSourceFiles','additionalUITests','additionalUITestSourceFiles']:s[key]=c[key]
 write(a.output/'mouse-staging.json',s);validate_stage(a.output/'app',a.output/'mouse-staging.json',a.baseline_checkout)
 print('PASS explicit recovered229 source baseline; historical ZIP removed, all other hashes unchanged')
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('action',choices=['stage','verify','preflight'])
 for n in ['baseline-checkout','source-checkout','case-checkout','engine-archive','engine-metadata','output']:p.add_argument('--'+n,type=Path)
 a=p.parse_args()
 if a.action=='preflight':config();frozen()
 elif a.action=='stage':stage(a)
 else:validate_stage(a.output/'app',a.output/'mouse-staging.json',a.baseline_checkout)

#!/usr/bin/env python3
"""Build23 diagnostic package: exact build22 business/runtime baseline plus reviewed overlay."""
import argparse,hashlib,importlib.util,json,os,plistlib,shutil,subprocess,sys,tempfile,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parent
BASE_PATH='experiments/release-ipa-156-build22'
def sha(b):return hashlib.sha256(b).hexdigest()
def need(v,m):
 if not v:raise ValueError(m)
def load(p):return json.loads(p.read_text())
def dump(p,x):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(x,indent=2,sort_keys=True)+'\n')
def files(root):
 result={}
 for f in sorted(root.rglob('*')):
  need(not f.is_symlink(),'Symlink in source inventory')
  if f.is_file():result[f.relative_to(root).as_posix()]=sha(f.read_bytes())
 return result

def config():
 x=load(ROOT/'inputs.json')
 need(x['schemaVersion']==1 and x['kind']=='EXPERIMENTAL-LONGRUN-DIAGNOSTIC','Wrong diagnostic scope')
 need(x['dispatchAllowed'] is True,'Diagnostic build dispatch not authorized')
 need(x['baselineSourceCommit']=='985f25c44ead766b2c4f9bd77b82e7b92bf95cc0' and x['frozenSourceCommit']=='9bc000e37695696f2427b25fe08efe4993bf22e5','Wrong baseline source commits')
 need(set(x['recipeFiles'])=={'package.py','run_focused_tests.py','workflow.yml','README.md','checks/test_long_run.js','checks/test_contract.py','checks/test_package.py'},'Incomplete recipe closure')
 need(x['version']=='1.5.6' and x['build']=='23' and x['bundleID']=='com.flashnest.app','Wrong package identity')
 for key in ['diagnosticOptInDefault','automaticUpload','cacheEvictionEnabled','engineProductChanges','originalCrashResolved','fullGatePassed','physicalDeviceCertified']:
  need(x[key] is False,'Invalid claim/behavior '+key)
 for p,h in x['recipeFiles'].items():need(sha((ROOT/p).read_bytes())==h,'Recipe hash mismatch '+p)
 need(set(x['overlay'])==set(files(ROOT/'overlay')),'Overlay closure differs')
 for p,row in x['overlay'].items():
  need(p.startswith(('App/','Tests/','UITests/')) or p=='project.yml','Unexpected overlay path')
  need('..' not in Path(p).parts and not Path(p).is_absolute() and '\\' not in p and ':' not in p and not p.startswith('App/Resources/Web/runtime/'),'Runtime/unsafe overlay')
  need(sha((ROOT/'overlay'/p).read_bytes())==row['after'],'Overlay hash differs '+p)
 return x

def load_release(recipe,x):
 base=recipe/BASE_PATH
 need(files(base)==x['releaseRecipeFiles'],'Frozen release recipe differs')
 sys.path.insert(0,str(base))
 spec=importlib.util.spec_from_file_location('release_baseline',base/'package.py');release=importlib.util.module_from_spec(spec);spec.loader.exec_module(release)
 y=release.inputs();phase,old=release.load_base(recipe,y)
 need(y['candidateAppFiles']==x['baselineAppFiles'] and y['candidateRuntimeFiles']==x['runtimeFiles'],'Baseline identity differs')
 return release,y,phase,old

def stage(source,recipe,out):
 x=config();source=source.resolve();recipe=recipe.resolve();out=out.resolve()
 need(subprocess.check_output(['git','-C',str(source),'rev-parse','HEAD'],text=True).strip()==x['frozenSourceCommit'],'Wrong frozen checkout')
 release,y,phase,old=load_release(recipe,x)
 need(not out.exists(),'Refuse overwrite of staging');out.mkdir();src=out/'source';src.mkdir()
 for p,h in old['sourceFiles'].items():
  f=source/'experiments/final-composite'/p;need(f.is_file() and not f.is_symlink() and sha(f.read_bytes())==h,'Frozen source mismatch '+p)
  d=src/p;d.parent.mkdir(parents=True,exist_ok=True);d.write_bytes(f.read_bytes())
 need(files(src)==old['sourceFiles'],'Frozen source closure differs')
 sys.path.insert(0,str(src/'scripts'));import stage_validation_runtime as runtime
 original_fetch=runtime.fetch
 runtime.fetch=lambda e:release.mirror_bytes(recipe,y,e) if e==old['engine'] else original_fetch(e)
 runtime.main();import stage_validation_inputs as materialize;materialize.main()
 app=src/'validation-app';phase.overlay(app,old);phase.diagnostic_overlay(app,old)
 need(files(app)==y['baseAppFiles'],'Phase baseline mismatch')
 candidate=original_fetch(y['candidateEngine']);(out/'candidate.zip').write_bytes(candidate)
 release.rebind(app,candidate,y)
 need(files(app)==x['baselineAppFiles'],'Build22 207-file baseline differs')
 for p,row in x['overlay'].items():
  f=app/p;need((f.is_file() and sha(f.read_bytes())==row['before']) if row['before'] is not None else not f.exists(),'Overlay before mismatch '+p)
 for p,row in x['overlay'].items():
  f=app/p;f.parent.mkdir(parents=True,exist_ok=True);f.write_bytes((ROOT/'overlay'/p).read_bytes())
 expected=dict(x['baselineAppFiles']);expected.update({p:r['after'] for p,r in x['overlay'].items()})
 need(files(app)==expected,'Final diagnostic source differs')
 shutil.copytree(app,out/'app')
 dump(out/'staging.json',{'schemaVersion':1,'baselineSourceCommit':x['baselineSourceCommit'],'baselineSourceFiles':x['baselineAppFiles'],'diagnosticSourceFiles':expected,'runtimeFiles':x['runtimeFiles'],'overlay':x['overlay'],'originalCrashResolved':False,'fullGatePassed':False})
 print('Build22 source and runtime verified; reviewed build23 diagnostic overlay staged')

def verify(ipa,app,out,record):
 x=config();staged=load(out/'staging.json')
 # Reuse frozen strict IPA path/Mach-O checks, not prior release waiver or prior tests.
 release,y,_,_=load_release(Path(os.environ['RECIPE_CHECKOUT']).resolve(),x);c=release.c
 c.verify_sources(app,staged['diagnosticSourceFiles'])
 raw_info=(app/'App/Info.plist').read_bytes();anchor=b'<key>CFBundleVersion</key>\n\t<string>23</string>'
 need(raw_info.count(anchor)==1 and sha(raw_info.replace(anchor,b'<key>CFBundleVersion</key>\n\t<string>19</string>'))=='b71b74d803b9a68e58a77e1043cbdcb07888606b513fecb8000651d73990085f','Generated Info.plist differs')
 test=load(out/'focused-tests/verification.json');need(test['diagnosticTestsPassed'] is True and test['fullGatePassed'] is False,'Missing actual focused native pass')
 need(test['sourceFiles']==staged['diagnosticSourceFiles'],'Native test source binding differs')
 with tempfile.TemporaryDirectory() as temp:
  with zipfile.ZipFile(ipa) as z:c.safe_ipa_members(z.infolist());need(z.testzip() is None,'IPA CRC');z.extractall(temp)
  bundle=Path(temp)/'Payload/FlashNest.app';c.verify_outer_payload(bundle)
  info=plistlib.loads((bundle/'Info.plist').read_bytes())
  expected={'CFBundleIdentifier':x['bundleID'],'CFBundleShortVersionString':x['version'],'CFBundleVersion':x['build'],'DTPlatformName':'iphoneos','CFBundleExecutable':'FlashNest','MinimumOSVersion':'17.0','DTSDKName':'iphoneos18.2'}
  for k,v in expected.items():need(info.get(k)==v,'Actual IPA identity differs '+k)
  macho=c.device_macho((bundle/'FlashNest').read_bytes())
  need(files(bundle/'Web')==files(app/'App/Resources/Web'),'IPA Web bytes differ')
  need(files(bundle/'Web/runtime')==x['runtimeFiles'],'IPA engine changed')
  dump(record,{'schemaVersion':1,'kind':x['kind'],'version':x['version'],'build':x['build'],'unsigned':True,'ipaSHA256':sha(ipa.read_bytes()),'ipaBytes':ipa.stat().st_size,'packagingCommit':os.environ.get('GITHUB_SHA'),'packagingRunID':os.environ.get('GITHUB_RUN_ID'),'baselineSourceCommit':x['baselineSourceCommit'],'appSourceFiles':staged['diagnosticSourceFiles'],'runtimeFiles':x['runtimeFiles'],'webFiles':files(bundle/'Web'),'nativeFocusedTests':test,'deviceExecutable':macho,'diagnosticOptInDefault':False,'automaticUpload':False,'originalCrashResolved':False,'fullGatePassed':False,'physicalDeviceCertified':False})
 print('Actual build23 diagnostic IPA verified; not full native or physical-device acceptance')
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('action',choices=['preflight','stage','verify']);p.add_argument('--source-checkout',type=Path);p.add_argument('--recipe-checkout',type=Path);p.add_argument('--output',type=Path);p.add_argument('--app',type=Path);p.add_argument('--ipa',type=Path);p.add_argument('--record',type=Path);a=p.parse_args()
 if a.action=='preflight':config();print('Diagnostic-only recipe verified')
 elif a.action=='stage':stage(a.source_checkout,a.recipe_checkout,a.output)
 else:verify(a.ipa,a.app,a.output,a.record)

#!/usr/bin/env python3
"""Explicit early-device-test package. Never creates full native acceptance."""
import argparse,importlib.util,json,os,plistlib,shutil,subprocess,sys,tempfile,zipfile
from pathlib import Path
import package_checks as c
ROOT=Path(__file__).resolve().parent
OWN={'package_checks.py','experiment.py','test_experiment.py','build-device-phase-diagnostic-ipa.yml','README.md','run_focused_tests.py','checks/test_phase.js','checks/test_server_phase.py','checks/test_native_contract.py'}

def inputs(verify_own=True):
 x=c.load(ROOT/'inputs.json')
 c.require(x.get('schemaVersion')==1 and x.get('kind')=='EXPERIMENTAL-UNVERIFIED' and x.get('userRequestedEarlyDeviceTest') is True,'Not explicit early-test scope')
 for key in ('nativeAccepted','fullGatePassed','physicalDeviceCertified'):c.require(x.get(key) is False,'Experimental package cannot claim acceptance')
 for key in ('experimentalGateOverride','experimentalOptIn'):c.require(x.get(key) is True,'Experimental sampling override must be explicit')
 for key,value in {'version':'1.5.6','build':'20','bundleID':'com.flashnest.app','repository':'op233qo123/FlashNest','xcode':'16.2','sdk':'18.2','minimumOS':'17.0','sourceCommit':'9bc000e37695696f2427b25fe08efe4993bf22e5'}.items():c.require(x.get(key)==value,'Frozen identity differs: '+key)
 for key in ('sourceFiles','appGateOffFiles','appGateOnFiles','runtimeFiles','recipeFiles'):c.hash_map(x[key])
 c.require(set(x['recipeFiles'])==OWN,'Own recipe incomplete')
 if verify_own:
  for p,h in x['recipeFiles'].items():c.require(c.digest((ROOT/p).read_bytes())==h,'Experimental recipe changed: '+p)
 expected={'App/Player/RenderSamplingSettings.swift','Tests/RenderSamplingSettingsTests.swift'}
 a,b=x['appGateOffFiles'],x['appGateOnFiles']
 c.require(set(a)==set(b) and {p for p in a if a[p]!=b[p]}==expected and set(x['gateOverlay'])==expected,'Only exact two-file experimental gate overlay allowed')
 for p,row in x['gateOverlay'].items():c.require(row['before']==a[p] and row['after']==b[p],'Gate hashes differ')
 c.require(x.get('diagnosticOptInDefault') is False and x.get('diagnosticOnly') is True, 'Diagnostic must remain default-off, not a fix')
 c.hash_map(x['diagnosticAppFiles'])
 changes=x['diagnosticOverlay']; c.require(isinstance(changes,dict) and changes, 'Diagnostic overlay not frozen')
 expected_delta={p for p in set(x['appGateOnFiles'])|set(x['diagnosticAppFiles']) if x['appGateOnFiles'].get(p)!=x['diagnosticAppFiles'].get(p)}
 c.require(set(changes)==expected_delta, 'Diagnostic delta inventory incomplete')
 for p,row in changes.items():
  c.safe(p); c.require(row['before']==x['appGateOnFiles'].get(p) and row['after']==x['diagnosticAppFiles'].get(p) and row['after'] is not None, 'Overlay identity mismatch')
  c.require(p=='project.yml' or p.startswith(('App/','Tests/')), 'Unexpected diagnostic source path')
  c.require(not p.startswith('App/Resources/Web/runtime/'), 'Runtime modification forbidden')
  if verify_own:
   f=ROOT/'overlay'/p; c.require(f.is_file() and not f.is_symlink() and c.digest(f.read_bytes())==row['after'], 'Diagnostic overlay bytes differ: '+p)
 if verify_own:c.require(c.file_map(ROOT/'overlay')=={p:r['after'] for p,r in changes.items()}, 'Extra overlay files')
 return x

def diagnostic_overlay(app,x):
 c.require(c.file_map(app)==x['appGateOnFiles'], 'Diagnostic input differs from frozen sampling-on App')
 for p,row in x['diagnosticOverlay'].items():
  f=app/p
  c.require((f.is_file() and c.digest(f.read_bytes())==row['before']) if row['before'] is not None else not f.exists(), 'Diagnostic before mismatch: '+p)
 # All sources validated before any write; no removal or binary runtime mutation.
 for p,row in x['diagnosticOverlay'].items():
  raw=(ROOT/'overlay'/p).read_bytes();c.require(c.digest(raw)==row['after'], 'Diagnostic payload mismatch')
  f=app/p;f.parent.mkdir(parents=True,exist_ok=True);f.write_bytes(raw)
 c.require(c.file_map(app)==x['diagnosticAppFiles'], 'Diagnostic final full App mismatch')

def overlay(app,x):
 c.require(c.file_map(app)==x['appGateOffFiles'],'Original full App input differs')
 for p,row in x['gateOverlay'].items():
  f=app/p;raw=f.read_bytes();old=row['old'].encode();new=row['new'].encode()
  c.require(raw.count(old)==1 and c.digest(raw)==row['before'],'Experimental gate anchor differs')
  changed=raw.replace(old,new);c.require(c.digest(changed)==row['after'],'Experimental gate change differs');f.write_bytes(changed)
 c.require(c.file_map(app)==x['appGateOnFiles'],'Experimental App includes other changes')

def stage(checkout,out):
 x=inputs();checkout=checkout.resolve();out=out.resolve()
 c.require(subprocess.check_output(['git','-C',str(checkout),'rev-parse','HEAD'],text=True).strip()==x['sourceCommit'],'Wrong exact source commit')
 c.require(not out.exists(),'Fresh experimental workspace required');out.mkdir()
 source=out/'source';source.mkdir();published=checkout/'experiments/final-composite'
 # Minimal complete execution closure, not the test harness or a mutable source tree.
 for p,h in x['sourceFiles'].items():
  f=published/p;c.require(f.is_file() and not f.is_symlink() and c.digest(f.read_bytes())==h,'Frozen execution input differs: '+p)
  dest=source/p;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(f.read_bytes())
 c.require(c.file_map(source)==x['sourceFiles'],'Source closure copy differs')
 lock=c.load(source/'validation-lock.json');c.require(lock['engine']==x['engine'] and lock['appSourceManifest']['files']==x['appGateOffFiles'],'Runtime/App manifest changed')
 for script in ('stage_validation_runtime.py','stage_validation_inputs.py'):subprocess.run([sys.executable,'-E','-B',str(source/'scripts'/script)],check=True)
 app=source/'validation-app';c.require(c.file_map(app/'App/Resources/Web/runtime')==x['runtimeFiles'],'Actual accepted runtime bytes differ')
 overlay(app,x);diagnostic_overlay(app,x);shutil.copytree(app,out/'app')
 (out/'experiment-staging.json').write_text(json.dumps({'kind':x['kind'],'sourceCommit':x['sourceCommit'],'engine':x['engine'],'experimentalGateOverride':True,'nativeAccepted':False,'fullGatePassed':False,'appFiles':x['diagnosticAppFiles'],'diagnosticOnly':True,'diagnosticOptInDefault':False},indent=2,sort_keys=True)+'\n')
 print('Exact experimental App staged; low sampling explicitly overridden ON; full native acceptance FALSE')

def verify(ipa,app,out,record):
 x=inputs();c.verify_sources(app,x['diagnosticAppFiles'])
 raw_info=(app/'App/Info.plist').read_bytes();version_anchor=b'<key>CFBundleVersion</key>\n\t<string>20</string>';c.require(raw_info.count(version_anchor)==1,'Generated Info version anchor differs')
 c.require(c.digest(raw_info.replace(version_anchor,b'<key>CFBundleVersion</key>\n\t<string>19</string>'))=='b71b74d803b9a68e58a77e1043cbdcb07888606b513fecb8000651d73990085f','Generated main Info.plist differs')
 staged=c.load(out/'experiment-staging.json');c.require(staged['appFiles']==x['diagnosticAppFiles'] and staged['diagnosticOnly'] is True and staged['diagnosticOptInDefault'] is False and staged['nativeAccepted'] is False and staged['fullGatePassed'] is False and staged['experimentalGateOverride'] is True,'Experiment staging scope differs')
 with tempfile.TemporaryDirectory() as tmp:
  with zipfile.ZipFile(ipa) as z:c.safe_ipa_members(z.infolist());c.require(z.testzip() is None,'IPA CRC failure');z.extractall(tmp)
  bundle=Path(tmp)/'Payload/FlashNest.app';c.verify_outer_payload(bundle)
  info=plistlib.loads((bundle/'Info.plist').read_bytes())
  for k,v in {'CFBundleIdentifier':x['bundleID'],'CFBundleShortVersionString':x['version'],'CFBundleVersion':x['build'],'DTPlatformName':'iphoneos','CFBundleExecutable':'FlashNest','MinimumOSVersion':'17.0','DTSDKName':'iphoneos18.2'}.items():c.require(info.get(k)==v,'Actual built identity differs: '+k)
  macho=c.device_macho((bundle/'FlashNest').read_bytes())
  c.require(c.file_map(bundle/'Web')==c.file_map(app/'App/Resources/Web'),'Full bundled Web differs')
  c.require(c.file_map(bundle/'Web/runtime')==x['runtimeFiles'],'Packaged runtime differs')
  sys.path.insert(0,str(app/'scripts'))
  spec=importlib.util.spec_from_file_location('experimental_runtime_verify',app/'scripts/verify_bundled_runtime.py');module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);module.verify_web(bundle/'Web',app)
  for name in ('shell.js','index.html'):
   raw=(bundle/'Web'/name).read_bytes();c.require(not any(v in raw for v in (b'__flashnestPhase',b'__nativeSamplingProbe',b'flashnest-native-sampling-pre-drag',b'late-audio-probe',b'audio-recovery-injection')),'Test probe in shipping Web')
  provenance={'schemaVersion':1,'kind':x['kind'],'experimentalGateOverride':True,'experimentalOptIn':True,'nativeAccepted':False,'fullGatePassed':False,'physicalDeviceCertified':False,'enhancedRenderHealthCertified':False,'originalCrashResolved':False,'peakMemoryImprovementEstablished':False,'version':x['version'],'build':x['build'],'bundleID':x['bundleID'],'sourceCommit':x['sourceCommit'],'engine':x['engine'],'acceptedBrowserReference':x['acceptedBrowserReference'],'packagingCommit':os.environ.get('GITHUB_SHA'),'packagingRunID':os.environ.get('GITHUB_RUN_ID'),'ipaSHA256':c.digest(ipa.read_bytes()),'ipaBytes':ipa.stat().st_size,'deviceExecutable':macho,'appSourceFiles':x['diagnosticAppFiles'],'diagnosticOverlay':x['diagnosticOverlay'],'diagnosticOnly':True,'diagnosticOptInDefault':False,'gateOverlay':x['gateOverlay'],'webFiles':c.file_map(bundle/'Web'),'knownLimitations':x['knownLimitations'],'unsigned':True}
  record.write_text(json.dumps(provenance,indent=2,sort_keys=True)+'\n')
 print('Experimental device IPA bytes verified; NOT complete native regression acceptance')

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('action',choices=('preflight','stage','verify'));p.add_argument('--checkout',type=Path);p.add_argument('--output',type=Path);p.add_argument('--ipa',type=Path);p.add_argument('--app',type=Path);p.add_argument('--record',type=Path);a=p.parse_args()
 if a.action=='preflight':inputs();print('Explicit experimental-only package scope verified')
 elif a.action=='stage':stage(a.checkout,a.output)
 else:verify(a.ipa,a.app,a.output,a.record)

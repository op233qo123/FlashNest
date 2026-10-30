#!/usr/bin/env python3
"""Independent build-only release decision; never changes the original XCTest gate."""
import argparse,importlib.util,json,os,plistlib,sys,tempfile,zipfile,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parent
BASE=Path(os.environ.get('RELEASE_RECIPE_PATH',str(ROOT.parent/'native-release-ipa-156-build22'))).resolve()
bootstrap=json.loads((ROOT/'inputs.json').read_text())
for name,digest in bootstrap['baseRecipeFiles'].items():
 file=BASE/name
 if Path(name).name!=name or file.is_symlink() or hashlib.sha256(file.read_bytes()).hexdigest()!=digest:raise ValueError('Frozen base recipe mismatch before import')
sys.path.insert(0,str(BASE))
import package_checks as c
import candidate_composite_runtime as consumer
spec=importlib.util.spec_from_file_location('frozen_release_package',BASE/'package.py');old=importlib.util.module_from_spec(spec);spec.loader.exec_module(old)
import run_selected_tests as prior_runner
OWN={'waiver.py','test_waiver.py','workflow.yml','README.md'}
def config(dispatch=False):
 x=c.load(ROOT/'inputs.json')
 c.require(x['schemaVersion']==1 and x['releaseDecision']=='accepted-known-ui-validation-limitation' and x['acceptedByUser'] is True,'Wrong release decision')
 c.require(x['selectedReleaseGatePassed'] is False and type(x['testsRunThisPackagingJob']) is int and x['testsRunThisPackagingJob']==0,'Application test result misrepresented')
 c.require((x['version'],x['build'],x['bundleID'])==('1.5.6','22','com.flashnest.app'),'Wrong release identity')
 c.require(x['baseRecipePath']=='experiments/release-ipa-156-build22','Wrong frozen recipe')
 c.require(set(x['sourceFiles'])==OWN and set(x['baseRecipeFiles'])==old.OWN|{'inputs.json'},'Incomplete waiver/base recipe closure')
 for path,h in x['sourceFiles'].items():c.require(c.digest((ROOT/path).read_bytes())==h,'Waiver source changed')
 for path,h in x['baseRecipeFiles'].items():c.require(c.digest((BASE/path).read_bytes())==h,'Frozen base recipe changed')
 if dispatch:c.require(x['dispatchAllowed'] is True,'Build-only release dispatch disabled')
 return x

def archive(raw,pin):
 c.require(len(raw)==pin['bytes'] and c.digest(raw)==pin['sha256'],'Historical artifact archive differs')
 with old.checked_zip(raw,1048576) as z:
  c.require({n:c.digest(z.read(n)) for n in z.namelist()}==pin['files'],'Historical full evidence inventory differs')
  return {n:json.loads(z.read(n)) for n in z.namelist()}

def validate_history(first,last,x,base):
 a=archive(first,x['history']['priorSelected']);b=archive(last,x['history']['lastUI']);unit=a['unit-result.json'];ui=a['ui-result.json'];source=a['test-source-receipt.json']
 pin=x['history']['priorSelected'];expected=['/'.join(('FlashNestTests',cls,method)) for cls,method in prior_runner.UNIT];ui_expected=['/'.join(('FlashNestUITests',cls,method)) for cls,method in prior_runner.UI]
 for row in (unit,ui,source):c.require(row['runID']==pin['runID'] and row['head']==pin['sourceCommit'],'Historical run/head differs')
 c.require(unit['selected']==expected and len(unit['passed'])==15 and set(unit['passed'])==set(expected) and unit['failed']==[] and unit['unexpectedMethodCount']==0,'Prior15 method evidence differs')
 c.require(unit['counts']=={'totalTestCount':15,'passedTests':15,'failedTests':0,'skippedTests':0,'expectedFailures':0},'Prior15 counts differ')
 c.require(ui['selected']==ui_expected and ui['passed']==[] and ui['failed']==ui_expected and ui['counts']=={'totalTestCount':1,'passedTests':0,'failedTests':1,'skippedTests':0,'expectedFailures':0},'Historical UI failure changed')
 c.require(source['original207SourceFiles']==base['candidateAppFiles'] and source['restoredOriginal207'] is True and source['testOnlyCleanup']==base['testOnlyCleanup'],'Original207 or reviewed test delta differs')
 before=source['baseSourceInventory'];tested=source['testedSourceInventory'];change=base['testOnlyCleanup'];expected_tested=dict(before);expected_tested[change['path']]={'sha256':change['afterSHA256'],'bytes':change['afterBytes']}
 c.require(tested==expected_tested and all(row['sha256']==base['candidateAppFiles'][path] for path,row in before.items()),'Actual test-source inventory differs')
 source=b['source-receipt.json'];observation=b['safe-ui-observation.json'];pin=x['history']['lastUI'];mapsha=c.digest(json.dumps(base['candidateAppFiles'],sort_keys=True,separators=(',',':')).encode())
 c.require(source['runID']==pin['runID'] and source['head']==pin['sourceCommit'] and source['baselineSourceFilesMapSHA256']==mapsha==source['restoredSourceFilesMapSHA256'],'LastUI original source/run binding differs')
 c.require(source['selectedReleaseGatePassed'] is False and source['observedUIAssertionsPassed'] is False and source['restoredOriginalSource'] is True and source['originalRuntimeUnchanged'] is True,'LastUI acceptance/restoration changed')
 c.require(source['executedTestOnlyOverlay']=={'path':'UITests/LifecyclePlayerUITests.swift','beforeSHA256':base['candidateAppFiles']['UITests/LifecyclePlayerUITests.swift'],'afterSHA256':'3dbdf9d3ff6a54f707cbf5cea8c8b20c774dafc11fd1e197fc76cd13f50b3bfb'},'LastUI diagnostic delta differs')
 c.require(observation['counts']=={'totalTestCount':1,'passedTests':0,'failedTests':1,'skippedTests':0,'expectedFailures':0} and observation['failures']==[{'schema':1,'step':'restartPlay','source':'LifecyclePlayerUITests.swift','line':121,'kind':'assertion'}],'LastUI observed failure differs')
 return {'prior15App':'passed','prior15Methods':expected,'UIstatus':'failed','selectedReleaseGatePassed':False,'priorSelected':x['history']['priorSelected'],'lastUI':x['history']['lastUI'],'limitation':'Simulator UI automation has not passed consistently; original combined gate remains failed.'}

def stage(source_checkout,recipe_checkout,out):
 x=config(True);old.stage(source_checkout,recipe_checkout,out)
 import stage_validation_runtime as runtime
 first=runtime.fetch(x['history']['priorSelected']);last=runtime.fetch(x['history']['lastUI']);history=validate_history(first,last,x,old.inputs())
 (out/'prior-selected.zip').write_bytes(first);(out/'last-ui.zip').write_bytes(last);(out/'release-decision.json').write_text(json.dumps(history,indent=2)+'\n')

def verify(ipa,app,out,record):
 decision=config(True);x=old.inputs();c.verify_sources(app,x['candidateAppFiles']);history=validate_history((out/'prior-selected.zip').read_bytes(),(out/'last-ui.zip').read_bytes(),decision,x)
 raw_info=(app/'App/Info.plist').read_bytes();version_anchor=b'<key>CFBundleVersion</key>\n\t<string>22</string>';c.require(raw_info.count(version_anchor)==1,'Generated Info version anchor differs')
 c.require(c.digest(raw_info.replace(version_anchor,b'<key>CFBundleVersion</key>\n\t<string>19</string>'))=='b71b74d803b9a68e58a77e1043cbdcb07888606b513fecb8000651d73990085f','Generated main Info.plist differs')
 staged=c.load(out/'staging.json');c.require(staged['candidateAppFiles']==x['candidateAppFiles'] and staged['browser']['verified'] is True and staged['candidateEngine']==x['candidateEngine'] and staged['nativeAccepted'] is False and staged['fullGatePassed'] is False,'Candidate staging binding differs')
 lock=c.load(app/'runtime.lock.json');consumer.verified_runtime((app/lock['archivePath']).read_bytes(),lock,c.load(app/'runtime.files.json'),(app/'App/Resources/Web/runtime-identity.json').read_bytes())
 with tempfile.TemporaryDirectory() as tmp:
  with zipfile.ZipFile(ipa) as z:c.safe_ipa_members(z.infolist());c.require(z.testzip() is None,'IPA CRC failure');z.extractall(tmp)
  bundle=Path(tmp)/'Payload/FlashNest.app';c.verify_outer_payload(bundle)
  info=plistlib.loads((bundle/'Info.plist').read_bytes())
  for k,v in {'CFBundleIdentifier':x['bundleID'],'CFBundleShortVersionString':x['version'],'CFBundleVersion':x['build'],'DTPlatformName':'iphoneos','CFBundleExecutable':'FlashNest','MinimumOSVersion':'17.0','DTSDKName':'iphoneos18.2'}.items():c.require(info.get(k)==v,'Actual built identity differs: '+k)
  macho=c.device_macho((bundle/'FlashNest').read_bytes())
  c.require(len(c.file_map(bundle/'Web'))==32 and c.file_map(bundle/'Web')==c.file_map(app/'App/Resources/Web'),'Full bundled Web differs')
  c.require(c.file_map(bundle/'Web/runtime')==x['candidateRuntimeFiles'],'Packaged runtime differs')
  sys.path.insert(0,str(app/'scripts'))
  spec=importlib.util.spec_from_file_location('experimental_runtime_verify',app/'scripts/verify_bundled_runtime.py');module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);module.verify_web(bundle/'Web',app)
  for name in ('shell.js','index.html'):
   raw=(bundle/'Web'/name).read_bytes();c.require(not any(v in raw for v in (b'__flashnestPhase',b'__nativeSamplingProbe',b'flashnest-native-sampling-pre-drag',b'late-audio-probe',b'audio-recovery-injection')),'Test probe in shipping Web')
  provenance={'schemaVersion':1,'kind':x['kind'],'releaseChannel':x['releaseChannel'],'releaseDecision':decision['releaseDecision'],'acceptedByUser':True,'selectedReleaseGatePassed':False,'testsRunThisPackagingJob':0,'testCountScope':'Application XCTest only; packaging integrity checks still execute','historicalValidation':history,'packageVerified':True,'experimentalGateOverride':True,'nativeAccepted':False,'fullGatePassed':False,'physicalDeviceCertified':False,'originalCrashResolved':False,'productionAccepted':False,'version':x['version'],'build':x['build'],'bundleID':x['bundleID'],'baseSourceCommit':x['sourceCommit'],'candidateEngine':x['candidateEngine'],'focusedBrowserReference':x['browserEvidence'],'packagingCommit':os.environ.get('GITHUB_SHA'),'packagingRunID':os.environ.get('GITHUB_RUN_ID'),'ipaSHA256':c.digest(ipa.read_bytes()),'ipaBytes':ipa.stat().st_size,'deviceExecutable':macho,'appSourceFiles':x['candidateAppFiles'],'baseAppFiles':x['baseAppFiles'],'candidateRuntimeExperiment':True,'diagnosticsRetained':True,'diagnosticOptInDefault':False,'webFiles':c.file_map(bundle/'Web'),'unsigned':True}
  record.write_text(json.dumps(provenance,indent=2,sort_keys=True)+'\n')
 print('Release IPA bytes verified under accepted UI-validation limitation; original selected test gate remains failed')

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('action',choices=['preflight','stage','verify']);p.add_argument('--source-checkout',type=Path);p.add_argument('--recipe-checkout',type=Path);p.add_argument('--output',type=Path);p.add_argument('--ipa',type=Path);p.add_argument('--app',type=Path);p.add_argument('--record',type=Path);a=p.parse_args()
 if a.action=='preflight':config(True);print('Explicit build-only release decision verified; application tests not run')
 elif a.action=='stage':stage(a.source_checkout,a.recipe_checkout,a.output)
 else:verify(a.ipa,a.app,a.output,a.record)

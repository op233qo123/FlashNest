#!/usr/bin/env python3
"""Diagnostic-only UI identity observation; never a release gate or product fix."""
import hashlib,json,os,plistlib,re,shutil,subprocess,sys,time
from pathlib import Path
HERE=Path(__file__).resolve().parent
BASE=Path(os.environ.get('RELEASE_RECIPE_PATH',str(HERE.parent/'native-release-ipa-156-build22'))).resolve()
sys.path.insert(0,str(BASE))
import package_checks as c
import run_selected_tests as original
import overlay
UNIT=original.UNIT;UI=original.UI;BUDGETS=original.BUDGETS;FIXTURE_BUNDLE=original.FIXTURE_BUNDLE
sha=original.sha;verify=original.verify;selectors=original.selectors;source_inventory=original.source_inventory

def preflight(dispatch=False):
 lock=c.load(HERE/'inputs.json');c.require(lock['diagnosticOnly'] is True and lock['selectedReleaseGatePassed'] is False,'Not diagnostic-only scope')
 c.require(c.digest((BASE/'inputs.json').read_bytes())==lock['baseInputsSHA256'],'Published release recipe differs')
 for path,h in lock['sourceFiles'].items():c.require(c.digest((HERE/path).read_bytes())==h,'Probe source differs: '+path)
 if dispatch:c.require(lock['dispatchAllowed'] is True,'Diagnostic dispatch not authorized')
 return lock

def run(app,out):
 preflight(True)
 app=Path(app).resolve();out=Path(out).resolve();out.mkdir(exist_ok=False)
 baseline=c.load(BASE/'inputs.json')['candidateAppFiles'];c.verify_sources(app,baseline)
 state=out/'overlay-state.json';probe_record={'diagnosticOnly':True,'selectedReleaseGatePassed':False,'baselineSourceFiles':baseline,'restoredOriginalSource':False};ui=None
 run_id=os.environ.get('GITHUB_RUN_ID','');head=os.environ.get('GITHUB_SHA','')
 c.require(run_id.isdigit() and int(run_id)>0 and re.fullmatch('[0-9a-f]{40}',head),'Missing CI run/head binding')
 inventory=source_inventory(app);deadline=time.monotonic()+BUDGETS['overallSeconds'];device=None
 def budget(seconds):
  remaining=deadline-time.monotonic();c.require(remaining>0,'Selected native regression total deadline exceeded')
  return min(seconds,remaining)
 def command(args,seconds,logname=None):
  if logname:
   with (out/logname).open('w') as log:return subprocess.run(args,cwd=app,stdout=log,stderr=subprocess.STDOUT,timeout=budget(seconds),check=True)
  return subprocess.check_output(args,cwd=app,stderr=subprocess.STDOUT,timeout=budget(seconds))
 def lane(name,scheme,bundle,expected,method_seconds,command_seconds):
  result=out/(name+'.xcresult')
  args=['xcodebuild','test','-project','FlashNest.xcodeproj','-scheme',scheme,'-configuration','Debug','-sdk','iphonesimulator',
        '-destination','platform=iOS Simulator,id='+device,'-derivedDataPath',str(out/'build'),'-resultBundlePath',str(result),
        '-disableAutomaticPackageResolution','-parallel-testing-enabled','NO','-maximum-concurrent-test-simulator-destinations','1',
        '-test-timeouts-enabled','YES','-default-test-execution-time-allowance',str(method_seconds),'-maximum-test-execution-time-allowance',str(method_seconds)]
  args+=selectors(bundle,expected)+['CODE_SIGNING_ALLOWED=NO','CODE_SIGNING_REQUIRED=NO']
  failure=None
  try:command(args,command_seconds,name+'.log')
  except (subprocess.CalledProcessError,subprocess.TimeoutExpired) as error:failure=error
  if result.exists():
   raw=command(['xcrun','xcresulttool','get','test-results','summary','--path',str(result)],60)
   (out/(name+'-summary.json')).write_bytes(raw)
  else:raw=None
  if failure:raise failure
  c.require(raw is not None,'Missing selected xcresult: '+name)
  receipt=verify(json.loads(raw),(out/(name+'.log')).read_text(),expected,bundle,device)
  receipt['summarySHA256']=sha(raw);receipt['resultBundle']=result.name
  (out/(name+'-verification.json')).write_text(json.dumps(receipt,indent=2)+'\n');return receipt
 try:
  device=command(['xcrun','simctl','create','FlashNestSelectedRegression','com.apple.CoreSimulator.SimDeviceType.iPhone-SE-3rd-generation','com.apple.CoreSimulator.SimRuntime.iOS-18-2'],60).decode().strip()
  c.require(re.fullmatch(r'[0-9A-Fa-f-]{36}',device) is not None,'Invalid created simulator identifier')
  command(['xcrun','simctl','boot',device],60);command(['xcrun','simctl','bootstatus',device,'-b'],180)
  unit=lane('unit','FlashNest','FlashNestTests',UNIT,120,BUDGETS['unitCommandSeconds'])
  # The existing UI test genuinely selects files from this separate app sandbox.
  command(['xcodebuild','build','-project','FlashNest.xcodeproj','-scheme','FlashNestFixtureSource','-configuration','Debug','-sdk','iphonesimulator',
           '-destination','platform=iOS Simulator,id='+device,'-derivedDataPath',str(out/'build'),'-disableAutomaticPackageResolution',
           'CODE_SIGNING_ALLOWED=NO','CODE_SIGNING_REQUIRED=NO'],BUDGETS['fixtureBuildSeconds'],'fixture-source-build.log')
  fixture=out/'build/Build/Products/Debug-iphonesimulator/FlashNestFixtureSource.app'
  info=plistlib.loads((fixture/'Info.plist').read_bytes());c.require(info.get('CFBundleIdentifier')==FIXTURE_BUNDLE,'Wrong fixture source app')
  executable=info.get('CFBundleExecutable');c.require(isinstance(executable,str) and re.fullmatch(r'[A-Za-z0-9_-]+',executable),'Unsafe fixture executable')
  binary=(fixture/executable).read_bytes()
  command(['xcrun','simctl','install',device,str(fixture)],60)
  installed=command(['xcrun','simctl','get_app_container',device,FIXTURE_BUNDLE,'app'],60).decode().strip()
  installed_info=plistlib.loads((Path(installed)/'Info.plist').read_bytes())
  c.require(installed_info.get('CFBundleIdentifier')==FIXTURE_BUNDLE and (Path(installed)/executable).read_bytes()==binary,'Installed fixture identity differs')
  overlay.apply(app,state,source_map=baseline)
  state_data=c.load(state);probe_record['probeSourceFiles']=state_data['overlayFiles']
  generator=Path(os.environ['RUNNER_TEMP'])/'xcodegen-experimental/xcodegen/bin/xcodegen'
  command([str(generator),'generate'],120,'probe-project.log')
  package_lock=app/'FlashNest.xcodeproj/project.xcworkspace/xcshareddata/swiftpm/Package.resolved'
  package_lock.parent.mkdir(parents=True,exist_ok=True);package_lock.write_bytes((app/'Package.resolved').read_bytes())
  c.require(sha(package_lock.read_bytes())==baseline['Package.resolved'],'Generated project package lock differs')
  ui=lane('ui','FlashNestUI','FlashNestUITests',UI,420,BUDGETS['uiCommandSeconds'])
  probe_record['observedUIAssertionsPassed']=True
  probe_record['unit']=unit;probe_record['ui']=ui

 finally:
  restore_error=None
  try:
   if state.exists():overlay.restore(app,state)
   c.verify_sources(app,baseline)
   probe_record['restoredOriginalSource']=True
   probe_record['restoredSourceFiles']={p:sha((app/p).read_bytes()) for p in baseline}
  except Exception as error:
   restore_error=error;probe_record['restoreErrorType']=type(error).__name__
  finally:
   probe_record.update(runID=int(run_id),head=head,originalRuntimeUnchanged=probe_record['restoredOriginalSource'],generatedProjectRestored=False,fullGatePassed=False,physicalDeviceCertified=False)
   (out/'diagnostic-receipt.json').write_text(json.dumps(probe_record,indent=2)+'\n')
  if device:
   for action in ('shutdown','delete'):
    try:subprocess.run(['xcrun','simctl',action,device],timeout=60,check=False)
    except (subprocess.TimeoutExpired,OSError):pass
  if restore_error:raise restore_error

if __name__=='__main__':
 if sys.argv[1:] == ['preflight']:preflight(True);print('Diagnostic-only source closure verified; no Release build')
 else:run(*sys.argv[1:])

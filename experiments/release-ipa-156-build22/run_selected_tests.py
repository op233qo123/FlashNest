#!/usr/bin/env python3
"""Bounded existing native regression subset. No full-suite or physical-device certification."""
import hashlib,json,os,plistlib,re,subprocess,sys,time
from pathlib import Path
import package_checks as c

UNIT = (
 ('LoadingPhaseDiagnosticsTests','testClientOnlyAcceptsBoundedScalarsAndCurrentSession'),
 ('LoadingPhaseDiagnosticsTests','testCapStillAllowsTerminationAndRejectsLaterEvents'),
 ('LoadingPhaseDiagnosticsTests','testAtomicRoundtripTwoSessionsAndClear'),
 ('LoadingPhaseDiagnosticsTests','testEncodedMetadataNeverContainsUntrustedExtraValues'),
 ('LoadingPhaseDiagnosticsTests','testOversizedMalformedAndSymlinkFilesRejected'),
 ('LoadingPhaseDiagnosticsTests','testPreferenceDefaultsOff'),
 ('LoopbackLoadPhaseTests','testGETRangeAndHEADHaveExactBytesAndOneTerminalEach'),
 ('LoopbackLoadPhaseTests','testDefaultOffAddsNoHeaderAndNoEvents'),
 ('LoopbackLoadPhaseTests','testStopDuringPreparedResponseHasOneStoppedTerminal'),
 ('RuffleRuntimeTests','testFolderImportExecutesSecondaryMovieInWebKit'),
 ('RuffleRuntimeTests','testZIPImportExecutesSecondaryMovieInWebKit'),
 ('SharedObjectPersistenceTests','testDestroyFlushPersistsAndRestartReadsActualSharedObject'),
 ('SharedObjectPersistenceTests','testExplicitSaveAndRestartUsesNewPageAndPreservesSaveAndGameFiles'),
 ('SharedObjectPersistenceTests','testExportImportMapsToSelectedNewPackageAndDoesNotLeakToAnotherGame'),
 ('SharedObjectPersistenceTests','testUpgradePreservesExistingWebKitSaveBeforeFirstNativeArchive'),
)
UI=(('LifecyclePlayerUITests','testBackgroundDirectSaveCancelManagementAndRestartSameGame'),)
RUNTIME='18.2'
FIXTURE_BUNDLE='com.flashnest.fixture-source'
BUDGETS={'overallSeconds':3600,'unitCommandSeconds':1800,'fixtureBuildSeconds':600,'uiCommandSeconds':900,
         'unitMethodSeconds':120,'uiMethodSeconds':420,'cleanupAdditionalSeconds':120}

def sha(data):return hashlib.sha256(data).hexdigest()
def selectors(bundle,expected):return ['-only-testing:'+bundle+'/'+cls+'/'+method for cls,method in expected]
def verify(summary,log,expected,bundle,device):
 c.require(summary.get('result')=='Passed','Selected tests did not pass: '+bundle)
 for key,value in {'totalTestCount':len(expected),'passedTests':len(expected),'failedTests':0,'skippedTests':0,'expectedFailures':0}.items():
  c.require(type(summary.get(key)) is int and summary[key]==value,'Wrong selected count: '+bundle+'/'+key)
 actual=re.findall(r"Test Case '-\["+re.escape(bundle)+r"\.([A-Za-z0-9_]+) ([A-Za-z0-9_]+)\]' passed",log)
 all_passes=re.findall(r"Test Case '-\[([A-Za-z0-9_]+)\.([A-Za-z0-9_]+) ([A-Za-z0-9_]+)\]' passed",log)
 c.require(len(all_passes)==len(actual) and all(row[0]==bundle for row in all_passes),'Foreign test bundle in selected log')
 c.require(len(actual)==len(expected) and set(actual)==set(expected),'Missing/duplicate/unexpected selected method: '+bundle)
 ds=summary.get('devicesAndConfigurations',[])
 c.require(len(ds)==1,'Wrong test configuration count')
 d=ds[0].get('device',{})
 c.require(d.get('osVersion')==RUNTIME and d.get('deviceId')==device and d.get('platform')=='iOS Simulator' and d.get('architecture')=='arm64','Wrong selected simulator identity')
 for key,value in {'passedTests':len(expected),'failedTests':0,'skippedTests':0,'expectedFailures':0}.items():
  c.require(type(ds[0].get(key)) is int and ds[0][key]==value,'Wrong per-device selected count: '+key)
 return {'bundle':bundle,'expected':['/'.join((bundle,cls,method)) for cls,method in expected],
         'actual':['/'.join((bundle,cls,method)) for cls,method in actual],
         'passed':len(expected),'failed':0,'skipped':0,'expectedFailures':0,'logSHA256':sha(log.encode())}

def source_inventory(app):
 result={}
 for directory,expected in [('Tests',UNIT),('UITests',UI)]:
  for cls in sorted({cls for cls,_ in expected}):
   p=app/directory/(cls+'.swift');raw=p.read_bytes();text=raw.decode()
   c.require(re.search(r'\bclass\s+'+re.escape(cls)+r'\s*:',text) is not None,'Selected class absent: '+cls)
   methods=re.findall(r'\bfunc (test[A-Za-z0-9_]+)\(',text)
   for _,method in [row for row in expected if row[0]==cls]:c.require(methods.count(method)==1,'Selected method absent/duplicate: '+cls+'/'+method)
   result[directory+'/'+p.name]={'sha256':sha(raw),'bytes':len(raw)}
 for name in ('project.yml','runtime.lock.json','runtime.files.json'):
  raw=(app/name).read_bytes();result[name]={'sha256':sha(raw),'bytes':len(raw)}
 c.require(len(UNIT)==15 and len(set(UNIT))==15 and len(UI)==1,'Selected inventory changed')
 return result

def run(app,out):
 app=Path(app).resolve();out=Path(out).resolve();out.mkdir(exist_ok=False)
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
  ui=lane('ui','FlashNestUI','FlashNestUITests',UI,420,BUDGETS['uiCommandSeconds'])
  c.require(source_inventory(app)==inventory,'Selected source changed during testing')
  receipt={'schema':'flashnest-selected-native-regression-v1','selectedNativeRegressionPassed':True,'selectedReleaseGatePassed':True,'runID':int(run_id),'head':head,
           'expected':unit['expected']+ui['expected'],'actual':unit['actual']+ui['actual'],'totalTestCount':16,
           'passedTests':16,'failedTests':0,'skippedTests':0,'expectedFailures':0,'unit':unit,'ui':ui,'sourceInventory':inventory,
           'fixtureSourceInstalled':{'bundleID':FIXTURE_BUNDLE,'executableSHA256':sha(binary)},'budgets':BUDGETS,
           'fullGatePassed':False,'physicalDeviceCertified':False,'nativePixelAcceptance':False,'samplingBackingPixelAcceptance':False,
           'scope':'Selected public synthetic save/import/lifecycle tests only; no app-process-relaunch or full-matrix certification.'}
  (out/'verification.json').write_text(json.dumps(receipt,indent=2)+'\n')
 finally:
  if device:
   for action in ('shutdown','delete'):
    try:subprocess.run(['xcrun','simctl',action,device],timeout=60,check=False)
    except (subprocess.TimeoutExpired,OSError):pass
if __name__=='__main__':run(*sys.argv[1:])

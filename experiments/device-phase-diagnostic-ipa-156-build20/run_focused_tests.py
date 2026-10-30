#!/usr/bin/env python3
"""Bounded simulator tests for diagnostic metadata/loopback only, not game acceptance."""
import json,re,subprocess,sys
from pathlib import Path
import package_checks as c
CLASSES=('LoadingPhaseDiagnosticsTests','LoopbackLoadPhaseTests')
def verify(summary,log,expected):
 c.require(summary.get('result')=='Passed','Focused tests did not pass')
 for key,value in {'totalTestCount':len(expected),'passedTests':len(expected),'failedTests':0,'skippedTests':0,'expectedFailures':0}.items():c.require(summary.get(key)==value,'Wrong focused count: '+key)
 actual=re.findall(r"Test Case '-\[FlashNestTests\.([A-Za-z0-9_]+) ([A-Za-z0-9_]+)\]' passed",log)
 c.require(len(actual)==len(expected) and set(actual)==set(expected),'Missing/duplicate/unexpected focused test method')
 ds=summary.get('devicesAndConfigurations',[]);c.require(len(ds)==1 and ds[0].get('device',{}).get('osVersion')=='18.2','Wrong simulator runtime')
def run(app,out):
 app=Path(app).resolve();out=Path(out).resolve();out.mkdir(exist_ok=False)
 expected=[]
 for cls in CLASSES:
  raw=(app/'Tests'/f'{cls}.swift').read_text();expected += [(cls,m) for m in re.findall(r'\bfunc (test[A-Za-z0-9_]+)\(',raw)]
 c.require(len(expected)==9 and len(expected)==len(set(expected)),'Focused test inventory absent/duplicate')
 device=None
 try:
  device=subprocess.check_output(['xcrun','simctl','create','FlashNestLoadingPhaseDiagnostic','com.apple.CoreSimulator.SimDeviceType.iPhone-SE-3rd-generation','com.apple.CoreSimulator.SimRuntime.iOS-18-2'],text=True,timeout=60).strip()
  subprocess.run(['xcrun','simctl','boot',device],check=True,timeout=60)
  subprocess.run(['xcrun','simctl','bootstatus',device,'-b'],check=True,timeout=180)
  result=out/'focused.xcresult'
  args=['xcodebuild','test','-project','FlashNest.xcodeproj','-scheme','FlashNest','-configuration','Debug','-sdk','iphonesimulator','-destination','platform=iOS Simulator,id='+device,'-derivedDataPath',str(out/'build'),'-resultBundlePath',str(result),'-disableAutomaticPackageResolution','-parallel-testing-enabled','NO','-maximum-concurrent-test-simulator-destinations','1','-test-timeouts-enabled','YES','-default-test-execution-time-allowance','30','-maximum-test-execution-time-allowance','30']+['-only-testing:FlashNestTests/'+s for s in CLASSES]+['CODE_SIGNING_ALLOWED=NO','CODE_SIGNING_REQUIRED=NO']
  with (out/'focused.log').open('w') as log:r=subprocess.run(args,cwd=app,stdout=log,stderr=subprocess.STDOUT,timeout=1200)
  raw=subprocess.check_output(['xcrun','xcresulttool','get','test-results','summary','--path',str(result)],timeout=60)
  (out/'summary.json').write_bytes(raw);c.require(r.returncode==0,'Focused xcodebuild failed')
  verify(json.loads(raw),(out/'focused.log').read_text(),expected)
  (out/'verification.json').write_text(json.dumps({'diagnosticTestsPassed':True,'expected':expected,'fullGatePassed':False,'physicalDeviceCertified':False},indent=2)+'\n')
 finally:
  if device:
   subprocess.run(['xcrun','simctl','shutdown',device],timeout=60,check=False)
   subprocess.run(['xcrun','simctl','delete',device],timeout=60,check=False)
if __name__=='__main__':run(*sys.argv[1:])

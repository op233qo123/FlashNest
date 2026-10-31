#!/usr/bin/env python3
"""Focused build23 simulator acceptance; exact selected methods, no full-game claim."""
import json,re,subprocess,sys,os
from pathlib import Path
import package as p

def run(app,out):
 app=Path(app).resolve();out=Path(out).resolve();out.mkdir(exist_ok=False)
 x=p.config();staged=p.load(out.parent/'staging.json');expected=[]
 for cls in x['testClasses']:
  raw=(app/'Tests'/f'{cls}.swift').read_text();expected += [(cls,m)for m in re.findall(r'\bfunc (test[A-Za-z0-9_]+)\(',raw)]
 p.need(expected and len(expected)==len(set(expected)) and expected==[tuple(i)for i in x['expectedNativeTests']],'Selected tests differ from reviewed inventory')
 release,_,_,_=p.load_release(Path(os.environ['RECIPE_CHECKOUT']).resolve(),x)
 release.c.verify_sources(app,staged['diagnosticSourceFiles'])
 device=None
 try:
  device=subprocess.check_output(['xcrun','simctl','create','FlashNestLongRunDiagnostic','com.apple.CoreSimulator.SimDeviceType.iPhone-SE-3rd-generation','com.apple.CoreSimulator.SimRuntime.iOS-18-2'],text=True,timeout=60).strip()
  subprocess.run(['xcrun','simctl','boot',device],check=True,timeout=60);subprocess.run(['xcrun','simctl','bootstatus',device,'-b'],check=True,timeout=180)
  result=out/'focused.xcresult'
  args=['xcodebuild','test','-project','FlashNest.xcodeproj','-scheme','FlashNest','-configuration','Debug','-sdk','iphonesimulator','-destination','platform=iOS Simulator,id='+device,'-derivedDataPath',str(out/'build'),'-resultBundlePath',str(result),'-disableAutomaticPackageResolution','-parallel-testing-enabled','NO','-maximum-concurrent-test-simulator-destinations','1','-test-timeouts-enabled','YES','-default-test-execution-time-allowance','180','-maximum-test-execution-time-allowance','180']+['-only-testing:FlashNestTests/'+s for s in x['testClasses']]+['CODE_SIGNING_ALLOWED=NO','CODE_SIGNING_REQUIRED=NO']
  with (out/'focused.log').open('w')as log:r=subprocess.run(args,cwd=app,stdout=log,stderr=subprocess.STDOUT,timeout=1800)
  raw=subprocess.check_output(['xcrun','xcresulttool','get','test-results','summary','--path',str(result)],timeout=60);(out/'summary.json').write_bytes(raw)
  summary=json.loads(raw);p.need(r.returncode==0 and summary.get('result')=='Passed','Focused simulator tests failed')
  for k,v in {'totalTestCount':len(expected),'passedTests':len(expected),'failedTests':0,'skippedTests':0,'expectedFailures':0}.items():p.need(summary.get(k)==v,'Unexpected test count '+k)
  actual=re.findall(r"Test Case '-\[FlashNestTests\.([A-Za-z0-9_]+) ([A-Za-z0-9_]+)\]' passed",(out/'focused.log').read_text())
  p.need(len(actual)==len(expected)and set(actual)==set(expected),'Missing/extra test method')
  ds=summary.get('devicesAndConfigurations',[]);p.need(len(ds)==1 and ds[0].get('device',{}).get('osVersion')=='18.2','Wrong simulator runtime')
  release.c.verify_sources(app,staged['diagnosticSourceFiles'])
  p.dump(out/'verification.json',{'diagnosticTestsPassed':True,'expected':[list(i)for i in expected],'counts':{k:summary[k]for k in ['totalTestCount','passedTests','failedTests','skippedTests','expectedFailures']},'sourceFiles':staged['diagnosticSourceFiles'],'fullGatePassed':False,'physicalDeviceCertified':False,'runID':os.environ.get('GITHUB_RUN_ID'),'head':os.environ.get('GITHUB_SHA')})
 finally:
  if device:
   subprocess.run(['xcrun','simctl','shutdown',device],timeout=60,check=False);subprocess.run(['xcrun','simctl','delete',device],timeout=60,check=False)
if __name__=='__main__':run(*sys.argv[1:])

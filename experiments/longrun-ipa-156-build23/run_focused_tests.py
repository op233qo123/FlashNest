#!/usr/bin/env python3
"""Focused build23 simulator acceptance; exact selected methods, no full-game claim."""
import json,re,subprocess,sys,os,plistlib
from pathlib import Path
import package as p

def swift_test_classes(raw):
 """Extract direct XCTestCase methods, ignoring strings/comments and nested scopes.
 Fail closed for duplicate declarations; no line-based class/file assumption.
 """
 masked=list(raw);i=0;n=len(raw)
 while i<n:
  start=i
  if raw.startswith('//',i):
   j=raw.find('\n',i);i=n if j<0 else j
  elif raw.startswith('/*',i):
   depth=1;i+=2
   while i<n and depth:
    if raw.startswith('/*',i):depth+=1;i+=2
    elif raw.startswith('*/',i):depth-=1;i+=2
    else:i+=1
   p.need(depth==0,'Unclosed Swift comment')
  else:
   marker=re.match(r'(#+)?("""|")',raw[i:])
   if not marker:i+=1;continue
   hashes=marker.group(1) or '';quote=marker.group(2);i+=len(marker.group(0));end=quote+hashes
   while i<n:
    if raw.startswith(end,i):i+=len(end);break
    if raw[i]=='\\' and raw.startswith(hashes,i+1):i+=2+len(hashes)
    else:i+=1
   else:raise ValueError('Unclosed Swift string')
  for k in range(start,i):
   if masked[k]!='\n':masked[k]=' '
 code=''.join(masked);result={}
 for match in re.finditer(r'\bclass\s+([A-Za-z_]\w*)\s*:\s*XCTestCase\b[^\{]*\{',code):
  cls=match.group(1);p.need(cls not in result,'Duplicate XCTest class '+cls)
  start=match.end();depth=1;end=start
  while end<len(code) and depth:
   if code[end]=='{':depth+=1
   elif code[end]=='}':depth-=1
   end+=1
  p.need(depth==0,'Unclosed XCTest class '+cls);methods=[];depth=0;cursor=start
  for token in re.finditer(r'\{|\}|\bfunc\s+(test[A-Za-z0-9_]+)\s*\(',code[start:end-1]):
   if token.group()=='{':depth+=1
   elif token.group()=='}':depth-=1
   elif depth==0:methods.append(token.group(1))
  p.need(len(methods)==len(set(methods)),'Duplicate method in '+cls);result[cls]=methods
 return result

def expected_test_methods(app,x,directory="Tests"):
 mapping=x['testSourceFiles'];p.need(set(mapping)==set(x['testClasses']),'Incomplete explicit class/source mapping')
 parsed={};result=[]
 for cls in x['testClasses']:
  rel=mapping[cls];path=Path(rel)
  p.need(path.parts[0]==directory and path.suffix=='.swift' and not path.is_absolute() and '..' not in path.parts and '\\' not in rel and ':' not in rel,'Unsafe test source')
  if rel not in parsed:parsed[rel]=swift_test_classes((app/path).read_text())
  p.need(cls in parsed[rel] and parsed[rel][cls],'Missing/empty XCTest class '+cls)
  result.extend((cls,m) for m in parsed[rel][cls])
 return result

def install_fixture_source(app,out,device):
 args=['xcodebuild','build','-project','FlashNest.xcodeproj','-scheme','FlashNestFixtureSource','-configuration','Debug','-sdk','iphonesimulator','-destination','platform=iOS Simulator,id='+device,'-derivedDataPath',str(out/'build'),'-disableAutomaticPackageResolution','CODE_SIGNING_ALLOWED=NO','CODE_SIGNING_REQUIRED=NO']
 with (out/'fixture-source-build.log').open('w') as log:subprocess.run(args,cwd=app,stdout=log,stderr=subprocess.STDOUT,timeout=600,check=True)
 fixture=out/'build/Build/Products/Debug-iphonesimulator/FlashNestFixtureSource.app'
 info=plistlib.loads((fixture/'Info.plist').read_bytes());p.need(info.get('CFBundleIdentifier')=='com.flashnest.fixture-source','Wrong fixture source identity')
 executable=info.get('CFBundleExecutable');p.need(isinstance(executable,str) and re.fullmatch(r'[A-Za-z0-9_-]+',executable),'Unsafe fixture executable')
 binary=(fixture/executable).read_bytes()
 subprocess.run(['xcrun','simctl','install',device,str(fixture)],check=True,timeout=60)
 installed=Path(subprocess.check_output(['xcrun','simctl','get_app_container',device,'com.flashnest.fixture-source','app'],text=True,timeout=60).strip())
 actual=plistlib.loads((installed/'Info.plist').read_bytes());p.need(actual.get('CFBundleIdentifier')=='com.flashnest.fixture-source' and (installed/executable).read_bytes()==binary,'Installed fixture mismatch')
 return {'bundleID':'com.flashnest.fixture-source','executableSHA256':p.sha(binary),'installedOnTestDevice':True}

def run_ui_lane(app,out,x,staged,device,release):
 mapping={'testClasses':x['uiTestClasses'],'testSourceFiles':x['uiTestSourceFiles']}
 expected=expected_test_methods(app,mapping,directory='UITests')
 p.need(expected and expected==[tuple(i) for i in x['expectedUITests']],'UI inventory differs')
 release.c.verify_sources(app,staged['diagnosticSourceFiles'])
 fixture=install_fixture_source(app,out,device)
 result=out/'ui.xcresult'
 args=['xcodebuild','test','-project','FlashNest.xcodeproj','-scheme','FlashNestUI','-configuration','Debug','-sdk','iphonesimulator','-destination','platform=iOS Simulator,id='+device,'-derivedDataPath',str(out/'build'),'-resultBundlePath',str(result),'-disableAutomaticPackageResolution','-parallel-testing-enabled','NO','-maximum-concurrent-test-simulator-destinations','1','-test-timeouts-enabled','YES','-default-test-execution-time-allowance','420','-maximum-test-execution-time-allowance','420']
 args += ['-only-testing:FlashNestUITests/'+cls+'/'+method for cls,method in expected]+['CODE_SIGNING_ALLOWED=NO','CODE_SIGNING_REQUIRED=NO']
 with (out/'ui.log').open('w') as log:r=subprocess.run(args,cwd=app,stdout=log,stderr=subprocess.STDOUT,timeout=1500)
 raw=subprocess.check_output(['xcrun','xcresulttool','get','test-results','summary','--path',str(result)],timeout=60);(out/'ui-summary.json').write_bytes(raw)
 summary=json.loads(raw);p.need(r.returncode==0 and summary.get('result')=='Passed','UI confirmation tests failed')
 for k,v in {'totalTestCount':len(expected),'passedTests':len(expected),'failedTests':0,'skippedTests':0,'expectedFailures':0}.items():p.need(type(summary.get(k)) is int and summary[k]==v,'Unexpected UI count '+k)
 log=(out/'ui.log').read_text();actual=re.findall(r"Test Case '-\[([A-Za-z0-9_]+)\.([A-Za-z0-9_]+) ([A-Za-z0-9_]+)\]' passed",log)
 p.need(len(actual)==len(expected) and set(actual)=={('FlashNestUITests',cls,m) for cls,m in expected},'Unexpected/missing UI methods or bundle')
 ds=summary.get('devicesAndConfigurations',[]);p.need(len(ds)==1 and ds[0].get('device',{}).get('osVersion')=='18.2' and ds[0].get('device',{}).get('deviceId')==device,'Wrong UI simulator')
 release.c.verify_sources(app,staged['diagnosticSourceFiles'])
 p.dump(out/'ui-verification.json',{'importConfirmationUIPassed':True,'scope':'Actual Files cross-container synthetic-fixture import and production confirmation UI with DEBUG warning threshold; not real large-file or all-provider acceptance','expected':[list(i) for i in expected],'counts':{k:summary[k] for k in ['totalTestCount','passedTests','failedTests','skippedTests','expectedFailures']},'sourceFiles':staged['diagnosticSourceFiles'],'deviceID':device,'fixtureSourceInstalled':fixture,'fullGatePassed':False,'physicalDeviceCertified':False,'runID':os.environ.get('GITHUB_RUN_ID'),'head':os.environ.get('GITHUB_SHA')})

def run(app,out):
 app=Path(app).resolve();out=Path(out).resolve();out.mkdir(exist_ok=False)
 x=p.config();staged=p.load(out.parent/'staging.json');expected=expected_test_methods(app,x)
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
  run_ui_lane(app,out,x,staged,device,release)
  p.dump(out/'verification.json',{'diagnosticTestsPassed':True,'expected':[list(i)for i in expected],'counts':{k:summary[k]for k in ['totalTestCount','passedTests','failedTests','skippedTests','expectedFailures']},'sourceFiles':staged['diagnosticSourceFiles'],'fullGatePassed':False,'physicalDeviceCertified':False,'runID':os.environ.get('GITHUB_RUN_ID'),'head':os.environ.get('GITHUB_SHA')})
 finally:
  if device:
   subprocess.run(['xcrun','simctl','shutdown',device],timeout=60,check=False);subprocess.run(['xcrun','simctl','delete',device],timeout=60,check=False)
if __name__=='__main__':run(*sys.argv[1:])

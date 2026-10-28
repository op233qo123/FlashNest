#!/usr/bin/env python3
"""Serial, synthetic-only final native regression adapter. No dispatch or IPA."""
import argparse, hashlib, importlib.util, json, os, platform, re, shutil, signal, subprocess, sys, time, zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parent; WORK=ROOT.parent
SAMPLING=WORK/'native-sampling-validation'; SAVE=WORK/'native-save-audio-validation'
ZIP=WORK/'zip-native-validation/payload/experiments/zip-selection'
CAP=128*1024*1024

def require(ok, why):
 if not ok: raise ValueError(why)
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def dump(p,obj):Path(p).parent.mkdir(parents=True,exist_ok=True);Path(p).write_text(json.dumps(obj,indent=2,sort_keys=True)+'\n')
def inventory(root):
 root=Path(root); require(root.is_dir() and not root.is_symlink(),'Regular input directory required')
 out={}
 for p in sorted(root.rglob('*')):
  require(not p.is_symlink(),'Symlink forbidden: '+str(p))
  if p.is_file():out[p.relative_to(root).as_posix()]=sha(p)
  else:require(p.is_dir(),'Nonregular member')
 return out

def load_module(name,path):
 spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m

def methods(source,classes):
 out=[]
 for name in sorted(classes):
  found=[]
  for p in sorted(Path(source).glob('*.swift')):
   s=p.read_text();match=re.search(r'final class '+re.escape(name)+r'\b',s)
   if match:
    tail=s[match.end():]; tail=re.split(r'\n(?:@\w+(?:\([^)]*\))?\s+)*(?:final\s+)?class\s+\w+',tail,1)[0]
    found += re.findall(r'\bfunc (test\w+)\s*\(',tail)
  require(found and len(found)==len(set(found)),'Missing/duplicate class methods: '+name)
  out += ['FlashNestTests/'+name+'/'+m for m in found]
 return out

def lane(name,scheme,selectors,seconds=180):return {'name':name,'scheme':scheme,'selectors':selectors,'expectedCount':len(selectors),'maximumTestExecutionSeconds':seconds}
def selections(app):
 sampling=methods(Path(app)/'Tests',['RenderSamplingSettingsTests','SamplingSessionTests','SamplingAppliedStatusTests','SamplingDocumentBindingTests'])
 require(len(sampling)==18,'Exactly18 sampling/status/session methods required')
 picker=methods(Path(app)/'Tests',['PackageImporterTests','ImportFlowTests','DocumentPickerDelegateTests','ImportAliasTests','LocalImportInboxTests','ExternalImportInboxTests','ExternalImportCopyTests'])
 require(len(picker)==31,'Exactly31 picker model methods required')
 saved=json.loads((SAVE/'test-selection.json').read_text())['lanes']
 base=['FlashNestSamplingUITests/NativeSamplingUITests/'+n for n in ('testShippingAutomaticShowAll','testShippingAutomaticNoScale','testShippingWebGLShowAll','testShippingWebGLNoScale')]
 extra=['FlashNestSamplingUITests/NativeSamplingUITests/'+n for n in ('testDiagnosticLaunchLowWebGLShowAll','testDiagnosticLaunchHighWebGLShowAll','testActualInitialRedirectAndNavigationFailure')]
 return {'sampling-gate-off':lane('sampling-gate-off','FlashNest',sampling),
  'sampling-gate-on':lane('sampling-gate-on','FlashNest',sampling),
  'picker-models':lane('picker-models','FlashNest',picker),
  'picker-ui':lane('picker-ui','FlashNestUI',['FlashNestUITests/ZIPSelectionUITests/testRealFilesCancelZIPSWFRepeatAndWholeFolder'],480),
  'sampling-baseline':lane('sampling-baseline','FlashNestSamplingUI',base,900),
  'sampling-candidate':lane('sampling-candidate','FlashNestSamplingUI',base+extra,900),
  **{x['name']:x for x in saved}}

def gate_on_overlay(app):
 paths=['App/Player/RenderSamplingSettings.swift','Tests/RenderSamplingSettingsTests.swift']
 before={p:sha(Path(app)/p) for p in paths}
 replacements=[('static let runtimeValidated = false','static let runtimeValidated = true'),
 ('XCTAssertFalse(RenderSamplingSettings.runtimeValidated, "Do not enable an unvalidated runtime")',
  'XCTAssertTrue(RenderSamplingSettings.runtimeValidated, "Validated simulator regression copy must activate sampling")')]
 for p,(old,new) in zip(paths,replacements):
  f=Path(app)/p;s=f.read_text();require(s.count(old)==1,'Exact gate/test anchor drift');f.write_text(s.replace(old,new))
 return {p:{'before':before[p],'after':sha(Path(app)/p)} for p in paths}

class Runner:
 def __init__(self,args):
  self.args=args;self.binding=json.loads(args.binding.read_text());self.out=args.output.resolve();self.stage=self.out.parent/(self.out.name+'-staging')
  require(not self.out.exists() and not self.stage.exists(),'Fresh output/staging required; inspect uncertain previous runs')
  self.out.mkdir(parents=True);self.stage.mkdir();self.results=[];self.verifier=load_module('save_verify',SAVE/'scripts/verify_results.py')
 def budget(self):
  n=sum(p.stat().st_size for p in self.out.rglob('*') if p.is_file());require(n<=CAP,'Evidence budget exceeded; no truncation or partial pass')
 def command(self,argv,name,cwd=None,timeout=1200,allowed=(0,)):
  log=self.out/(name+'.log');start=time.monotonic()
  with log.open('xb') as f:
   proc=subprocess.Popen([str(x) for x in argv],cwd=cwd,stdout=f,stderr=subprocess.STDOUT,start_new_session=True,env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1'})
   try:
    while proc.poll() is None:
     require(time.monotonic()-start <= timeout, 'Bounded command timed out: '+name)
     require(log.stat().st_size <= 16*1024*1024, 'Full log exceeded16MiB; failed, never truncated: '+name)
     self.budget();time.sleep(.5)
    code=proc.returncode
   except BaseException:
    os.killpg(proc.pid,signal.SIGKILL);proc.wait();raise
  self.budget();require(code in allowed,'Command failed '+name+' exit='+str(code));return log
 def capture(self,argv,name,cwd=None,timeout=120):return self.command(argv,name,cwd,timeout).read_text()
 def preflight(self):
  b=self.binding;require(b.get('ready') is True,'Review/freeze binding before execution')
  require(platform.system()=='Darwin','Actual macOS Xcode runner required')
  require(os.environ.get('DEVELOPER_DIR')=='/Applications/Xcode_16.2.app/Contents/Developer','Exact Xcode directory required')
  require('Xcode 16.2\n' in self.capture(['xcodebuild','-version'],'xcode-version'),'Exact Xcode16.2 required')
  require(inventory(self.args.app)==b['appFiles'],'Frozen final App file map differs')
  require(sha(ROOT/'helper-lock.json')==b['helperLockSHA256'],'Reviewed helper lock differs')
  helpers=json.loads((ROOT/'helper-lock.json').read_text())['files'];require(helpers,'Empty helper lock')
  for rel,h in helpers.items():require(sha(WORK/rel)==h,'Frozen helper differs: '+rel)
  require(sha(self.args.candidate_engine/'provenance.json')==b['engine']['provenanceSHA256'],'Engine provenance differs')
  full=self.args.candidate_engine/'runtime-files.json';require(sha(full)==b['engine']['runtimeInventorySHA256'],'Engine inventory differs')
  self.candidate_map=json.loads(full.read_text());self.check_runtime(self.args.candidate_engine/'runtime',self.candidate_map)
  self.check_runtime(self.args.app/'App/Resources/Web/runtime',self.candidate_map)
  require(len([p for p in self.candidate_map if p.endswith('.wasm')])==2,'Dual release runtime required')
  baseline=self.args.baseline/'sampling';historical=self.args.baseline/'historical'
  require(sha(baseline/'runtime.files.json')=='25d4453b0375349e55b9f63f609bd129d6a3549e1da792e811f0e5d121247e90','Delivered155 sampling baseline required')
  self.sampling_map=json.loads((baseline/'runtime.files.json').read_text());require(inventory(baseline/'runtime')==self.sampling_map,'Sampling baseline bytes differ')
  self.historical_map=json.loads((SAVE/'diagnostics/baseline-runtime-identity.json').read_text())['runtimeFiles']
  self.check_runtime(historical/'runtime',self.historical_map)
  require(json.loads((historical/'runtime-files.json').read_text())==self.historical_map,'Historical audio inventory differs')
  runtime_json=json.loads(self.capture(['xcrun','simctl','list','devices','available','--json'],'available-devices'))
  devices=runtime_json['devices'].get('com.apple.CoreSimulator.SimRuntime.iOS-18-2',[])
  wanted=b['simulatorNames'];require(set(wanted)=={'2','3'},'Exactly DPR2/3 model selections required')
  self.devices={}
  for dpr,name in wanted.items():
   candidates=[d for d in devices if d['name']==name and d.get('isAvailable') is True]
   require(len(candidates)==1,'Exact installed18.2 simulator missing/ambiguous: '+name);self.devices[dpr]=candidates[0]['udid']
  require(len(set(self.devices.values()))==2,'Two separate models required; native observed DPR still mandatory')
  expected_archive='a760b4bf97460341316a2c00d8c87b2946c6c2729eb57e9a72abb3ef7bc0ef82'
  archive=Path(b['xcodegenArchivePath']).resolve();require(sha(archive)==b['xcodegenArchiveSHA256']==expected_archive,'Pinned official XcodeGen archive differs')
  self.xcodegen=Path(b['xcodegenExecutable']).resolve()
  with zipfile.ZipFile(archive) as z:
   member='xcodegen/bin/xcodegen';require(z.namelist().count(member)==1,'Canonical executable archive entry missing/duplicate')
   binary_hash=hashlib.sha256(z.read(member)).hexdigest()
  require(sha(self.xcodegen)==binary_hash,'Installed XcodeGen differs from exact authenticated archive member')
  if b.get('xcodegenExecutableSHA256'):require(binary_hash==b['xcodegenExecutableSHA256'],'Independently pinned executable differs')
  require('2.42.0' in self.capture([self.xcodegen,'--version'],'xcodegen-version'),'XcodeGen2.42 required')
  dump(self.out/'tool-receipt.json',{'archiveSHA256':expected_archive,'archiveMember':member,'executableSHA256':binary_hash,'version':'2.42.0'})
  dump(self.out/'binding.json',b);self.lanes=selections(self.args.app);dump(self.out/'test-selection.json',self.lanes)
 def check_runtime(self,root,declared):
  require(inventory(root)=={p:r['sha256'] for p,r in declared.items()},'Runtime map differs')
  require(all((root/p).stat().st_size==r['bytes'] for p,r in declared.items()),'Runtime size differs')
 def metadata_overlay(self,app,source,mapping):
  allowed={'App/Resources/Web/runtime-identity.json','App/Resources/Web/Ruffle-MODIFICATIONS.md','App/Resources/Web/Ruffle-THIRD-PARTY-LICENSES.md','App/Resources/Web/THIRD_PARTY_NOTICES.md','App/Resources/Web/licenses.manifest.json'}
  require(set(mapping)==allowed,'All five explicitly reviewed per-arm metadata files required')
  for rel,row in mapping.items():
   p=source/rel;require(p.is_file() and not p.is_symlink() and sha(p)==row['sha256'] and p.stat().st_size==row['bytes'],'Metadata bytes differ')
   shutil.copyfile(p,app/rel)
 def copy_app(self,name,runtime=None,string_map=None):
  p=self.stage/name;shutil.copytree(self.args.app,p)
  if runtime is not None:
   dest=p/'App/Resources/Web/runtime';shutil.rmtree(dest);shutil.copytree(runtime,dest)
   (p/'runtime.files.json').write_text(json.dumps(string_map,indent=2,sort_keys=True)+'\n')
  return p
 def project(self,app,name,scheme='FlashNest'):
  self.command([self.xcodegen,'generate'],name+'-xcodegen',app,120)
  target=app/(('LateAudioDiagnostic' if scheme=='LateAudioDiagnostic' else 'FlashNest')+'.xcodeproj')
  pin=target/'project.xcworkspace/xcshareddata/swiftpm/Package.resolved';pin.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(app/'Package.resolved',pin)
  self.command(['xcodebuild','-resolvePackageDependencies','-project',target.name,'-scheme',scheme,'-disableAutomaticPackageResolution'],name+'-resolve',app,300)
  return target.name
 def reset(self,device,name):
  # Only exact installed hosted simulator IDs checked in preflight. Never user device.
  states=json.loads(self.capture(['xcrun','simctl','list','devices','available','--json'],name+'-device-state'))
  matches=[d for d in states['devices'].get('com.apple.CoreSimulator.SimRuntime.iOS-18-2',[]) if d['udid']==device]
  require(len(matches)==1,'Simulator identity disappeared')
  if matches[0]['state']=='Booted':self.command(['xcrun','simctl','shutdown',device],name+'-shutdown')
  else:require(matches[0]['state']=='Shutdown','Simulator is not in a stable shutdown/booted state')
  self.command(['xcrun','simctl','erase',device],name+'-erase')
  self.command(['xcrun','simctl','bootstatus',device,'-b'],name+'-boot',timeout=120)
 def test(self,app,project,device,key,name=None):
  cfg=self.lanes[key];name=name or key;result=self.stage/(name+'.xcresult');seconds=cfg['maximumTestExecutionSeconds']
  argv=['xcodebuild','test','-project',project,'-scheme',cfg['scheme'],'-configuration','Debug','-sdk','iphonesimulator','-destination','platform=iOS Simulator,id='+device,'-derivedDataPath',str(app/'build'),'-resultBundlePath',str(result),'-disableAutomaticPackageResolution','-parallel-testing-enabled','NO','-maximum-concurrent-test-simulator-destinations','1','-test-timeouts-enabled','YES','-default-test-execution-time-allowance',str(seconds),'-maximum-test-execution-time-allowance',str(seconds)]
  argv += ['-only-testing:'+s for s in cfg['selectors']]+['CODE_SIGNING_ALLOWED=NO','CODE_SIGNING_REQUIRED=NO']
  error=None
  try:log=self.command(argv,name,app,timeout=min(2400,seconds*cfg['expectedCount']+300))
  except Exception as e:error=e;log=self.out/(name+'.log')
  if result.exists():
   summary=json.loads(self.capture(['xcrun','xcresulttool','get','test-results','summary','--path',result],name+'-summary'))
   dump(self.out/(name+'-summary.json'),summary)
   export=self.stage/(name+'-attachments')
   self.command(['xcrun','xcresulttool','export','attachments','--path',result,'--output-path',export],name+'-export',timeout=180)
   for p in sorted(export.rglob('*')):
    require(not p.is_symlink(),'Linked attachment rejected')
    if p.is_file() and p.suffix.lower() in ('.png','.jpg','.jpeg','.txt','.json'):
     require(p.stat().st_size<=8*1024*1024,'Oversized attachment rejected, not truncated')
     dest=self.out/'attachments'/name/p.relative_to(export);dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,dest);self.budget()
   if error is None:
    report=self.verifier.verify(summary,log.read_text(),cfg)
    if key.startswith('audio-'):report['audio']=self.verifier.verify_audio_records(log.read_text(),cfg)
    report['runName']=name;self.results.append(report);dump(self.out/(name+'-verification.json'),report)
  require(result.exists(), 'xcodebuild produced no xcresult: '+name)
  if error:raise error
 def install_source(self,app,project,device,name):
  self.command(['xcodebuild','-project',project,'-scheme','FlashNestFixtureSource','-configuration','Debug','-sdk','iphonesimulator','-destination','platform=iOS Simulator,id='+device,'-derivedDataPath',str(app/'build-source'),'-disableAutomaticPackageResolution','CODE_SIGNING_ALLOWED=NO','CODE_SIGNING_REQUIRED=NO','build'],name+'-source-build',app,600)
  self.command(['xcrun','simctl','install',device,app/'build-source/Build/Products/Debug-iphonesimulator/FlashNestFixtureSource.app'],name+'-source-install')
 def execute(self):
  self.preflight();b=self.binding;device=self.devices['3'];self.reset(device,'main-gate-off')
  main=self.copy_app('main-gate-off');project=self.project(main,'main-gate-off')
  self.test(main,project,device,'sampling-gate-off')
  # Same approved App source, two exact runtime baselines and isolated sampling hooks.
  identities={};sampling_apps={};candidate_string={p:r['sha256'] for p,r in self.candidate_map.items()}
  for arm in ('baseline','candidate'):
   runtime=self.args.baseline/'sampling/runtime' if arm=='baseline' else self.args.candidate_engine/'runtime'
   mapping=self.sampling_map if arm=='baseline' else candidate_string
   app=self.copy_app('sampling-'+arm,runtime,mapping)
   if arm=='baseline':shutil.copyfile(self.args.baseline/'sampling/runtime.files.json',app/'runtime.files.json')
   dump(app/'NATIVE_VALIDATION_COPY.json',{'disposable':True,'sdk':'iphonesimulator'})
   repin=b['samplingAppManifests'][arm]; repin_path=(self.args.binding.parent/repin['path']).resolve();require(sha(repin_path)==repin['sha256'],'Per-arm App manifest differs')
   if arm=='baseline': self.metadata_overlay(app,self.args.baseline/'sampling/app-metadata',b['samplingBaselineMetadata'])
   invhash=sha(app/'runtime.files.json');proof={'frozen':True,'releaseEquivalent':True,'runtimeInventorySHA256':invhash,'approvedAppManifestSHA256':repin['sha256']}
   dump(self.stage/'sampling-candidate-freeze.json',proof)
   args=[sys.executable,SAMPLING/'scripts/prepare_overlay.py','--app',app,'--arm',arm,'--runtime-inventory-sha256',invhash,'--approved-app-manifest',repin_path,'--approved-app-manifest-sha256',repin['sha256']]
   if arm=='candidate':args+=['--candidate-freeze',self.stage/'sampling-candidate-freeze.json']
   self.command(args,'sampling-'+arm+'-stage',timeout=120)
   identities[arm]=json.loads((app/'NativeSamplingValidation/SamplingIdentity.json').read_text())
   shutil.copyfile(app/'NativeSamplingValidation/staging-provenance.json',self.out/('sampling-'+arm+'-staging-provenance.json'))
   sampling_apps[arm]=(app,self.project(app,'sampling-'+arm,'FlashNestSamplingUI'))
  # Frozen externally from source staging BEFORE any sampling launch, never inferred from results.
  dump(self.out/'sampling-expected-identities.json',identities)
  for dpr,device in self.devices.items():
   for arm,(app,project) in sampling_apps.items():
    name='sampling-'+arm+'-dpr'+dpr;self.reset(device,name)
    self.test(app,project,device,'sampling-'+arm,name)
  self.command([sys.executable,SAMPLING/'scripts/verify_results.py','--attachments',self.out/'attachments','--candidate-inventory-sha256',identities['candidate']['runtimeInventorySHA256'],'--baseline-inventory-sha256',identities['baseline']['runtimeInventorySHA256'],'--expected-identities',self.out/'sampling-expected-identities.json','--output',self.out/'sampling-geometry.json'],'sampling-geometry-verifier',timeout=180)
  geometry=json.loads((self.out/'sampling-geometry.json').read_text());require(geometry['matrixPassed'] is True and geometry['shippingReductionRequirementMet'] is True,'Native geometry not accepted; do not run gate-on copy')
  # No shipping mutation: new main copy, only gate and exact hardcoded test expectation change.
  main=self.copy_app('main-gate-on');overlay=gate_on_overlay(main);dump(self.out/'gate-on-overlay.json',overlay)
  shutil.copyfile(SAVE/'Tests/NativeSaveSettingsPreservationTests.swift',main/'Tests/NativeSaveSettingsPreservationTests.swift')
  device=self.devices['3'];self.reset(device,'main-gate-on');project=self.project(main,'main-gate-on')
  for key in ('sampling-gate-on','save-models','save-webkit','picker-models'):self.test(main,project,device,key)
  # Fresh application data before each real Files-based scenario.
  picker=self.copy_app('picker-gate-on');dump(self.out/'picker-gate-on-overlay.json',gate_on_overlay(picker))
  for source,dest in [('FixtureSourceApp.swift','UITestSupport/FixtureSource/FixtureSourceApp.swift'),('ZIPSelectionUITests.swift','UITests/ZIPSelectionUITests.swift')]:shutil.copyfile(ZIP/'overlay'/source,picker/dest)
  picker_project=self.project(picker,'picker-gate-on')
  self.reset(device,'picker-ui');self.install_source(picker,picker_project,device,'picker-ui');self.test(picker,picker_project,device,'picker-ui')
  self.command([sys.executable,ZIP/'verify_containers.py',device,self.out/'picker-copy-verification.json'],'picker-private-copy-verifier')
  self.reset(device,'save-ui');self.install_source(main,project,device,'save-ui');self.test(main,project,device,'save-ui')
  # Audio uses the unmodified gate-off App, exact candidate or historical runtime.
  for role,key in [('candidate-composite','audio-candidate'),('baseline-historical','audio-baseline')]:
   runtime=self.args.candidate_engine if key=='audio-candidate' else self.args.baseline/'historical'
   full=runtime/'runtime-files.json';app=self.stage/key
   audio_source=self.args.app
   if key=='audio-baseline':
    audio_source=self.copy_app('audio-historical-source')
    self.metadata_overlay(audio_source,self.args.baseline/'historical/app-metadata',b['audioFinalMetadata'][role])
   metadata=self.stage/(key+'-metadata.json');dump(metadata,b['audioFinalMetadata'][role])
   self.command([sys.executable,SAVE/'scripts/stage_audio_target.py','stage','--source',audio_source,'--runtime',runtime/'runtime','--runtime-inventory',full,'--runtime-inventory-sha256',sha(full),'--role',role,'--output',app,'--final-metadata',metadata],key+'-stage',timeout=120)
   self.reset(device,key);project=self.project(app,key,'LateAudioDiagnostic');self.test(app,project,device,key)
   shutil.copyfile(app/'source-manifest.json',self.out/(key+'-source-manifest.json'))
  require(inventory(self.args.app)==b['appFiles'],'Immutable final App input changed during tests')
  self.check_runtime(self.args.candidate_engine/'runtime',self.candidate_map)
  observed=geometry['wasmActuallyObserved']['candidate'];require(len(observed)==1,'Native selected multiple/unknown runtime branches')
  require(sum(x['tests'] for x in self.results)==161,'Exact161 native method executions required')
  receipt={'passed':True,'skipped':0,'evidenceKind':'iOS simulator','physicalDeviceCertified':False,'shippingDefaultAppliesAllTiers':'automatic' in geometry['actualShippingReductionPolicies'],
   'shippingReductionRequirementMet':geometry['shippingReductionRequirementMet'],
   'shippingPoliciesWithAllReductions':geometry['actualShippingReductionPolicies'],
   'engineSHA256':b['engine']['sha256'],'selectedWasmSHA256':self.candidate_map[observed[0]]['sha256'],
   'samplingRows':52,'samplingPhases':156,'nativeMethods':sum(x['tests'] for x in self.results),'results':self.results,
   'audibleOutputProven':False,'privateProviderReproduced':False,'ipaBuilt':False}
  dump(self.out/'native-acceptance.json',receipt);self.budget();return receipt

def main():
 p=argparse.ArgumentParser(description=__doc__)
 for k in ('app','candidate-engine','baseline','binding','output'):p.add_argument('--'+k,required=True,type=Path)
 a=p.parse_args();runner=Runner(a)
 try: print(json.dumps(runner.execute()))
 except Exception as e:
  dump(runner.out/'native-failure.json',{'passed':False,'error':str(e),'completedLanes':runner.results,'ipaBuilt':False});raise
if __name__=='__main__':main()

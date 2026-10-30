#!/usr/bin/env python3
"""Exact build20 + verified candidate engine + version22; never full acceptance."""
import argparse,importlib.util,io,json,os,plistlib,shutil,subprocess,sys,tempfile,zipfile
from pathlib import Path
import package_checks as c
import candidate_composite_runtime as consumer
ROOT=Path(__file__).resolve().parent
OWN={'package.py','package_checks.py','candidate_composite_runtime.py','test_candidate_consumer.py','test_package.py','workflow.yml','README.md','run_selected_tests.py'}
def encoded(x):return (json.dumps(x,sort_keys=True,indent=2)+'\n').encode()
def inputs(verify=True,dispatch=False):
 x=c.load(ROOT/'inputs.json')
 c.require(x['kind']=='RELEASE-PACKAGE' and x['releaseChannel']=='release','Wrong release distribution identity')
 c.require(x['schemaVersion']==1 and x['build']=='22' and x['version']=='1.5.6' and x['bundleID']=='com.flashnest.app','Wrong release package identity')
 for k in ('nativeAccepted','fullGatePassed','physicalDeviceCertified','originalCrashResolved','diagnosticOptInDefault'):c.require(x[k] is False,'Unjustified acceptance/default-on '+k)
 c.require(x['experimentalGateOverride'] is True,'Prior experimental sampling setting must remain on')
 c.require(x['candidateEngine']['runID']==40998892881 and x['candidateEngine']['sha256']=='2cb4022b1859156f2e28dcb5d499ebf01cbf13b386acb8467d34c147ed22d28d','Wrong candidate engine')
 c.require(x['browserEvidence']['runID']==41002083024 and x['browserEvidence']['cases']==6 and x['browserEvidence']['sha256']=='59729cc06fa314146a8190c3ab6d396186e00c9bd48f4fbdcc447f898e0ab7aa','Wrong actual focused browser evidence')
 c.require(len(x['baseAppFiles'])==207 and len(x['candidateRuntimeFiles'])==12,'Incomplete baseline/runtime inventory')
 for k in ('baseRecipeFiles','baseAppFiles','candidateRuntimeFiles','candidateAppFiles','recipeFiles'):c.hash_map(x[k])
 c.require(set(x['recipeFiles'])==OWN,'Incomplete recipe closure')
 allowed={'project.yml','App/Info-Debug.plist','App/Resources/Web/runtime-identity.json','runtime.lock.json','runtime.files.json','FINAL_ENGINE_STAGING.json','Tests/FrameOrderRuntimeTests.swift','scripts/composite_runtime.py','App/Resources/Web/Ruffle-MODIFICATIONS.md','App/Resources/Web/licenses.manifest.json','THIRD_PARTY_NOTICES.md','App/Resources/Web/THIRD_PARTY_NOTICES.md','vendor/ruffle-composite-40794075613.zip','vendor/ruffle-composite-40998892881.zip'}
 for path in set(x['baseAppFiles'])|set(x['candidateAppFiles']):
  if not path.startswith('App/Resources/Web/runtime/') and path not in allowed:c.require(x['baseAppFiles'].get(path)==x['candidateAppFiles'].get(path),'Unexpected business/source change: '+path)
 c.require(len(x['candidateAppFiles'])==207,'Candidate App source closure incomplete')
 c.require({p[len('App/Resources/Web/runtime/'):]:h for p,h in x['candidateAppFiles'].items() if p.startswith('App/Resources/Web/runtime/')}==x['candidateRuntimeFiles'],'Candidate App runtime inventory differs')
 c.require(x['baseRecipePath']=='experiments/device-phase-diagnostic-ipa-156-build20' and x['sourceCommit']=='9bc000e37695696f2427b25fe08efe4993bf22e5','Wrong frozen baseline recipe/source')

 if verify:
  for p,h in x['recipeFiles'].items():c.require(c.digest((ROOT/p).read_bytes())==h,'Recipe changed: '+p)
 if dispatch:c.require(x['dispatchAllowed'] is True,'Candidate IPA dispatch disabled pending exact approval')
 return x

def load_base(checkout,x):
 base=checkout/x['baseRecipePath'];c.require(c.file_map(base)==x['baseRecipeFiles'],'Published build20 recipe changed')
 sys.path.insert(0,str(base));spec=importlib.util.spec_from_file_location('frozen_build20_experiment',base/'experiment.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
 old=m.inputs();c.require(old['diagnosticAppFiles']==x['baseAppFiles'],'Build20 source differs');return m,old

def mirror_bytes(checkout,x,engine):
 t=x['baselineEngineMirror'];c.require(t['kind']=='repository-exact-archive-parts' and t['repository']=='op233qo123/FlashNest' and t['sha256']==engine['sha256'] and t['bytes']==engine['bytes'],'Wrong original mirror')
 names=['engine-mirrors/ruffle-composite-40794075613.zip.part1','engine-mirrors/ruffle-composite-40794075613.zip.part2'];c.require([p['path']for p in t['parts']]==names,'Mirror part order/path changed');root=checkout/'experiments/final-composite';data=bytearray()
 for row in t['parts']:
  f=root/row['path'];c.require(not f.is_symlink() and not f.parent.is_symlink() and f.is_file() and f.stat().st_size==row['bytes'] and 0<row['bytes']<8*1024*1024,'Invalid mirror part');b=f.read_bytes();c.require(c.digest(b)==row['sha256'],'Mirror part hash differs');data.extend(b)
 b=bytes(data);c.require(len(b)==engine['bytes'] and c.digest(b)==engine['sha256'],'Original archive reconstruction differs');return b

def checked_zip(raw,maximum=402653184):
 z=zipfile.ZipFile(io.BytesIO(raw));seen=set();c.require(len(z.infolist())<5000 and sum(i.file_size for i in z.infolist())<=maximum,'Archive too large')
 import stat
 for i in z.infolist():
  c.safe(i.filename);c.require(i.filename not in seen and stat.S_IFMT(i.external_attr>>16) in (0,stat.S_IFREG) and i.file_size<=67108864,'Archive duplicate/nonregular/oversized');seen.add(i.filename)
 c.require(z.testzip() is None,'Archive CRC failure');return z

def verify_browser(raw,x,base_runtime):
 pin=x['browserEvidence'];c.require(len(raw)==pin['bytes'] and c.digest(raw)==pin['sha256'],'Browser artifact bytes differ')
 with checked_zip(raw,134217728) as z:
  c.require({n:c.digest(z.read(n))for n in z.namelist()}==pin['files'],'Browser full evidence inventory differs')
  result=c.parse(z.read('browser/result.json'));contract_raw=z.read('focused-browser-contract.json');contract=c.parse(contract_raw)
  c.require(result['passed'] is True and result['contractSHA256']==c.digest(contract_raw),'Browser receipt not successful/bound')
  c.require(contract['runtimes']['candidate']['runID']==x['candidateEngine']['runID'] and contract['runtimes']['candidate']['files']==x['candidateRuntimeFiles'],'Browser tested other candidate')
  c.require(contract['runtimes']['baseline']['files']==base_runtime,'Browser baseline differs')
  fixtures={'neutral-eight-jpeg3.swf':2,'neutral-forward-reference.swf':2,'neutral-shared-boundaries.swf':5};pairs={(r['arm'],r['fixture'])for r in result['rows']};c.require(len(result['rows'])==6 and pairs=={(a,f)for a in ('baseline','candidate')for f in fixtures},'Incomplete six pages')
  for row in result['rows']:
   selected=contract['runtimes'][row['arm']]['selectedWasmSHA256'];c.require(row['wasm'] and all(w['sha256']==selected for w in row['wasm']),'Actual fetched WASM differs')
   c.require(len(row['states'])==fixtures[row['fixture']] and all(s['actualRenderer']=='webgl' and not s['errors'] and not s['overflow'] for s in row['states']),'Invalid WebGL page states')
 return {'verified':True,'reference':pin,'scope':'Pinned actual desktop WebGL six-page evidence only; not native acceptance'}

def rebind(app,raw,x,verify_final=True):
 c.require(c.file_map(app)==x['baseAppFiles'],'Not exact build20 App')
 e=x['candidateEngine'];c.require(len(raw)==e['bytes'] and c.digest(raw)==e['sha256'],'Candidate archive differs')
 with checked_zip(raw) as z:
  prefix=consumer.PREFIX;rraw=z.read(prefix+'provenance.json');receipt=c.parse(rraw);invraw=z.read(prefix+'runtime-files.json');rows=c.parse(invraw)
  c.require(c.digest(rraw)==e['provenanceSHA256'] and c.digest(invraw)==e['runtimeInventorySHA256'] and receipt['run']['GITHUB_SHA']==e['sourceCommit'] and receipt['run']['GITHUB_RUN_ID']==str(e['runID']),'Candidate original receipt differs')
  c.require(receipt['sourceLockSHA256']==e['sourceLockSHA256'] and receipt['sourceSetSHA256']==e['sourceSetSHA256'],'Candidate source differs')
  lock={'schemaVersion':4,'runtimeKind':consumer.KIND,'runtimePrefix':prefix+'runtime/','provenancePath':prefix+'provenance.json','archiveBytes':len(raw),'archivePath':f"vendor/ruffle-composite-{e['runID']}.zip",'sha256':c.digest(raw),'identitySHA256':None,'provenanceSHA256':c.digest(rraw),'sourceLockSHA256':receipt['sourceLockSHA256'],'sourceSetSHA256':receipt['sourceSetSHA256'],'runtimeInventorySHA256':receipt['runtimeInventorySHA256'],'upstreamSourceCommit':receipt['upstreamCommit'],'buildSourceCommit':e['sourceCommit'],'buildRunID':e['runID'],'version':'0.7.1','experimentalVersionName':receipt['versionSeal']['version_name'],'name':'FlashNest modified Ruffle','license':'MIT OR Apache-2.0','status':'experimental-lazy-graphic-candidate-native-acceptance-separate','checksumProvenance':'Exact GitHub Actions artifact bytes, not publisher signature or independent reproducible build'}
  ident={k:lock[k]for k in ('runtimeKind','experimentalVersionName','upstreamSourceCommit','buildSourceCommit','buildRunID','provenanceSHA256','sourceLockSHA256','sourceSetSHA256','runtimeInventorySHA256')};ident.update(schemaVersion=3,artifactArchiveSHA256=lock['sha256'],upstreamBaseVersion='0.7.1',runtimeFiles=rows);identity=encoded(ident);lock['identitySHA256']=c.digest(identity);manifest={k:r['sha256']for k,r in rows.items()};c.require(manifest==x['candidateRuntimeFiles'],'Unexpected candidate runtime')
  files=consumer.verified_runtime(raw,lock,manifest,identity)
  modifications=z.read(prefix+'source-correspondence/licenses/Ruffle-MODIFICATIONS.md')
 web=app/'App/Resources/Web';oldlock=c.load(app/'runtime.lock.json');oldidentity=c.digest((web/'runtime-identity.json').read_bytes());test=app/'Tests/FrameOrderRuntimeTests.swift';before='private static let identitySHA256 = "'+oldidentity+'"';text=test.read_text();c.require(text.count(before)==1,'FrameOrder pin changed')
 # All artifact/source checks above complete before replacing controlled staging bytes.
 shutil.rmtree(web/'runtime');(web/'runtime').mkdir()
 for name,data in files.items():(web/'runtime'/name).write_bytes(data)
 test.write_text(text.replace(before,'private static let identitySHA256 = "'+lock['identitySHA256']+'"'))
 (web/'runtime-identity.json').write_bytes(identity);(app/'runtime.lock.json').write_bytes(encoded(lock));(app/'runtime.files.json').write_bytes(encoded(manifest))
 (app/oldlock['archivePath']).unlink();(app/lock['archivePath']).write_bytes(raw)
 (app/'scripts/composite_runtime.py').write_bytes((ROOT/'candidate_composite_runtime.py').read_bytes())
 binding=("\n## Current packaged runtime identity\n\nEarlier composite identity references above describe the inherited baseline. The runtime packaged here is candidate engine run "+str(e['runID'])+", source commit "+e['sourceCommit']+", source set "+e['sourceSetSHA256']+". Actual focused desktop WebGL run41002083024 passed six pages; native/physical-device acceptance and original-crash resolution remain unproven.\n").encode()
 (web/'Ruffle-MODIFICATIONS.md').write_bytes(modifications+binding)
 notices=(app/'THIRD_PARTY_NOTICES.md').read_bytes()+binding;(app/'THIRD_PARTY_NOTICES.md').write_bytes(notices);(web/'THIRD_PARTY_NOTICES.md').write_bytes(notices)
 licenses=c.load(web/'licenses.manifest.json');licenses['Ruffle-MODIFICATIONS.md']=c.digest(modifications+binding);licenses['THIRD_PARTY_NOTICES.md']=c.digest(notices);(web/'licenses.manifest.json').write_bytes(encoded(licenses))
 (app/'FINAL_ENGINE_STAGING.json').write_bytes(encoded({'candidateEngineVerified':True,'engine':e,'runtimeLockSHA256':c.digest(encoded(lock)),'identitySHA256':lock['identitySHA256'],'samplingGateEnabled':True,'experimentalGateOverride':True,'nativeAccepted':False,'ipaBuilt':False,'productionAccepted':False}))
 for path,old,new in [('project.yml',"CFBundleVersion: '20'","CFBundleVersion: '22'"),('project.yml',"CURRENT_PROJECT_VERSION: '20'","CURRENT_PROJECT_VERSION: '22'"),('App/Info-Debug.plist','<key>CFBundleVersion</key>\n\t<string>20</string>','<key>CFBundleVersion</key>\n\t<string>22</string>')]:
  f=app/path;s=f.read_text();c.require(s.count(old)==1,'Version anchor differs');f.write_text(s.replace(old,new))
 if verify_final:c.require(c.file_map(app)==x['candidateAppFiles'],'Candidate full App differs')

def stage(source_checkout,recipe_checkout,out):
 x=inputs(dispatch=True);source_checkout=source_checkout.resolve();recipe_checkout=recipe_checkout.resolve();out=out.resolve();old,base=load_base(recipe_checkout,x)
 c.require(subprocess.check_output(['git','-C',str(source_checkout),'rev-parse','HEAD'],text=True).strip()==x['sourceCommit'],'Wrong source checkout')
 c.require(not out.exists(),'Fresh stage required');out.mkdir();source=out/'source';source.mkdir()
 for name,h in base['sourceFiles'].items():
  f=source_checkout/'experiments/final-composite'/name;c.require(f.is_file() and not f.is_symlink() and c.digest(f.read_bytes())==h,'Frozen baseline source differs');d=source/name;d.parent.mkdir(parents=True,exist_ok=True);d.write_bytes(f.read_bytes())
 c.require(c.file_map(source)==base['sourceFiles'],'Frozen source closure differs')
 sys.path.insert(0,str(source/'scripts'));import stage_validation_runtime as runtime
 original_fetch=runtime.fetch;runtime.fetch=lambda e:mirror_bytes(recipe_checkout,x,e) if e==base['engine'] else original_fetch(e)
 runtime.main();import stage_validation_inputs as staging;staging.main()
 app=source/'validation-app';old.overlay(app,base);old.diagnostic_overlay(app,base);c.require(c.file_map(app)==x['baseAppFiles'],'Build20 source reconstruction differs')
 candidate=original_fetch(x['candidateEngine']);browser=original_fetch(x['browserEvidence']);(out/'candidate.zip').write_bytes(candidate);(out/'browser.zip').write_bytes(browser);proof=verify_browser(browser,x,base['runtimeFiles']);rebind(app,candidate,x);shutil.copytree(app,out/'app')
 (out/'staging.json').write_bytes(encoded({'candidateAppFiles':x['candidateAppFiles'],'browser':proof,'candidateEngine':x['candidateEngine'],'baselineEngineMirror':x['baselineEngineMirror'],'nativeAccepted':False,'fullGatePassed':False,'diagnosticOptInDefault':False}))
 print('Exact build20 business code + candidate runtime/required metadata + build21 staged; no native acceptance')

def selected_gate(app,evidence):
 import run_selected_tests as runner
 evidence=evidence.resolve();r=c.load(evidence/'verification.json')
 c.require(r.get('schema')=='flashnest-selected-native-regression-v1' and r.get('selectedNativeRegressionPassed') is True,'Selected native gate not passed')
 for k,v in {'totalTestCount':16,'passedTests':16,'failedTests':0,'skippedTests':0,'expectedFailures':0}.items():c.require(type(r.get(k)) is int and r[k]==v,'Selected receipt count differs: '+k)
 c.require(r['sourceInventory']==runner.source_inventory(app),'Selected source inventory differs')
 for k in ('fullGatePassed','physicalDeviceCertified','nativePixelAcceptance','samplingBackingPixelAcceptance'):c.require(r[k] is False,'Selected tests promoted to full acceptance')
 device=None;methods=[];proof={}
 for lane,bundle,expected in [('unit','FlashNestTests',runner.UNIT),('ui','FlashNestUITests',runner.UI)]:
  summaryraw=(evidence/(lane+'-summary.json')).read_bytes();summary=json.loads(summaryraw);log=(evidence/(lane+'.log')).read_text()
  current=summary['devicesAndConfigurations'][0]['device']['deviceId']
  if device is None:device=current
  c.require(device==current,'Selected lanes used different simulators')
  verified=runner.verify(summary,log,expected,bundle,device);verified.update(summarySHA256=c.digest(summaryraw),resultBundle=lane+'.xcresult')
  c.require(r[lane]==verified and c.load(evidence/(lane+'-verification.json'))==verified,'Selected lane receipt differs')
  methods+=verified['actual'];proof[lane]=verified
 c.require(r.get('selectedReleaseGatePassed') is True and r['expected']==proof['unit']['expected']+proof['ui']['expected'] and r['actual']==methods,'Selected exact method receipt differs')
 c.require(str(r['runID'])==os.environ.get('GITHUB_RUN_ID') and r['head']==os.environ.get('GITHUB_SHA'),'Selected run/head differs')
 c.require(r['fixtureSourceInstalled']['bundleID']==runner.FIXTURE_BUNDLE,'Fixture identity differs')
 c.require(isinstance(r['fixtureSourceInstalled']['executableSHA256'],str) and len(r['fixtureSourceInstalled']['executableSHA256'])==64,'Fixture executable hash missing')
 return {'selectedReleaseGatePassed':True,'selectedNativeMethods':methods,'selectedEvidenceSHA256':c.digest((evidence/'verification.json').read_bytes()),'actualPackagingRunID':os.environ.get('GITHUB_RUN_ID'),'actualPackagingCommit':os.environ.get('GITHUB_SHA'),'lanes':proof,'skippedTests':0,'fullGatePassed':False,'physicalDeviceCertified':False}

def verify(ipa,app,out,record,evidence):
 x=inputs(dispatch=True);c.verify_sources(app,x['candidateAppFiles']);gate=selected_gate(app,evidence)
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
  c.require(c.file_map(bundle/'Web')==c.file_map(app/'App/Resources/Web'),'Full bundled Web differs')
  c.require(c.file_map(bundle/'Web/runtime')==x['candidateRuntimeFiles'],'Packaged runtime differs')
  sys.path.insert(0,str(app/'scripts'))
  spec=importlib.util.spec_from_file_location('experimental_runtime_verify',app/'scripts/verify_bundled_runtime.py');module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);module.verify_web(bundle/'Web',app)
  for name in ('shell.js','index.html'):
   raw=(bundle/'Web'/name).read_bytes();c.require(not any(v in raw for v in (b'__flashnestPhase',b'__nativeSamplingProbe',b'flashnest-native-sampling-pre-drag',b'late-audio-probe',b'audio-recovery-injection')),'Test probe in shipping Web')
  provenance={'schemaVersion':1,'kind':x['kind'],'releaseChannel':x['releaseChannel'],'selectedReleaseGate':gate,'experimentalGateOverride':True,'nativeAccepted':False,'fullGatePassed':False,'physicalDeviceCertified':False,'originalCrashResolved':False,'productionAccepted':False,'version':x['version'],'build':x['build'],'bundleID':x['bundleID'],'baseSourceCommit':x['sourceCommit'],'candidateEngine':x['candidateEngine'],'focusedBrowserReference':x['browserEvidence'],'packagingCommit':os.environ.get('GITHUB_SHA'),'packagingRunID':os.environ.get('GITHUB_RUN_ID'),'ipaSHA256':c.digest(ipa.read_bytes()),'ipaBytes':ipa.stat().st_size,'deviceExecutable':macho,'appSourceFiles':x['candidateAppFiles'],'baseAppFiles':x['baseAppFiles'],'candidateRuntimeExperiment':True,'diagnosticsRetained':True,'diagnosticOptInDefault':False,'webFiles':c.file_map(bundle/'Web'),'unsigned':True}
  record.write_text(json.dumps(provenance,indent=2,sort_keys=True)+'\n')
 print('Release device IPA bytes verified; selected native gate is not full regression acceptance')


if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('action',choices=('preflight','stage','verify'));p.add_argument('--source-checkout',type=Path);p.add_argument('--recipe-checkout',type=Path);p.add_argument('--output',type=Path);p.add_argument('--ipa',type=Path);p.add_argument('--app',type=Path);p.add_argument('--record',type=Path);p.add_argument('--selected-evidence',type=Path);a=p.parse_args()
 if a.action=='preflight':inputs(dispatch=True);print('Explicit release IPA package contract verified')
 elif a.action=='stage':stage(a.source_checkout,a.recipe_checkout,a.output)
 else:verify(a.ipa,a.app,a.output,a.record,a.selected_evidence)

#!/usr/bin/env python3
import hashlib, json, pathlib, struct, unittest, zipfile
from test_runtime_bundle import RuntimeBundleTests
ROOT=pathlib.Path(__file__).resolve().parents[1]; WEB=ROOT/'App/Resources/Web'
class StaticTests(unittest.TestCase):
 def test_declared_versions_match_native_test_and_debug_bundle(self):
  import plistlib, re
  project=(ROOT/'project.yml').read_text()
  info=plistlib.loads((ROOT/'App/Info-Debug.plist').read_bytes())
  native=(ROOT/'Tests/LocalizationTests.swift').read_text()
  for key, setting in [('CFBundleShortVersionString','MARKETING_VERSION'),('CFBundleVersion','CURRENT_PROJECT_VERSION')]:
   value=info[key]
   self.assertIn(key+": '"+value+"'",project)
   self.assertIn(setting+": '"+value+"'",project)
   pattern=re.escape('forInfoDictionaryKey: "'+key+'") as? String, "')+'([^"\n]+)'
   self.assertEqual(re.search(pattern,native).group(1),value)

 def test_external_document_routing_and_strict_types(self):
  import plistlib
  info=plistlib.loads((ROOT/'App/Info-Debug.plist').read_bytes())
  kinds=info['CFBundleDocumentTypes'][0]['LSItemContentTypes']
  self.assertEqual(set(kinds),{'public.zip-archive','com.adobe.flash','public.folder'})
  saves=info['CFBundleDocumentTypes'][1]
  self.assertEqual(saves['LSHandlerRank'],'Alternate')
  self.assertEqual(set(saves['LSItemContentTypes']),{'public.json','com.flashnest.save','com.flashnest.shared-object'})
  self.assertNotIn('public.data',kinds+saves['LSItemContentTypes'])
  project=(ROOT/'project.yml').read_text()
  for kind in kinds+saves['LSItemContentTypes']: self.assertIn('- '+kind,project)
  self.assertIn('.onOpenURL { externalImports.receive($0) }',(ROOT/'App/FlashNestApp.swift').read_text())
  self.assertIn('LibraryNavigation.navigateToSourceFolder(named: fixtureTitle, in: app)',(ROOT/'UITests/LifecyclePlayerUITests.swift').read_text())

 def test_loopback_listener_port_is_specified_once(self):
  s=(ROOT/'App/Server/LoopbackServer.swift').read_text()
  self.assertIn('requiredLocalEndpoint = .hostPort(host: "127.0.0.1", port: endpointPort)',s)
  self.assertIn('requiredInterfaceType = .loopback',s)
  self.assertIn('NWListener(using: parameters)',s)
  self.assertNotIn('NWListener(using: parameters, on:',s)
 def test_simulator_selection(self):
  from select_simulator import select
  data={'devices':{
    'com.apple.CoreSimulator.SimRuntime.iOS-18-5':[{'isAvailable':True,'name':'iPhone Test','udid':'expected'},{'isAvailable':False,'name':'iPhone Earlier','udid':'wrong'}],
    'com.apple.CoreSimulator.SimRuntime.iOS-26-0':[{'isAvailable':True,'name':'iPhone New','udid':'incompatible'}],
    'com.apple.CoreSimulator.SimRuntime.tvOS-18-5':[{'isAvailable':True,'name':'Apple TV','udid':'wrong'}]}}
  self.assertEqual(select(data,'18.5'),'expected')
  with self.assertRaises(ValueError): select(data,'17.0')

 def test_package_storage_isolation_contract(self):
  s=(ROOT/'App/Player/PlayerSession.swift').read_text()
  registry=(ROOT/'App/Player/PackageWebKitProfiles.swift').read_text()
  self.assertIn('PackageWebKitProfiles.shared.store(for: package.id',s)
  self.assertIn('WKWebsiteDataStore(forIdentifier: id)',registry)
  self.assertIn('profiles[id]',registry)
  self.assertNotIn('websiteDataStore = .default()',s)
  self.assertNotIn('WKWebsiteDataStore.default()',registry)
 def test_actual_runtime(self):
  lock=json.loads((ROOT/'runtime.lock.json').read_text())
  self.assertEqual(json.loads((WEB/'runtime/package.json').read_text())['version'],lock['version'])
  self.assertGreater((WEB/'runtime/ruffle.js').stat().st_size,100000)
  for p in (WEB/'runtime').glob('*.wasm'): self.assertEqual(p.read_bytes()[:4],b'\0asm')
  self.assertEqual(len(list((WEB/'runtime').glob('*.wasm'))),2)
 def test_offline_contract(self):
  s=(WEB/'shell.js').read_text(); h=(WEB/'index.html').read_text()
  for v in ("allowScriptAccess:false","allowNetworking:'internal'","openUrlMode:'deny'","socketProxy:[]","parts.map(encodeURIComponent)","new URL('./',url)",".suspend()",".resume()"):
   self.assertIn(v,s)
  self.assertIn("connect-src 'self'",h)
  self.assertNotIn('https://',h)
  self.assertIn('pointercancel',s); self.assertIn('lostpointercapture',s)
 def test_fixture(self):
  for p in (ROOT/'fixtures/multi-swf').rglob('*.swf'):
   b=p.read_bytes(); self.assertEqual(b[:3],b'FWS'); self.assertEqual(struct.unpack('<I',b[4:8])[0],len(b))
  self.assertIn(b'sub/child.swf',(ROOT/'fixtures/multi-swf/main.swf').read_bytes())
  main=(ROOT/'fixtures/multi-swf/main.swf').read_bytes()
  # ActionGetURL2 length=1, flags LoadVariables|LoadTarget for string _root.
  self.assertIn(b'\x9a\x01\x00\xc0',main)
  self.assertNotIn(b'\x9a\x01\x00\x80',main)
  self.assertIn(b'FLASHNEST_CHILD_OK',(ROOT/'fixtures/multi-swf/sub/child.swf').read_bytes())
  with zipfile.ZipFile(ROOT/'fixtures/multi-swf.zip') as z:
   self.assertIn('sub/child.swf',z.namelist())
   self.assertEqual(z.read('main.swf'),main)
 def test_shared_object_fixtures(self):
  root=ROOT/'fixtures/shared-object'
  explicit=(root/'explicit-flush.swf').read_bytes()
  close=(root/'close-flush.swf').read_bytes()
  readonly=(root/'read-only.swf').read_bytes()
  for data in (explicit,close,readonly):
   self.assertEqual(data[:3],b'FWS')
   self.assertEqual(struct.unpack('<I',data[4:8])[0],len(data))
   for marker in (b'SharedObject',b'getLocal',b'FlashNestFixture',b'FLASHNEST_SAVE_BEFORE:',b'FLASHNEST_SAVE_READY'):
    self.assertIn(marker,data)
  self.assertIn(b'flush',explicit)
  self.assertNotIn(b'flush',close)
  self.assertNotIn(b'flush',readonly)
  def opcodes(swf):
   offset=8+(5+4*(swf[8]>>3)+7)//8+4
   while offset<len(swf):
    header=struct.unpack_from('<H',swf,offset)[0]; offset+=2
    size=header&63
    if size==63: size=struct.unpack_from('<I',swf,offset)[0]; offset+=4
    body=swf[offset:offset+size]; offset+=size
    if header>>6==12:
     codes=[]; i=0
     while i<len(body):
      code=body[i]; codes.append(code); i+=1
      if code>=128:
       size=struct.unpack_from('<H',body,i)[0]; i+=2+size
     self.assertEqual(i,len(body))
     return codes
   self.fail('Missing DoAction tag')
  self.assertIn(0x4f,opcodes(close))  # ActionSetMember progress=42.
  self.assertNotIn(0x4f,opcodes(readonly))
  self.assertEqual(opcodes(explicit).count(0x52),2)  # getLocal + flush.
  self.assertEqual(opcodes(close).count(0x52),1)
 def test_lifecycle_fixture_is_separate_from_rendering_experiment(self):
  base=ROOT/'fixtures/lifecycle'
  main=(base/'main.swf').read_bytes(); child=(base/'sub/scene.swf').read_bytes()
  for data in (main,child):
   self.assertEqual(data[:3],b'FWS')
   self.assertEqual(struct.unpack('<I',data[4:8])[0],len(data))
   self.assertIn(b'LifecycleFixture',data); self.assertIn(b'flush',data)
   for vector in (b'createEmptyMovieClip',b'beginFill',b'lineTo'):
    self.assertNotIn(vector,data)
  self.assertIn(b'LIFECYCLE_ROOT_READY:',main); self.assertIn(b'sub/scene.swf',main)
  self.assertIn(b'removeListener',main)
  self.assertIn(b'rootListener',main); self.assertIn(b'childListener',child)
  self.assertNotIn(b'_root',main); self.assertNotIn(b'_root',child)
  self.assertIn(b'LIFECYCLE_CHILD_KEY:',child); self.assertIn(b'LIFECYCLE_CHILD_POINTER:',child)
  project=(ROOT/'project.yml').read_text()
  self.assertIn('path: fixtures/lifecycle',project)
  self.assertNotIn('path: fixtures/viewport-input',project)
  self.assertNotIn('experiments/',project)
  self.assertTrue((ROOT/'experiments/half-resolution/Tests/ViewportRenderingRuntimeTests.swift').is_file())
  self.assertNotIn('renderMode',(ROOT/'App/Player/PlayerSession.swift').read_text())
  self.assertNotIn('usesHalfResolution',(ROOT/'App/Player/PlayerSession.swift').read_text())
 def test_default_frame_order_regression_identity_and_capture_equivalence(self):
  import re
  default=(ROOT/'Tests/FrameOrderRuntimeTests.swift').read_text()
  candidate=(ROOT/'experiments/frame-order/candidate-native/FrameOrderCandidateRuntimeTests.swift').read_text()
  identity=(WEB/'runtime-identity.json').read_bytes()
  self.assertIn('private static let identitySHA256 = "'+hashlib.sha256(identity).hexdigest()+'"',default)
  for name in ('installObserver','snapshot'):
   pattern=r'private static let '+name+r' = """(.*?)"""'
   self.assertEqual(re.search(pattern,default,re.S).group(1),re.search(pattern,candidate,re.S).group(1),name)
  for name in ('nested-child-goto.swf','control-no-child-goto.swf'):
   self.assertEqual((ROOT/'fixtures/frame-order'/name).read_bytes(),(ROOT/'experiments/frame-order/fixtures'/name).read_bytes())
  for name in ('nested-repair-target.txt','control.txt'):
   self.assertEqual((ROOT/'fixtures/frame-order'/name).read_bytes(),(ROOT/'experiments/frame-order/engine-patch/expectations'/name).read_bytes())

 def test_manifest(self):
  manifest=json.loads((ROOT/'runtime.files.json').read_text())
  self.assertEqual({p.name for p in (WEB/'runtime').iterdir()},set(manifest))
  for name,digest in manifest.items(): self.assertEqual(hashlib.sha256((WEB/'runtime'/name).read_bytes()).hexdigest(),digest,name)
if __name__=='__main__': unittest.main()

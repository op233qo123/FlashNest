#!/usr/bin/env python3
import hashlib, json, pathlib, struct, unittest, zipfile
ROOT=pathlib.Path(__file__).resolve().parents[1]; WEB=ROOT/'App/Resources/Web'
class StaticTests(unittest.TestCase):
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
  self.assertIn('WKWebsiteDataStore(forIdentifier: package.id)',s)
  self.assertNotIn('websiteDataStore = .default()',s)
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
 def test_manifest(self):
  manifest=json.loads((ROOT/'runtime.files.json').read_text())
  for name,digest in manifest.items(): self.assertEqual(hashlib.sha256((WEB/'runtime'/name).read_bytes()).hexdigest(),digest,name)
if __name__=='__main__': unittest.main()

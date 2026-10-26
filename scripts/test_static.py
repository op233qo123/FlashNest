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
 def test_manifest(self):
  manifest=json.loads((ROOT/'runtime.files.json').read_text())
  for name,digest in manifest.items(): self.assertEqual(hashlib.sha256((WEB/'runtime'/name).read_bytes()).hexdigest(),digest,name)
if __name__=='__main__': unittest.main()

"""Synthetic Mach-O bytes only; no execution, build or platform availability claim."""
import hashlib,pathlib,struct,tempfile,unittest
from installed_bundle import arm64_simulator_executable

def macho(commands=None,**override):
 if commands is None:commands=[struct.pack('<6I',0x32,24,7,0x00110000,0x00120200,0)]
 values=dict(magic=0xfeedfacf,cpu=0x0100000c,subtype=0,filetype=2,ncmds=len(commands),sizeofcmds=sum(map(len,commands)),flags=0,reserved=0);values.update(override)
 return struct.pack('<8I',*(values[k]for k in ['magic','cpu','subtype','filetype','ncmds','sizeofcmds','flags','reserved']))+b''.join(commands)+b'SYNTHETIC-NOT-EXECUTABLE'
class MachOTests(unittest.TestCase):
 def check(self,data):
  with tempfile.TemporaryDirectory()as t:
   p=pathlib.Path(t)/'main';p.write_bytes(data);return arm64_simulator_executable(p)
 def test_exact_thin_arm64_ios_simulator18_2(self):
  data=macho();r=self.check(data)
  self.assertEqual(r['architecture'],'arm64');self.assertEqual(r['platformID'],7);self.assertEqual(r['sdk'],'18.2');self.assertEqual(r['sha256'],hashlib.sha256(data).hexdigest())
  self.check(macho([struct.pack('<8I',0x32,32,7,0x00110000,0x00120200,1,3,100)]))
 def test_fat_foreign_subtype_filetype_and_truncated_rejected(self):
  invalid=[b'',b'\xcf\xfa\xed\xfe',macho()[:40]]
  invalid += [macho(**{k:v})for k,v in [('magic',0xcafebabe),('magic',0xbebafeca),('magic',0xcafebabf),('magic',0xcffaedfe),('magic',0xfeedface),('cpu',0x01000007),('cpu',12),('subtype',2),('subtype',0x80000000),('filetype',6),('reserved',1),('ncmds',0),('ncmds',4097),('sizeofcmds',4*1024*1024+1)]]
  for data in invalid:
   with self.subTest(header=data[:32]),self.assertRaises(ValueError):self.check(data)
 def test_device_missing_duplicate_mixed_legacy_platforms_rejected(self):
  build=lambda platform:struct.pack('<6I',0x32,24,platform,0x00110000,0x00120200,0)
  for commands in [[build(2)],[build(1)],[build(6)],[],[build(7),build(7)],[build(7),build(2)],[struct.pack('<2I',0x25,8),build(7)],[struct.pack('<2I',0x24,8),build(7)]]:
   with self.subTest(commands=commands),self.assertRaises(ValueError):self.check(macho(commands))
 def test_commands_alignment_bounds_tools_and_sdk_rejected(self):
  bad=[struct.pack('<2I',0x32,0),struct.pack('<2I',0x32,7),struct.pack('<2I',0x32,16)+b'0'*8,struct.pack('<6I',0x32,24,7,0x00110000,0x00120200,1),struct.pack('<6I',0x32,24,7,0x00110000,0x00120200,65),struct.pack('<6I',0x32,24,7,0x00110000,0x00120500,0),struct.pack('<6I',0x32,24,7,0x00130000,0x00120200,0)]
  for command in bad:
   with self.subTest(command=command),self.assertRaises(ValueError):self.check(macho([command]))
  with self.assertRaises(ValueError):self.check(macho(ncmds=2))
  with self.assertRaises(ValueError):self.check(macho(sizeofcmds=32))
 def test_symlink_rejected(self):
  with tempfile.TemporaryDirectory()as t:
   t=pathlib.Path(t);p=t/'real';p.write_bytes(macho());link=t/'link';link.symlink_to(p)
   with self.assertRaises(ValueError):arm64_simulator_executable(link)
if __name__=='__main__':unittest.main()

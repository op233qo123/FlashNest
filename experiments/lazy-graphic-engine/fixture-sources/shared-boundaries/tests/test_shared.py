import hashlib,io,json,pathlib,struct,sys,unittest,zlib
from PIL import Image
ROOT=pathlib.Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT));import generate as g

def tags(data):
 assert data[:4]==b'FWS\x0f' and struct.unpack_from('<I',data,4)[0]==len(data)
 pos=8+(5+(data[8]>>3)*4+7)//8;assert struct.unpack_from('<HH',data,pos)==(6144,2);pos+=4;out=[]
 while pos<len(data):
  h=struct.unpack_from('<H',data,pos)[0];pos+=2;n=h>>6;size=h&63
  if size==63:size=struct.unpack_from('<I',data,pos)[0];pos+=4
  assert pos+size<=len(data);out.append((n,data[pos:pos+size]));pos+=size
 return out
class Shared(unittest.TestCase):
 def setUp(self):self.data=(ROOT/'neutral-shared-boundaries.swf').read_bytes();self.tags=tags(self.data)
 def test_one_definition_two_placements_same_shape(self):
  self.assertEqual([n for n,_ in self.tags],[69,82,76,35,32,1,26,26,1,0])
  self.assertEqual(self.tags[4][1],g.shape(1))
  for depth,body in enumerate([b for n,b in self.tags if n==26],1):
   self.assertEqual(body[0],0x26);self.assertEqual(struct.unpack_from('<HH',body,1),(depth,101))
 def test_real_image_and_alpha(self):
  body=self.tags[3][1];ident,size=struct.unpack_from('<HI',body);self.assertEqual(ident,1)
  im=Image.open(io.BytesIO(body[6:6+size])).convert('RGBA');self.assertEqual(im.size,(16,16));self.assertEqual(im.getpixel((8,8)),(20,200,49,255))
  self.assertEqual(zlib.decompress(body[6+size:]),bytes([255])*256)
 def test_generation_stable_and_corrupt_length_rejected(self):
  old=json.loads((ROOT/'fixture-manifest.json').read_text());self.assertEqual(g.generate(),old)
  self.assertEqual((ROOT/'neutral-shared-boundaries.swf').read_bytes(),self.data)
  wrong=bytearray(self.data);wrong[4]^=1
  with self.assertRaises(AssertionError):tags(wrong)
 def test_actual_null_semantics(self):
  log=(ROOT/'core-smoke.log').read_text();rows=[line[1:] for line in log.splitlines() if line.startswith('<NEUTRAL_SHARED')]
  self.assertEqual(rows,['NEUTRAL_SHARED ready','NEUTRAL_SHARED shown','NEUTRAL_SHARED redrawn','NEUTRAL_SHARED masked','NEUTRAL_SHARED hit inside=true outside=false'])
  self.assertNotIn('ReferenceError',log);self.assertNotIn('ERROR ruffle',log)
 def test_deferred_redraw_and_bound_keys(self):
  source=(ROOT/'as/NeutralSharedRoot.as').read_text()
  self.assertIn('waitFrames=2',source);self.assertIn('if(--waitFrames>0)return',source)
  self.assertIn('phase==0',source);self.assertIn('phase==1',source);self.assertIn('phase==3',source);self.assertIn('phase==4',source)
  self.assertIn('stage.removeEventListener(KeyboardEvent.KEY_DOWN,key)',source)
if __name__=='__main__':unittest.main()

import hashlib,io,json,pathlib,struct,sys,unittest,zlib
from PIL import Image
ROOT=pathlib.Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT));import generate as g

def parse(data):
 assert data[:4]==b'FWS\x0f' and struct.unpack_from('<I',data,4)[0]==len(data)
 pos=8;rectBytes=(5+(data[pos]>>3)*4+7)//8;pos+=rectBytes
 fps,frames=struct.unpack_from('<HH',data,pos);pos+=4;assert fps==24*256 and frames==2
 out=[]
 while pos<len(data):
  h=struct.unpack_from('<H',data,pos)[0];pos+=2;n=h>>6;size=h&63
  if size==63:size=struct.unpack_from('<I',data,pos)[0];pos+=4
  assert pos+size<=len(data);out.append((n,data[pos:pos+size]));pos+=size
  if n==0:break
 assert pos==len(data);return out
class Fixture(unittest.TestCase):
 def setUp(self):self.data=(ROOT/'neutral-eight-jpeg3.swf').read_bytes();self.tags=parse(self.data)
 def test_exact_definition_and_placement(self):
  self.assertEqual([n for n,_ in self.tags],[69,82,76]+[n for _ in range(8) for n in (35,32)]+[1,26,1,0])
  self.assertEqual([struct.unpack_from('<H',body)[0] for n,body in self.tags if n==35],list(range(1,9)))
  self.assertEqual([struct.unpack_from('<H',body)[0] for n,body in self.tags if n==32],list(range(101,109)))
  placement=next(body for n,body in self.tags if n==26)
  self.assertEqual(placement[0],6);self.assertEqual(struct.unpack_from('<HH',placement,1),(1,101))
  for ident,(_,body) in enumerate([(n,b) for n,b in self.tags if n==32],1):self.assertEqual(body,g.shape(ident))
 def test_eight_real_jpeg_and_nontransparent_alpha(self):
  for n,body in self.tags:
   if n!=35:continue
   ident,offset=struct.unpack_from('<HI',body);jpeg=body[6:6+offset]
   self.assertEqual(jpeg,(ROOT/'images'/f'{ident}.jpg').read_bytes())
   image=Image.open(io.BytesIO(jpeg));image.load();self.assertEqual(image.format,'JPEG');self.assertEqual(image.size,(16,16))
   self.assertEqual(zlib.decompress(body[6+offset:]),bytes([255])*256)
 def test_reproducible_frozen_image_inputs(self):
  original=self.data;manifest=json.loads((ROOT/'fixture-manifest.json').read_text());self.assertEqual(g.generate(),manifest)
  self.assertEqual((ROOT/'neutral-eight-jpeg3.swf').read_bytes(),original)
  self.assertEqual(hashlib.sha256(original).hexdigest(),manifest['sha256'])
 def test_null_core_semantic_log_not_golden_acceptance(self):
  log=(ROOT/'core-smoke.log').read_text()
  self.assertEqual(log.count('<NEUTRAL_GRAPHIC ready unshown=8'),1)
  self.assertEqual(log.count('<NEUTRAL_GRAPHIC first-display requested=1 remaining-unshown=7'),1)
  self.assertNotIn('ERROR ruffle',log)
  self.assertIn('0 passed; 1 failed',log) # intentionally empty Flash golden, not acceptance
 def test_forward_reference_control_exact_order(self):
  data=(ROOT/'neutral-forward-reference.swf').read_bytes();self.assertEqual(g.forward_reference(self.data),data)
  tags=parse(data);self.assertEqual([n for n,_ in tags],[69,82,76,32,35,1,26,1,0])
  self.assertEqual(struct.unpack_from('<H',tags[3][1])[0],101)
  self.assertEqual(struct.unpack_from('<H',tags[4][1])[0],1)
 def test_corruption_rejected(self):
  data=bytearray(self.data);data[4]^=1
  with self.assertRaises(AssertionError):parse(data)
if __name__=='__main__':unittest.main()

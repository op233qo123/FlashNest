import hashlib,json,pathlib,struct,unittest
ROOT=pathlib.Path(__file__).resolve().parent.parent

def parse(path):
 b=path.read_bytes();assert b[:3]==b'FWS' and struct.unpack_from('<I',b,4)[0]==len(b)
 n=b[8]>>3;pos=8+(5+4*n+7)//8;fps,frames=struct.unpack_from('<HH',b,pos);pos+=4;tags=[]
 while pos<len(b):
  h=struct.unpack_from('<H',b,pos)[0];pos+=2;size=h&63;code=h>>6
  if size==63:size=struct.unpack_from('<I',b,pos)[0];pos+=4
  payload=b[pos:pos+size];assert len(payload)==size;pos+=size;tags.append((code,payload))
  if code==0:break
 assert pos==len(b)
 return fps,frames,tags
class Fixtures(unittest.TestCase):
 def test_bytes(self):
  m=json.loads((ROOT/'fixtures/manifest.json').read_text())
  for row in m['files']:
   p=ROOT/'fixtures'/row['file'];b=p.read_bytes();self.assertEqual(len(b),row['bytes']);self.assertEqual(hashlib.sha256(b).hexdigest(),row['sha256']);fps,frames,tags=parse(p);self.assertEqual(fps,24*256);self.assertEqual(sum(c==1 for c,p in tags),frames);self.assertEqual(sum(c==82 for c,p in tags),1);self.assertEqual(sum(c==12 for c,p in tags),0);self.assertEqual(struct.unpack('<I',next(p for c,p in tags if c==69))[0],8)
 def test_root_counts(self):
  for n in [16,64]:
   _,frames,tags=parse(ROOT/'fixtures'/f'root-{n}.swf');self.assertEqual(frames,n+1);self.assertEqual(sum(c==35 for c,p in tags),n);self.assertEqual(sum(c==32 for c,p in tags),n);self.assertEqual(sum(c==26 for c,p in tags),n);self.assertEqual(sum(c==28 for c,p in tags),n-1)
 def test_loader_sources(self):
  for name in ['TextureLoaderRetain','TextureLoaderRelease']:
   s=(ROOT/'fixture-src/as'/f'{name}.as').read_text();self.assertIn('loader.unload()',s);self.assertIn('frames==120',s);self.assertNotIn('System.gc',s);self.assertNotIn('.dispose(',s)
if __name__=='__main__':unittest.main()

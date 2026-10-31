import hashlib,json,pathlib,struct,zlib,sys,io
from PIL import Image
ROOT=pathlib.Path(__file__).resolve().parent;F=ROOT.parent/'fixtures'
sys.path.insert(0,str(ROOT));from run import validate,inventory
m=json.loads((F/'manifest.json').read_text());assert len(m['fixtures'])==9
assert sum(row['jpegProgressive'] for row in m['fixtures'])==4
assert {(row['width'],row['imageMode'],row['jpegSubsampling']) for row in m['fixtures'] if row['jpegProgressive']}=={(1024,'RGB',0),(1024,'RGB',2),(1024,'L',0),(512,'RGB',2)}
for row in m['fixtures']:
 b=(F/row['file']).read_bytes();assert hashlib.sha256(b).hexdigest()==row['sha256'];assert len(b)==row['bytes']==struct.unpack_from('<I',b,4)[0]
 assert b[:4]==b'FWS\x0f';pos=8+(5+(b[8]>>3)*4+7)//8+4;tags=[]
 while pos<len(b):
  h=struct.unpack_from('<H',b,pos)[0];pos+=2;code,n=h>>6,h&63
  if n==63:n=struct.unpack_from('<I',b,pos)[0];pos+=4
  tags.append((code,b[pos:pos+n]));pos+=n
 assert pos==len(b);assert [c for c,_ in tags]==[69,82,76,35,32,1,26,26,1,0]
 image=[d for c,d in tags if c==35][0];ident,offset=struct.unpack_from('<HI',image);jpeg=image[6:6+offset];alpha=zlib.decompress(image[6+offset:])
 image=Image.open(io.BytesIO(jpeg))
 assert ident==1 and image.size==(row['width'],row['height']) and image.mode==row['imageMode']
 assert bool(image.info.get('progressive',False))==row['jpegProgressive']
 # Read marker segments rather than searching entropy bytes for SOF2.
 assert jpeg[:2]==b'\xff\xd8';jp=2;sof=[]
 while jp<len(jpeg):
  assert jpeg[jp]==255;jp+=1
  while jpeg[jp]==255:jp+=1
  marker=jpeg[jp];jp+=1
  if marker in [0xda,0xd9]:break
  n=int.from_bytes(jpeg[jp:jp+2],'big');assert n>=2
  if marker in [0xc0,0xc2]:sof.append(marker)
  jp+=n
 assert sof==([0xc2] if row['jpegProgressive'] else [0xc0])
 assert len(alpha)==row['width']*row['height'];assert hashlib.sha256(alpha).hexdigest()==row['alphaSHA256'];assert hashlib.sha256(jpeg).hexdigest()==row['jpegSHA256']
 abc=[d for c,d in tags if c==82][0][5:];assert hashlib.sha256(abc).hexdigest()==m['abcSHA256']
print('9 synthetic SWF structure/JPEG SOF0/SOF2/alpha/ABC/hash cases passed')
page=(ROOT/'page.html').read_text();runner=(ROOT/'run.py').read_text();assert 'chromium_sandbox=True' in runner and '--no-sandbox' not in runner and '--disable-web-security' not in runner
assert "contextEvents:evidence.contextEvents.slice()" in page and 'm.buffer.byteLength' in page
print('Sandbox and observation source contracts passed; actual browser not run')

# A late upload during screenshot must appear in the paired observation.
from run import capture_after_paint
class FakePage:
 def __init__(self):self.calls=[];self.uploads=0
 def locator(self,selector):assert selector=='#host';return self
 def screenshot(self,path):self.calls.append('screenshot');self.uploads=1
 def evaluate(self,script):assert script=='window.snapshot()';self.calls.append('snapshot');return {'uploads':self.uploads}
fake=FakePage();assert capture_after_paint(fake,ROOT/'unused.png')=={'uploads':1};assert fake.calls==['screenshot','snapshot']
print('Late render capture ordering regression passed')

# Aggregate recovery limits across all 1024 patterned progressive/ordinary cases.
from run import record_context_recovery
summary={};record_context_recovery(summary,{'successful':False},{'successful':False})
record_context_recovery(summary,{'successful':True},{'successful':True})
assert summary=={'contextRecoveryBothSuccessful':False,'contextRecoveryLimitation':True}
try:record_context_recovery({}, {'successful':True},{'successful':False})
except AssertionError:pass
else:raise AssertionError('Candidate context recovery regression was not rejected')
print('Multi-case context recovery aggregation regression passed')

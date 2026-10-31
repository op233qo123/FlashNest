import hashlib,json,pathlib,struct,zlib,sys,io
from PIL import Image
ROOT=pathlib.Path(__file__).resolve().parent;F=ROOT.parent/'fixtures'
sys.path.insert(0,str(ROOT));from run import validate,inventory
m=json.loads((F/'manifest.json').read_text());assert len(m['fixtures'])==5
for row in m['fixtures']:
 b=(F/row['file']).read_bytes();assert hashlib.sha256(b).hexdigest()==row['sha256'];assert len(b)==row['bytes']==struct.unpack_from('<I',b,4)[0]
 assert b[:4]==b'FWS\x0f';pos=8+(5+(b[8]>>3)*4+7)//8+4;tags=[]
 while pos<len(b):
  h=struct.unpack_from('<H',b,pos)[0];pos+=2;code,n=h>>6,h&63
  if n==63:n=struct.unpack_from('<I',b,pos)[0];pos+=4
  tags.append((code,b[pos:pos+n]));pos+=n
 assert pos==len(b);assert [c for c,_ in tags]==[69,82,76,35,32,1,26,26,1,0]
 image=[d for c,d in tags if c==35][0];ident,offset=struct.unpack_from('<HI',image);jpeg=image[6:6+offset];alpha=zlib.decompress(image[6+offset:])
 assert ident==1 and Image.open(io.BytesIO(jpeg)).size==(row['width'],row['height'])
 assert len(alpha)==row['width']*row['height'];assert hashlib.sha256(alpha).hexdigest()==row['alphaSHA256'];assert hashlib.sha256(jpeg).hexdigest()==row['jpegSHA256']
 abc=[d for c,d in tags if c==82][0][5:];assert hashlib.sha256(abc).hexdigest()==m['abcSHA256']
print('5 synthetic SWF structure/JPEG/alpha/ABC/hash cases passed')
page=(ROOT/'page.html').read_text();runner=(ROOT/'run.py').read_text();assert 'chromium_sandbox=True' in runner and '--no-sandbox' not in runner and '--disable-web-security' not in runner
assert "contextEvents:evidence.contextEvents.slice()" in page and 'm.buffer.byteLength' in page
print('Sandbox and observation source contracts passed; actual browser not run')

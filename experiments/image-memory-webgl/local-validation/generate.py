from PIL import Image
from pathlib import Path
import json,zlib,random
r=Path(__file__).parent/'fixtures';r.mkdir(exist_ok=True);cases=[]
def add(name,j,a):
 (r/(name+'.jpg')).write_bytes(j)
 if a is not None:(r/(name+'.alpha')).write_bytes(a)
 cases.append({'name':name,'jpeg':name+'.jpg','alpha':None if a is None else name+'.alpha'})
def jpeg(n,mode):
 import io
 rgb=Image.new('RGB',(n,n));rgb.putdata([((i*17)%256,(i//n*7)%256,(i*11+i//n)%256) for i in range(n*n)])
 im=rgb.convert(mode);b=io.BytesIO();im.save(b,format='JPEG',quality=85);return b.getvalue()
for n,mode in [(32,'RGB'),(32,'L'),(32,'CMYK'),(511,'RGB'),(512,'RGB'),(513,'RGB'),(512,'L'),(512,'CMYK'),(1024,'RGB')]:
 j=jpeg(n,mode);raw=bytes(random.Random(n+len(mode)).randbytes(n*n))
 add(f'{mode}-{n}-random',j,zlib.compress(raw));add(f'{mode}-{n}-opaque',j,zlib.compress(bytes([255])*(n*n)))
 if n in [32,1024] and mode=='RGB':
  add(f'{mode}-{n}-none',j,None)
  for suffix,a in [('empty',zlib.compress(b'')),('short',zlib.compress(raw[:-1])),('long',zlib.compress(raw+b'!')),('bad',b'bad zlib'),('latebad',zlib.compress(raw)[:-1]+bytes([zlib.compress(raw)[-1]^255])),('truncated',zlib.compress(raw)[:-2]),('trailing',zlib.compress(raw)+b'trailing'),('concatenated',zlib.compress(raw)+zlib.compress(b'second stream'))]:add(f'{mode}-{n}-{suffix}',j,a)
add('bad-jpeg',b'\xff\xd8INVALID\xff\xd9',zlib.compress(b'alpha'))
(r/'manifest.json').write_text(json.dumps(cases,indent=2));print(len(cases),'cases')

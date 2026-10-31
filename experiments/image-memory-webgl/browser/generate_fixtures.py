"""Generate only mathematical color/alpha patterns using the pinned neutral ABC.
No game input. Bitmap fills are scaled to show the whole decoded bitmap in 16x16.
"""
import hashlib, importlib.util, io, json, pathlib, struct, zlib
from PIL import Image
HERE=pathlib.Path(__file__).resolve().parent
OLD=HERE.parents[1]/'lazy-graphic-engine/fixture-sources/shared-boundaries'
OUT=HERE.parent/'fixtures'
spec=importlib.util.spec_from_file_location('old',OLD/'generate.py'); old=importlib.util.module_from_spec(spec);spec.loader.exec_module(old)
def sha(b):return hashlib.sha256(b).hexdigest()
def shape(size):
 # Same16pxgeometry; scale full source bitmap to fit it, not first16pixels.
 raw=old.shape(1);prefix=struct.pack('<H',101)+old.rect(320,320)+b'\x01\x41'+struct.pack('<H',1)
 assert raw.startswith(prefix)
 oldmatrix=old.matrix(scale=20)
 assert raw[len(prefix):].startswith(oldmatrix)
 return prefix+old.matrix(scale=320/size)+raw[len(prefix)+len(oldmatrix):]
def generate():
 OUT.mkdir(exist_ok=True);abc=(OLD/'abc/NeutralSharedRoot.abc').read_bytes()
 assert sha(abc)=='be06602acfb6558e7fe1363bfe2944bad9cd0244e31af02391ad1534da868439'
 rows=[]
 for size,mode in [(64,'pattern'),(511,'pattern'),(512,'pattern'),(1024,'pattern'),(1024,'opaque')]:
  rgb=bytes(v for y in range(size) for x in range(size) for v in (30+(x*180//size),40+(y*160//size),60+((x//max(1,size//8)+y//max(1,size//8))%2)*120))
  image=Image.frombytes('RGB',(size,size),rgb);buffer=io.BytesIO();image.save(buffer,format='JPEG',quality=90,subsampling=0,optimize=False)
  jpeg=buffer.getvalue();alpha=bytes([255])*(size*size) if mode=='opaque' else bytes((64,128,192,255)[(x//max(1,size//4)+y//max(1,size//4))%4] for y in range(size) for x in range(size))
  tags=[old.tag(69,struct.pack('<I',8)),old.tag(82,struct.pack('<I',1)+b'\0'+abc),old.tag(76,struct.pack('<HH',1,0)+b'NeutralSharedRoot\0'),old.tag(35,struct.pack('<HI',1,len(jpeg))+jpeg+zlib.compress(alpha,9)),old.tag(32,shape(size)),old.tag(1)]
  for depth,name,x in [(1,'leftGraphic',32),(2,'rightGraphic',80)]:tags.append(old.tag(26,b'\x26'+struct.pack('<HH',depth,101)+old.matrix(tx=x*20,ty=640)+name.encode()+b'\0'))
  tags += [old.tag(1),old.tag(0)];raw=old.rect(6400,4800)+struct.pack('<HH',24*256,2)+b''.join(tags);swf=b'FWS\x0f'+struct.pack('<I',len(raw)+8)+raw
  filename=f'neutral-jpeg3-{size}-{mode}.swf';(OUT/filename).write_bytes(swf)
  rows.append(dict(file=filename,sha256=sha(swf),bytes=len(swf),width=size,height=size,alpha=mode,alphaSHA256=sha(alpha),jpegSHA256=sha(jpeg),shapePixels=16,bitmapMatrixScale=320/size))
 manifest={'schema':'image-memory-webgl-fixtures-v1','privateInputs':False,'abcSHA256':sha(abc),'abcSource':'experiments/lazy-graphic-engine/fixture-sources/shared-boundaries/as/NeutralSharedRoot.as','states':['ready','shown','redrawn','masked','hit'],'stage':[320,240],'fixtures':rows}
 (OUT/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n');return manifest
if __name__=='__main__':print(json.dumps(generate(),indent=2))

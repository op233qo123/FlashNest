"""Neutral AVM2 root and Loader resource lifetime fixtures. No private input.
Run with pinned Pillow 13.0.0. ABC bindings are checked against compiler provenance.
"""
import hashlib,io,json,pathlib,struct,zlib
from PIL import Image,__version__ as pillow_version
from reference_generate import Bits,rect,matrix,tag
HERE=pathlib.Path(__file__).resolve().parent;OUT=HERE.parent/'fixtures'
def sha(b):return hashlib.sha256(b).hexdigest()
def shape(bitmap_id):
 size=1280;b=Bits();b.put(1,4);b.put(0,4);b.put(0,1);b.put(3,5);b.put(1,5);b.put(0,1);b.put(0,1);b.put(1,1)
 for dx,dy in [(size,0),(0,size),(-size,0),(0,-size)]:
  n=max(abs(dx),abs(dy)).bit_length()+1;b.put(1,1);b.put(1,1);b.put(n-2,4);b.put(0,1);b.put(dy!=0,1);b.put(dy if dy else dx,n)
 b.put(0,6)
 return struct.pack('<H',1000+bitmap_id)+rect(size,size)+b'\x01\x41'+struct.pack('<H',bitmap_id)+matrix(scale=size/512)+b'\0'+b.bytes()
def header(classname):
 abc=(HERE/'abc'/f'{classname}.abc').read_bytes()
 return [tag(69,struct.pack('<I',8)),tag(9,b'\xff\xff\xff'),tag(82,struct.pack('<I',1)+b'\0'+abc),tag(76,struct.pack('<HH',1,0)+classname.encode()+b'\0')]
def image_tags(i):
 rgb=bytes(v for y in range(512) for x in range(512) for v in ((x+i*17)%256,(y+i*29)%256,((x//32+y//32+i)%2)*160+40))
 im=Image.frombytes('RGB',(512,512),rgb);buf=io.BytesIO();im.save(buf,'JPEG',quality=85,subsampling=2,optimize=False,progressive=False);jpg=buf.getvalue()
 return [tag(35,struct.pack('<HI',i,len(jpg))+jpg+zlib.compress(bytes([255])*512*512,9)),tag(32,shape(i))]
def write(name,tags,frames):
 raw=rect(6400,4800)+struct.pack('<HH',24*256,frames)+b''.join(tags+[tag(0)]);data=b'FWS\x0f'+struct.pack('<I',len(raw)+8)+raw;(OUT/name).write_bytes(data)
 return {'file':name,'bytes':len(data),'sha256':sha(data)}
def generate():
 OUT.mkdir(parents=True,exist_ok=True);files=[];cases=[]
 for n,cycles in [(16,4),(64,2)]:
  name=f'root-{n}';tags=header('TextureRoot')
  for i in range(1,n+1):tags+=image_tags(i)
  tags+=[tag(1)]
  for i in range(1,n+1):
   if i>1:tags+=[tag(28,struct.pack('<H',1))]
   tags += [tag(26,b'\x06'+struct.pack('<HH',1,1000+i)+matrix(tx=640,ty=640)),tag(1)]
  files.append(write(name+'.swf',tags,n+1))
  steps=[{'label':'ready','trace':f'TEXTURE_LIFETIME {name} ready','visible':False}]
  steps += [{'label':f'cycle-{c}','trace':f'TEXTURE_LIFETIME {name} cycle={c}','key':'s' if c==1 else 'r','visible':True} for c in range(1,cycles+1)]
  steps += [{'label':'empty','trace':f'TEXTURE_LIFETIME {name} empty','key':'u','visible':False}]
  cases.append({'name':name,'file':name+'.swf','avm':'AVM2','uniqueImages':n,'cycles':cycles,'steps':steps})
 tags=header('TextureChild')+image_tags(1)+[tag(26,b'\x06'+struct.pack('<HH',1,1001)+matrix()),tag(1)]
 files.append(write('texture-child.swf',tags,1))
 for retain in [False,True]:
  name='loader-retain' if retain else 'loader-release';classname='TextureLoaderRetain' if retain else 'TextureLoaderRelease'
  files.append(write(name+'.swf',header(classname)+[tag(1)],1))
  steps=[{'label':'ready','trace':f'TEXTURE_LIFETIME {name} ready','visible':False},{'label':'unloaded-six','trace':f'TEXTURE_LIFETIME {name} complete','key':'s','visible':False},{'label':'retained-rehang','trace':f'TEXTURE_LIFETIME {name} retained={3 if retain else 0}','key':'r','visible':retain},{'label':'dropped','trace':f'TEXTURE_LIFETIME {name} dropped','key':'u','visible':False},{'label':'normal-frames','trace':f'TEXTURE_LIFETIME {name} done','visible':False}]
  cases.append({'name':name,'file':name+'.swf','avm':'AVM2','loadCycles':6,'retainedReferences':3 if retain else 0,'steps':steps})
 manifest={'schema':'neutral-texture-lifetime-v1','privateInputs':False,'pillow':pillow_version,'bitmapSize':[512,512],'shapeSize':[64,64],'stage':[320,240],'fps':24,'files':files,'cases':cases,'limitations':['No forced GC or explicit BitmapData.dispose.','Root definitions remain alive at empty phase until player teardown.','JS deleteTexture requests are not physical GPU release proof.'],'protocol':'Trusted s/r/u keydown drives each stable phase. Root holds each resource four ENTER_FRAME ticks; cycle marker stops progression. Loader shows/unloads six child instances, R reattaches retained3 or0, U drops references then120 normal frames. Loaded and unloaded markers recorded for all6 cycles.'}
 (OUT/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n');return manifest
if __name__=='__main__': print(json.dumps(generate(),indent=2))

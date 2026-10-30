"""Eight tiny public synthetic JPEG3 definitions, no placed bitmap until frame 2."""
import hashlib,json,pathlib,struct,zlib
ROOT=pathlib.Path(__file__).resolve().parent
class Bits:
 def __init__(self):self.bits=''
 def put(self,value,count):self.bits+=format(value & ((1<<count)-1),'0%db'%count) if count else ''
 def bytes(self):
  value=self.bits+'0'*(-len(self.bits)%8)
  return int(value,2).to_bytes(len(value)//8,'big') if value else b''
def rect(xmax,ymax):
 b=Bits();n=max(xmax,ymax).bit_length()+1;b.put(n,5)
 for v in (0,xmax,0,ymax):b.put(v,n)
 return b.bytes()
def matrix(scale=None,tx=0,ty=0):
 b=Bits();b.put(scale is not None,1)
 if scale is not None:
  n=int(scale*65536).bit_length()+1;b.put(n,5);b.put(int(scale*65536),n);b.put(int(scale*65536),n)
 b.put(0,1);n=max(abs(tx),abs(ty)).bit_length()+1 if tx or ty else 0;b.put(n,5);b.put(tx,n);b.put(ty,n)
 return b.bytes()
def tag(code,body=b''):
 return struct.pack('<H',code*64+min(len(body),63))+(struct.pack('<I',len(body)) if len(body)>=63 else b'')+body
def shape(bitmapID):
 b=Bits();b.put(1,4);b.put(0,4) # one fill index bit; no lines
 b.put(0,1);b.put(3,5);b.put(1,5);b.put(0,1);b.put(0,1);b.put(1,1) # move0 and fill0=1
 for dx,dy in [(320,0),(0,320),(-320,0),(0,-320)]:
  n=max(abs(dx),abs(dy)).bit_length()+1;b.put(1,1);b.put(1,1);b.put(n-2,4);b.put(0,1);b.put(dy!=0,1);b.put(dy if dy else dx,n)
 b.put(0,6)
 return struct.pack('<H',100+bitmapID)+rect(320,320)+b'\x01\x41'+struct.pack('<H',bitmapID)+matrix(scale=20)+b'\x00'+b.bytes()
def forward_reference(data):
 # Keep the same compiled root and two-frame input contract, but only one
 # image/shape, in forward-reference order. Root trace numbers are not its oracle.
 pos=8+(5+(data[8]>>3)*4+7)//8+4;tags=[]
 while pos<len(data):
  h=struct.unpack_from('<H',data,pos)[0];pos+=2;code=h>>6;size=h&63
  if size==63:size=struct.unpack_from('<I',data,pos)[0];pos+=4
  tags.append((code,data[pos:pos+size]));pos+=size
 selected=tags[:3]+[tags[4],tags[3]]+tags[-4:]
 raw=rect(6400,4800)+struct.pack('<HH',24*256,2)+b''.join(tag(code,body) for code,body in selected)
 return b'FWS\x0f'+struct.pack('<I',len(raw)+8)+raw
def generate():
 abc=(ROOT/'abc/NeutralGraphicRoot.abc').read_bytes()
 tags=[tag(69,struct.pack('<I',8)),tag(82,struct.pack('<I',1)+b'\0'+abc),tag(76,struct.pack('<HH',1,0)+b'NeutralGraphicRoot\0')]
 imageManifest=[]
 for ident in range(1,9):
  jpeg=(ROOT/'images'/f'{ident}.jpg').read_bytes();alpha=bytes([255])*256
  tags += [tag(35,struct.pack('<HI',ident,len(jpeg))+jpeg+zlib.compress(alpha,9)),tag(32,shape(ident))]
  imageManifest.append({'id':ident,'shapeID':100+ident,'width':16,'height':16,'alphaBytes':256,'alphaValue':255,'jpegSHA256':hashlib.sha256(jpeg).hexdigest()})
 tags += [tag(1),tag(26,b'\x06'+struct.pack('<HH',1,101)+matrix(tx=640,ty=640)),tag(1),tag(0)]
 raw=rect(6400,4800)+struct.pack('<HH',24*256,2)+b''.join(tags)
 data=b'FWS\x0f'+struct.pack('<I',len(raw)+8)+raw
 (ROOT/'neutral-eight-jpeg3.swf').write_bytes(data)
 (ROOT/'neutral-forward-reference.swf').write_bytes(forward_reference(data))
 manifest={'schema':'neutral-eight-jpeg3-v1','bytes':len(data),'sha256':hashlib.sha256(data).hexdigest(),'images':imageManifest,'initialBitmapPlacements':0,'frame2BitmapPlacements':1,'trigger':'one Space keydown (keyCode32); render after timeline advances','privateInputs':False,'pressureTest':False}
 (ROOT/'fixture-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n');return manifest
if __name__=='__main__':print(generate())

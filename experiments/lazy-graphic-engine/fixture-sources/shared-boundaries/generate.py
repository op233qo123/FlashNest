"""Tiny shared shape, redraw, mask and hit-test boundary control."""
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
def generate():
 abc=(ROOT/'abc/NeutralSharedRoot.abc').read_bytes();jpeg=(ROOT/'image.jpg').read_bytes()
 tags=[tag(69,struct.pack('<I',8)),tag(82,struct.pack('<I',1)+b'\0'+abc),tag(76,struct.pack('<HH',1,0)+b'NeutralSharedRoot\0'),tag(35,struct.pack('<HI',1,len(jpeg))+jpeg+zlib.compress(bytes([255])*256,9)),tag(32,shape(1)),tag(1)]
 for depth,name,x in [(1,'leftGraphic',32),(2,'rightGraphic',80)]:
  tags.append(tag(26,b'\x26'+struct.pack('<HH',depth,101)+matrix(tx=x*20,ty=640)+name.encode()+b'\0'))
 tags += [tag(1),tag(0)]
 raw=rect(6400,4800)+struct.pack('<HH',24*256,2)+b''.join(tags)
 data=b'FWS\x0f'+struct.pack('<I',len(raw)+8)+raw
 (ROOT/'neutral-shared-boundaries.swf').write_bytes(data)
 manifest={'schema':'neutral-shared-boundaries-v1','bytes':len(data),'sha256':hashlib.sha256(data).hexdigest(),'imageID':1,'shapeID':101,'imageSize':[16,16],'placements':[[32,32],[80,32]],'keys':['S','R','M','H'],'stage':[320,240],'backgroundRGBA':[255,255,255,255],'maskRectangle':[32,32,8,16],'insideHit':[84,36],'outsideHit':[100,36],'rendererCounts':'must observe, not assumed','originalEightImageFixtureUnchanged':True}
 (ROOT/'fixture-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n');return manifest
if __name__=='__main__':print(generate())

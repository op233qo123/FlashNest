#!/usr/bin/env python3
"""Original AVM1 diagnostic assembler, not a general AS compiler; no game assets."""
import hashlib,json,struct
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
MODES=('showAll','noBorder','exactFit','noScale')
ALIGNS=('', 'T','B','L','R','TL','TR','BL','BR')
def action(op,data=b''):
    return bytes([op])+(struct.pack('<H',len(data))+data if op>=128 else data)
def string(s): return action(0x96,b'\0'+s.encode()+b'\0')
def integer(n): return action(0x96,b'\x07'+struct.pack('<i',n))
def var(s): return string(s)+action(0x1c)
def member(obj,s): return obj+string(s)+action(0x4e)
def setmember(obj,s,value): return obj+string(s)+value+action(0x4f)
def call(obj,s,*args): return b''.join(reversed(args))+integer(len(args))+obj+string(s)+action(0x52)
def discard(code): return code+action(0x17)
def trace(label,*values):
    code=string('DENSITY|'+label)
    for value in values: code+=string('|')+action(0x47)+value+action(0x47)
    return code+action(0x26)
def function(code):
    body=code+b'\0'
    # DefineFunction ActionLength excludes its separately sized code body.
    return action(0x9b,b'\0'+struct.pack('<HH',0,len(body)))+body
def tag(n,b=b''):
    return struct.pack('<H',n<<6|min(len(b),63))+(struct.pack('<I',len(b)) if len(b)>=63 else b'')+b
def rect():
    bits='01110'+''.join(format(x,'014b') for x in (0,6400,0,4800));bits+='0'*(-len(bits)%8)
    return int(bits,2).to_bytes(len(bits)//8,'big')
def movie(mode,align,quality=None):
    root=var('_root');stage=var('Stage');box=member(root,'target')
    code=setmember(stage,'scaleMode',string(mode))+setmember(stage,'align',string(align))
    if quality is not None: code+=setmember(root,'_quality',string(quality))
    code+=discard(call(root,'createEmptyMovieClip',string('target'),integer(1)))
    code+=setmember(box,'_x',integer(100))+setmember(box,'_y',integer(70))
    code+=discard(call(box,'beginFill',integer(0x19ab75),integer(100)))
    for name,x,y in [('moveTo',0,0),('lineTo',120,0),('lineTo',120,100),('lineTo',0,100),('lineTo',0,0)]:
        code+=discard(call(box,name,integer(x),integer(y)))
    code+=discard(call(box,'endFill'))
    x=member(root,'_xmouse');y=member(root,'_ymouse')
    hit=call(box,'hitTest',x,y) # shape's bounds, stage coordinates
    metadata=(member(stage,'width'),member(stage,'height'),member(stage,'scaleMode'),member(stage,'align'))
    # Trace all clicks, including misses; drag only when the vector bounds hit.
    drag=discard(call(box,'startDrag'))
    down=trace('DOWN',x,y,hit,*metadata)+hit+action(0x12)+action(0x9d,struct.pack('<h',len(drag)))+drag
    # v2: retain motion/UP evidence before deterministic reset for cross-arm pixels.
    count=member(root,'moveCount')
    code+=setmember(root,'moveCount',integer(0))
    move=setmember(root,'moveCount',count+integer(1)+action(0x47))
    code+=setmember(root,'onMouseMove',function(move))
    up=discard(call(box,'stopDrag'))+trace('UP',x,y,member(box,'_x'),member(box,'_y'),*metadata)
    up+=trace('MOTION',count,x,y,member(box,'_x'),member(box,'_y'))
    up+=setmember(box,'_x',integer(100))+setmember(box,'_y',integer(70))+setmember(root,'moveCount',integer(0))
    up+=trace('RESET',member(box,'_x'),member(box,'_y'))
    code+=setmember(root,'onMouseDown',function(down))+setmember(root,'onMouseUp',function(up))
    code+=setmember(root,'onResize',function(trace('RESIZE',*metadata)))
    code+=discard(call(stage,'addListener',root))+trace('READY',*metadata)+action(0x07)
    body=rect()+struct.pack('<HH',24*256,1)+tag(9,bytes([29,39,58]))+tag(12,code+b'\0')+tag(1)+tag(0)
    return b'FWS\x07'+struct.pack('<I',len(body)+8)+body

def main():
    out=ROOT/'fixtures';out.mkdir(exist_ok=True)
    manifest={'contract':'flashnest-native-sampling-v2','resetAfterUpTrace':True,'original':True,'stage':[320,240],'files':{}}
    for mode, quality, name in [('showAll',None,'showAll-center.swf'),('noScale',None,'noScale-center.swf')]:
        data=movie(mode,'',quality)
        (out/name).write_bytes(data)
        manifest['files'][name]={'mode':mode,'align':'','fixtureQuality':quality,'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()}
    (out/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
if __name__=='__main__':main()

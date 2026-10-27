#!/usr/bin/env python3
"""Original AVM2 SharedObject regression; no user save/game data or Adobe compiler."""
import hashlib,importlib.util,json,struct
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('original_abc',ROOT/'experiments/frame-order/make_fixtures.py')
f=importlib.util.module_from_spec(spec);spec.loader.exec_module(f)
def make(writer):
 a=f.ABC();this=b'\xd0';header=b'\xd0\x30';end=b'\x47'
 ctor=a.method('RawSaveFixture$iinit',header+this+a.op(0x49,0)+a.call(this,'addFrameScript',a.push(0),this+a.prop('frame1'))+end)
 get=a.op(0x60,a.qname('SharedObject','flash.net'))+a.push('FlashNestFixture')+a.push('/')+a.op(0x46,a.qname('getLocal'),2)
 save=this+a.prop('save');data=save+a.prop('data')
 code=header+this+get+a.op(0x61,a.qname('save'))
 code+=a.trace('RAW_SOL_BEFORE',data+a.prop('progress'))
 if writer:
  code+=data+a.push(42)+a.op(0x61,a.qname('progress'))+a.call(save,'flush')
 code+=a.trace('RAW_SOL_READY')+a.call(this,'stop')+end
 frame=a.method('RawSaveFixture$frame1',code);a.class_('RawSaveFixture',ctor,[('frame1',frame)])
 ancestors=[('Object',''),('EventDispatcher','flash.events'),('DisplayObject','flash.display'),('InteractiveObject','flash.display'),('DisplayObjectContainer','flash.display'),('Sprite','flash.display'),('MovieClip','flash.display')]
 script=header+b'\x65\x00'
 for name,package in ancestors:script+=a.op(0x60,a.qname(name,package))+b'\x30'
 script+=a.op(0x60,a.qname('MovieClip','flash.display'))+a.op(0x58,0)+b'\x1d'*7+a.op(0x68,a.instances[0]['name'])+end
 a.scripts.append(a.method('rawsave$script',script,scope=0))
 tags=f.tag(69,struct.pack('<I',8))+f.tag(9,bytes([32,55,75]))
 tags+=f.tag(82,struct.pack('<I',0)+b'original-raw-save\0'+a.serialize())
 tags+=f.tag(76,struct.pack('<HH',1,0)+b'RawSaveFixture\0')+f.tag(1)+f.tag(0)
 body=f.rect(320,240)+struct.pack('<HH',24*256,1)+tags
 return b'FWS\x25'+struct.pack('<I',len(body)+8)+body

def main():
 out=ROOT/'fixtures/raw-sol';out.mkdir(exist_ok=True);manifest={}
 for name,writer in [('writer.swf',True),('reader.swf',False)]:
  data=make(writer);(out/name).write_bytes(data);manifest[name]={'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()}
 name=b'FlashNestFixture';body=b'\x11progress\x04\x07\0'
 tail=b'TCSO\x00\x04\x00\x00\x00\x00'+struct.pack('>H',len(name))+name+b'\0\0\0\3'+body
 data=b'\x00\xbf'+struct.pack('>I',len(tail))+tail;(out/'original-progress-7.sol').write_bytes(data)
 manifest['original-progress-7.sol']={'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()}
 (out/'manifest.json').write_text(json.dumps({'original':True,'files':manifest},indent=2)+'\n')
 (out/'README.txt').write_text('Original synthetic AVM2 SWF37 writer/reader: SharedObject.getLocal("FlashNestFixture", "/"), trace RAW_SOL_BEFORE value and RAW_SOL_READY; writer sets progress42 and calls flush. Original AMF3 SOL sets progress7. No user/game data. Source scripts/make_raw_sol_fixtures.py uses existing original ABC assembler.\n')
if __name__=='__main__':main()

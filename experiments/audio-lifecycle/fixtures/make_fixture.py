#!/usr/bin/env python3
"""Original silent AVM2 heartbeat/vector fixture. No compiler or game input."""
from pathlib import Path
import hashlib,json,struct
import abc_subset as f
ROOT=Path(__file__).resolve().parent
HELPER='d8d7f30cc2edc06fda039f0d57fc8b8e38126b5f98d0b6b7b82e0de464de6701'

def make():
 a=f.ABC();this=b'\xd0';head=b'\xd0\x30';end=b'\x47'
 p=lambda name:this+a.prop(name)
 set_=lambda name,value:this+value+a.op(0x61,a.qname(name))
 ctor=a.method('AudioLifecycleRoot$iinit',head+this+a.op(0x49,0)+a.call(this,'addFrameScript',a.push(0),p('frame1'))+end)
 g=p('graphics')
 setup=head+set_('beats',a.push(0))+a.call(g,'beginFill',a.push(str(0x336699)))+a.call(g,'drawRect',a.push(0),a.push(0),a.op(0x25,320),a.op(0x25,240))+a.call(g,'endFill')
 setup+=a.call(this,'addEventListener',a.push('enterFrame'),p('onTick'))+a.trace('AL_READY')+a.call(this,'stop')+end
 frame=a.method('AudioLifecycleRoot$frame1',setup)
 tick=head+set_('beats',p('beats')+a.push(1)+b'\xc5')
 marker=a.trace('AL_ACTIVE')
 tick+=marker+end
 tickid=a.method('AudioLifecycleRoot$onTick',tick,args=1)
 a.class_('AudioLifecycleRoot',ctor,[('frame1',frame),('onTick',tickid)])
 ancestors=[('Object',''),('EventDispatcher','flash.events'),('DisplayObject','flash.display'),('InteractiveObject','flash.display'),('DisplayObjectContainer','flash.display'),('Sprite','flash.display'),('MovieClip','flash.display')]
 script=head+b'\x65\x00'
 for name,pkg in ancestors:script+=a.op(0x60,a.qname(name,pkg))+b'\x30'
 script+=a.op(0x60,a.qname('MovieClip','flash.display'))+a.op(0x58,0)+b'\x1d'*7+a.op(0x68,a.instances[0]['name'])+end
 a.scripts.append(a.method('audiofixture$script',script,scope=0))
 tags=f.tag(69,struct.pack('<I',8))+f.tag(9,bytes([0x33,0x66,0x99]))+f.tag(82,struct.pack('<I',0)+b'original-audio-lifecycle\0'+a.serialize())
 tags+=f.tag(76,struct.pack('<HH',1,0)+b'AudioLifecycleRoot\0')+f.tag(1)+f.tag(0)
 body=f.rect(320,240)+struct.pack('<HH',24*256,1)+tags
 return b'FWS\x25'+struct.pack('<I',len(body)+8)+body
if __name__=='__main__':
 assert hashlib.sha256((ROOT/'abc_subset.py').read_bytes()).hexdigest()==HELPER
 data=make();(ROOT/'silent.swf').write_bytes(data)
 m={'schemaVersion':1,'provenance':'Original AVM2 vector/heartbeat only; no sound tags, network, storage, game assets or compiler','swfVersion':37,'runtimeExecuted':False,'adobeReferenceExecuted':False,'abcHelperSha256':HELPER,'files':{'silent.swf':{'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()}}}
 (ROOT/'manifest.json').write_text(json.dumps(m,indent=2)+'\n');print(json.dumps(m,indent=2))

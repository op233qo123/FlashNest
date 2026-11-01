#!/usr/bin/env python3
"""Original neutral Loader reentrancy fixture, no private-game input. UNRUN runtime."""
import sys, struct, hashlib, json
from pathlib import Path
from abc_fixture import ABC, tag, rect

OUT=Path(__file__).resolve().parent/'fixtures'

def wrap(a,name):
    script=b'\xd0\x30\x65\x00'
    for n,p in [('Object',''),('EventDispatcher','flash.events'),('DisplayObject','flash.display'),('InteractiveObject','flash.display'),('DisplayObjectContainer','flash.display'),('Sprite','flash.display'),('MovieClip','flash.display')]:
        script+=a.op(0x60,a.qname(n,p))+b'\x30'
    script+=a.op(0x60,a.qname('MovieClip','flash.display'))+a.op(0x58,0)+b'\x1d'*7+a.op(0x68,a.instances[0]['name'])+b'\x47'
    a.scripts.append(a.method('probe$script',script,scope=0))
    tags=tag(69,struct.pack('<I',8))+tag(9,b'\x20\x30\x40')
    tags+=tag(82,struct.pack('<I',0)+b'neutral-loader-chain\0'+a.serialize())
    tags+=tag(76,struct.pack('<HH',1,0)+name.encode()+b'\0')+tag(1)+tag(0)
    body=rect(160,120)+struct.pack('<HH',24*256,1)+tags
    return b'FWS'+bytes([37])+struct.pack('<I',len(body)+8)+body

def child(label):
    a=ABC(); g=b'\xd0'+a.prop('graphics')
    color=127 if label=='FIRST_CHILD_CONSTRUCTED' else 32512
    drawing=a.call(g,'beginFill',a.op(0x25,color))+a.call(g,'drawRect',a.push(0),a.push(0),a.push(120),a.push(90))+a.call(g,'endFill')
    ctor=a.method('Child$iinit',b'\xd0\x30\xd0'+a.op(0x49,0)+drawing+a.trace(label)+b'\x47')
    a.class_('Child',ctor,[]);return wrap(a,'Child')

def root(variant):
    assert variant in ('attached-control','moved-removed')
    a=ABC();t=b'\xd0';h=b'\xd0\x30';end=b'\x47'
    loader=lambda:t+a.prop('loader')
    moved=lambda:t+a.prop('moved')
    holder=lambda:t+a.prop('holder')
    info=lambda:loader()+a.prop('contentLoaderInfo')
    equal=lambda left,right:left+right+b'\xac'
    def construct(name,package,*args):
        q=a.qname(name,package)
        return a.op(0x5d,q)+b''.join(args)+a.op(0x4a,q,len(args))
    def load(url):
        return a.trace('REQUEST',a.push(url))+a.call(loader(),'load',construct('URLRequest','flash.net',a.push(url)))
    def install():
        code=t+construct('Loader','flash.display')+a.op(0x61,a.qname('loader'))
        for event,handler in [('init','onInit'),('complete','onComplete'),('unload','onUnload'),('ioError','onError'),('securityError','onError')]:
            code+=a.call(info(),'addEventListener',a.push(event),t+a.prop(handler))
        return code
    ctor=a.method('Main$iinit',h+t+a.op(0x49,0)+t+b'\x27'+a.op(0x61,a.qname('started'))
        +a.trace('VARIANT:'+variant)+install()+a.call(t,'addChild',loader())+load('first.swf')+end)
    first=t+b'\x26'+a.op(0x61,a.qname('started'))+a.trace('FIRST_COMPLETE')
    first+=t+loader()+a.prop('content')+a.op(0x61,a.qname('moved'))
    first+=a.trace('PRE_CONTENT_PARENT_LOADER',equal(moved()+a.prop('parent'),loader()))
    first+=a.trace('PRE_CONTENT_INFO_MATCH',equal(moved()+a.prop('loaderInfo'),info()))
    if variant=='moved-removed':
        first+=t+construct('Sprite','flash.display')+a.op(0x61,a.qname('holder'))
        first+=a.call(t,'addChild',holder())+a.call(holder(),'addChild',moved())
        first+=a.trace('PRE_CONTENT_PARENT_HOLDER',equal(moved()+a.prop('parent'),holder()))
    first+=a.call(t,'addEventListener',a.push('enterFrame'),t+a.prop('onTransition'))+end
    complete=a.method('Main$onComplete',h+a.trace('COMPLETE_INFO_MATCH',equal(b'\xd1'+a.prop('currentTarget'),info()))+t+a.prop('started')+b'\x11'+len(first).to_bytes(3,'little',signed=True)+first+a.trace('NEXT_COMPLETE')+end,args=1)
    transition=h+a.call(t,'removeEventListener',a.push('enterFrame'),t+a.prop('onTransition'))+a.trace('TRANSITION_ENTER_FRAME')
    if variant=='moved-removed':
        transition+=a.call(moved(),'stop')+a.call(holder(),'removeChild',moved())
        transition+=a.trace('PRE_MOVED_PARENT_NULL',equal(moved()+a.prop('parent'),b'\x20'))
        transition+=a.trace('PRE_HOLDER_EMPTY',equal(holder()+a.prop('numChildren'),a.push(0)))
    else:
        transition+=a.trace('PRE_ATTACHED_CONTENT_PARENT_LOADER',equal(moved()+a.prop('parent'),loader()))
    transition+=a.call(t,'removeChild',loader())+a.trace('PRE_LOADER_PARENT_NULL',equal(loader()+a.prop('parent'),b'\x20'))
    transition+=a.trace('UNLOAD_CALL_BEGIN')+a.call(loader(),'unloadAndStop')+a.trace('UNLOAD_CALL_RETURNED')+end
    unload_code=h+a.trace('UNLOAD_BEGIN')+a.call(info(),'removeEventListener',a.push('unload'),t+a.prop('onUnload'))
    unload_code+=a.trace('UNLOAD_LISTENER_REMOVED')+a.call(t,'startNext')+a.trace('UNLOAD_END')+end
    unload=a.method('Main$onUnload',unload_code,args=1)
    next_method=a.method('Main$startNext',h+a.trace('NEXT_BEGIN')+install()+a.trace('FRESH_LOADER_CREATED')+a.call(t,'addChild',loader())+load('next.swf')+a.trace('NEXT_LOAD_RETURNED')+end)
    init=a.method('Main$onInit',h+a.trace('INIT_INFO_MATCH',equal(b'\xd1'+a.prop('currentTarget'),info()))+a.trace('INIT')+end,args=1)
    error=a.method('Main$onError',h+a.trace('LOAD_ERROR',b'\xd1'+a.prop('text'))+end,args=1)
    a.class_('Main',ctor,[('onComplete',complete),('onUnload',unload),('startNext',next_method),('onInit',init),('onError',error),('onTransition',a.method('Main$onTransition',transition,args=1))])
    return wrap(a,'Main')

if __name__=='__main__':
    OUT.mkdir(exist_ok=True)
    files={'first.swf':child('FIRST_CHILD_CONSTRUCTED'),'next.swf':child('NEXT_CHILD_CONSTRUCTED')}
    files.update({v+'.swf':root(v) for v in ('attached-control','moved-removed')})
    receipt={'runtimeExecuted':False,'privateGameInputs':False,'files':{}}
    for n,b in files.items():
        (OUT/n).write_bytes(b);receipt['files'][n]={'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest()}
    (OUT/'manifest.json').write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps(receipt,indent=2))

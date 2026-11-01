#!/usr/bin/env python3
"""Original neutral Loader reentrancy fixture, no private-game input. Focused engine regression input."""
import sys, struct, hashlib, json, zlib
from pathlib import Path
from abc_fixture import ABC, tag, rect

OUT=Path(__file__).resolve().parent/'fixtures'

def bit_bytes(parts):
    bits=''.join(parts);bits+='0'*(-len(bits)%8);return int(bits,2).to_bytes(len(bits)//8,'big')

def bitmap_shape_tags(next_child=False):
    # Original 16x16 opaque ARGB, no external image input.
    pixels=bytes([255,30,60,230] if next_child else [255,230,30,90])*256
    bitmap=tag(36,struct.pack('<HBHH',1,5,16,16)+zlib.compress(pixels))
    matrix=bit_bytes(['1',format(22,'05b'),format(20*65536,'022b')*2,'0','00000'])
    edges=['0','00101','00001','0','0','1']  # Move(0,0), FillStyle1=1.
    for vertical,delta in [(False,320),(True,320),(False,-320),(True,-320)]:
        edges+=['1','1','1000','0','1' if vertical else '0',format(delta & 1023,'010b')]
    edges+=['000000']
    shape=struct.pack('<H',2)+rect(16,16)+b'\x01\x41'+struct.pack('<H',1)+matrix+b'\x00\x10'+bit_bytes(edges)
    return bitmap+tag(32,shape),tag(26,b'\x06'+struct.pack('<HH',1,2)+b'\x00')

def wrap(a,name,static_bitmap=False,next_child=False):
    script=b'\xd0\x30\x65\x00'
    for n,p in [('Object',''),('EventDispatcher','flash.events'),('DisplayObject','flash.display'),('InteractiveObject','flash.display'),('DisplayObjectContainer','flash.display'),('Sprite','flash.display'),('MovieClip','flash.display')]:
        script+=a.op(0x60,a.qname(n,p))+b'\x30'
    script+=a.op(0x60,a.qname('MovieClip','flash.display'))+a.op(0x58,0)+b'\x1d'*7+a.op(0x68,a.instances[0]['name'])+b'\x47'
    a.scripts.append(a.method('probe$script',script,scope=0))
    tags=tag(69,struct.pack('<I',8))+tag(9,b'\x20\x30\x40')
    placement=b''
    if static_bitmap:
        definitions,placement=bitmap_shape_tags(next_child);tags+=definitions
    tags+=tag(82,struct.pack('<I',0)+b'neutral-loader-chain\0'+a.serialize())
    tags+=tag(76,struct.pack('<HH',1,0)+name.encode()+b'\0')+placement+tag(1)+tag(0)
    body=rect(160,120)+struct.pack('<HH',24*256,1)+tags
    return b'FWS'+bytes([37])+struct.pack('<I',len(body)+8)+body

def child(label):
    a=ABC(); g=b'\xd0'+a.prop('graphics')
    color=127 if label=='FIRST_CHILD_CONSTRUCTED' else 32512
    drawing=a.call(g,'beginFill',a.op(0x25,color))+a.call(g,'drawRect',a.push(0),a.push(0),a.push(120),a.push(90))+a.call(g,'endFill')
    ctor=a.method('Child$iinit',b'\xd0\x30\xd0'+a.op(0x49,0)+b'\xd0'+a.push(37 if label=='FIRST_CHILD_CONSTRUCTED' else 74)+a.op(0x61,a.qname('token'))+drawing+a.trace(label)+b'\x47')
    a.class_('Child',ctor,[]);return wrap(a,'Child',static_bitmap=True,next_child=label=='NEXT_CHILD_CONSTRUCTED')

MODES=('attached-fresh','moved-removed-fresh','moved-kept-fresh','attached-same','moved-removed-same','recursive-unload','repeated-unload','no-load','incomplete-load','failed-load','retained-script','added-before-init')

def root(mode):
    assert mode in MODES
    a=ABC();t=b'\xd0';h=b'\xd0\x30';end=b'\x47'
    get=lambda name:t+a.prop(name)
    loader=lambda:get('loader');info=lambda:loader()+a.prop('contentLoaderInfo');held=lambda:get('held')
    eq=lambda left,right:left+right+b'\xac'
    set_=lambda name,value:t+value+a.op(0x61,a.qname(name))
    def construct(name,package,*args):
        q=a.qname(name,package);return a.op(0x5d,q)+b''.join(args)+a.op(0x4a,q,len(args))
    def load(url):return a.trace('REQUEST',a.push(url))+a.call(loader(),'load',construct('URLRequest','flash.net',a.push(url)))
    def install():
        code=set_('loader',construct('Loader','flash.display'))
        for event,handler in [('init','onInit'),('complete','onComplete'),('unload','onUnload'),('ioError','onError'),('securityError','onError')]:
            code+=a.call(info(),'addEventListener',a.push(event),get(handler))
        return code
    ctor=h+t+a.op(0x49,0)+set_('started',b'\x27')+set_('nestedOnce',b'\x27')+a.trace('MODE:'+mode)+install()+a.call(t,'addChild',loader())
    if mode=='added-before-init':ctor+=a.call(loader(),'addEventListener',a.push('added'),get('onAdded'))
    if mode=='no-load':ctor+=a.trace('UNLOAD_CALL_BEGIN')+a.call(loader(),'unloadAndStop')+a.trace('UNLOAD_CALL_RETURNED')
    elif mode=='incomplete-load':ctor+=load('delayed-first.swf')+a.trace('UNLOAD_CALL_BEGIN')+a.call(loader(),'unloadAndStop')+a.trace('UNLOAD_CALL_RETURNED')
    elif mode=='failed-load':ctor+=load('missing.swf')
    else:ctor+=load('first.swf')
    ctor=a.method('Main$iinit',ctor+end)
    first=set_('started',b'\x26')+a.trace('FIRST_COMPLETE')+set_('held',loader()+a.prop('content'))
    first+=a.trace('PRE_CONTENT_PARENT_LOADER',eq(held()+a.prop('parent'),loader()))+a.trace('PRE_CONTENT_INFO_MATCH',eq(held()+a.prop('loaderInfo'),info()))+a.trace('PRE_FIRST_TOKEN',eq(held()+a.prop('token'),a.push(37)))
    if mode.startswith('moved-'):
        first+=set_('holder',construct('Sprite','flash.display'))+a.call(t,'addChild',get('holder'))+a.call(get('holder'),'addChild',held())
        first+=a.trace('PRE_CONTENT_PARENT_HOLDER',eq(held()+a.prop('parent'),get('holder')))
        if mode.startswith('moved-kept'):first+=get('holder')+a.op(0x25,128)+a.op(0x61,a.qname('x'))
    first+=a.call(t,'addEventListener',a.push('enterFrame'),get('onTransition'))+end
    next_=set_('nextCaptured',b'\xd1'+a.prop('currentTarget')+a.prop('content'))+a.trace('NEXT_COMPLETE')+a.trace('NEXT_CONTENT_PRESENT',eq(loader()+a.prop('content'),b'\x20')+b'\x96')
    # A named null-content observation returns without manufacturing an AVM2 error.
    next_+=eq(loader()+a.prop('content'),b'\x20')+b'\x12'+(1).to_bytes(3,'little',signed=True)+end
    next_+=a.trace('NEXT_PARENT_LOADER',eq(loader()+a.prop('content')+a.prop('parent'),loader()))
    next_+=a.trace('NEXT_INFO_MATCH',eq(loader()+a.prop('content')+a.prop('loaderInfo'),info()))
    next_+=a.trace('NEXT_LOADER_CONTENT_MATCH',eq(loader()+a.prop('content'),get('nextCaptured')))
    next_+=a.trace('NEXT_CHILD_COUNT_ONE',eq(loader()+a.prop('numChildren'),a.push(1)))
    next_+=a.trace('OLD_CHILD_NOT_IN_LOADER',eq(held()+a.prop('parent'),loader())+b'\x96')
    next_+=a.trace('NEXT_TOKEN',eq(loader()+a.prop('content')+a.prop('token'),a.push(74)))+end
    complete=a.method('Main$onComplete',h+a.trace('COMPLETE_INFO_MATCH',eq(b'\xd1'+a.prop('currentTarget'),info()))+get('started')+b'\x11'+len(first).to_bytes(3,'little',signed=True)+first+next_,args=1)
    transition=h+a.call(t,'removeEventListener',a.push('enterFrame'),get('onTransition'))+a.trace('TRANSITION_ENTER_FRAME')
    if mode.startswith('moved-removed'):
        transition+=a.call(held(),'stop')+a.call(get('holder'),'removeChild',held())+a.trace('PRE_MOVED_PARENT_NULL',eq(held()+a.prop('parent'),b'\x20'))
    elif mode.startswith('moved-kept'):
        transition+=a.trace('PRE_MOVED_PARENT_HOLDER',eq(held()+a.prop('parent'),get('holder')))
    else:transition+=a.trace('PRE_ATTACHED_CONTENT_PARENT_LOADER',eq(held()+a.prop('parent'),loader()))
    transition+=a.call(t,'removeChild',loader())+a.trace('PRE_LOADER_PARENT_NULL',eq(loader()+a.prop('parent'),b'\x20'))
    transition+=a.trace('UNLOAD_CALL_BEGIN')+a.call(loader(),'unloadAndStop')+a.trace('UNLOAD_CALL_RETURNED')
    if mode=='repeated-unload':transition+=a.trace('SECOND_UNLOAD_BEGIN')+a.call(loader(),'unloadAndStop')+a.trace('SECOND_UNLOAD_RETURNED')
    if mode=='retained-script':
        transition+=a.trace('RETAINED_TOKEN',eq(held()+a.prop('token'),a.push(37)))+a.call(held(),'stop')+a.call(t,'addChild',held())+a.trace('RETAINED_REATTACHED',eq(held()+a.prop('parent'),t))
        transition+=a.call(held()+a.prop('graphics'),'drawRect',a.push(4),a.push(4),a.push(8),a.push(8))+a.trace('RETAINED_GRAPHICS_CALL_RETURNED')
    if mode.startswith('moved-kept'):
        transition+=a.trace('MOVED_KEPT_PARENT_PRESERVED',eq(held()+a.prop('parent'),get('holder')))
    transition+=end
    unload=h+a.trace('UNLOAD_BEGIN')+a.trace('UNLOAD_INFO_MATCH',eq(b'\xd1'+a.prop('currentTarget'),info()))+a.trace('UNLOAD_CONTENT_IS_HELD',eq(b'\xd1'+a.prop('currentTarget')+a.prop('content'),held()))
    if mode=='recursive-unload':
        nested=set_('nestedOnce',b'\x26')+a.trace('NESTED_UNLOAD_BEGIN')+a.call(loader(),'unloadAndStop')+a.trace('NESTED_UNLOAD_RETURNED')
        unload+=get('nestedOnce')+b'\x11'+len(nested).to_bytes(3,'little',signed=True)+nested
    if mode.endswith(('-fresh','-same')):
        unload+=a.call(info(),'removeEventListener',a.push('unload'),get('onUnload'))+a.trace('UNLOAD_LISTENER_REMOVED')+a.call(t,'startNext')
    unload+=a.trace('UNLOAD_END')+end
    next_code=h+a.trace('NEXT_BEGIN')
    if mode.endswith('-fresh'):next_code+=install()+a.trace('FRESH_LOADER_CREATED')
    else:next_code+=a.trace('SAME_LOADER_REUSED')
    next_code+=a.call(t,'addChild',loader())+load('next.swf')+a.trace('NEXT_LOAD_RETURNED')+end
    init=a.method('Main$onInit',h+a.trace('INIT_INFO_MATCH',eq(b'\xd1'+a.prop('currentTarget'),info()))+a.trace('INIT')+end,args=1)
    error=h+a.trace('LOAD_ERROR',b'\xd1'+a.prop('text'))
    if mode=='failed-load':error+=a.trace('FAILED_LOAD_OBSERVED')+a.trace('UNLOAD_CALL_BEGIN')+a.call(loader(),'unloadAndStop')+a.trace('UNLOAD_CALL_RETURNED')
    error+=end
    added=h
    added_body=set_('held',b'\xd1'+a.prop('target'))+a.trace('PRE_ADDED_TARGET_PARENT_LOADER',eq(held()+a.prop('parent'),loader()))+a.trace('ADDED_BEFORE_UNLOAD')+a.trace('UNLOAD_CALL_BEGIN')+a.call(loader(),'unloadAndStop')+a.trace('UNLOAD_CALL_RETURNED')
    added+=eq(b'\xd1'+a.prop('target')+a.prop('parent'),loader())+b'\x12'+len(added_body).to_bytes(3,'little',signed=True)+added_body+end
    a.class_('Main',ctor,[('onAdded',a.method('Main$onAdded',added,args=1)),('onComplete',complete),('onUnload',a.method('Main$onUnload',unload,args=1)),('startNext',a.method('Main$startNext',next_code)),('onInit',init),('onError',a.method('Main$onError',error,args=1)),('onTransition',a.method('Main$onTransition',transition,args=1))])
    return wrap(a,'Main')

def fixtures():
    files={'first.swf':child('FIRST_CHILD_CONSTRUCTED'),'next.swf':child('NEXT_CHILD_CONSTRUCTED')}
    files.update({mode+'.swf':root(mode) for mode in MODES});return files
if __name__=='__main__':
    OUT.mkdir(exist_ok=True)
    manifest={}
    for name,data in fixtures().items():(OUT/name).write_bytes(data);manifest[name]={'sha256':hashlib.sha256(data).hexdigest(),'bytes':len(data)}
    print(json.dumps(manifest,indent=2))

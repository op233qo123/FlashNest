"""Neutral original AS3 fixture, uses documented local ABC assembler, no game assets."""
import struct
from pathlib import Path
from mouse_probe_abc import ABC, tag, rect

def fixture():
    a = ABC()
    t, h, end = b'\xd0', b'\xd0\x30', b'\x47'
    get = lambda n: t + a.prop(n)
    set_ = lambda n, v: t + v + a.op(0x61, a.qname(n))
    # Full-stage colored interactive surface: works before any hover/frame warm-up.
    drawing = a.call(get('graphics'), 'beginFill', a.push(100))
    drawing += a.call(get('graphics'), 'drawRect', a.push(0), a.push(0), a.op(0x25,320), a.op(0x25,240))
    drawing += a.call(get('graphics'), 'endFill')
    events = ['mouseDown','mouseUp','click','rightMouseDown','rightMouseUp','rightClick']
    ctor = h+t+a.op(0x49,0)+drawing+set_('pressed',b'\x27')
    methods=[]
    for event in events:
        name='on_'+event
        code=h+a.trace('EVENT:'+event)
        if event=='mouseDown': code+=set_('pressed',b'\x26')
        if event=='mouseUp': code+=set_('pressed',b'\x27')
        methods.append((name,a.method(name,code+end,args=1)))
        ctor+=a.call(t,'addEventListener',a.push(event),get(name))
    # Records whether a game using enterFrame ever observes the button held.
    frame=h+a.trace('FRAME_PRESSED',get('pressed'))+end
    methods.append(('onFrame',a.method('onFrame',frame,args=1)))
    ctor+=a.call(t,'addEventListener',a.push('enterFrame'),get('onFrame'))+a.trace('READY')+end
    a.class_('MouseProbe',a.method('MouseProbe$iinit',ctor),methods)
    script=h+b'\x65\x00'
    for n,p in [('Object',''),('EventDispatcher','flash.events'),('DisplayObject','flash.display'),('InteractiveObject','flash.display'),('DisplayObjectContainer','flash.display'),('Sprite','flash.display'),('MovieClip','flash.display')]:
        script+=a.op(0x60,a.qname(n,p))+b'\x30'
    script+=a.op(0x60,a.qname('MovieClip','flash.display'))+a.op(0x58,0)+b'\x1d'*7+a.op(0x68,a.instances[0]['name'])+end
    a.scripts.append(a.method('MouseProbe$script',script,scope=0))
    tags=tag(69,struct.pack('<I',8))+tag(9,b'\x20\x30\x40')
    tags+=tag(82,struct.pack('<I',0)+b'neutral-mouse-events\0'+a.serialize())
    tags+=tag(76,struct.pack('<HH',1,0)+b'MouseProbe\0')+tag(1)+tag(0)
    body=rect(320,240)+struct.pack('<HH',30*256,1)+tags
    return b'FWS'+bytes([37])+struct.pack('<I',len(body)+8)+body

if __name__=='__main__':
    Path(__file__).with_name('mouse-probe.swf').write_bytes(fixture())

#!/usr/bin/env python3
"""Original bounded SWF37 Loader transition diagnostics. No compiler/game input."""
import hashlib
import json
import struct
from pathlib import Path
import abc_subset as f

ROOT = Path(__file__).resolve().parent
PIN = '89a7049965f3090e706265670df309a5128233ac'
HELPER_SHA = '41a549bf200bac3bb97d55273d36da8bd6311ca3ed6922979d0faa6865843fef'
FIELDS = ['generation', 'rootHeartbeat', 'pointerCount', 'keyCount', 'ready', 'observedChildGeneration', 'observedChildHeartbeat', 'errors', 'unloadCalls', 'unloadEvents']

class Code:
    def __init__(self): self.a = f.ABC(); self.this = b'\xd0'; self.header = b'\xd0\x30'; self.end = b'\x47'; self.methods = []
    def n(self, x):
        assert -1 <= x <= 32767
        return b'\x24\xff' if x == -1 else self.a.op(0x25, x)
    def p(self, name): return self.this + self.a.prop(name)
    def set(self, receiver, name, value): return receiver + value + self.a.op(0x61, self.a.qname(name))
    def st(self, name, value): return self.set(self.this, name, value)
    def inc(self, name): return self.st(name, self.p(name) + self.n(1) + b'\xc5')
    def call(self, recv, name, *args): return self.a.call(recv, name, *args)
    def result(self, recv, name, *args): return recv + b''.join(args) + self.a.op(0x46, self.a.qname(name), len(args))
    def new(self, name, package, *args): return self.a.op(0x60, self.a.qname(name, package)) + b''.join(args) + self.a.op(0x42, len(args))
    def eq(self, x, y, body): return x + y + b'\x14' + len(body).to_bytes(3, 'little', signed=True) + body
    def ne(self, x, y, body): return x + y + b'\x13' + len(body).to_bytes(3, 'little', signed=True) + body
    def method(self, name, code, args=0): self.methods.append((name, self.a.method(name, self.header + code + self.end, args=args)))
    def mark(self, kind, detail=None): return self.call(self.this, 'mark', self.a.push(kind), self.a.push('') if detail is None else detail)
    def listener(self, recv, event, method): return self.call(recv, 'addEventListener', self.a.push(event), self.p(method))
    def finish(self, name, ctor):
        a = self.a
        a.class_(name, a.method(name+'$iinit', self.header + self.this + a.op(0x49,0) + ctor + self.end), self.methods)
        ancestors = [('Object',''),('EventDispatcher','flash.events'),('DisplayObject','flash.display'),('InteractiveObject','flash.display'),('DisplayObjectContainer','flash.display'),('Sprite','flash.display'),('MovieClip','flash.display')]
        script = self.header + b'\x65\x00'
        for ancestor, pkg in ancestors: script += a.op(0x60,a.qname(ancestor,pkg)) + b'\x30'
        script += a.op(0x60,a.qname('MovieClip','flash.display')) + a.op(0x58,0) + b'\x1d'*7 + a.op(0x68,a.instances[0]['name']) + self.end
        a.scripts.append(a.method(name+'$script',script,scope=0))
        return a.serialize()


def root_abc(arm):
    assert arm in ('unload','unloadAndStop')
    c=Code(); a=c.a; stage=c.p('stage'); loader=c.p('currentLoader'); info=loader+a.prop('contentLoaderInfo'); event=b'\xd1'; target=event+a.prop('currentTarget')
    # Mark reads the live active content, not a mirrored/fake child counter.
    code=c.st('observedChildGeneration',c.n(-1))+c.st('observedChildHeartbeat',c.n(0))
    code+=c.eq(c.p('ready'),c.n(1),c.st('observedChildGeneration',loader+a.prop('content')+a.prop('childGeneration'))+c.st('observedChildHeartbeat',loader+a.prop('content')+a.prop('childHeartbeat')))
    line=a.push('LT|')+b'\xd1\xa0'+a.push('|')+b'\xa0'+c.p('bootToken')+b'\xa0'
    for field in FIELDS: line+=a.push('|')+b'\xa0'+c.p(field)+b'\xa0'
    code+=c.st('traceLine',line)
    code+=c.ne(b'\xd2',a.push(''),c.st('traceLine',c.p('traceLine')+a.push('|')+b'\xa0\xd2\xa0'))
    code+=a.op(0x5d,a.qname('trace'))+c.p('traceLine')+a.op(0x4f,a.qname('trace'),1)
    c.method('mark',code,args=2)
    c.method('reportChild',c.call(c.this,'mark',b'\xd1',b'\xd2'),args=2)

    setup=b''
    for field in ('generation','rootHeartbeat','pointerCount','keyCount','ready','errors','unloadCalls','unloadEvents'): setup+=c.st(field,c.n(0))
    setup+=c.st('currentLoader',b'\x20')
    setup+=c.st('bootToken',c.result(a.op(0x60,a.qname('Math')),'random')+b'\x70')
    setup+=c.set(stage,'scaleMode',a.push('noScale'))+c.set(stage,'align',a.push('TL'))
    setup+=c.set(stage,'focus',c.this)
    setup+=c.listener(stage,'click','onClick')+c.listener(stage,'keyDown','onKey')+c.listener(stage,'resize','onResize')+c.listener(c.this,'enterFrame','onTick')
    setup+=c.call(c.this,'drawBackground')+c.mark('BOOT',a.push(arm))+c.call(c.this,'startLoad')+c.call(c.this,'stop')
    c.method('frame1',setup)

    g=c.p('graphics')
    draw=c.call(g,'clear')+c.call(g,'beginFill',a.push(str(0x18354b)))+c.call(g,'drawRect',c.n(0),c.n(0),stage+a.prop('stageWidth'),stage+a.prop('stageHeight'))+c.call(g,'endFill')
    c.method('drawBackground',draw)
    c.method('onTick',c.inc('rootHeartbeat'),args=1)
    c.method('onResize',c.call(c.this,'drawBackground')+c.mark('RESIZE'),args=1)
    c.method('onKey',c.eq(event+a.prop('keyCode'),c.n(13),c.inc('keyCount')+c.mark('STATE')),args=1)
    advance=c.eq(c.p('generation'),c.n(3),c.end)+c.call(c.this,'transition')
    c.method('onClick',c.inc('pointerCount')+c.set(stage,'focus',c.this)+c.mark('POINTER')+c.eq(c.p('ready'),c.n(1),advance),args=1)

    code=c.st('ready',c.n(0))+c.st('currentLoader',c.new('Loader','flash.display'))
    code+=c.set(loader,'name',a.push('scene-')+c.p('generation')+b'\xa0')
    code+=c.set(loader,'x',c.n(36))+c.set(loader,'y',c.n(48))
    for evt,method in [('open','onOpen'),('progress','onProgress'),('init','onInit'),('complete','onComplete'),('unload','onUnload'),('ioError','onError'),('securityError','onError')]:code+=c.listener(info,evt,method)
    code+=c.call(c.this,'addChild',loader)+c.mark('LOAD_BEGIN',loader+a.prop('name'))
    code+=c.call(loader,'load',c.new('URLRequest','flash.net',a.push('sub/child.swf')))
    code+=c.mark('LOAD_RETURN',loader+a.prop('name'))
    c.method('startLoad',code)

    code=c.st('ready',c.n(0))+c.mark('UNLOAD_BEGIN',loader+a.prop('name'))+c.call(loader,arm)
    code+=c.inc('unloadCalls')+c.mark('UNLOAD_RETURN',loader+a.prop('name'))+c.call(c.this,'removeChild',loader)
    code+=c.inc('generation')+c.call(c.this,'startLoad')
    c.method('transition',code)
    origin=target+a.prop('loader')+a.prop('name')
    for name,kind in [('onOpen','OPEN'),('onProgress','PROGRESS'),('onInit','INIT')]:c.method(name,c.mark(kind,origin),args=1)
    c.method('onUnload',c.inc('unloadEvents')+c.mark('UNLOAD_EVENT',origin),args=1)
    c.method('onError',c.inc('errors')+c.mark('ERROR',event+a.prop('type')+a.push(':')+b'\xa0'+event+a.prop('text')+b'\xa0'),args=1)
    fail=c.inc('errors')+c.mark('ERROR',a.push('stale-or-duplicate-complete'))+c.end
    code=c.ne(target,info,fail)+c.eq(c.p('ready'),c.n(1),fail)
    code+=c.set(loader+a.prop('content'),'childGeneration',c.p('generation'))+c.st('ready',c.n(1))+c.mark('COMPLETE',origin)+c.mark('READY')
    c.method('onComplete',code,args=1)
    return c.finish('LoaderTransitionRoot',c.call(c.this,'addFrameScript',c.n(0),c.p('frame1')))


def child_abc():
    c=Code();a=c.a;parent=c.p('parent'); reporter=c.p('reporter')
    ctor=c.st('childHeartbeat',c.n(0))+c.st('childGeneration',c.n(-1))+c.st('reporter',b'\x20')+c.st('origin',a.push('not-attached'))
    g=c.p('graphics')
    ctor+=c.call(g,'beginFill',a.push(str(0xff4a66)))+c.call(g,'drawRect',c.n(0),c.n(0),c.n(96),c.n(96))+c.call(g,'endFill')
    ctor+=c.listener(c.this,'enterFrame','onTick')+c.listener(c.this,'addedToStage','onAdded')+c.listener(c.this,'removedFromStage','onRemoved')+c.call(c.this,'stop')
    c.method('onTick',c.inc('childHeartbeat'),args=1)
    c.method('onAdded',c.st('reporter',parent+a.prop('parent'))+c.st('origin',parent+a.prop('name'))+c.call(reporter,'reportChild',a.push('CHILD_ADDED'),c.p('origin')),args=1)
    c.method('onRemoved',c.ne(reporter,b'\x20',c.call(reporter,'reportChild',a.push('CHILD_REMOVED'),c.p('origin'))),args=1)
    return c.finish('LoaderTransitionChild',ctor)


def swf(abc,name):
    tags=f.tag(69,struct.pack('<I',8))+f.tag(9,bytes([0x18,0x35,0x4b]))
    tags+=f.tag(82,struct.pack('<I',0)+b'original-loader-transition\0'+abc)
    tags+=f.tag(76,struct.pack('<HH',1,0)+name.encode()+b'\0')+f.tag(1)+f.tag(0)
    body=f.rect(320,240)+struct.pack('<HH',24*256,1)+tags
    return b'FWS\x25'+struct.pack('<I',len(body)+8)+body

def outputs():
    return {'main.swf':swf(root_abc('unload'),'LoaderTransitionRoot'), 'sub/child.swf':swf(child_abc(),'LoaderTransitionChild')}

def main():
    assert hashlib.sha256((ROOT/'abc_subset.py').read_bytes()).hexdigest()==HELPER_SHA
    assert not (ROOT/'main-unload-and-stop.swf').exists(), 'Unselected payload must not exist in selected fixture folder'
    files=outputs()
    for name,data in files.items():
        p=ROOT/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(data)
    manifest={'schemaVersion':1,'provenance':'Original generated AVM2 diagnostic; no user assets or proprietary compiler','formatSourcePin':PIN,'swfVersion':37,'rootFrames':1,'frameRate':24,'generations':[0,1,2,3],'selectedArm':'main.swf: unload','unselectedPrototypeSupport':'root_abc(unloadAndStop) retained for in-memory checks only; no alternate SWF emitted','runtimeExecuted':False,'adobeReferenceExecuted':False,'abcHelperSha256':HELPER_SHA,'traceFields':['LT','kind','bootToken','generation','rootHeartbeat','pointerCount','keyCount','ready','activeChildGeneration','childHeartbeat','errors','unloadCalls','unloadEvents'],'files':{name:{'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()}for name,data in files.items()}}
    (ROOT/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n');print(json.dumps(manifest,indent=2))
if __name__=='__main__':main()

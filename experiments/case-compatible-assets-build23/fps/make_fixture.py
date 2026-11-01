#!/usr/bin/env python3
"""Original neutral SWF37/AVM2 frame-cadence diagnostic. No Adobe toolchain/game input.

Writes the tiny, documented ABC subset needed by the single neutral FrameProbe class. Binary layout
and opcodes were checked against ruffle-rs/ruffle at commit
89a7049965f3090e706265670df309a5128233ac, swf/src/avm2/{write,opcode}.rs.
This is a fixture assembler, NOT a general ActionScript compiler.
"""
from pathlib import Path
import hashlib
import json
import struct

ROOT = Path(__file__).resolve().parent


def u30(value):
    assert 0 <= value < 1 << 30
    out = bytearray()
    while value >= 128:
        out.append((value & 127) | 128)
        value >>= 7
    return bytes(out + bytes([value]))


def tag(code, payload=b''):
    size = len(payload)
    return struct.pack('<H', code << 6 | min(size, 63)) + (struct.pack('<I', size) if size >= 63 else b'') + payload


def rect(width, height):
    values = (0, width * 20, 0, height * 20)
    bits = max(v.bit_length() + 1 for v in values)
    s = f'{bits:05b}' + ''.join(f'{v:0{bits}b}' for v in values)
    s += '0' * (-len(s) % 8)
    return int(s, 2).to_bytes(len(s) // 8, 'big')


class ABC:
    def __init__(self):
        self.strings = ['']
        self.namespaces = [None]
        self.names = [None]
        self.methods = []
        self.instances = []
        self.scripts = []

    def string(self, value):
        if value not in self.strings:
            self.strings.append(value)
        return self.strings.index(value)

    def qname(self, value, package=''):
        namespace = (0x16, self.string(package))  # PackageNamespace
        if namespace not in self.namespaces:
            self.namespaces.append(namespace)
        name = (self.namespaces.index(namespace), self.string(value))
        if name not in self.names:
            self.names.append(name)
        return self.names.index(name)

    def op(self, opcode, *operands):
        return bytes([opcode]) + b''.join(u30(value) for value in operands)

    def push(self, value):
        if isinstance(value, int):
            assert 0 <= value < 128
            return bytes([0x24, value])
        return self.op(0x2c, self.string(value))

    def prop(self, name):
        return self.op(0x66, self.qname(name))

    def call(self, receiver, name, *args):
        return receiver + b''.join(args) + self.op(0x4f, self.qname(name), len(args))

    def trace(self, message, *args):
        return self.op(0x5d, self.qname('trace')) + self.push(message) + b''.join(args) + self.op(0x4f, self.qname('trace'), len(args) + 1)

    def method(self, name, code, args=0, scope=9):
        index = len(self.methods)
        self.methods.append(dict(name=name, code=code, args=args, scope=scope))
        self.string(name)
        self.qname('void')
        return index

    def trait_method(self, name, index):
        return u30(self.qname(name)) + b'\x01' + u30(0) + u30(index)

    def class_(self, name, ctor, methods):
        # The script captures global + seven MovieClip ancestors; class methods
        # then see the class object as the ninth outer scope.
        cinit = self.method(name + '$cinit', b'\xd0\x30\x47', scope=8)
        self.instances.append(dict(name=self.qname(name), ctor=ctor, cinit=cinit, methods=methods))

    def serialize(self):
        # Complete all pools before serializing them.
        for m in self.methods:
            self.string(m['name'])
        super_name = self.qname('MovieClip', 'flash.display')
        traits = [[self.trait_method(name, method) for name, method in c['methods']] for c in self.instances]
        script_traits = [u30(c['name']) + b'\x04' + u30(index + 1) + u30(index) for index, c in enumerate(self.instances)]
        out = struct.pack('<HH', 16, 46) + b'\x01\x01\x01'
        out += u30(len(self.strings)) + b''.join(u30(len(s.encode())) + s.encode() for s in self.strings[1:])
        out += u30(len(self.namespaces)) + b''.join(bytes([kind]) + u30(name) for kind, name in self.namespaces[1:])
        out += b'\x01'  # empty namespace-set pool
        out += u30(len(self.names)) + b''.join(b'\x07' + u30(ns) + u30(name) for ns, name in self.names[1:])
        out += u30(len(self.methods))
        for m in self.methods:
            out += u30(m['args']) + u30(self.qname('void')) + b'\x00' * m['args'] + u30(self.string(m['name'])) + b'\x00'
        out += b'\x00' + u30(len(self.instances))  # metadata, classes
        for c, ts in zip(self.instances, traits):
            out += u30(c['name']) + u30(super_name) + b'\x00\x00' + u30(c['ctor']) + u30(len(ts)) + b''.join(ts)
        for c in self.instances:
            out += u30(c['cinit']) + b'\x00'
        out += b'\x01' + u30(self.scripts[0]) + u30(len(script_traits)) + b''.join(script_traits)
        out += u30(len(self.methods))
        for index, m in enumerate(self.methods):
            out += u30(index) + u30(20) + u30(m['args'] + 1) + u30(m['scope']) + u30(m['scope'] + (8 if m['scope'] == 0 else 1))
            out += u30(len(m['code'])) + m['code'] + b'\x00\x00'
        return out


def make_swf():
    a = ABC()
    this, header, end = b'\xd0', b'\xd0\x30', b'\x47'
    ctor = a.method('FrameProbe$iinit', header + this + a.op(0x49, 0)
        + this + a.push(0) + a.op(0x61, a.qname('ticks'))
        + a.call(this, 'addEventListener', a.push('enterFrame'), this + a.prop('onTick'))
        + a.call(this, 'stop') + a.trace('FPS_READY') + end)
    tick = a.method('FrameProbe$onTick', header + this + this + a.prop('ticks')
        + a.push(1) + b'\xc5' + a.op(0x61, a.qname('ticks'))
        + a.trace('FPS_TICK', this + a.prop('ticks')) + end, args=1)
    a.class_('FrameProbe', ctor, [('onTick', tick)])
    script = header + b'\x65\x00'
    for name, package in [('Object',''), ('EventDispatcher','flash.events'),
            ('DisplayObject','flash.display'), ('InteractiveObject','flash.display'),
            ('DisplayObjectContainer','flash.display'), ('Sprite','flash.display'),
            ('MovieClip','flash.display')]:
        script += a.op(0x60, a.qname(name, package)) + b'\x30'
    script += a.op(0x60, a.qname('MovieClip','flash.display')) + a.op(0x58, 0)
    script += b'\x1d' * 7 + a.op(0x68, a.instances[0]['name']) + end
    a.scripts.append(a.method('probe$script', script, scope=0))
    tags = tag(69, struct.pack('<I',8)) + tag(9,b'\x20\x30\x40')
    tags += tag(82, struct.pack('<I',0) + b'neutral-fps\0' + a.serialize())
    tags += tag(76, struct.pack('<HH',1,0) + b'FrameProbe\0') + tag(1) + tag(0)
    body = rect(160,120) + struct.pack('<HH',24*256,1) + tags
    return b'FWS' + bytes([37]) + struct.pack('<I',len(body)+8) + body


if __name__ == '__main__':
    import argparse
    parser=argparse.ArgumentParser(); parser.add_argument('output',type=Path)
    args=parser.parse_args(); data=make_swf(); args.output.write_bytes(data)
    print(json.dumps({'sha256':hashlib.sha256(data).hexdigest(),'bytes':len(data),
        'fps':24,'privateGameInputs':False}))


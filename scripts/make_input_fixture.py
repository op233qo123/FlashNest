#!/usr/bin/env python3
"""Original AVM1 input/focus regression; no third-party SWF or compiler.
The root's first key loads a child scene. That scene reports Key/Mouse listener
callbacks so tests observe real Ruffle execution, not DOM event delivery alone.
"""
from pathlib import Path
import struct

ROOT = Path(__file__).resolve().parents[1]


def tag(number, body=b''):
    short = len(body) if len(body) < 63 else 63
    return struct.pack('<H', number << 6 | short) + (struct.pack('<I', len(body)) if short == 63 else b'') + body


def action(opcode, body=b''):
    return bytes([opcode]) + (struct.pack('<H', len(body)) + body if opcode >= 128 else b'')


def push(value):
    return action(0x96, b'\0' + value.encode() + b'\0')


def integer(value):
    return action(0x96, b'\x07' + struct.pack('<i', value))


def variable(name):
    return push(name) + action(0x1c)


def call_method(obj, name, args=()):
    return b''.join(reversed(args)) + integer(len(args)) + obj + push(name) + action(0x52)


def trace(value):
    return push(value) + action(0x26)


def listener(event_name, body, broadcaster):
    code = body + b'\0'
    # AVM1 DefineFunction action length excludes its nested code block.
    # Pinned Ruffle swf/src/avm1/write.rs::write_define_function follows this.
    anonymous = action(0x9b, b'\0' + struct.pack('<HH', 0, len(code))) + code
    assign = variable('_root') + push(event_name) + anonymous + action(0x4f)
    register = call_method(variable(broadcaster), 'addListener', (variable('_root'),)) + action(0x17)
    return assign + register


def movie(actions, color):
    bits = '01110' + ''.join(format(x & ((1 << 14) - 1), '014b') for x in (0, 6400, 0, 4800))
    bits += '0' * (-len(bits) % 8)
    rect = int(bits, 2).to_bytes(len(bits) // 8, 'big')
    body = rect + struct.pack('<HH', 12 * 256, 1) + tag(9, bytes(color)) + tag(12, actions + b'\0') + tag(1) + tag(0)
    return b'FWS' + bytes([7]) + struct.pack('<I', len(body) + 8) + body


def generate():
    base = ROOT / 'fixtures/input-focus'
    (base / 'sub').mkdir(parents=True, exist_ok=True)
    first_key = trace('FOCUS_ROOT_KEY')
    first_key += action(0x83, b'sub/scene.swf\0_level1\0')
    first_key += call_method(variable('Key'), 'removeListener', (variable('_root'),)) + action(0x17)
    root = listener('onKeyDown', first_key, 'Key') + trace('FOCUS_ROOT_READY') + action(0x07)
    key_callback = push('FOCUS_CHILD_KEY:') + call_method(variable('Key'), 'getCode') + action(0x47) + action(0x26)
    child = listener('onKeyDown', key_callback, 'Key')
    child += listener('onMouseDown', trace('FOCUS_CHILD_POINTER'), 'Mouse')
    child += trace('FOCUS_CHILD_READY') + action(0x07)
    (base / 'main.swf').write_bytes(movie(root, (22, 44, 88)))
    (base / 'sub/scene.swf').write_bytes(movie(child, (24, 130, 96)))
    (base / 'README.txt').write_text(
        'Original AVM1 input/focus regression. Main registers Key.onKeyDown; first key traces FOCUS_ROOT_KEY, '
        'loads sub/scene.swf into _level1, and unregisters itself. Child registers independent Key and Mouse '
        'listeners and traces FOCUS_CHILD_READY, FOCUS_CHILD_KEY:<keyCode>, FOCUS_CHILD_POINTER. '
        'A stopped timeline still receives listeners. Test must explicitly move DOM focus outside Ruffle, '
        'then use the native FlashNest.key bridge and require the SWF callback. DOM key dispatch alone is not proof.\n'
    )
    print('Generated original root-to-child input focus fixture')


if __name__ == '__main__':
    generate()

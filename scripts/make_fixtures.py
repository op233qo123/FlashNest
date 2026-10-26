#!/usr/bin/env python3
"""Original minimal SWF 7 fixtures; no Adobe compiler or third-party movie code.
Uses documented AVM1 GetURL(_level1) and GetURL2(LoadVariables) opcodes.
"""
import struct, pathlib, zipfile
ROOT = pathlib.Path(__file__).resolve().parents[1]
def tag(n, b=b''):
    return struct.pack('<H', n << 6 | (len(b) if len(b)<63 else 63)) + (b'' if len(b)<63 else struct.pack('<I',len(b))) + b
def action(n,b=b''):
    return bytes([n]) + (struct.pack('<H',len(b))+b if n>=128 else b'')
def push(s): return action(0x96,b'\0'+s.encode()+b'\0')
def trace(s): return push(s)+action(0x26)
def rect():
    bits = '01110'+''.join(format(x & ((1<<14)-1),'014b') for x in (0,6400,0,4800))
    bits += '0' * (-len(bits)%8)
    return int(bits,2).to_bytes(len(bits)//8,'big')
def movie(actions,color):
    body=rect()+struct.pack('<HH',12*256,1)+tag(9,bytes(color))+tag(12,actions+b'\0')+tag(1)+tag(0)
    return b'FWS'+bytes([7])+struct.pack('<I',len(body)+8)+body
base=ROOT/'fixtures'/'multi-swf'; (base/'sub').mkdir(parents=True,exist_ok=True)
main=trace('FLASHNEST_MAIN_OK')+action(0x83,b'sub/child.swf\0_level1\0')
main+=push('sibling.txt')+push('_root')+action(0x9a,b'\x80')+action(0x07)
(base/'main.swf').write_bytes(movie(main,(22,44,88)))
(base/'sub'/'child.swf').write_bytes(movie(trace('FLASHNEST_CHILD_OK')+action(0x07),(24,130,96)))
(base/'sibling.txt').write_text('fixture=FLASHNEST_TEXT_OK&answer=42\n')
(base/'README.txt').write_text('Original FlashNest synthetic AVM1 test. main.swf loads sub/child.swf into _level1 and sibling.txt with LoadVariables. Child background green and trace FLASHNEST_CHILD_OK prove execution. No external assets.\n')
with zipfile.ZipFile(ROOT/'fixtures'/'multi-swf.zip','w',zipfile.ZIP_DEFLATED) as z:
    for p in sorted(base.rglob('*')):
        if p.is_file():
            info=zipfile.ZipInfo(str(p.relative_to(base)),(2026,1,1,0,0,0))
            info.compress_type=zipfile.ZIP_DEFLATED; info.external_attr=0o100644 << 16
            z.writestr(info,p.read_bytes())
print('Generated original multi-SWF fixture and import ZIP')

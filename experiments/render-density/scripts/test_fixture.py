#!/usr/bin/env python3
"""Read-only structural tests; not AVM/browser execution."""
import hashlib,importlib.util,json,struct,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('fixture',Path(__file__).with_name('make_fixture.py'));f=importlib.util.module_from_spec(spec);spec.loader.exec_module(f)
def actions(data):
    offsets=set();branches=[];at=0;ended=False
    while at<len(data):
        offsets.add(at);op=data[at];at+=1
        if op==0:
            if at!=len(data):raise ValueError('trailing action bytes')
            ended=True;break
        n=struct.unpack_from('<H',data,at)[0] if op>=128 else 0
        if op>=128:at+=2
        payload=data[at:at+n]
        if len(payload)!=n:raise ValueError('truncated action')
        at+=n
        if op==0x9b:
            if payload[:3]!=b'\0\0\0' or n!=5:raise ValueError('DefineFunction header length must exclude code body')
            size=struct.unpack_from('<H',payload,3)[0]
            body=data[at:at+size]
            if len(body)!=size:raise ValueError('truncated function body')
            actions(body);at+=size
        if op==0x9d:branches.append(at+struct.unpack('<h',payload)[0])
    if not ended:raise ValueError('missing action end')
    if any(b not in offsets for b in branches):raise ValueError('branch not on action boundary')
    return offsets
class FixtureTests(unittest.TestCase):
    def test_all_36_deterministic_headers_hashes_and_actions(self):
        manifest=json.loads((ROOT/'fixtures/manifest.json').read_text());self.assertEqual(len(manifest['files']),36)
        for name,info in manifest['files'].items():
            data=(ROOT/'fixtures'/name).read_bytes();self.assertEqual(data,f.movie(info['mode'],info['align']))
            self.assertEqual(hashlib.sha256(data).hexdigest(),info['sha256']);self.assertEqual(data[:4],b'FWS\x07');self.assertEqual(struct.unpack_from('<I',data,4)[0],len(data))
            rectbytes=(5+4*(data[8]>>3)+7)//8;at=8+rectbytes+4;codes=[]
            while at<len(data):
                header=struct.unpack_from('<H',data,at)[0];at+=2;code=header>>6;n=header&63
                if n==63:n=struct.unpack_from('<I',data,at)[0];at+=4
                payload=data[at:at+n];self.assertEqual(len(payload),n);at+=n;codes.append(code)
                if code==12:actions(payload)
            self.assertEqual(codes,[9,12,1,0]);self.assertEqual(at,len(data))
    def test_original_diagnostic_includes_real_input_and_stage_properties(self):
        data=f.movie('showAll','')
        for marker in [b'Stage\0',b'scaleMode\0',b'align\0',b'onMouseDown\0',b'onMouseUp\0',b'_xmouse\0',b'_ymouse\0',b'hitTest\0',b'startDrag\0',b'stopDrag\0',b'beginFill\0']:
            self.assertIn(marker,data)
        for forbidden in [b'getURL',b'loadMovie',b'ExternalInterface',b'SharedObject']:self.assertNotIn(forbidden,data)
    def test_define_function_length_excludes_body(self):
        body=f.trace('READY',f.integer(320),f.integer(240),f.string('showAll'),f.string(''))+b'\0'
        encoded=f.function(body[:-1])
        self.assertEqual(encoded[:8],b'\x9b\x05\0\0\0\0'+struct.pack('<H',len(body)))
        self.assertEqual(encoded[8:],body)
        actions(encoded+f.action(0x17)+b'\0')
        inflated=bytearray(encoded);struct.pack_into('<H',inflated,1,5+len(body))
        with self.assertRaisesRegex(ValueError,'header length'):actions(bytes(inflated)+b'\0')
        with self.assertRaisesRegex(ValueError,'truncated function'):actions(encoded[:-1])
    def test_truncated_action_fails(self):
        with self.assertRaises((ValueError,struct.error)):actions(b'\x96\x05\x00x')
if __name__=='__main__':unittest.main()

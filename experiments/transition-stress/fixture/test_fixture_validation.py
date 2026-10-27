#!/usr/bin/env python3
"""Binary/source structure tests only. No SWF/AVM2 runtime is invoked."""
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
import make_fixtures as make
import validate_fixtures as validate
ROOT=Path(__file__).resolve().parent

class FixtureTests(unittest.TestCase):
    def test_deterministic_outputs_and_exact_helper(self):
        self.assertEqual(hashlib.sha256((ROOT/'abc_subset.py').read_bytes()).hexdigest(),make.HELPER_SHA)
        manifest=json.loads((ROOT/'manifest.json').read_text())
        for name,data in make.outputs().items():
            self.assertEqual(data,(ROOT/name).read_bytes())
            self.assertEqual(hashlib.sha256(data).hexdigest(),manifest['files'][name]['sha256'])

    def test_selected_structures_and_prototype_abc_in_memory(self):
        for path in make.outputs(): validate.validate(ROOT/path)
        validate.validate_abc(make.root_abc('unloadAndStop'), 'LoaderTransitionRoot')

    def test_exact_fixed_field_order_and_marker_sites(self):
        row=validate.validate(ROOT/'main.swf')
        methods={m['method']:m['decoded']for m in row['abc']['methods']}
        mark=methods['mark']; start=next(i for i,x in enumerate(mark)if x.get('string')=='LT|')
        stop=next(i for i,x in enumerate(mark[start:],start)if x.get('name')==['','traceLine']and x['opcode']=='0x61')
        getters=[x['name'][1]for x in mark[start:stop]if x['opcode']=='0x66']
        self.assertEqual(getters,['bootToken']+make.FIELDS)
        manifest=json.loads((ROOT/'manifest.json').read_text())
        self.assertEqual(len(manifest['traceFields']),13)
        for marker,method in [('READY','onComplete'),('STATE','onKey')]:
            self.assertEqual([n for n,code in methods.items()if any(x.get('string')==marker for x in code)],[method])
        setters=[n for n,code in methods.items()if any(x.get('name')==['','generation']and x['opcode']=='0x61'for x in code)]
        self.assertEqual(set(setters),{'frame1','transition'})
        self.assertFalse(any(x.get('name')==['','mark']for x in methods['onTick']))

    def test_selected_and_prototype_arms_do_not_mix(self):
        for arm,other in [('unload','unloadAndStop'),('unloadAndStop','unload')]:
            abc=validate.validate_abc(make.root_abc(arm), 'LoaderTransitionRoot')
            trans=next(m['decoded']for m in abc['methods']if m['method']=='transition')
            calls=[x['name'][1]for x in trans if x['opcode']=='0x4f']
            self.assertEqual(calls.count(arm),1);self.assertNotIn(other,calls)

    def test_reject_out_of_bounds_branch_and_stack_underflow(self):
        for code in [b'\xd0\x30\x25\x01\x25\x01\x14\xff\xff\x7f\x47', b'\xa0\x47']:
            with self.assertRaises(AssertionError):
                validate.validate_code(code,[None],[''],1,9,10,20,1,'bad')

    def test_reject_truncated_abc(self):
        data=make.root_abc('unload')
        for cut in (1,2,10):
            with self.assertRaises((AssertionError,ValueError,IndexError,UnicodeDecodeError)):
                validate.validate_abc(data[:-cut],'LoaderTransitionRoot')

if __name__=='__main__':unittest.main()

#!/usr/bin/env python3
"""Independent byte reader for these original fixtures; does not run AVM2.

Checks original Loader fixture ABC references and control-flow
stack/scope balance. Not a substitute for a Flash or Ruffle verifier/runtime.
"""
from pathlib import Path
import hashlib
import json
import struct

ROOT = Path(__file__).resolve().parent


class Reader:
    def __init__(self, data):
        self.data, self.pos = data, 0

    def take(self, n):
        assert n >= 0 and self.pos + n <= len(self.data)
        value = self.data[self.pos:self.pos+n]
        self.pos += n
        return value

    def byte(self):
        return self.take(1)[0]

    def u16(self):
        return struct.unpack('<H', self.take(2))[0]

    def u30(self):
        value = 0
        for i in range(5):
            byte = self.byte()
            value |= (byte & 127) << (7*i)
            if byte < 128:
                assert value < 1 << 30
                return value
        raise AssertionError('Malformed u30')

    def zstr(self):
        end = self.data.index(b'\0', self.pos)
        return self.take(end-self.pos+1)[:-1].decode()

    def done(self):
        assert self.pos == len(self.data), (self.pos, len(self.data))


def read_tags(data):
    r, result = Reader(data), []
    while r.pos < len(data):
        head = r.u16()
        size = head & 63
        if size == 63:
            size = struct.unpack('<I', r.take(4))[0]
        code = head >> 6
        result.append((code, r.take(size)))
        if code == 0:
            r.done()
    assert result[-1] == (0, b'')
    return result


def validate_abc(data, expected_class):
    r = Reader(data)
    assert (r.u16(), r.u16()) == (16, 46)
    assert [r.u30() for _ in range(3)] == [1, 1, 1]
    strings = [''] + [r.take(r.u30()).decode() for _ in range(r.u30()-1)]
    namespaces = [None] + [(r.byte(), r.u30()) for _ in range(r.u30()-1)]
    assert all(kind == 0x16 and 0 <= name < len(strings) for kind, name in namespaces[1:])
    assert r.u30() == 1
    names = [None]
    for _ in range(r.u30()-1):
        assert r.byte() == 7
        ns, name = r.u30(), r.u30()
        assert 0 < ns < len(namespaces) and 0 < name < len(strings)
        names.append((strings[namespaces[ns][1]], strings[name]))

    def name(index):
        assert 0 < index < len(names)
        return names[index][1]

    methods = []
    for _ in range(r.u30()):
        argc, return_type = r.u30(), r.u30()
        assert name(return_type) == 'void'
        assert all(r.u30() == 0 for _ in range(argc))
        method_name = strings[r.u30()]
        assert r.byte() == 0
        methods.append((method_name, argc))
    assert r.u30() == 0  # metadata
    class_count = r.u30()
    assert class_count == 1

    def traits(allowed):
        result = []
        for _ in range(r.u30()):
            trait_name, kind = name(r.u30()), r.byte()
            assert kind in allowed
            slot, target = r.u30(), r.u30()
            assert target < (class_count if kind == 4 else len(methods))
            result.append((trait_name, kind, slot, target))
        return result

    classes = []
    for _ in range(class_count):
        class_name, base = name(r.u30()), name(r.u30())
        assert base == 'MovieClip' and r.byte() == 0 and r.u30() == 0
        ctor = r.u30()
        assert ctor < len(methods)
        classes.append((class_name, ctor, traits({1})))
    assert [c[0] for c in classes] == [expected_class]
    cinits = []
    for _ in range(class_count):
        cinits.append(r.u30())
        assert r.u30() == 0
    assert r.u30() == 1
    script = r.u30()
    script_traits = traits({4})
    assert [t[0] for t in script_traits] == [expected_class]
    count = r.u30()
    assert count == len(methods)
    results, seen = [], set()
    for _ in range(count):
        method, max_stack, locals_, init_scope, max_scope = [r.u30() for _ in range(5)]
        assert method not in seen and method < len(methods)
        seen.add(method)
        code = r.take(r.u30())
        assert r.u30() == 0 and r.u30() == 0
        assert locals_ == methods[method][1] + 1
        expected_scope = 0 if method == script else 8 if method in cinits else 9
        assert init_scope == expected_scope
        results.append(validate_code(code, names, strings, locals_, init_scope, max_scope, max_stack, class_count, methods[method][0]))
    r.done()
    # No file, socket, URL, storage or host bridge APIs can appear in this subset.
    banned = {'ExternalInterface', 'navigateToURL', 'SharedObject', 'Socket', 'NetConnection', 'Shader', 'ShaderData'}
    assert not banned.intersection(strings)
    return {'methods': results, 'strings': strings[1:], 'classes': classes}


def validate_code(code, names, strings, locals_, init_scope, max_scope, max_stack, class_count, method_name):
    r, ins = Reader(code), {}
    while r.pos < len(code):
        pos, op = r.pos, r.byte()
        args, effect, scope_effect, required, branch = [], 0, 0, 0, None
        if op in (0xd0, 0xd1, 0xd2):
            assert op-0xd0 < locals_
            effect = 1
        elif op == 0x20:
            effect = 1
        elif op == 0x24:
            args = [r.byte()]
            effect = 1
        elif op == 0x25:
            args = [r.u30()]
            assert 0 <= args[0] <= 32767
            effect = 1
        elif op == 0x2c:
            args = [r.u30()]
            assert 0 <= args[0] < len(strings)
            effect = 1
        elif op in (0x60, 0x5d, 0x66, 0x61, 0x68):
            args = [r.u30()]
            assert 0 < args[0] < len(names)
            effect = 1 if op in (0x60, 0x5d) else -2 if op in (0x61, 0x68) else 0
            required = 2 if effect == -2 else 1 if op == 0x66 else 0
        elif op in (0x4f, 0x46):
            args = [r.u30(), r.u30()]
            assert 0 < args[0] < len(names)
            required = args[1] + 1
            effect = -required + (1 if op == 0x46 else 0)
        elif op == 0x42:
            args = [r.u30()]
            required = args[0] + 1
            effect = -args[0]
        elif op == 0x49:
            args = [r.u30()]
            required = args[0] + 1
            effect = -required
        elif op == 0x58:
            args = [r.u30()]
            assert args[0] < class_count
            required = 1
        elif op == 0x65:
            args, effect = [r.byte()], 1
        elif op == 0x30:
            required, effect, scope_effect = 1, -1, 1
        elif op == 0x1d:
            scope_effect = -1
        elif op == 0x70:
            required = 1
        elif op in (0xc5, 0xa0):
            required, effect = 2, -1
        elif op in (0x13, 0x14):
            delta = int.from_bytes(r.take(3), 'little', signed=True)
            branch = r.pos + delta
            required, effect = 2, -2
        elif op == 0x47:
            pass
        else:
            raise AssertionError((method_name, pos, hex(op)))
        ins[pos] = (op, args, r.pos, effect, scope_effect, required, branch)
    pending, states = [(0, 0, init_scope)], {}
    peak_stack, peak_scope = 0, init_scope
    while pending:
        pos, stack, scope = pending.pop()
        if pos in states:
            assert states[pos] == (stack, scope), (method_name, pos, states[pos], (stack, scope))
            continue
        states[pos] = (stack, scope)
        assert pos in ins
        op, args, next_, effect, scope_effect, required, branch = ins[pos]
        assert stack >= required
        if op == 0x65:
            assert args[0] < scope
        if op == 0x58:
            assert scope == 8, 'class must capture global plus full ancestor chain'
        stack, scope = stack + effect, scope + scope_effect
        assert stack <= max_stack and init_scope <= scope <= max_scope
        peak_stack, peak_scope = max(peak_stack, stack), max(peak_scope, scope)
        if op == 0x47:
            assert stack == 0
            continue
        pending.append((next_, stack, scope))
        if branch is not None:
            pending.append((branch, stack, scope))
    assert set(states) == set(ins), 'unreachable instructions'
    decoded = []
    for offset, (op, args, next_, effect, scope_effect, required, branch) in ins.items():
        entry = {'offset': offset, 'opcode': hex(op), 'args': args}
        if op in (0x60, 0x5d, 0x66, 0x61, 0x68, 0x4f, 0x46):
            entry['name'] = list(names[args[0]])
        elif op == 0x2c:
            entry['string'] = strings[args[0]]
        if branch is not None:
            entry['branchTarget'] = branch
        decoded.append(entry)
    return {'method': method_name, 'instructions': len(ins), 'maxObservedStack': peak_stack, 'maxObservedScope': peak_scope, 'decoded': decoded}


def validate(path):
    data = path.read_bytes()
    assert data[:4] == b'FWS\x25'
    assert struct.unpack_from('<I', data, 4)[0] == len(data)
    rect_bytes = (5 + 4*(data[8] >> 3) + 7)//8
    rate, frames = struct.unpack_from('<HH', data, 8 + rect_bytes)
    assert (rate, frames) == (24*256, 1)
    tags = read_tags(data[12+rect_bytes:])
    assert [code for code, _ in tags] == [69, 9, 82, 76, 1, 0]
    assert tags[0][1] == struct.pack('<I', 8)
    expected = 'LoaderTransitionChild' if path.name == 'child.swf' else 'LoaderTransitionRoot'
    sr = Reader(tags[3][1]); assert sr.u16() == 1
    assert (sr.u16(), sr.zstr()) == (0, expected); sr.done()
    ar = Reader(tags[2][1]); assert ar.take(4) == b'\0'*4 and ar.zstr() == 'original-loader-transition'
    abc = validate_abc(ar.take(len(ar.data)-ar.pos), expected)
    by_name = {m['method']: m['decoded'] for m in abc['methods']}
    calls = lambda code: [i['name'][1] for i in code if i['opcode'] in ('0x4f','0x46')]
    sets = lambda code: [i['name'][1] for i in code if i['opcode']=='0x61']
    if expected == 'LoaderTransitionRoot':
        assert sum(i.get('string')=='sub/child.swf' for m in by_name.values() for i in m)==1
        assert 'load' in calls(by_name['startLoad'])
        assert not any('load' in calls(m) for n,m in by_name.items() if n!='startLoad')
        assert calls(by_name['onTick'])==[] and sets(by_name['onTick'])==['rootHeartbeat']
        assert sets(by_name['onKey'])==['keyCount'] and 'transition' not in calls(by_name['onKey'])
        assert 'transition' not in calls(by_name['onResize'])
        assert sum(calls(m).count('transition') for m in by_name.values())==1
        assert 'transition' in calls(by_name['onClick'])
        transition_calls=calls(by_name['transition'])
        arm='unloadAndStop' if path.name=='main-unload-and-stop.swf' else 'unload'
        assert arm in transition_calls and ({'unload','unloadAndStop'}-{arm}).isdisjoint(transition_calls)
        assert transition_calls.index(arm)<transition_calls.index('removeChild')<transition_calls.index('startLoad')
        trans=by_name['transition']; unload_ix=next(i for i,x in enumerate(trans)if x.get('name')==['',arm]); count_ix=next(i for i,x in enumerate(trans)if x.get('name')==['','unloadCalls']and x['opcode']=='0x61')
        assert unload_ix<count_ix
        assert sets(by_name['onUnload'])==['unloadEvents']
        ready_setters=[]
        for n,m in by_name.items():
            for i,x in enumerate(m):
                if x['opcode']=='0x61' and x.get('name')==['','ready']:
                    assert m[i-1]['opcode']=='0x25'
                    ready_setters.append((n,m[i-1]['args'][0]))
        assert [n for n,v in ready_setters if v==1]==['onComplete']
        assert all(v in (0,1)for _,v in ready_setters)
        assert any(x.get('name')==['','content']for x in by_name['mark'])
        assert any(x.get('name')==['','childHeartbeat']for x in by_name['mark'])
        assert 'SharedObject' not in abc['strings']
    else:
        assert sets(by_name['onTick'])==['childHeartbeat'] and calls(by_name['onTick'])==[]
        assert 'reportChild' in calls(by_name['onAdded']) and 'reportChild' in calls(by_name['onRemoved'])
        assert not {'Loader','URLRequest'}.intersection(abc['strings'])
    return {'file':path.relative_to(ROOT).as_posix(),'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest(),'swfVersion':37,'abc':abc}

if __name__=='__main__':
    results=[validate(ROOT/p)for p in ('main.swf','sub/child.swf')]
    manifest=json.loads((ROOT/'manifest.json').read_text())
    for row in results: assert manifest['files'][row['file']]['sha256']==row['sha256']
    report={'result':'STRUCTURAL_PASS_ONLY','runtimeExecuted':False,'adobeReferenceExecuted':False,'fixtures':results}
    (ROOT/'structural-validation.json').write_text(json.dumps(report,indent=2)+'\n')
    print('PASS SWF37/ABC pools, references, control-flow stack/scope, bounded load sites and silent live heartbeat structure; not runtime verification')

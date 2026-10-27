#!/usr/bin/env python3
"""Checks the exact embedded capture JS, without WebKit/Ruffle execution."""
from pathlib import Path
import json
import re
import subprocess

ROOT = Path(__file__).resolve().parent
swift = (ROOT / 'FrameOrderRuntimeTests.swift').read_text()


def embedded(name):
    match = re.search(r'private static let ' + name + r' = """\n(.*?)\n    """', swift, re.S)
    assert match, name
    source = match[1]
    assert '\\(' not in source, 'No Swift interpolation supported by this small extractor'
    # The only escapes used in these Swift multiline literals are backslashes
    # in the JS regex. Assert that rather than pretending to parse all Swift.
    assert not re.search(r'(?<!\\)\\(?!\\)', source)
    return source.replace('\\\\', '\\')


install, snapshot = embedded('installObserver'), embedded('snapshot')
program = r'''
const assert = require('node:assert/strict');
const vm = require('node:vm');
const install = INSTALL;
const snapshot = SNAPSHOT;
new vm.Script(install);
new vm.Script(snapshot);
function environment() {
  const context = vm.createContext({performance: {now: () => 5}});
  vm.runInContext(`
    globalThis.window = globalThis;
    globalThis.api = new (class {
      set traceObserver(fn) { this.callback = fn; }
    })();
    globalThis.document = {
      hidden: false, readyState: 'complete',
      querySelector: () => ({ruffle: () => api}),
      getElementById: id => id === 'status' ? {textContent: 'ready'} : {disabled: false}
    };
  `, context);
  assert.equal(vm.runInContext(install, context), true);
  return context;
}
function emit(ctx, text) { ctx.api.callback(text); }
const normal = environment();
let forwarded = 0;
normal.api.traceObserver = () => { forwarded++; }; // late shell assignment
emit(normal, 'FO_P1_BEGIN 0 1 1');
for (let i = 1; i <= 12; i++) emit(normal, `FO_STATE ${i} 2 5`);
emit(normal, 'FO_DONE 11 2 5');
assert.equal(normal.__frameOrderCapture.done, false);
emit(normal, 'FO_DONE 12 2 5');
assert.equal(normal.__frameOrderCapture.done, true);
assert.equal(normal.__frameOrderCapture.observerInstalls, 2);
assert.equal(forwarded, 15);
assert.equal(normal.__frameOrderCapture.traces.length, 15);
const report = JSON.parse(vm.runInContext(snapshot, normal));
assert.deepEqual(report.traces.map(x => x.sequence), Array.from({length:15}, (_, i) => i + 1));
assert.deepEqual(report.traces.filter(x => x.line.startsWith('FO_STATE ')).map(x => +x.line.split(' ')[1]), Array.from({length:12}, (_, i) => i + 1));
assert.equal(report.hidden, false);
assert.equal(report.status, 'ready');
assert.equal(report.overflow, false);
assert.equal(report.truncatedLines, 0);
const limited = environment();
emit(limited, 'x'.repeat(2049));
assert.equal(limited.__frameOrderCapture.truncatedLines, 1);
assert.equal(limited.__frameOrderCapture.traces[0].line.length, 2048);
for (let i = 1; i < 512; i++) emit(limited, 'row');
emit(limited, 'FO_DONE 12 2 5'); // overflow must not pretend completion
assert.equal(limited.__frameOrderCapture.overflow, true);
assert.equal(limited.__frameOrderCapture.traces.length, 512);
assert.equal(limited.__frameOrderCapture.done, false);
const unavailable = vm.createContext({document:{querySelector:()=>null}});
assert.equal(vm.runInContext(install, unavailable), false);
console.log('PASS: embedded JS syntax; late observer replacement; ordered 12-tick capture; completion validation; snapshot; truncation; overflow; missing player');
'''.replace('INSTALL', json.dumps(install)).replace('SNAPSHOT', json.dumps(snapshot))
subprocess.run(['node', '-'], input=program, text=True, check=True)

# Source-contract checks only; no claim that these compile or test Swift timing.
assert swift.count('evaluateJavaScript(') == 1
assert 'view.evaluateJavaScript(script) { value, error in' in swift
assert 'case javascriptTimedOut(String)' in swift
assert 'before: min(deadline, Date().addingTimeInterval(2))' in swift
assert 'operation: "final snapshot"' in swift
assert swift.index('add(rawAttachment)') < swift.index('try await session.closeWithoutSaving()')
assert 'session.stop()' not in swift
assert 'Self.priorCleanupFailure = cleanupError' in swift
print('PASS: source contracts for bounded JS routing and awaited teardown (not native compile/execution)')

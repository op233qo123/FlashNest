#!/usr/bin/env python3
"""Exact embedded JavaScript and Swift source contracts, not native compilation."""
import hashlib
import json
from pathlib import Path
import re
import subprocess
import unittest

HERE = Path(__file__).resolve().parent


def embedded(swift, name):
    match = re.search(r'private static let ' + name + r' = """\n(.*?)\n    """', swift, re.S)
    if not match:
        raise AssertionError("Missing literal: " + name)
    source = match[1]
    if '\\(' in source or re.search(r'(?<!\\)\\(?!\\)', source):
        raise AssertionError("Unsupported Swift interpolation/escape in small JS extractor")
    return source.replace('\\\\', '\\')


class CandidateHarnessChecks(unittest.TestCase):
    def test_original_harness_unchanged_and_candidate_source_contracts(self):
        original = HERE.parent / "FrameOrderRuntimeTests.swift"
        self.assertEqual(hashlib.sha256(original.read_bytes()).hexdigest(),
                         "5beb4b3205cf5b7b8fe09a8b5cc0b946a235612501d2072a50ab255c7db92308")
        swift = (HERE / "FrameOrderCandidateRuntimeTests.swift").read_text()
        self.assertEqual(swift.count("evaluateJavaScript("), 1)
        self.assertNotIn("session.stop()", swift)
        self.assertLess(swift.index("add(rawAttachment)"), swift.index("try await session.closeWithoutSaving()"))
        self.assertLess(swift.index("try attest(resource:"), swift.index("await session.start("))
        for text in ("FrameOrderCandidateIdentity.pinSHA256", "FrameOrderCandidateIdentity.lockSHA256",
                     "verifyInventory(root: resource", "verifyInventory(root: webRoot.appendingPathComponent",
                     "rows.count == lines.count", "sequences == rows.indices.map", "stateRowsIntact",
                     "XCTAssertTrue(captureComplete", "Self.priorCleanupFailure = cleanupError",
                     "before: min(deadline, Date().addingTimeInterval(2))"):
            self.assertIn(text, swift)
        self.assertIn('lines.filter { $0.hasPrefix("FO_DONE 12 ") }.count == 1', swift)
        self.assertLess(swift.index("XCTAssertTrue(captureComplete"), swift.index("return Observation("))
        self.assertEqual(re.findall(r'func (test\w+)\(', swift),
                         ["testCandidateNestedRepairContract", "testCandidateControlContract"])

    def test_embedded_observer_and_late_setter_overflow_truncation(self):
        swift = (HERE / "FrameOrderCandidateRuntimeTests.swift").read_text()
        install, snapshot = embedded(swift, "installObserver"), embedded(swift, "snapshot")
        program = r'''
const assert = require('node:assert/strict');
const vm = require('node:vm');
const install = INSTALL, snapshot = SNAPSHOT;
new vm.Script(install); new vm.Script(snapshot);
const ctx = vm.createContext({performance:{now:()=>1}});
vm.runInContext(`globalThis.window=globalThis;
  class API { set traceObserver(fn) { globalThis.sink=fn; } }
  globalThis.player={ruffle:()=>new API()};
  globalThis.document={querySelector:()=>player,hidden:false,readyState:'complete',
    getElementById:()=>({textContent:'ready',disabled:false})};`,ctx);
assert.equal(vm.runInContext(install,ctx),true);
let forwarded=0;
ctx.player.ruffle().traceObserver=()=>forwarded++;
ctx.sink('FO_P1_BEGIN 0 1 1');
for(let i=1;i<=12;i++)ctx.sink(`FO_STATE ${i} 2 7`);
ctx.sink('FO_DONE 11 2 7'); assert.equal(ctx.__frameOrderCapture.done,false);
ctx.sink('FO_DONE 12 2 7'); assert.equal(ctx.__frameOrderCapture.done,true);
assert.equal(forwarded,15); assert.equal(ctx.__frameOrderCapture.observerInstalls,2);
const report=JSON.parse(vm.runInContext(snapshot,ctx));
assert.equal(report.traces.length,15);
assert.deepEqual(report.traces.map(r=>r.sequence),Array.from({length:15},(_,i)=>i+1));
ctx.sink('x'.repeat(2049)); assert.equal(ctx.__frameOrderCapture.truncatedLines,1);
for(let i=0;i<600;i++)ctx.sink('extra');
assert.equal(ctx.__frameOrderCapture.traces.length,512); assert.equal(ctx.__frameOrderCapture.overflow,true);
'''.replace("INSTALL", json.dumps(install)).replace("SNAPSHOT", json.dumps(snapshot))
        subprocess.run(["node", "-"], input=program, text=True, check=True)


if __name__ == "__main__":
    unittest.main(verbosity=2)

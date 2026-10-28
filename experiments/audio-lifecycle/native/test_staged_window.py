"""Actual staged observer with fake native objects: no WebKit/audio execution."""
import importlib.util
from pathlib import Path
import subprocess
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('staged_window_adapter', HERE / 'stage_native.py')
stage = importlib.util.module_from_spec(spec)
spec.loader.exec_module(stage)


class StagedWindow(unittest.TestCase):
    def test_actual_transformed_observer_preserves_metadata_late_promises_and_node_cap(self):
        browser = stage.ROOT / 'experiments/audio-lifecycle/browser-tests'
        source = (browser / 'test_observer.mjs').read_text()
        environment = source[source.index('function environment()'):source.index('const flush=')]
        javascript = r"""
import assert from 'node:assert/strict';
import {installAudioObserver} from './observer.mjs';
ENVIRONMENT
const receipt=(cycle,status)=>({token:'test/'+cycle,cycle,start:status.start,endExclusive:status.endExclusive,count:status.count,bytes:1,sha256:'a'.repeat(64)});
{
 const e=environment(),observer=installAudioObserver(e.g);observer.setCycle(0);
 try {
  const ctx=new e.Context(),node=ctx.createBufferSource();function original(){};node.onended=original;
  let settle;ctx.closePromise=new Promise(resolve=>settle=resolve);assert.equal(ctx.close(),ctx.closePromise);
  const before=observer.snapshot(),r=receipt(0,before.eventWindow);observer.nativeWindow.armReceipt(r);
  // A real observer Promise continuation runs after prefix acknowledgment.
  observer.nativeWindow.acceptReceipt(r);settle();await Promise.resolve();await Promise.resolve();
  const after=observer.snapshot();assert.equal(after.events[0].seq,r.endExclusive);assert.equal(after.events[0].kind,'close-fulfilled');
  assert.deepEqual(after.contexts[0].closeSnapshots[0].attachedIds,[1]);assert.equal(after.nodes[0].attached,true);
  assert.equal(node.onended,original);assert.equal(after.contexts[0].closeFulfilled,1);
  observer.nativeWindow.markFinalBoundary();ctx.createBufferSource();
  assert(observer.snapshot().eventWindow.postFinalActivity>0);assert.equal(observer.snapshot().nodes.length,2);
 } finally {observer.restore();e.restored()}
}
{
 const e=environment(),observer=installAudioObserver(e.g);observer.setCycle(0);
 try {
  const ctx=new e.Context();
  for(let cycle=0;cycle<8;cycle++){
   for(let n=0;n<512;n++)ctx.createBufferSource();
   const s=observer.snapshot(),r=receipt(cycle,s.eventWindow);assert.equal(s.overflow,false);
   observer.nativeWindow.armReceipt(r);observer.nativeWindow.acceptReceipt(r);
  }
  assert.equal(observer.snapshot().nodes.length,4096);assert.equal(observer.snapshot().events.length,0);
  const returned=ctx.createBufferSource();assert(returned instanceof e.Source);
  const s=observer.snapshot();assert.equal(s.overflow,true);assert.equal(s.nodes.length,4096);
  assert.equal(s.contexts[0].sourceAttempts,4097);assert.equal(s.contexts[0].nodes,4096);
 } finally {observer.restore();e.restored()}
}
console.log('PASS staged observer late Promise, exact original callback identity, global metadata and retained4096-node cap');
""".replace('ENVIRONMENT', environment)
        with tempfile.TemporaryDirectory(prefix='native-window-stage-') as directory:
            out = Path(directory)
            transformed, record = stage.transform((browser / 'observer.mjs').read_bytes(), stage.OBSERVER_TRANSFORMS,
                                                   'observer.mjs', 'observer.mjs')
            self.assertEqual(len(record['replacements']), 3)
            (out / 'observer.mjs').write_bytes(transformed)
            (out / 'observer-window.mjs').write_bytes((HERE / 'Web/observer-window.mjs').read_bytes())
            (out / 'test.mjs').write_text(javascript)
            subprocess.run(['node', str(out / 'test.mjs')], check=True, timeout=20)

    def test_host_readback_failure_cannot_reach_receipt_delivery(self):
        # Source/control-flow check, not a substituted filesystem implementation
        # or Swift execution: any throwing retainBytes/readback exits the enclosing
        # do block into the existing fatal-evidence catch before the Task is made.
        host = (HERE / 'Host/NativeAudioHost.swift').read_text()
        block = host[host.index('            case "case":'):host.index('            case "complete":')]
        self.assertLess(block.index('try retainBytes('), block.index('caseReceiptTasks.append'))
        self.assertLess(block.index('try retain("case-receipt-'), block.index('caseReceiptTasks.append'))
        write = host[host.index('    private func retainBytes('):host.index('    private func verifyBundle(')]
        for source in ['options: [.atomic]', 'try handle.read(upToCount: 2 * 1024 * 1024 + 1)', 'readback == data',
                       'data.count <= 2 * 1024 * 1024', 'retainedBytes + data.count <= 16 * 1024 * 1024']:
            self.assertIn(source, write)
        self.assertEqual(write.count('defer { try? handle.close() }'), 1)
        self.assertNotIn('try?', write.replace('defer { try? handle.close() }', ''))
        self.assertIn('Evidence/bridge error:', host)


if __name__ == '__main__':
    unittest.main()

"""Local command-order mocks, not a real TypeScript/WASM compilation claim."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
SCRIPT = HERE / 'build_web_candidate.sh'


class CompileGate(unittest.TestCase):
    def run_recipe(self, fail_types=False):
        with tempfile.TemporaryDirectory(prefix='audio-compile-order-') as directory:
            root = Path(directory)
            tools = root / 'tools'
            tools.mkdir()
            source = root / 'source'
            (source / 'web/node_modules').mkdir(parents=True)
            output = root / 'output'
            output.mkdir()
            commands = {
                'rustc': 'echo "rustc 1.99.1 (mock)"',
                'node': 'echo v24.22.1',
                'wasm-bindgen': 'echo "wasm-bindgen 0.2.127"',
                'wasm-opt': 'echo "wasm-opt version 129"',
                'python3': 'printf "python %s\\n" "$*" >> "$ORDER_LOG"; if [[ "$2" == prepare ]]; then echo 1; fi',
                'npm': '''printf 'npm|%s|%s\\n' "${BUILD_WASM_MVP-unset}" "$*" >> "$ORDER_LOG"
if [[ "$1" == exec && "${FAIL_TYPES:-0}" == 1 ]]; then echo 'synthetic typecheck failure' >&2; exit 19; fi''',
            }
            for name, body in commands.items():
                path = tools / name
                path.write_text('#!/usr/bin/env bash\nset -eu\n' + body + '\n')
                path.chmod(0o755)
            log = root / 'order.txt'
            env = dict(os.environ, PATH=str(tools) + os.pathsep + os.environ['PATH'],
                       ORDER_LOG=str(log), FAIL_TYPES='1' if fail_types else '0')
            result = subprocess.run(['bash', str(SCRIPT), str(source), str(output)],
                                    env=env, text=True, capture_output=True, timeout=15)
            return result, log.read_text().splitlines(), sorted(p.name for p in output.iterdir())

    def test_real_binding_then_full_core_before_dual_build(self):
        result, lines, files = self.run_recipe()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual([x for x in lines if x.startswith('npm|')], [
            'npm|unset|run prebuild --workspace=ruffle-core',
            'npm|unset|exec --workspace=ruffle-core -- tsc --build --force',
            'npm|true|run build --workspace=ruffle-core',
            'npm|true|run build --workspace=ruffle-selfhosted',
            'npm|true|test --workspace=ruffle-core -- --reporter json --forbid-only --forbid-pending',
        ])
        self.assertIn('core-types-preflight.log', files)
        self.assertTrue(any('check_js_results.py' in x for x in lines))
        self.assertTrue(lines[-1].startswith('python ') and ' package ' in lines[-1])

    def test_typecheck_failure_prevents_dual_build_tests_and_packaging(self):
        result, lines, files = self.run_recipe(fail_types=True)
        self.assertEqual(result.returncode, 19)
        self.assertEqual(len([x for x in lines if x.startswith('npm|')]), 2)
        self.assertFalse(any(' package ' in x or 'check_js_results.py' in x for x in lines))
        self.assertEqual(files, ['core-types-preflight.log'])

    def test_workflow_copy_and_preflight_selftest(self):
        root = HERE.parents[2]
        workflow = root / '.github/workflows/experiment-audio-recovery.yml'
        self.assertEqual(workflow.read_bytes(), (HERE.parent / 'workflow-draft.yml').read_bytes())
        self.assertIn('python3 experiments/audio-recovery/engine-build/test_compile_gate.py', workflow.read_text())

    def test_exact_binding_block_skips_absent_instance_without_assertion(self):
        # Run the actual added JavaScript-compatible block reconstructed from the
        # patch, not a replacement implementation or hand-written ABI declaration.
        patch = (HERE.parent / 'audio-recovery.patch').read_text()
        added = '\n'.join(line[1:] for line in patch.splitlines() if line.startswith('+') and not line.startswith('+++'))
        marker = '        // Bind before the autoplay/visibility wait or any frontend resume.'
        self.assertEqual(added.count(marker), 1)
        block = added.split(marker, 1)[1].split('\n\n', 1)[0]
        self.assertIn('const context = this.instance?.audio_context();', block)
        javascript = '''const assert = require('node:assert/strict');
const block = BLOCK;
const execute = new Function('bindAudioContext', 'CustomEvent', block);
class Event { constructor(type, options) { this.type=type; this.detail=options.detail; } }
let binds=0, reads=0, emitted=[];
const bind=(context, listener)=>{ binds++; assert.equal(context, real); listener('owned'); return 'release'; };
const real={};
for (const instance of [null, undefined, {audio_context(){ reads++; return null; }}]) {
  const host={instance, element:{dispatchEvent(){ throw Error('must not emit'); }}};
  execute.call(host, bind, Event); assert.equal(host.releaseAudioContext, undefined);
}
assert.equal(binds,0); assert.equal(reads,1);
const host={instance:{audio_context(){ reads++; return real; }}, element:{dispatchEvent(event){ emitted.push(event); }}};
execute.call(host, bind, Event); assert.equal(binds,1); assert.equal(reads,2);
assert.equal(host.releaseAudioContext,'release'); assert.equal(emitted[0].type,'ruffle-audio-status'); assert.equal(emitted[0].detail,'owned');
const failure=new Error('original accessor error');
assert.throws(()=>execute.call({instance:{audio_context(){throw failure;}}}, bind, Event),e=>e===failure);
'''.replace('BLOCK', json.dumps(block))
        subprocess.run(['node', '-e', javascript], check=True, capture_output=True, timeout=15)


if __name__ == '__main__':
    unittest.main()

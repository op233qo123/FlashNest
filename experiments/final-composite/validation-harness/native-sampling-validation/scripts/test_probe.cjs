// Mock contract tests ONLY. These are not rendered/native evidence.
const assert = require('node:assert/strict');
const fs = require('node:fs'), vm = require('node:vm');
const source = fs.readFileSync(__dirname + '/../Host/sampling-probe.js', 'utf8');
function setup(quality = '') {
  const listeners = {}, calls = [];
  class GL {
    constructor(canvas) { this.canvas = canvas; this.drawingBufferWidth = 300; this.drawingBufferHeight = 450; }
    renderbufferStorage(...args) { calls.push(['single', this, args]); return 9; }
  }
  class GL2 extends GL { renderbufferStorageMultisample(...args) { calls.push(['multi', this, args]); return 7; } }
  class Canvas {
    constructor() { this.width = 300; this.height = 450; this.clientWidth = 400; this.clientHeight = 600; this.attributes = []; this.context = new GL2(this); }
    addEventListener(type, callback, options) { assert.equal(options.passive, true); listeners[type] = callback; }
    getContext(type) { if (type === 'throw') throw Error('original exception'); return type === 'webgl2' ? this.context : null; }
    getBoundingClientRect() { return {x: 0, y: 0, width: 400, height: 600}; }
  }
  const canvas = new Canvas(), player = {shadowRoot: {querySelector: () => canvas}};
  const box = {HTMLCanvasElement: Canvas, WebGLRenderingContext: GL, WebGL2RenderingContext: GL2,
    location: {search: quality ? '?nativeSamplingQuality=' + quality : ''}, URL, URLSearchParams,
    console: {log: (...args) => { calls.push(['log', args]); return 11; }}, devicePixelRatio: 3,
    document: {querySelector: () => player, activeElement: player, hidden: false,
      addEventListener: (type, callback, options) => { assert.equal(options.capture, true); assert.equal(options.passive, true); listeners[type] = callback; }},
    performance: {getEntriesByType: () => [{name: 'http://127.0.0.1/private-capability/runtime/actual.wasm'}]}};
  box.window = box; vm.createContext(box); vm.runInContext(source, box);
  return {box, canvas, calls, listeners};
}
let {box, canvas, calls, listeners} = setup();
assert.strictEqual(canvas.getContext('webgl2'), canvas.context);
assert.equal(canvas.getContext('2d'), null);
assert.throws(() => canvas.getContext('throw'), /original exception/);
assert.equal(canvas.context.renderbufferStorageMultisample(1, 4, 2, 1200, 1800), 7);
assert.equal(canvas.context.renderbufferStorageMultisample(1, 4, 2, 1200, 1800), 7);
assert.equal(box.console.log('%cNew Ruffle instance created (Version: test | Used renderer: webgl)'), 11);
const e = {composedPath: () => [canvas], type: 'pointerdown', isTrusted: true, clientX: 30, clientY: 40, offsetX: 30, offsetY: 40, pointerType: 'touch', pointerId: 1};
listeners.pointerdown(e);
let m = box.__samplingNativeProbe.measure();
assert.deepEqual(Array.from(m.gl), [300, 450]); assert.equal(m.storage.length, 1);
assert.deepEqual(Array.from(m.storage[0]), [4, 1200, 1800]); assert.equal(m.allocations, 2);
assert.equal(m.renderer, 'webgl'); assert.equal(m.events[0].trusted, true);
assert.deepEqual(Array.from(m.wasm), ['actual.wasm']); assert.equal(m.diagnosticLaunchQuality, null);
assert.equal(canvas.width, 300); assert.equal(canvas.height, 450); assert.equal(m.overflow, false);
assert.equal(calls[0][1], canvas.context, 'allocator this and result preserved');
for (let i = 0; i < 64; i++) listeners.pointerdown(e);
assert.equal(box.__samplingNativeProbe.measure().events.length, 64);
assert.equal(box.__samplingNativeProbe.measure().overflow, true);
assert.equal(setup('high').box.__samplingNativeDiagnosticQuality, 'high');
assert.equal(setup('low').box.__samplingNativeDiagnosticQuality, 'low');
assert.throws(() => setup('arbitrary'), /Invalid diagnostic quality/);
console.log('PASS observer mock contracts: transparent calls, allocation evidence, bounded passive touch, privacy, explicit diagnostic identity; NOT native execution');

// v3 passive actual-load forwarding: exact receiver/object/result/throw, not an echo.
{
 const x=setup();x.canvas.getContext('webgl2');const config={preferredRenderer:'webgl'}, result={exact:true};
 const api={load(c){assert.strictEqual(this,api);assert.strictEqual(c,config);return result;}};
 assert.strictEqual(x.box.__samplingNativeProbe.observeLoad(api,config),result);
 const seen=x.box.__samplingNativeProbe.measure().loadObservation;
 assert.equal(seen.preferredRenderer,'webgl');assert.equal(seen.hasPreferredRenderer,true);assert.equal(seen.rendererQuery,null);
}
{
 const x=setup();x.canvas.getContext('webgl2');x.box.location.search='?renderer=enhanced';
 const config={};const failure=new Error('original load failure');const api={load(c){assert.strictEqual(c,config);throw failure;}};
 assert.throws(()=>x.box.__samplingNativeProbe.observeLoad(api,config),e=>e===failure);
 const seen=x.box.__samplingNativeProbe.measure().loadObservation;assert.equal(seen.rendererQuery,'enhanced');assert.equal(seen.hasPreferredRenderer,false);assert.equal(seen.preferredRenderer,null);
}
console.log('PASS actual load forwarding models; NOT native backend proof');

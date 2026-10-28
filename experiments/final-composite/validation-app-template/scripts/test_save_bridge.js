/* Pure bridge contract/rollback tests; real Ruffle execution lives in
 * SharedObjectWebKitTests.swift and test_saves_browser.py. */
const assert = require('node:assert/strict'), vm = require('node:vm'), fs = require('node:fs'), path = require('node:path');
const source = fs.readFileSync(path.join(__dirname, '../App/Resources/Web/save-bridge.js'), 'utf8');
const id = '11111111-1111-4111-8111-111111111111', otherID = '22222222-2222-4222-8222-222222222222';
const cap = 'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa', otherCap = 'bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb';
const sol = size => { const bytes = Buffer.alloc(size || 24); bytes[1] = 191; bytes.write('TCSO', 6); bytes[11] = 4; return bytes.toString('base64'); };
const valid = sol(), changed = sol(25);
class Storage {
  constructor(entries = []) { this.map = new Map(entries); this.failNextSet = false; }
  get length() { return this.map.size; }
  key(index) { return [...this.map.keys()][index] ?? null; }
  getItem(key) { return this.map.get(key) ?? null; }
  setItem(key, value) { if (this.failNextSet) { this.failNextSet = false; throw new Error('quota fixture'); } this.map.set(key, value); }
  removeItem(key) { this.map.delete(key); }
}
function create(storage, token = cap, packageID = id) {
  const context = {window:{}, URL, TextEncoder, atob, btoa};
  vm.runInNewContext(source, context);
  return context.window.FlashNestSaveBridge.create({storage, location:`http://127.0.0.1:8766/${token}/web/index.html`, packageID});
}
const plain = value => JSON.parse(JSON.stringify(value));
const entry = (scope, key, value = valid) => ({scope, key, value});
const capture = entries => ({version:1, entries});
const raw = {
  package:`127.0.0.1/${cap}/games/${id}/nested/%E5%85%A5%E5%8F%A3.swf/Save`,
  origin:'127.0.0.1//RootSave', games:`127.0.0.1/${cap}/games/GamesSave`, ancestor:`127.0.0.1/${cap}/AncestorSave`,
  slash:`127.0.0.1// #unused`
};
const storage = new Storage([[raw.package, valid], [raw.origin, valid], [raw.games, valid], [raw.ancestor, valid], ['preference','keep']]);
const bridge = create(storage);
const logical = plain(bridge.capture());
assert.deepEqual(logical, capture([
  entry('package','nested/%E5%85%A5%E5%8F%A3.swf/Save'), entry('origin','RootSave'),
  entry('ancestor','games/GamesSave'), entry('ancestor','capability/AncestorSave')
]));
assert(!JSON.stringify(logical).includes(cap)); assert(!JSON.stringify(logical).includes(id)); assert(!JSON.stringify(logical).includes('127.0.0.1'));
const migratedStorage = new Storage([['preference','keep']]), migrated = create(migratedStorage, otherCap, otherID);
migrated.restore(logical);
assert.deepEqual(plain(migrated.capture()), logical);
assert(migratedStorage.getItem(`127.0.0.1/${otherCap}/games/${otherID}/nested/%E5%85%A5%E5%8F%A3.swf/Save`));
assert.equal(migratedStorage.getItem('preference'), 'keep');
// Slash-containing names have Ruffle's explicit # marker; empty name components
// are allowed by pinned Ruffle and must not be normalized away by our bridge.
for (const e of [entry('origin','#nested//Save'), entry('ancestor','games/#nested/Save'), entry('package','nested.swf/#nested/Save')]) {
  const s = new Storage(), b = create(s); b.restore(capture([e])); assert.deepEqual(plain(b.capture()), capture([e]));
}
const before = [...storage.map];
for (const bad of [
  {version:2,entries:[]}, capture([entry('unknown','key')]), capture([entry('origin','nested/Save')]),
  capture([entry('ancestor','games/' + otherID + '/Save')]), capture([entry('ancestor','unknown/Save')]),
  capture([entry('package','../Save')]), capture([entry('package','.hidden.swf/Save')]), capture([entry('package','remote:Save')]),
  capture([entry('origin','bad\\key')]), capture([entry('origin','bad\0key')]), capture([entry('origin','x'.repeat(4097))]),
  capture([entry('origin','Save'),entry('origin','Save')]), capture([entry('origin','Save','not base64')]),
  capture([entry('origin','Save',valid + '\n')]), capture([entry('origin','Save',Buffer.from('not SOL').toString('base64'))]),
  capture([entry('origin','Save',sol(1048577))]), capture(Array.from({length:257},(_,i) => entry('origin','Save'+i))),
  capture(Array.from({length:9},(_,i) => entry('origin','Save'+i,sol(1048576))))
]) {
  assert.throws(() => bridge.restore(bad)); assert.deepEqual([...storage.map], before, 'Reject all invalid entries before mutation');
}
const unknown = new Storage([['remote.example/game.swf/Save',valid]]);
assert.throws(() => create(unknown).capture(), /scope/);
const otherPackage = new Storage([[`127.0.0.1/${cap}/games/${otherID}/game.swf/Save`,valid]]);
assert.throws(() => create(otherPackage).capture(), /scope/);
const collision = new Storage([[raw.origin,'not SOL']]);
assert.throws(() => create(collision).restore(capture([entry('origin','RootSave')])), /collision/);
assert.equal(collision.getItem(raw.origin), 'not SOL');
storage.failNextSet = true;
assert.throws(() => bridge.restore(capture([entry('origin','RootSave',changed)])), /previous storage restored/);
assert.deepEqual([...storage.map].sort(), [...before].sort(), 'Failed quota write restores all old SOL and unrelated storage');
bridge.restore(capture([]));
assert.deepEqual([...storage.map], [['preference','keep']], 'Explicit empty restore removes SOL only');
// Lazily supply synthetic values and count reads: an invalid inventory must
// stop before materializing/retaining later large strings. This measures a
// bridge iteration bound, not browser Storage/RSS or WebContent memory.
class CountingStorage {
  constructor(count, valueAt) { this.length = count; this.valueAt = valueAt; this.reads = 0; this.writes = 0; }
  key(index) { return `127.0.0.1//Object${index}`; }
  getItem(key) { this.reads++; return this.valueAt(Number(key.slice(key.lastIndexOf('Object') + 6))); }
  setItem() { this.writes++; throw new Error('Unexpected write'); }
  removeItem() { this.writes++; throw new Error('Unexpected write'); }
}
const fullObject = sol(1048576);
const tooManyBytes = new CountingStorage(200, () => fullObject);
assert.throws(() => create(tooManyBytes).capture(), /total size/);
assert.equal(tooManyBytes.reads, 9, 'Stop on the first object beyond 8 MiB, not after all 200 reads');
assert.equal(tooManyBytes.writes, 0);
const oversizedValue = new CountingStorage(200, () => sol(1048577));
assert.throws(() => create(oversizedValue).capture(), /object size/);
assert.equal(oversizedValue.reads, 1, 'Reject oversized SOL before requesting another value');
const malformedValue = new CountingStorage(200, () => valid + '\n');
assert.throws(() => create(malformedValue).capture(), /SOL encoding/);
assert.equal(malformedValue.reads, 1, 'Canonical base64 still fails before additional reads');
const tooManyObjects = new CountingStorage(300, () => valid);
assert.throws(() => create(tooManyObjects).capture(), /object count/);
assert.equal(tooManyObjects.reads, 257);
const failedRestoreInventory = new CountingStorage(200, () => fullObject);
assert.throws(() => create(failedRestoreInventory).restore(capture([entry('origin','Replacement')])), /total size/);
assert.equal(failedRestoreInventory.reads, 9);
assert.equal(failedRestoreInventory.writes, 0, 'Invalid existing inventory never starts restore or rollback writes');
const exactLimit = new CountingStorage(8, () => fullObject);
assert.equal(create(exactLimit).capture().entries.length, 8, 'Exactly 8 MiB remains valid');
console.log('PASS save bridge logical scopes, cross-install mapping, validation, limits, unrelated data and rollback (unit tests)');

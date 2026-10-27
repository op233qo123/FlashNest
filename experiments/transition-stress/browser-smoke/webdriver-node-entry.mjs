import assert from 'node:assert/strict';
import path from 'node:path';
import {pathToFileURL} from 'node:url';

// Do not import build/index.js: it is the browser entry and omits Node screenshot handlers.
export function webdriverNodeEntry(pkg, directory) {
  assert.equal(pkg.version, '9.32.0', 'Pinned WebdriverIO version');
  assert.equal(pkg.exports?.['.']?.import, './build/node.js', 'Pinned WebdriverIO Node export');
  return pathToFileURL(path.resolve(directory, 'build/node.js')).href;
}

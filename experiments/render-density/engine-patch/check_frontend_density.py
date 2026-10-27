#!/usr/bin/env python3
"""Exact pinned source and additive patch checks; not Rust/GPU execution."""
import argparse
import difflib
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def method(source, marker):
    start = source.index(marker)
    opening = source.index('{', start)
    depth = 1
    for index in range(opening + 1, len(source)):
        depth += (source[index] == '{') - (source[index] == '}')
        if depth == 0:
            return source[start:index + 1]
    raise AssertionError('Unclosed method')


def check(original, modified):
    if not __debug__:
        raise RuntimeError('Do not disable source assertions')
    manifest = json.loads((HERE / 'frontend-source-manifest.json').read_text())
    assert manifest['upstreamCommit'] == '89a7049965f3090e706265670df309a5128233ac'
    old, new, patch = {}, {}, []
    for row in manifest['files']:
        relative = row['path']
        path = original / relative
        a = path.read_bytes() if path.exists() else b''
        b = (modified / relative).read_bytes()
        assert hashlib.sha256(b).hexdigest() == row['modifiedSHA256'], relative
        assert len(b) == row['bytes'], relative
        if row['originalGitBlob'] is not None:
            assert hashlib.sha256(a).hexdigest() == row['originalSHA256'], relative
            assert hashlib.sha1(b'blob ' + str(len(a)).encode() + b'\0' + a).hexdigest() == row['originalGitBlob'], relative
        else:
            assert not path.exists(), relative
        old[relative], new[relative] = a.decode(), b.decode()
        patch.extend(difflib.unified_diff(a.decode().splitlines(True), b.decode().splitlines(True),
            fromfile='a/' + relative if path.exists() else '/dev/null', tofile='b/' + relative))
    assert (HERE / 'frontend-webgl-density.patch').read_text() == ''.join(patch)
    player = 'core/src/player.rs'
    marker = '    pub fn set_viewport_dimensions('
    assert method(old[player], marker) == method(new[player], marker)
    gl = 'render/webgl/src/lib.rs'
    marker = '    fn set_viewport_dimensions('
    assert method(old[gl], marker) == method(new[gl], marker).replace('        self.virtual_viewport = None;\n', '')
    opt_in = method(new[gl], '    fn set_viewport_dimensions_with_backing(')
    assert opt_in.index('self.msaa_sample_count > 1') < opt_in.index('self.set_viewport_dimensions(dimensions)')
    assert 'self.gl.drawing_buffer_width() != backing_width as i32' in opt_in
    assert 'self.virtual_viewport = Some(dimensions)' in opt_in
    web = 'web/src/lib.rs'
    a = old[web].split('    fn tick(self, timestamp: f64) {')[0]
    b = new[web].split('    fn tick(self, timestamp: f64) {')[0]
    assert a == b.replace('    render_scale: f64,\n', '').replace('            render_scale: config.render_scale,\n', '')
    for fragment in ['let canvas_width = instance.canvas.client_width();',
                     'let canvas_height = instance.canvas.client_height();',
                     'let device_pixel_ratio = instance.window.device_pixel_ratio();',
                     'let viewport_width = (f64::from(canvas_width) * device_pixel_ratio) as u32;',
                     'let viewport_height = (f64::from(canvas_height) * device_pixel_ratio) as u32;']:
        assert fragment in old[web] and fragment in new[web]
    tests = new['web/packages/core/test/render-scale.ts']
    assert tests.count('    it(') == 4
    defaults = 'web/packages/core/src/public/config/default.ts'
    assert old[defaults] == new[defaults].replace('    renderScale: null,\n', '')
    assert 'renderScale?: 1 | 0.75 | 0.5 | 0.25 | null;' in new['web/packages/core/src/public/config/load-options.ts']
    assert 'assert.equal(DEFAULT_CONFIG.renderScale, null)' in tests
    assert 'apply({ renderScale: DEFAULT_CONFIG.renderScale })' in tests
    assert 'core/src/display_object/stage.rs' not in new
    assert 'core/src/display_object/movie_clip.rs' not in new
    print('PASS: eight pinned Git blobs, exact nine-file patch, unchanged default/input paths, four config tests')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--original', type=Path, required=True)
    parser.add_argument('--modified', type=Path, required=True)
    args = parser.parse_args()
    check(args.original, args.modified)

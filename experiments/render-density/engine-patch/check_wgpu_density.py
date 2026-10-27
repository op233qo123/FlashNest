#!/usr/bin/env python3
"""Read-only source/patch checks; not a Rust build or GPU rendering test."""
import argparse
import difflib
import hashlib
import math
from pathlib import Path

FILES = {
    'render/wgpu/src/backend.rs': '5dcf43c0a7d97e02d34722bee428a5e5095e0828',
    'render/wgpu/src/surface.rs': 'b6197150dd94ca85900250b01573d704037b3090',
    'render/wgpu/src/surface/commands.rs': '647a687d353bb7a6187ee56694b065abefc125f7',
    'render/wgpu/src/surface/target.rs': '1cfe3dc5b7228463a047adaaec636876193d0948',
}


def between(source, first, last):
    start = source.index(first)
    return source[start:source.index(last, start)]


def check(original, modified, patch):
    if not __debug__:
        raise RuntimeError('Run source assertions without Python optimization (-O)')
    old, new, expected_patch = {}, {}, []
    for relative in sorted(map(Path, FILES)):
        path = str(relative)
        data = (original / path).read_bytes()
        blob = b'blob ' + str(len(data)).encode() + b'\0' + data
        assert hashlib.sha1(blob).hexdigest() == FILES[path], path
        old[path] = data.decode()
        new[path] = (modified / path).read_text()
        expected_patch.extend(difflib.unified_diff(
            old[path].splitlines(keepends=True), new[path].splitlines(keepends=True),
            fromfile='a/' + path, tofile='b/' + path))
    assert patch.read_text() == ''.join(expected_patch)

    backend = 'render/wgpu/src/backend.rs'
    a, b = old[backend], new[backend]
    old_setter = between(a, '    fn set_viewport_dimensions(', '    fn create_context3d(')
    new_setter = between(b, '    fn set_viewport_dimensions(',
                         '    fn set_viewport_dimensions_with_backing(')
    assert old_setter.rstrip() == new_setter.replace(
        '        self.virtual_viewport = None;\n', '').rstrip()
    for first, last in [
        ('        for entry in cache_entries {', '        self.surface.draw_commands_and_copy_to('),
        ('        let Some(frame_output) = self.target.get_next_texture() else {',
         '        for entry in cache_entries {'),
        ('    fn create_context3d(', '    fn debug_info('),
        ('    fn render_offscreen(', '    fn apply_filter('),
    ]:
        assert between(a, first, last) == between(b, first, last), first
    special = between(b, '    fn set_viewport_dimensions_with_backing(',
                      '    fn create_context3d(')
    before_mutation = special[:special.index('        if backing_width == dimensions.width')]
    for guard in ['dimensions.width == 0', 'dimensions.height == 0',
                  'dimensions.width > limit', 'dimensions.height > limit',
                  '!dimensions.scale_factor.is_finite()', 'dimensions.scale_factor <= 0.0',
                  'backing_width == 0', 'backing_height == 0',
                  'backing_width > dimensions.width', 'backing_height > dimensions.height']:
        assert guard in before_mutation, guard
    assert 'return false;' in before_mutation
    assert 'self.virtual_viewport = Some(dimensions);' in special
    assert 'let projection_size = self.surface.projection_size();' in b
    assert '.with_projection_size(projection_size);' in b
    assert 'if let Some(dimensions) = self.virtual_viewport' in b

    surface = new['render/wgpu/src/surface.rs']
    assert 'projection_size: (width, height),' in surface
    assert 'if self.projection_size != (self.size.width, self.size.height)' in surface
    assert 'target.set_projection_size(descriptors, texture_pool, self.projection_size);' in surface
    assert 'target.height(),\n            self.projection_size,' in surface
    target = 'render/wgpu/src/surface/target.rs'
    assert between(old[target], '    pub fn new(', '    pub fn globals(') == between(
        new[target], '    pub fn new(', '    pub fn globals(')
    assert 'self.globals = pool.get_globals(descriptors, size.0, size.1);' in new[target]
    commands = new['render/wgpu/src/surface/commands.rs']
    assert commands.count('.with_projection_size(self.projection_size);') == 2
    assert commands.count('self.projection_size.0 as f32,') == 2
    assert commands.count('self.projection_size.1 as f32,') == 2
    assert 'Matrix::scale(target.width()' not in commands
    assert 'Matrix::scale(maskee.width()' not in commands

    # Algebra check only: integer physical sizes cancel when presented at the
    # same CSS extent. This does not execute Stage, AS3, shaders, or hit tests.
    cases = 0
    for css_width, css_height in [(393, 759), (759, 393), (551, 401), (1, 3)]:
        for dpr in [1, 1.25, 1.5, 2, 3]:
            virtual = (int(css_width * dpr), int(css_height * dpr))
            for tier in [1, .75, .5, .25]:
                physical = tuple(max(1, math.floor(value * tier + .5)) for value in virtual)
                for css, logical, backing in zip((css_width, css_height), virtual, physical):
                    for fraction in [0, .125, .5, .875, 1]:
                        coordinate = logical * fraction
                        presented = (coordinate / logical * backing) / backing * css
                        assert math.isclose(presented, css * fraction, abs_tol=1e-10)
                cases += 1
    return cases


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--original', type=Path, required=True)
    parser.add_argument('--modified', type=Path, required=True)
    parser.add_argument('--patch', type=Path,
                        default=Path(__file__).with_name('wgpu-density.patch'))
    args = parser.parse_args()
    cases = check(args.original, args.modified, args.patch)
    print(f'PASS: four pinned Git blobs, exact patch, source invariants, {cases} algebra cases')

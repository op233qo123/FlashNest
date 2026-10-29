"""Independent numeric oracle for center-aligned, zero-origin 320x240 fixture.
Models source matrix quantization, not fitted SWF responses. No input calibration.
Source: render/src/matrix.rs, display_object.rs::local_mouse_position, stage.rs.
Root local_to_global is identity. Float32 and ties-even are deliberate.
"""
import math
import struct

def f32(x):
    return struct.unpack('<f', struct.pack('<f', x))[0]

def rounded(x):
    return round(f32(x))

def stage_position(offset, viewport, dpr, mode):
    """Stored stage Twips from current canvas offset CSS point."""
    w, h = viewport
    scale = min(w / 320, h / 240) if mode == 'showAll' else dpr
    assert mode in ('showAll', 'noScale') and scale > 0
    a = f32(scale)
    det = f32(a * a)
    inv = f32(a / det)
    out = []
    for p, v, size in zip(offset, viewport, (320, 240)):
        translation = math.trunc((v - size * scale) / 2 * 20)
        inv_translation = rounded(f32(-f32(a * f32(translation)) / det))
        input_twips = math.trunc(p * dpr * 20)
        out.append(rounded(f32(inv * f32(input_twips))) + inv_translation)
    return tuple(out)

def reported_position(stage_twips, viewport, dpr, mode):
    """Root _xmouse/_ymouse; also use NEW viewport on OLD stored Twips after resize."""
    w, h = viewport
    scale = f32(min(w / 320, h / 240) if mode == 'showAll' else dpr)
    px = f32(1 / 20)
    coefficient = f32(scale * px)
    determinant = f32(coefficient * coefficient)
    inverse = f32(coefficient / determinant)
    result = []
    for value in stage_twips:
        physical_twips = rounded(f32(scale * f32(value)))
        physical_pixels = rounded(f32(px * f32(physical_twips)))
        result.append(rounded(f32(inverse * f32(physical_pixels))) / 20)
    return tuple(result)

def current_position(offset, viewport, dpr, mode):
    return reported_position(stage_position(offset, viewport, dpr, mode), viewport, dpr, mode)

if __name__ == '__main__':
    points = [(56,203),(319,203),(56,399),(319,399),(188,301)]
    expected = [(47.8,36.25),(272.2,36.25),(47.8,203.5),(272.2,203.5),(160.45,119.9)]
    actual = [current_position(p,(750,1204),2,'showAll') for p in points]
    assert actual == expected, (actual, expected)
    print('PASS exact five independently computed diagnostic UP coordinates:', actual)
    print('Not native execution; baseline source identity and all viewport modes still require real validation.')

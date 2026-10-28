"""Port of vetted synthetic vector-bound gate; not visual-equivalence at low tiers."""
import math
from PIL import ImageChops

def compare(actual, baseline, css_width):
    assert actual.size == baseline.size
    def bounds(image):
        channels = image.split()
        mask = channels[0].point(lambda x: 255 if abs(x-25)<8 else 0)
        for channel, target in zip(channels[1:], [171,117]):
            mask = ImageChops.multiply(mask, channel.point(lambda x: 255 if abs(x-target)<8 else 0))
        assert sum(mask.histogram()[1:]) >= 100, 'missing green vector'
        return mask.getbbox()
    box, ref = bounds(actual), bounds(baseline)
    tolerance = math.ceil(4*actual.width/css_width)
    assert all(abs(a-b)<=tolerance for a,b in zip(box,ref)), ('vector geometry differs',box,ref,tolerance)
    return {'vectorBoundsExclusive':box,'baselineVectorBoundsExclusive':ref,'edgeTolerancePixels':tolerance}

def validate_warning(state):
    assert state['visible'] is True and state['id']=='hardware-acceleration-modal'
    assert state['text']=='It looks like hardware acceleration is disabled. While Ruffle may work, it could be very slow. You can find out how to enable hardware acceleration by following the link below:'
    assert state['linkText']=='FAQ - Chrome Hardware Acceleration'
    assert state['link']=='https://github.com/ruffle-rs/ruffle/wiki/Frequently-Asked-Questions-For-Users#chrome-hardware-acceleration'
    assert state['closeCount']==1 and state['closeHit'] is True
    assert len(state['point'])==2 and all(math.isfinite(v) and v>=0 for v in state['point'])

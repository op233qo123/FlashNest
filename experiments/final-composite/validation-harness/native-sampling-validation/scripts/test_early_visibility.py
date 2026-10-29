"""Synthetic image/JSON rejection tests, not native screenshots or a golden."""
import hashlib,json,tempfile,unittest
from pathlib import Path
from PIL import Image,ImageDraw
import check_early_visibility as early
class EarlyVisibility(unittest.TestCase):
    def make(self,p,color='white',vector=True):
        image=Image.new('RGB',(64,64),color)
        if vector:ImageDraw.Draw(image).rectangle((10,10,30,30),fill=(25,171,117))
        image.save(p/'crop.png');sha=hashlib.sha256((p/'crop.png').read_bytes()).hexdigest()
        for i in range(12):(p/f'{i}.json').write_text(json.dumps({'schema':'flashnest-native-sampling-before-input-v1','row':str(i),'phase':'portrait','cropSHA256':sha}))
    def test_visible_is_not_acceptance(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d);self.make(p);r=early.check(p,12)
            self.assertFalse(r['nativeAcceptance']);self.assertEqual(r['observedPhases'],12)
    def test_black_white_missing_duplicate_hash_rejected(self):
        for mutant in ('white','black','missing','duplicate','hash'):
            with self.subTest(mutant=mutant),tempfile.TemporaryDirectory() as d:
                p=Path(d);self.make(p,color=mutant if mutant in ('white','black') else 'white',vector=mutant not in ('white','black'))
                if mutant=='missing':(p/'0.json').unlink()
                if mutant=='duplicate':(p/'1.json').write_bytes((p/'0.json').read_bytes())
                if mutant=='hash':(p/'crop.png').unlink()
                with self.assertRaises(AssertionError):early.check(p,12)
if __name__=='__main__':unittest.main(verbosity=2)

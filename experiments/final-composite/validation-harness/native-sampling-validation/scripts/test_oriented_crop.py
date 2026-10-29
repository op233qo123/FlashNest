"""Local preparation controls only; no UIKit or full native acceptance."""
import copy,hashlib,importlib.util,sys,tempfile,unittest
from pathlib import Path
from PIL import Image
import verify_results as v
class Contracts(unittest.TestCase):
 def model(self,p):
  f=p/'crop.png';Image.new('RGB',(1334,660),'green').save(f);sha=hashlib.sha256(f.read_bytes()).hexdigest()
  s={'identity':{'arm':'candidate','source':'exact'},'epoch':1,'screenScale':2,'screenBounds':[667,375],'viewport':[0,45,667,330],'measurement':{'css':[0,0,667,330]}}
  c={'captureName':'row-landscape','cropSHA256':sha,'identity':s['identity'],'epoch':1,'screenScale':2,'screenBounds':s['screenBounds'],'viewport':s['viewport'],'css':s['measurement']['css'],'normalization':'UIImage.draw-oriented-scale1-v1','rawCGPixels':[750,1334],'imageOrientation':3,'normalizedPixels':[1334,750],'cropRectPixels':[0,90,1334,660]}
  return s,c,{sha:f}
 def test_good_and_same_pixel_different_capture(self):
  with tempfile.TemporaryDirectory() as d:
   s,c,pngs=self.model(Path(d));key=('candidate',2,'row-landscape');used=set();crops={key:c}
   v.check_oriented_crop(s,key[-1],c['cropSHA256'],crops,pngs,used)
   other=copy.deepcopy(c);other['captureName']='another-row';crops[('candidate',2,'another-row')]=other
   v.check_oriented_crop(s,'another-row',c['cropSHA256'],crops,pngs,used)
   self.assertEqual(len(used),2)
   with self.assertRaises(AssertionError):v.check_oriented_crop(s,key[-1],c['cropSHA256'],crops,pngs,used)
 def test_reject_mutations(self):
  for mutation in ('missing','identity','epoch','sha','orientation','stretch','clip','size','css','screen','viewport'):
   with self.subTest(mutation=mutation),tempfile.TemporaryDirectory() as d:
    s,c,pngs=self.model(Path(d));s=copy.deepcopy(s);c=copy.deepcopy(c);key=('candidate',2,'row-landscape');crops={key:c}
    if mutation=='missing':crops.clear()
    if mutation=='identity':c['identity']['source']='wrong'
    if mutation=='epoch':c['epoch']=2
    if mutation=='sha':c['cropSHA256']='bad'
    if mutation=='orientation':c['imageOrientation']=0
    if mutation=='stretch':c['rawCGPixels'][0]+=5
    if mutation=='clip':c['cropRectPixels'][2]-=5
    if mutation=='size':Image.new('RGB',(1333,660)).save(next(iter(pngs.values())))
    if mutation=='css':c['css'][2]-=1
    if mutation=='screen':c['screenBounds'][0]+=1
    if mutation=='viewport':c['viewport'][1]-=1
    with self.assertRaises(AssertionError):v.check_oriented_crop(s,key[-1],next(iter(pngs)),crops,pngs,set())
if __name__=='__main__':unittest.main(verbosity=2)

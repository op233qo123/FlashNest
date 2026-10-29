"""Strict outer-screen edge models; actual artifact replay separately labeled."""
import copy,hashlib,tempfile,unittest
from pathlib import Path
from PIL import Image
import verify_results as v
class RasterEdge(unittest.TestCase):
 def model(self,p):
  s={'identity':{'arm':'baseline'},'epoch':1,'screenScale':3,'screenBounds':[393,852],'viewport':[0,104,393,714],'measurement':{'css':[0,0,393,714]}}
  crop=p/'crop.png';Image.new('RGB',(1178,2142),'green').save(crop);h=hashlib.sha256(crop.read_bytes()).hexdigest()
  full=p/'original.png';Image.new('RGB',(1179,2556),'green').save(full);original=hashlib.sha256(full.read_bytes()).hexdigest()
  c={'captureName':'edge','cropSHA256':h,'identity':s['identity'],'epoch':1,'screenScale':3,'screenBounds':s['screenBounds'],'viewport':s['viewport'],'css':s['measurement']['css'],'normalization':'UIImage.draw-oriented-scale1-v1','rawCGPixels':[1178,2556],'imageOrientation':0,'normalizedPixels':[1178,2556],'cropRectPixels':[0,312,1178,2142],'cropMapping':'nominal-dpr-explicit-outer-edge-v1','desiredCropRectPixels':[0,312,1179,2142],'missingOuterEdgePixels':[0,0,1,0],'imagePointSize':[1178/3,852],'imageScale':3,'originalPNGSHA256':original,'originalPNGPixels':[1179,2556]}
  return s,c,{h:crop,original:full}
 def check(self,s,c,pngs):v.check_oriented_crop(s,'edge',c['cropSHA256'],{('baseline',3,'edge'):c},pngs,set())
 def test_only_proven_outer_one_pixel_without_rescale(self):
  with tempfile.TemporaryDirectory() as d:
   s,c,pngs=self.model(Path(d));self.check(s,c,pngs)
   self.assertEqual(c['desiredCropRectPixels'],[0,312,1179,2142]);self.assertEqual(c['cropRectPixels'],[0,312,1178,2142])
   self.assertNotEqual(c['originalPNGPixels'],c['rawCGPixels']) # representation sizes may differ; not a root-cause assertion
 def test_internal_multi_pixel_left_mismatch_and_missing_evidence_rejected(self):
  for mutation in ('internal','multipixel','left','screen','pointsize','declarededge','originalmissing','originalsize','actualsize','desired'):
   with self.subTest(mutation=mutation),tempfile.TemporaryDirectory() as d:
    s,c,pngs=self.model(Path(d));s=copy.deepcopy(s);c=copy.deepcopy(c)
    if mutation=='internal':
     s['measurement']['css'][2]=390;c['css'][2]=390;c['desiredCropRectPixels'][2]=1170;c['cropRectPixels'][2]=1169
    if mutation=='multipixel':c['rawCGPixels'][0]=c['normalizedPixels'][0]=1177;c['imagePointSize'][0]=1177/3
    if mutation=='left':s['measurement']['css'][0]=-1/3;c['css'][0]=-1/3;c['desiredCropRectPixels'][0]=-1;c['cropRectPixels'][0]=-1
    if mutation=='screen':s['screenBounds'][0]=394;c['screenBounds'][0]=394
    if mutation=='pointsize':c['imagePointSize'][0]+=1
    if mutation=='declarededge':c['missingOuterEdgePixels']=[0,0,0,0]
    if mutation=='originalmissing':c['originalPNGSHA256']='missing'
    if mutation=='originalsize':c['originalPNGPixels']=[1178,2556]
    if mutation=='actualsize':Image.new('RGB',(1177,2142)).save(pngs[c['cropSHA256']])
    if mutation=='desired':c['desiredCropRectPixels'][2]-=1
    with self.assertRaises(AssertionError):self.check(s,c,pngs)
 def test_bottom_and_corner_deficits_including_rotated_image(self):
  for right,orientation in ((0,0),(1,2)):
   with self.subTest(right=right,orientation=orientation),tempfile.TemporaryDirectory() as d:
    p=Path(d);s,c,pngs=self.model(p);width=1179-right;height=2555
    s['viewport']=[0,0,393,852];s['measurement']['css']=[0,0,393,852]
    c.update(viewport=s['viewport'],css=s['measurement']['css'],normalizedPixels=[width,height],rawCGPixels=[height,width] if orientation in (2,3,6,7) else [width,height],imageOrientation=orientation,imagePointSize=[width/3,height/3],desiredCropRectPixels=[0,0,1179,2556],cropRectPixels=[0,0,width,height],missingOuterEdgePixels=[0,0,right,1])
    file=p/'bottom.png';Image.new('RGB',(width,height),'green').save(file);h=hashlib.sha256(file.read_bytes()).hexdigest();pngs[h]=file;c['cropSHA256']=h;self.check(s,c,pngs)
    for mode in ('internal','multiple'):
     bad=copy.deepcopy(c);state=copy.deepcopy(s)
     if mode=='internal':state['measurement']['css'][3]=850;bad['css'][3]=850;bad['desiredCropRectPixels'][3]=2550;bad['cropRectPixels'][3]=2549
     else:
      bad['normalizedPixels'][1]=2554;bad['rawCGPixels']=[2554,width] if orientation in (2,3,6,7) else [width,2554];bad['imagePointSize'][1]=2554/3
     with self.assertRaises(AssertionError):self.check(state,bad,pngs)
 def test_oriented_point_size_relation_all_eight_orientations(self):
  with tempfile.TemporaryDirectory() as d:
   s,c,pngs=self.model(Path(d))
   for orientation in range(8):
    c['imageOrientation']=orientation;c['rawCGPixels']=[2556,1178] if orientation in (2,3,6,7) else [1178,2556]
    self.check(s,c,pngs)
if __name__=='__main__':unittest.main(verbosity=2)

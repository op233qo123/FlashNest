import pathlib,sys,unittest,json,copy,tempfile,hashlib,struct,zlib
from PIL import Image,ImageDraw
ROOT=pathlib.Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT));import generate_fixtures as g;import pixel_oracle as o;import verify_phases as v
class Bitmap(unittest.TestCase):
 def test_fixtures_binary_and_bitmap(self):
  baseline=json.loads((ROOT/'baseline-fixture-manifest.json').read_text());manifest=json.loads((ROOT/'fixture-manifest.json').read_text())
  for which in ('main','old','new'):
   data=g.build(which);self.assertEqual(g.inspect(data),manifest['files']['sized-bitmap/'+which+'.swf'])
   if which!='main':
    tags=g.inspect(data)['tags'];self.assertEqual(next(t for t in tags if t['code']==87),next(t for t in baseline['files']['sized/'+which+'.swf']['tags'] if t['code']==87))
    bitmap=next(t for t in tags if t['code']==36);self.assertEqual(bitmap['decodedPixelBytes'],4194304)
  self.assertLess(sum(x['compressedBytes'] for x in manifest['files'].values()),64*g.MIB)
 def test_literal_bitmap_pixels(self):
  expected={'old':[(255,255,0,0),(255,0,255,0),(255,0,0,255),(255,255,255,255)],'new':[(255,0,255,255),(255,255,0,255),(255,255,255,0),(255,0,0,0)]}
  for label in expected:
   comp,raw=g.bitmap_bytes(label);self.assertEqual(zlib.decompress(comp),raw)
   for y in (0,511,512,1023):
    for x in (0,511,512,1023):self.assertEqual(tuple(raw[(y*1024+x)*4:(y*1024+x)*4+4]),expected[label][(2 if y>=512 else 0)+(1 if x>=512 else 0)])
 def phases(self):return [json.loads(l[len('<SCENE_PHASE '):]) for l in (ROOT/'core-smoke.log').read_text().splitlines() if l.startswith('<SCENE_PHASE ')]
 def test_core_and_single_key(self):
  records=self.phases();self.assertEqual(len(records),17);v.verify_as(records)
  for phase in ('transition.key','old.awaiting-space','old.first-frame'):
   r=copy.deepcopy(records);next(x for x in r if x['phase']==phase)['phase']='unexpected'
   with self.assertRaises(AssertionError):v.verify_as(r)
 def make_visual(self,folder,label='old',rotate=False):
  identity={'arm':'candidate','runtimeFiles':{'synthetic.wasm':'hash'}};norm=Image.new('RGBA',(750,1334),(30,30,30,255));draw=ImageDraw.Draw(norm)
  palettes={'old':[(255,0,0),(0,255,0),(0,0,255),(255,255,255)],'new':[(0,255,255),(255,0,255),(255,255,0),(0,0,0)]}
  for idx,rgb in enumerate(palettes[label]):
   x=64+(idx%2)*256;y=90+64+(idx//2)*256;draw.rectangle((x,y,x+255,y+255),fill=rgb+(255,))
  crop=norm.crop((0,90,750,1310));raw=norm.transpose(Image.Transpose.ROTATE_90) if rotate else norm.copy()
  def save(im,name):
   p=folder/(label+name+'.png');im.save(p);return hashlib.sha256(p.read_bytes()).hexdigest()
  snapshot=dict(identity=identity,case='sized-bitmap',sameWK=True,epoch=1,jsPending=False,jsCompletedForRequest=1,request=1,observedUptimeSeconds=1,screenScale=2,viewport=[0,45,375,610],screenBounds=[375,667],measurement=dict(dpr=2,css=[0,0,375,610],renderCalls={'drawElements':2}))
  samples=[]
  for center,rgb in zip([(96,96),(224,96),(96,224),(224,224)],palettes[label]):samples.append(dict(centerCSS=list(center),centerPixels=[center[0]*2,center[1]*2],patchPixels=5,minimumRGBA=list(rgb)+[255],maximumRGBA=list(rgb)+[255],matches=True))
  visual=dict(schema='flashnest-native-bitmap-visual-v1',diagnosticOnly=True,nativeAcceptance=False,label=label,identity=identity,snapshot=snapshot,nativeUptimeSeconds=2,cropSHA256=save(crop,'crop'),paletteMatches=True,samples=samples,geometry=dict(rawPNGSHA256=save(raw,'raw'),normalizedPNGSHA256=save(norm,'norm'),rawCGPixels=list(raw.size),imageOrientation=2 if rotate else 0,imagePointSize=[375,667],imageScale=2,normalization='UIImage.draw-oriented-scale1-v1',normalizedPixels=list(norm.size),cropRectPixels=[0,90,750,1220]))
  return visual,identity
 def test_actual_png_geometry_and_palette(self):
  with tempfile.TemporaryDirectory() as tmp:
   p=pathlib.Path(tmp)
   for label in ('old','new'):
    for rotate in (False,True):
     visual,identity=self.make_visual(p,label,rotate);self.assertTrue(o.verify_visual(visual,p,identity)['independentPaletteMatches'])
 def test_visual_negatives(self):
  with tempfile.TemporaryDirectory() as tmp:
   p=pathlib.Path(tmp);visual,identity=self.make_visual(p)
   for mutate in [lambda x:x.update(label='new'),lambda x:x.update(paletteMatches=False),lambda x:x['geometry'].update(cropRectPixels=[0,89,750,1220]),lambda x:x['geometry'].update(normalizedPixels=[751,1334]),lambda x:x['geometry'].update(imagePointSize=[376,667]),lambda x:x['samples'][0].update(centerPixels=[200,200]),lambda x:x['snapshot'].update(jsPending=True),lambda x:x.update(cropSHA256='0'*64)]:
    row=copy.deepcopy(visual);mutate(row)
    with self.assertRaises(AssertionError):o.verify_visual(row,p,identity)
if __name__=='__main__':unittest.main()

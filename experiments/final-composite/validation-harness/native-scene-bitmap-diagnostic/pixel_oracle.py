"""Independent screenshot geometry and source-defined bitmap palette oracle; never calibrates from pixels."""
import hashlib,math,pathlib
from PIL import Image
COLORS={'old':[(255,0,0),(0,255,0),(0,0,255),(255,255,255)],'new':[(0,255,255),(255,0,255),(255,255,0),(0,0,0)]}
CENTERS=[(96,96),(224,96),(96,224),(224,224)]
DRAW_METHODS=('drawArrays','drawElements','drawArraysInstanced','drawElementsInstanced')
def require(x,message):
 if not x:raise AssertionError(message)
def finite(x):return type(x) in (int,float) and math.isfinite(x)
def draw_count(snapshot):
 calls=snapshot['measurement']['renderCalls'];total=0
 for name in DRAW_METHODS:
  count=calls.get(name,0);require(type(count) is int and count>=0,'Draw counter type');total+=count
 return total

def find_image(folder,digest):
 require(isinstance(digest,str) and len(digest)==64,'PNG digest')
 matches=[p for p in pathlib.Path(folder).rglob('*.png') if hashlib.sha256(p.read_bytes()).hexdigest()==digest]
 require(bool(matches),'PNG absent')
 with Image.open(matches[0]) as image:
  require(image.format=='PNG' and image.width*image.height<=20_000_000,'PNG size/type');image.load();return image.convert('RGBA')

def verify_visual(visual,folder,identity):
 require(visual['schema']=='flashnest-native-bitmap-visual-v1','Visual schema')
 require(visual['diagnosticOnly'] is True and visual['nativeAcceptance'] is False,'Visual role')
 label=visual['label'];require(label in COLORS,'Visual label');s=visual['snapshot'];g=visual['geometry']
 require(visual['identity']==identity and s['identity']==identity,'Visual identity')
 require(s['case']=='sized-bitmap' and s['sameWK'] is True and s['epoch']==1,'Visual WK')
 require(s['jsPending'] is False and s['jsCompletedForRequest']==s['request'],'Visual stale measurement')
 require(finite(visual['nativeUptimeSeconds']) and s['observedUptimeSeconds']<=visual['nativeUptimeSeconds'],'Visual time')
 dpr=s['screenScale'];require(finite(dpr) and dpr==2 and s['measurement']['dpr']==dpr,'DPR2')
 viewport=s['viewport'];screen=s['screenBounds'];css=s['measurement']['css']
 require(len(viewport)==4 and len(css)==4 and len(screen)==2 and all(finite(x) for x in viewport+screen+css),'Native geometry')
 require(css[2]>=288 and css[3]>=288,'Canvas cannot contain fixed bitmap')
 raw=find_image(folder,g['rawPNGSHA256']);norm=find_image(folder,g['normalizedPNGSHA256']);crop=find_image(folder,visual['cropSHA256'])
 require(list(raw.size)==g['rawCGPixels'] and list(norm.size)==g['normalizedPixels'],'Actual full PNG sizes')
 orientation=g['imageOrientation'];require(type(orientation) is int and 0<=orientation<=7,'UIImage orientation')
 oriented=(raw.height,raw.width) if orientation in (2,3,6,7) else raw.size
 require(norm.size==oriented and g['normalization']=='UIImage.draw-oriented-scale1-v1','No stretched normalization')
 require(len(g['imagePointSize'])==2 and finite(g['imageScale']) and g['imageScale']>0,'Image point geometry')
 require(all(finite(p) and abs(p*g['imageScale']-n)<1e-6 for p,n in zip(g['imagePointSize'],oriented)),'UIImage point/pixel relation')
 require(all(abs(actual-points*dpr)<=1 for actual,points in zip(norm.size,screen)),'Independent screen/raster size')
 origin=[(viewport[i]+css[i])*dpr for i in (0,1)]
 x,y=map(math.floor,origin);right=math.ceil(origin[0]+css[2]*dpr);bottom=math.ceil(origin[1]+css[3]*dpr)
 rect=[x,y,right-x,bottom-y];require(g['cropRectPixels']==rect,'Crop not native CSS integral rectangle')
 require(x>=0 and y>=0 and right<=norm.width and bottom<=norm.height,'No hidden crop clipping')
 require(crop.size==(rect[2],rect[3]),'Actual crop dimensions')
 require(crop.tobytes()==norm.crop((x,y,right,bottom)).tobytes(),'Crop not exact normalized source')
 samples=[]
 for (cx,cy),rgb in zip(CENTERS,COLORS[label]):
  px=math.floor(cx*dpr+origin[0]-x+0.5);py=math.floor(cy*dpr+origin[1]-y+0.5)
  require(2<=px<crop.width-2 and 2<=py<crop.height-2,'Patch outside crop')
  pixels=[crop.getpixel((xx,yy)) for yy in range(py-2,py+3) for xx in range(px-2,px+3)];minimum=[min(p[i] for p in pixels) for i in range(4)];maximum=[max(p[i] for p in pixels) for i in range(4)]
  matched=minimum[3]==255 and maximum[3]==255 and all(minimum[i]>=max(0,rgb[i]-2) and maximum[i]<=min(255,rgb[i]+2) for i in range(3))
  samples.append({'centerCSS':[cx,cy],'centerPixels':[px,py],'patchPixels':5,'minimumRGBA':minimum,'maximumRGBA':maximum,'matches':matched})
 require(visual['samples']==samples,'Swift sample report differs from actual PNG')
 require(all(s['matches'] for s in samples) and visual['paletteMatches'] is True,'Source-defined palette not visible')
 return {'label':label,'independentPaletteMatches':True,'drawCount':draw_count(s),'cropSHA256':visual['cropSHA256'],'samples':samples}

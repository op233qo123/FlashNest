#!/usr/bin/env python3
"""Local Playwright smoke matrix using recovered fixture; not UIKit or hardware-memory evidence."""
import argparse, functools, hashlib, http.server, json, math, pathlib, threading, time, traceback
from playwright.sync_api import sync_playwright
from pixel_checks import compare, validate_warning
from evidence_budget import write_png, write_json
ROOT=pathlib.Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser();p.add_argument('--candidate',required=True);p.add_argument('--baseline',required=True);p.add_argument('--backend',choices=['webgl','wgpu-webgl'],required=True);a=p.parse_args()
OUT=ROOT/'evidence'/('geometry-'+a.backend);OUT.mkdir(exist_ok=True,parents=True)
routes={'baseline':pathlib.Path(a.baseline).resolve(),'candidate':pathlib.Path(a.candidate).resolve(),'fixtures':ROOT/'history/fixtures'}
class Handler(http.server.BaseHTTPRequestHandler):
 def do_GET(self):
  from urllib.parse import urlparse,unquote
  rel=unquote(urlparse(self.path).path)
  try:
   if rel=='/':f=ROOT/'history/browser-tests/page.html'
   else:
    head,tail=rel.lstrip('/').split('/',1);base=routes[head];f=(base/tail).resolve();assert f.is_relative_to(base)
   data=f.read_bytes();self.send_response(200);self.send_header('Content-Type','application/wasm' if f.suffix=='.wasm' else 'text/javascript' if f.suffix=='.js' else 'text/html' if f.suffix=='.html' else 'application/octet-stream');self.end_headers();self.wfile.write(data)
  except Exception:self.send_error(404)
 def log_message(self,*args):pass
server=http.server.ThreadingHTTPServer(('127.0.0.1',0),Handler);threading.Thread(target=server.serve_forever,daemon=True).start()
result={'passed':False,'backend':a.backend,'scope':'DPR 1/3, portrait/landscape, four scaleModes, center alignment, four density tiers; trusted mouse corners/center, actual canvas/drawingbuffer, resize and Original screenshot parity. Not native touch, full alignment/visual matrix, or memory.','rows':[]}
def save(): write_json(OUT/'result.json',json.dumps(result,indent=2)+'\n')
def wait(page,expr):page.wait_for_function(expr,timeout=30000)
def parse(lines,label):return [x.split('|')[2:] for x in lines if x.startswith('DENSITY|'+label+'|')]
def near(rows,expected):
 assert len(rows)==len(expected)
 for row,ref in zip(rows,expected):
  assert len(row)==len(ref)
  for x,y in zip(row,ref):
   try:assert abs(float(x)-float(y))<=0.1,(x,y)
   except ValueError:assert x==y,(x,y)
try:
 with sync_playwright() as pw:
  browser=pw.chromium.launch(chromium_sandbox=True,headless=True,args=['--enable-unsafe-swiftshader'])
  for dpr in [1,3]:
   context=browser.new_context(viewport={'width':900,'height':900},device_scale_factor=dpr)
   page=context.new_page();refs={};shots={}
   page.route('**/*',lambda route: route.continue_() if route.request.url.startswith(f'http://127.0.0.1:{server.server_port}/') else route.abort())
   result['browserVersion']=browser.version
   for arm in ['baseline','candidate']:
    page.goto(f'http://127.0.0.1:{server.server_port}/?runtime={arm}');wait(page,'window.runtimeReady===true')
    for w,h in [(443,287),(319,481)]:
     for mode in ['showAll','noBorder','exactFit','noScale']:
      for scale in ([1] if arm=='baseline' else [1,.75,.5,.25]):
       case={'arm':arm,'scale':scale,'dpr':dpr,'viewport':[w,h],'mode':mode};result['active']=case;save()
       page.evaluate('(v)=>window.startCase(...v)',[f'/fixtures/{mode}-center.swf',scale,w,h,a.backend,'low'])
       wait(page,'window.evidence.loaded&&window.evidence.observerInstalled');page.locator('#play').click();wait(page,"window.evidence.traces.some(x=>x.startsWith('DENSITY|READY|'))")
       expected=[max(1,math.floor(v*dpr*scale+.5)) for v in [w,h]]
       page.wait_for_function('(v)=>{const m=window.measure();return m&&m.width===v[0]&&m.height===v[1]}',arg=expected,timeout=15000)
       points=[(round(w*x),round(h*y)) for x,y in [(.05,.05),(.95,.05),(.05,.95),(.95,.95),(.5,.5)]]
       page.mouse.move(*points[0]);warning=page.evaluate('window.hardwareWarningState()')
       if warning['visible']:
        validate_warning(warning)
        write_png(OUT/f'warning-{len(result["rows"])}.png',page.screenshot())
        result.setdefault('warnings',[]).append({'case':case,'state':warning});save()
        latest=page.evaluate('window.hardwareWarningState()');validate_warning(latest);assert latest['point']==warning['point']
        page.mouse.click(*warning['point']);wait(page,'!window.hardwareWarningState().visible')
       phases=[];result['activePhases']=phases;save()
       page.evaluate('window.__resizePlayer=window.player')
       for phase,pw_,ph_ in [('initial',w,h),('resized',h,w),('restored',w,h)]:
        page.evaluate('(v)=>{const h=document.getElementById("host");h.style.width=v[0]+"px";h.style.height=v[1]+"px"}',[pw_,ph_])
        physical=[max(1,math.floor(v*dpr*scale+.5)) for v in [pw_,ph_]]
        page.wait_for_function('(v)=>{const m=window.measure();return m&&m.width===v[0]&&m.height===v[1]&&m.gl&&m.gl[0]===v[0]&&m.gl[1]===v[1]}',arg=physical,timeout=15000)
        assert page.evaluate('window.player===window.__resizePlayer&&window.player===document.querySelector("ruffle-player")')
        m=page.evaluate('window.measure()')
        current={'phase':phase,'canvas':m};result['activePhase']=current;save()
        assert m['actualRenderer']==a.backend,m
        assert m['dpr']==dpr and m['css']==[0,0,pw_,ph_] and m['client']==[pw_,ph_],m
        assert [m['width'],m['height']]==physical and m['gl']==physical,m
        if arm=='candidate':
         attrs=m['attributes']
         assert attrs['data-flashnest-render-scale']==str(scale) and attrs['data-flashnest-render-request']==str(scale),m
         assert [int(attrs['data-flashnest-viewport-width']),int(attrs['data-flashnest-viewport-height'])]==[pw_*dpr,ph_*dpr],m
         assert attrs['data-flashnest-renderer']==a.backend,m
        # Compare real composited pixels, including the same player's resize/restore.
        shot=page.locator('#host').screenshot();key=(w,h,mode,phase)
        shotfile=f'{arm}-{scale}-{dpr}-{w}x{h}-{mode}-{phase}.png'
        write_png(OUT/shotfile,shot)
        current.update(screenshot=shotfile,screenshotSHA256=hashlib.sha256(shot).hexdigest());save()
        from PIL import Image
        import io
        img=Image.open(io.BytesIO(shot)).convert('RGB')
        assert img.size==(pw_*dpr,ph_*dpr),img.size
        for color,label in [((25,171,117),'green vector'),((29,39,58),'fixture background')]:
         assert sum(n for n,c in img.getcolors(img.width*img.height) or [] if all(abs(c[i]-color[i])<8 for i in range(3)))>=100,'missing visible '+label
        if arm=='baseline':shots[key]=img.copy()
        elif scale==1:assert img.tobytes()==shots[key].tobytes(),'Original screenshot pixel mismatch: '+phase
        comparison=compare(img,shots[key],pw_)
        points=[(round(pw_*x),round(ph_*y)) for x,y in [(.05,.05),(.95,.05),(.05,.95),(.95,.95),(.5,.5)]]
        page.evaluate('window.pointerEvents=[]')
        before=len(page.evaluate('window.evidence.traces.filter(x=>x.startsWith("DENSITY|UP|"))'))
        for i,point in enumerate(points):
         assert page.evaluate('(p)=>window.gameHitTarget(...p).canvasTopmost',point),'Canvas not topmost'
         page.mouse.click(*point)
         page.wait_for_function('(n)=>window.evidence.traces.filter(x=>x.startsWith("DENSITY|UP|")).length===n',arg=before+i+1,timeout=5000)
        events=page.evaluate('window.pointerEvents');current['pointerEvents']=events;save()
        assert len(events)==10,events
        for i,event in enumerate(events):
         assert event['trusted'] is True and event['type']==['pointerdown','pointerup'][i%2],event
         assert [event['x'],event['y']]==list(points[i//2]) and event['button']==0,event
         assert any(e['tag']=='CANVAS' for e in event['path']),event
        phases.append({'phase':phase,'pixelComparison':comparison,'canvas':m,'pointerEvents':events,'screenshot':shotfile,'screenshotSHA256':hashlib.sha256(shot).hexdigest()})
        result['activePhases']=phases;save()
       e=page.evaluate('window.evidence');assert not e['errors'] and not e['overflow'],e
       down,up=parse(e['traces'],'DOWN'),parse(e['traces'],'UP');assert len(down)==len(up)==15
       key=(w,h,mode)
       if arm=='baseline':refs[key]=(down,up)
       else:near(down,refs[key][0]);near(up,refs[key][1])
       row={**case,'phases':phases,'down':down,'up':up};result['rows'].append(row);save();print(json.dumps(case),flush=True)
   context.close()
  browser.close()
 assert len(result['rows'])==80
 result['passed']=True
except Exception as e:
 result['error']=str(e);result['traceback']=traceback.format_exc()
 try:
  result['failureObservation']=page.evaluate('({evidence:window.evidence,pointerContext:window.pointerContext?.(),canvas:window.measure?.()})')
 except Exception:pass
 raise
finally:save();server.shutdown();server.server_close()

#!/usr/bin/env python3
"""290 final-runtime rows on the actual unmodified shipping loader selection."""
import argparse,hashlib,http.server,io,json,math,pathlib,threading,time,traceback
from urllib.parse import unquote,urlparse
from contracts import ROOT,bind,digest,matrix,key,verify_measure,near,verify_baseline_entry
from pixel_checks import compare,validate_warning
from evidence_budget import write_png,write_json

def capture_failure(page,result):
 """Observe the still-live page before Playwright tears down; never alter input."""
 try:
  result['failureObservation']=page.evaluate('({evidence:window.evidence,canvas:window.measure?.(),pointerContext:window.pointerContext?.(),hardwareWarning:window.hardwareWarningState?.()})')
 except Exception as exc:
  result['failureObservationError']=type(exc).__name__+': '+str(exc)[:2000]

def prepare_pointer(page,result,index,out,width,height):
 # The actual CPU-adapter frontend opens its warning on the first mouseover,
 # not on READY. Trigger that one-time UI transition before any game click.
 page.mouse.move(width/2,height/2)
 warning=page.evaluate('window.hardwareWarningState()')
 if warning['visible']:
  validate_warning(warning);name=f'warning-{index}.png';write_png(out/name,page.screenshot())
  assert page.evaluate('window.hardwareWarningState()')==warning
  traces_before=page.evaluate('window.evidence.traces.slice()')
  page.evaluate('window.pointerEvents=[]')
  page.mouse.click(*warning['point']);page.wait_for_function('!window.hardwareWarningState().visible')
  events=page.evaluate('window.pointerEvents')
  assert len(events)==2,'Warning dismissal must be one separate trusted click'
  for i,event in enumerate(events):
   assert event['trusted'] is True and event['type']==['pointerdown','pointerup'][i]
   assert [event['x'],event['y']]==warning['point'] and event['button']==0
   assert any(e['id']=='hardware-acceleration-modal' for e in event['path'])
  assert page.evaluate('window.evidence.traces.slice()')==traces_before,'Warning dismissal leaked into game input'
  result.setdefault('warnings',[]).append({'index':index,'state':warning,'screenshot':name,'dismissalEvents':events,'gameClick':False})
 assert page.evaluate('(p)=>window.gameHitTarget(...p).canvasTopmost',[width/2,height/2]),'Unknown overlay after pointer readiness'

def run(a):
 from playwright.sync_api import sync_playwright
 from PIL import Image
 contract=json.loads(a.contract.read_text());assert contract['schemaVersion']==1
 preflight=json.loads((ROOT/'evidence/browser-preflight.json').read_text());assert preflight['passed'] is True and preflight['matrixCases']==0 and preflight['chromiumSandbox'] is True
 assert preflight['playwright']=='1.64.1'
 assert contract['finalComposite'] is True and contract['baselineRunID']==40614335019
 verify_baseline_entry(contract['baseline'])
 routes={'baseline':a.baseline.resolve(),'candidate':a.candidate.resolve(),'fixtures':ROOT/'fixtures'}
 pins={arm:bind(routes[arm],contract[arm]) for arm in ['baseline','candidate']}
 assert contract['fixtureManifestSHA256']==digest(ROOT/'fixtures/manifest.json')
 for name,row in json.loads((ROOT/'fixtures/manifest.json').read_text())['files'].items():
  assert digest(ROOT/'fixtures'/name)==row['sha256']
 rows=matrix();out=ROOT/'evidence';out.mkdir(exist_ok=True)
 result={'passed':False,'rows':[],'runtimeBindingSHA256':digest(a.contract),'runtimeInventories':pins,'selection':'unmodified-shipping-default','mvpExecution':'not-established','scope':'Desktop sandboxed Chrome/SwiftShader; real composite pixels/trusted mouse/GL allocation. Not native touch/device/memory.'}
 def save():write_json(out/'result.json',json.dumps(result,indent=2)+'\n')
 class Handler(http.server.BaseHTTPRequestHandler):
  def do_GET(self):
   try:
    rel=unquote(urlparse(self.path).path)
    if rel=='/':f=ROOT/'page.html'
    else:
     head,tail=rel.lstrip('/').split('/',1);base=routes[head];f=(base/tail).resolve();assert f.is_relative_to(base)
    data=f.read_bytes();self.send_response(200);self.send_header('Content-Type','application/wasm' if f.suffix=='.wasm' else 'text/javascript' if f.suffix=='.js' else 'text/html' if f.suffix=='.html' else 'application/octet-stream');self.end_headers();self.wfile.write(data)
   except Exception:self.send_error(404)
  def log_message(self,*args):pass
 server=http.server.ThreadingHTTPServer(('127.0.0.1',0),Handler);threading.Thread(target=server.serve_forever,daemon=True).start()
 origin=f'http://127.0.0.1:{server.server_port}/';started=time.monotonic();refs={};shots={};page=None
 try:
  with sync_playwright() as pw:
   browser=pw.chromium.launch(channel='chrome',chromium_sandbox=True,headless=True,args=['--enable-unsafe-swiftshader'])
   result['browserVersion']=browser.version
   assert browser.version==preflight['browserVersion'],'Browser changed after reviewed preflight'
   result['preflightSHA256']=digest(ROOT/'evidence/browser-preflight.json')
   for index,row in enumerate(rows):
    assert time.monotonic()-started<1800,'Matrix exceeded30minute bound; incomplete'
    result['active']={'index':index,**row};result['activePhases']=[];result.pop('activeInput',None);save()
    context=browser.new_context(viewport={'width':900,'height':900},device_scale_factor=row['dpr'])
    context.route('**/*',lambda route:route.continue_() if route.request.url.startswith(origin) else route.abort())
    page=context.new_page();wasm=[];response_errors=[]
    def on_response(response):
     path=urlparse(response.url).path
     if not path.endswith('.wasm'):return
     try:
      arm,rel=unquote(path).lstrip('/').split('/',1);assert arm==row['arm'] and rel in pins[arm]
      data=response.body();got={'sha256':hashlib.sha256(data).hexdigest(),'bytes':len(data)}
      assert response.status==200 and got==pins[arm][rel],('Fetched WASM mismatch',rel)
      wasm.append({'path':rel,**got})
     except Exception as exc:response_errors.append(str(exc))
    page.on('response',on_response)
    page.goto(origin+'?runtime='+row['arm']);page.wait_for_function('window.runtimeReady===true')
    w,h=row['viewport'];fixture=f"/fixtures/{row['mode']}-{row['align'] or 'center'}.swf"
    page.evaluate('(v)=>window.startCase(...v)',[fixture,row['scale'],w,h,row['renderer'],row['quality']])
    page.wait_for_function('window.evidence.loaded&&window.evidence.observerInstalled',timeout=30000)
    page.locator('#play').click();page.wait_for_function("window.evidence.traces.some(x=>x.startsWith('DENSITY|READY|'))",timeout=30000)
    prepare_pointer(page,result,index,out,w,h)
    page.evaluate('window.__resizePlayer=window.player');phases=[];initial_pixels=None
    for phase,pw_,ph_ in [('initial',w,h),('resized',h,w),('restored',w,h)]:
     page.evaluate('(v)=>{const h=document.getElementById("host");h.style.width=v[0]+"px";h.style.height=v[1]+"px"}',[pw_,ph_])
     # Wait for real resize; Python oracle checks full expected physical state below.
     page.wait_for_function('(v)=>{const m=window.measure();return m&&m.client[0]===v[0]&&m.client[1]===v[1]}',arg=[pw_,ph_])
     deadline=time.monotonic()+15
     while True:
      m=page.evaluate('window.measure()')
      try:status=verify_measure(row,m,pw_,ph_);break
      except (AssertionError,KeyError):
       if time.monotonic()>=deadline:raise
       page.wait_for_timeout(50)
     assert page.evaluate('window.player===window.__resizePlayer&&window.player===document.querySelector("ruffle-player")')
     shot=page.locator('#host').screenshot();filename=f'{index:03d}-{phase}.png';write_png(out/filename,shot)
     img=Image.open(io.BytesIO(shot)).convert('RGB');assert img.size==(pw_*row['dpr'],ph_*row['dpr'])
     for color,label in [((25,171,117),'green vector'),((29,39,58),'background')]:
      assert sum(n for n,c in img.getcolors(img.width*img.height) or [] if all(abs(c[i]-color[i])<8 for i in range(3)))>=100,'Missing '+label
     k=(key(row),phase)
     if row['arm']=='baseline':shots[k]=img.copy()
     elif status['appliedScale']==1:assert img.tobytes()==shots[k].tobytes(),'Original/fallback pixel mismatch'
     comparison=compare(img,shots[k],pw_)
     if phase=='initial':initial_pixels=img.tobytes()
     if phase=='restored':assert img.tobytes()==initial_pixels,'Same-player restoration pixel mismatch'
     points=[(round(pw_*x),round(ph_*y)) for x,y in [(.05,.05),(.95,.05),(.05,.95),(.95,.95),(.5,.5)]]
     page.evaluate('window.pointerEvents=[]');before=page.evaluate('window.evidence.traces.filter(x=>x.startsWith("DENSITY|UP|")).length')
     for i,point in enumerate(points):
      result['activeInput']={'phase':phase,'point':list(point),'clickIndex':i,'upCountBeforePhase':before,'expectedUpCount':before+i+1}
      try:
       assert page.evaluate('(p)=>window.gameHitTarget(...p).canvasTopmost',point),'Canvas not topmost'
       page.mouse.click(*point)
       page.wait_for_function('(n)=>window.evidence.traces.filter(x=>x.startsWith("DENSITY|UP|")).length===n',arg=before+i+1,timeout=5000)
      except Exception:
       capture_failure(page,result);save();raise
     events=page.evaluate('window.pointerEvents');assert len(events)==10
     for i,event in enumerate(events):
      assert event['trusted'] is True and event['type']==['pointerdown','pointerup'][i%2]
      assert [event['x'],event['y']]==list(points[i//2]) and event['button']==0
      assert any(e['tag']=='CANVAS' for e in event['path'])
     phases.append({'phase':phase,'canvas':m,'status':status,'pixelComparison':comparison,'pointerEvents':events,'screenshot':filename,'screenshotSHA256':hashlib.sha256(shot).hexdigest()})
     result['activePhases']=phases;save()
    e=page.evaluate('window.evidence');assert not e['errors'] and not e['overflow'];assert not response_errors,response_errors
    assert len(wasm)==1,'Expected exactly one actual fetched core WASM per fresh row'
    parse=lambda label:[x.split('|')[2:] for x in e['traces'] if x.startswith('DENSITY|'+label+'|')]
    down,up=parse('DOWN'),parse('UP');assert len(down)==len(up)==15
    if row['arm']=='baseline':refs[key(row)]=(down,up)
    else:near(down,refs[key(row)][0]);near(up,refs[key(row)][1])
    result['rows'].append({**row,'phases':phases,'down':down,'up':up,'fetchedWasm':wasm});save();print(json.dumps({'index':index,**row}),flush=True)
    context.close()
   browser.close()
  assert len(result['rows'])==290
  for arm in pins:assert bind(routes[arm],contract[arm])==pins[arm],'Post-run runtime changed'
  result['passed']=True;result['elapsedSeconds']=time.monotonic()-started
 except Exception as exc:
  result['error']=str(exc);result['traceback']=traceback.format_exc()
  if page and 'failureObservation' not in result:capture_failure(page,result)
  raise
 finally:save();server.shutdown();server.server_close()
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--candidate',type=pathlib.Path,required=True);p.add_argument('--baseline',type=pathlib.Path,required=True);p.add_argument('--contract',type=pathlib.Path,required=True);run(p.parse_args())

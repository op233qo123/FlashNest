"""Focused actual-WebGL observation; no defaults authorize a run or supply candidate WASM."""
import argparse,hashlib,http.server,json,pathlib,threading
from urllib.parse import urlparse,unquote
ROOT=pathlib.Path(__file__).resolve().parent
FIXTURES=[('neutral-eight-jpeg3.swf',[('ready',None,'NEUTRAL_GRAPHIC ready'),('shown','Space','NEUTRAL_GRAPHIC first-display')]),('neutral-forward-reference.swf',[('ready',None,'NEUTRAL_GRAPHIC ready'),('shown','Space','NEUTRAL_GRAPHIC first-display')])]
FIXTURES.append(('neutral-shared-boundaries.swf',[('ready',None,'NEUTRAL_SHARED ready'),('shown','s','NEUTRAL_SHARED shown'),('redrawn','r','NEUTRAL_SHARED redrawn'),('masked','m','NEUTRAL_SHARED masked'),('hit','h','NEUTRAL_SHARED hit inside=true outside=false')]))
def uploads16(state):
 return sum(1 for c in state['calls'] if c['width']==16 and c['height']==16 and 'Image' in c['name'])
def check_pixels(image,fixture,state):
 def pixel(point,expected):
  got=image.getpixel(point)
  assert all(abs(a-b)<=2 for a,b in zip(got,expected)),f'Pixel {point}: {got} != {expected}'
 white=(255,255,255,255);color=(20,200,49,255)
 if fixture=='neutral-shared-boundaries.swf':
  for point in [(36,36),(44,36),(84,36)]:
   expected=white if state=='ready' or (state in ['masked','hit'] and point==(44,36)) else color
   pixel(point,expected)
 else:
  pixel((8,8),(32,64,96,255));pixel((36,36),white if state=='ready' else color)
 pixel((200,180),white)
def digest(data):return hashlib.sha256(data).hexdigest()
def inventory(root):return {str(p.relative_to(root)):digest(p.read_bytes()) for p in sorted(root.rglob('*')) if p.is_file()}
def validate(contract,roots):
 assert contract['dispatchAllowed'] is True,'Disabled until separately authorized and candidate runtime pinned'
 assert set(contract['runtimes'])=={'baseline','candidate'}
 for arm in roots:
  assert inventory(roots[arm])==contract['runtimes'][arm]['files'],'Runtime byte inventory mismatch'
  assert contract['runtimes'][arm]['selectedWasmSHA256'],'Missing selected WASM pin'
 assert contract['runtimes']['baseline']['selectedWasmSHA256']!=contract['runtimes']['candidate']['selectedWasmSHA256'],'Candidate cannot reuse baseline WASM'
def run(a):
 from playwright.sync_api import sync_playwright
 from PIL import Image
 roots={'baseline':a.baseline.resolve(),'candidate':a.candidate.resolve()};contract=json.loads(a.contract.read_text());validate(contract,roots)
 fixture_root=a.fixtures.resolve();assert inventory(fixture_root)==contract['fixtures'],'Fixture inventory mismatch'
 out=a.out.resolve();out.mkdir(parents=True,exist_ok=False)
 routes={**roots,'fixtures':fixture_root}
 class Handler(http.server.BaseHTTPRequestHandler):
  def do_GET(self):
   try:
    path=unquote(urlparse(self.path).path)
    if path=='/':p=ROOT/'page.html'
    else:
     arm,rel=path.lstrip('/').split('/',1);base=routes[arm];p=(base/rel).resolve();assert p.is_relative_to(base)
    data=p.read_bytes();self.send_response(200);self.send_header('Content-Type',{'.js':'text/javascript','.wasm':'application/wasm','.html':'text/html'}.get(p.suffix,'application/octet-stream'));self.end_headers();self.wfile.write(data)
   except Exception:self.send_error(404)
  def log_message(self,*args):pass
 server=http.server.ThreadingHTTPServer(('127.0.0.1',0),Handler);threading.Thread(target=server.serve_forever,daemon=True).start()
 result={'passed':False,'scope':'Desktop Chromium actual WebGL calls/pixels, not native GPU memory or decode counters','rows':[],'contractSHA256':digest(a.contract.read_bytes())}
 try:
  with sync_playwright() as pw:
   browser=pw.chromium.launch(headless=True,chromium_sandbox=True,args=['--use-angle=swiftshader','--enable-unsafe-swiftshader'])
   try:
    for fixture,states in FIXTURES:
     for arm in ['baseline','candidate']:
      context=browser.new_context(viewport={'width':400,'height':280},device_scale_factor=1)
      page=context.new_page();page.set_default_timeout(20000);wasm=[]
      def response_seen(response):
       if urlparse(response.url).path.endswith('.wasm'):wasm.append({'name':pathlib.PurePosixPath(urlparse(response.url).path).name,'sha256':digest(response.body())})
      page.on('response',response_seen)
      row={'arm':arm,'fixture':fixture,'states':[],'wasm':wasm};result['rows'].append(row)
      try:
       page.goto(f'http://127.0.0.1:{server.server_port}/?arm={arm}');page.wait_for_function('window.runtimeReady===true');page.evaluate('f=>window.start(f)',fixture);page.locator('#play').click()
       for state,key,trace in states:
        if key:
         assert page.evaluate('document.activeElement===window.player'),'Player focus lost before trusted key'
         page.keyboard.press(key)
        page.wait_for_function('(text)=>evidence.traces.some(t=>t.includes(text))',arg=trace);page.evaluate('window.settled()')
        observation=page.evaluate('window.snapshot()');assert not observation['errors'] and not observation['overflow'];assert observation['contexts'],'No actual WebGL context'
        assert 'webgl' in observation.get('actualRenderer','').lower(),'Renderer fallback or missing actual renderer report'
        assert observation.get('traceAttached') is True and observation.get('instanceTraceAttachments')==1,'Trace observer was not attached once at live-instance creation'
        assert any(c['name'] in ['drawArrays','drawElements'] for c in observation['calls']),'No actual WebGL draw call'
        filename=f'{fixture}-{arm}-{state}.png';page.locator('#host').screenshot(path=str(out/filename));pixels=Image.open(out/filename).convert('RGBA')
        assert pixels.size==(320,240)
        check_pixels(pixels,fixture,state)
        observation.update(state=state,png=filename,rgbaSHA256=digest(pixels.tobytes()));row['states'].append(observation)
       assert wasm and all(w['sha256']==contract['runtimes'][arm]['selectedWasmSHA256'] for w in wasm),'Actual selected WASM differs from pin'
       expectedKeys=[' ' if key=='Space' else key for _,key,_ in states if key]
       assert row['states'][-1]['keys']==[{'key':key,'trusted':True} for key in expectedKeys],'Exact trusted input sequence required'
      except Exception as exc:
       row['failure']=type(exc).__name__+': '+str(exc)[:1500]
       try:
        row['failureObservation']=page.evaluate('window.snapshot()');page.screenshot(path=str(out/f'{fixture}-{arm}-failure.png'))
       except Exception:row['failureObservationUnavailable']=True
       raise
      finally:context.close()
    for fixture,_ in FIXTURES:
     rows=[r for r in result['rows'] if r['fixture']==fixture]
     for astate,bstate in zip(rows[0]['states'],rows[1]['states']):
      assert astate['state']==bstate['state'] and astate['rgbaSHA256']==bstate['rgbaSHA256'],'Full-canvas pixel regression'
     assert rows[0]['states'][0]['rgbaSHA256']!=rows[0]['states'][1]['rgbaSHA256'],'Display input had no visible effect'
    mechanism=[r for r in result['rows'] if r['fixture']=='neutral-eight-jpeg3.swf']
    baseline,candidate=mechanism
    assert uploads16(baseline['states'][0])>uploads16(candidate['states'][0]),'No initial 16x16 upload-call reduction observed'
    assert uploads16(candidate['states'][1])>uploads16(candidate['states'][0]),'First display did not register an observed 16x16 upload call'
    shared=[r for r in result['rows'] if r['fixture']=='neutral-shared-boundaries.swf']
    for row in shared:
     counts=[uploads16(state) for state in row['states']]
     assert counts[1:]==[counts[1]]*4,'Repaint/mask/hit created extra 16x16 upload calls'
     assert row['states'][1]['rgbaSHA256']==row['states'][2]['rgbaSHA256'],'Hide/reveal redraw pixels changed'
     assert row['states'][2]['rgbaSHA256']!=row['states'][3]['rgbaSHA256'],'Mask had no visible effect'
     assert row['states'][3]['rgbaSHA256']==row['states'][4]['rgbaSHA256'],'Hit test changed visible pixels'
    result['passed']=True
   finally:browser.close()
 finally:
  server.shutdown();(out/'result.json').write_text(json.dumps(result,indent=2)+'\n')
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--contract',type=pathlib.Path,required=True);p.add_argument('--baseline','--baseline-runtime',type=pathlib.Path,required=True);p.add_argument('--candidate','--candidate-runtime',type=pathlib.Path,required=True);p.add_argument('--fixtures',type=pathlib.Path,required=True);p.add_argument('--out','--output',type=pathlib.Path,required=True);run(p.parse_args())

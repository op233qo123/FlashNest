"""Bounded real WebGL A/B. Browser pages are not process RSS or iOS results."""
import argparse,hashlib,http.server,json,pathlib,threading,time
from urllib.parse import urlparse,unquote
ROOT=pathlib.Path(__file__).resolve().parent
STATES=[('ready',None,'NEUTRAL_SHARED ready'),('shown','s','NEUTRAL_SHARED shown'),('redrawn','r','NEUTRAL_SHARED redrawn'),('masked','m','NEUTRAL_SHARED masked'),('hit','h','NEUTRAL_SHARED hit inside=true outside=false')]
def digest(data):return hashlib.sha256(data).hexdigest()
def inventory(root):return {str(p.relative_to(root)):digest(p.read_bytes()) for p in sorted(root.rglob('*')) if p.is_file()}
def validate(contract,roots,fixtures):
 assert contract['schema']=='image-memory-webgl-contract-v1'
 assert set(contract['runtimes'])=={'baseline','candidate'}
 assert contract['source']['baselineSourceSetSHA256'] and contract['source']['candidatePatchSHA256']
 assert contract['source']['candidateReconstructed'] in [True,False]
 for arm,root in roots.items():
  assert inventory(root)==contract['runtimes'][arm]['files'],'Runtime inventory mismatch'
  assert contract['runtimes'][arm]['selectedWasmSHA256'],'Missing selected WASM pin'
 assert contract['runtimes']['baseline']['selectedWasmSHA256']!=contract['runtimes']['candidate']['selectedWasmSHA256']
 assert inventory(fixtures)==contract['fixtures'],'Fixture inventory mismatch'
def check_pixels(image,state):
 assert image.size==(320,240)
 for point in [(8,8),(200,180)]:assert image.getpixel(point)==(255,255,255,255)
 if state=='ready':assert image.getpixel((84,36))==(255,255,255,255)
 else:
  crop=image.crop((80,32,96,48));assert len(set(crop.getdata()))>16,'Pattern blank or uniform'
  assert any(p[:3]!=(255,255,255) for p in crop.getdata())
 if state in ['masked','hit']:assert image.getpixel((44,36))==(255,255,255,255),'Mask boundary missing'
def image_uploads(state,size):return sum(c['width']==size and c['height']==size and 'Image' in c['name'] for c in state['calls'])
def run(a):
 from playwright.sync_api import sync_playwright
 from PIL import Image
 roots={'baseline':a.baseline.resolve(),'candidate':a.candidate.resolve()};fixture_root=a.fixtures.resolve();contract=json.loads(a.contract.read_text());validate(contract,roots,fixture_root)
 manifest=json.loads((fixture_root/'manifest.json').read_text());out=a.out.resolve();out.mkdir(parents=True,exist_ok=False)
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
 result={'passed':False,'scope':'Desktop Chrome sandboxed WebGL; WASM linear memory capacity, not peak allocation, RSS, native GPU memory or iOS','rows':[],'contractSHA256':digest(a.contract.read_bytes()),'timingScope':'Instrumented single page per arm/case; descriptive only, not benchmark medians','contextRecoveryIsSeparateObservation':True,'explicitCacheAsBitmapRebuild':'not_run','classification':'pending','memoryScope':'Exported WASM linear memory capacity at stages; linear memory does not shrink, not live allocations/RSS','textureHashScope':'SHA256 all original-resolution RGBA upload bytes; WebCrypto may copy outside WASM and affect timing'}
 try:
  with sync_playwright() as pw:
   browser=pw.chromium.launch(channel='chrome',headless=True,chromium_sandbox=True)
   result['browserVersion']=browser.version;result['sandboxRequested']=True
   try:
    for fixture in manifest['fixtures']:
     for arm in ['baseline','candidate']:
      context=browser.new_context(viewport={'width':400,'height':280},device_scale_factor=1);page=context.new_page();page.set_default_timeout(25000);wasm=[]
      def response_seen(response):
       if urlparse(response.url).path.endswith('.wasm'):wasm.append({'name':pathlib.PurePosixPath(urlparse(response.url).path).name,'sha256':digest(response.body())})
      page.on('response',response_seen);row={'arm':arm,'fixture':fixture['file'],'size':fixture['width'],'states':[],'wasm':wasm};result['rows'].append(row)
      try:
       page.goto(f'http://127.0.0.1:{server.server_port}/?arm={arm}');page.wait_for_function('window.runtimeReady===true');page.evaluate('f=>window.start(f)',fixture['file']);page.locator('#play').click()
       for state,key,trace in STATES:
        began=time.perf_counter()
        if key:
         assert page.evaluate('document.activeElement===window.player'),'Player lost focus'
         page.keyboard.press(key)
        page.wait_for_function('(text)=>evidence.traces.some(t=>t.includes(text))',arg=trace);page.evaluate('window.settled()');elapsed=(time.perf_counter()-began)*1000
        observation=page.evaluate('window.snapshot()');assert not observation['errors'] and not observation['overflow'];assert observation['contexts']
        assert not observation['contextEvents'],'Unexpected context loss before controlled test'
        assert 'webgl' in observation.get('actualRenderer','').lower(),'Wrong renderer'
        assert observation.get('traceAttached') and observation.get('instanceTraceAttachments')==1
        assert any(c['name'] in ['drawArrays','drawElements'] for c in observation['calls'])
        assert observation['memories'],'No actual exported WASM memory observed; do not substitute JS memory'
        filename=f"{fixture['file']}-{arm}-{state}.png";page.locator('#host').screenshot(path=str(out/filename));pixels=Image.open(out/filename).convert('RGBA');check_pixels(pixels,state)
        observation.update(state=state,png=filename,rgbaSHA256=digest(pixels.tobytes()),trustedKeyToSettledWallMs=elapsed if key else None);row['states'].append(observation)
       assert wasm and all(w['sha256']==contract['runtimes'][arm]['selectedWasmSHA256'] for w in wasm),'Wrong actual selected WASM'
       assert row['states'][-1]['keys']==[{'key':k,'trusted':True} for _,k,_ in STATES if k]
       counts=[image_uploads(s,fixture['width']) for s in row['states']]
       assert counts[0]==0 and counts[1]>0,'Lazy preload/first upload contract failed'
       target_hashes=[u for u in row['states'][1]['uploadHashes'] if u['width']==fixture['width'] and u['height']==fixture['height']]
       assert target_hashes,'Missing full target bitmap RGBA upload hash'
       assert all(u.get('sha256') and u['bytes']==fixture['width']*fixture['height']*4 for u in target_hashes),'Incomplete target bitmap upload hash'
       assert counts[1:]==[counts[1]]*4,'Repeat/mask/hit unexpectedly reuploaded image'
       assert row['states'][1]['rgbaSHA256']==row['states'][2]['rgbaSHA256']
       assert row['states'][2]['rgbaSHA256']!=row['states'][3]['rgbaSHA256']
       assert row['states'][3]['rgbaSHA256']==row['states'][4]['rgbaSHA256']
       if fixture['width']==1024 and fixture['alpha']=='pattern':
        recovery={'supported':page.evaluate('window.controlledLoss()')};row['controlledContextRecovery']=recovery
        assert recovery['supported'],'Required context-loss extension unavailable'
        page.wait_for_function("evidence.contextEvents.some(e=>e.type==='lost')");page.wait_for_timeout(100);page.evaluate('window.restoreControlledContext()')
        try:page.wait_for_function("evidence.contextEvents.some(e=>e.type==='restored')",timeout=5000);recovery['restoredEvent']=True
        except Exception:recovery['restoredEvent']=False
        page.wait_for_timeout(500);page.evaluate('window.settled()');recovery['observation']=page.evaluate('window.snapshot()');assert not recovery['observation']['overflow'],'Controlled recovery exceeded observation budget'
        filename=f"{fixture['file']}-{arm}-controlled-restored.png";page.locator('#host').screenshot(path=str(out/filename));pixels=Image.open(out/filename).convert('RGBA');recovery['rgbaSHA256']=digest(pixels.tobytes());recovery['png']=filename
        recovery['pixelsRecovered']=recovery['rgbaSHA256']==row['states'][-1]['rgbaSHA256'];recovery['successful']=recovery['restoredEvent'] and recovery['pixelsRecovered'] and not recovery['observation']['errors']
      except Exception as exc:
       row['failure']=type(exc).__name__+': '+str(exc)[:1500]
       try:row['failureObservation']=page.evaluate('window.snapshot()');page.screenshot(path=str(out/f"{fixture['file']}-{arm}-failure.png"))
       except Exception:row['failureObservationUnavailable']=True
       raise
      finally:context.close()
    for fixture in manifest['fixtures']:
     pair=[r for r in result['rows'] if r['fixture']==fixture['file']];assert len(pair)==2
     for left,right in zip(pair[0]['states'],pair[1]['states']):
      assert left['state']==right['state'] and left['rgbaSHA256']==right['rgbaSHA256'],'Full-canvas pixel mismatch'
      assert [(u['width'],u['height'],u['bytes'],u['sha256']) for u in left['uploadHashes']]==[(u['width'],u['height'],u['bytes'],u['sha256']) for u in right['uploadHashes']],'Full source-resolution RGBA texture upload mismatch'
     if 'controlledContextRecovery' in pair[0]:
      old,new=[r['controlledContextRecovery'] for r in pair]
      assert not old['successful'] or new['successful'],'Candidate regressed baseline context recovery'
      result['contextRecoveryBothSuccessful']=old['successful'] and new['successful']
      result['contextRecoveryLimitation']=not result['contextRecoveryBothSuccessful']
    result['passed']=True
    result['classification']='pixel_and_loading_parity_with_context_recovery_limitation' if result.get('contextRecoveryLimitation') else 'pixel_loading_and_context_recovery_parity'
   finally:browser.close()
 finally:
  server.shutdown();(out/'result.json').write_text(json.dumps(result,indent=2)+'\n')
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--contract',type=pathlib.Path,required=True);p.add_argument('--baseline',type=pathlib.Path,required=True);p.add_argument('--candidate',type=pathlib.Path,required=True);p.add_argument('--fixtures',type=pathlib.Path,required=True);p.add_argument('--out',type=pathlib.Path,required=True);run(p.parse_args())

"""Pure diagnostics of accepted runtime: API requests are not physical GPU memory."""
import argparse,hashlib,http.server,json,pathlib,threading,time
from urllib.parse import urlparse,unquote
ROOT=pathlib.Path(__file__).resolve().parent
PACKAGE=ROOT.parent
def sha(b):return hashlib.sha256(b).hexdigest()
def validate(runtime,fixtures):
 lock=json.loads((PACKAGE/'engine-lock.json').read_text())
 actual={p.name:{'bytes':p.stat().st_size,'sha256':sha(p.read_bytes())} for p in runtime.iterdir() if p.is_file()}
 assert actual==lock['runtimeFiles'],'Engine is not accepted baseline'
 manifest=json.loads((fixtures/'manifest.json').read_text())
 for row in manifest['files']:
  data=(fixtures/row['file']).read_bytes();assert len(data)==row['bytes'] and sha(data)==row['sha256']
 return lock,manifest

def run(a):
 from playwright.sync_api import sync_playwright
 from PIL import Image
 runtime=a.runtime.resolve();fixtures=a.fixtures.resolve();lock,manifest=validate(runtime,fixtures)
 out=a.out.resolve();out.mkdir(parents=True,exist_ok=False)
 routes={'runtime':runtime,'fixtures':fixtures}
 requests=[]
 class Handler(http.server.BaseHTTPRequestHandler):
  def do_GET(self):
   try:
    path=unquote(urlparse(self.path).path)
    if path=='/':p=ROOT/'page.html'
    elif path=='/instrumentation.js':p=ROOT/'instrumentation.js'
    else:
     arm,rel=path.lstrip('/').split('/',1);base=routes[arm];p=(base/rel).resolve();assert p.is_relative_to(base)
    data=p.read_bytes();self.send_response(200);self.send_header('Content-Type',{'.js':'text/javascript','.wasm':'application/wasm','.html':'text/html'}.get(p.suffix,'application/octet-stream'));self.send_header('Cache-Control','no-store');self.end_headers();self.wfile.write(data)
    requests.append({'path':path,'bytes':len(data),'status':200})
   except Exception:self.send_error(404);requests.append({'path':self.path,'status':404})
  def log_message(self,*args):pass
 server=http.server.ThreadingHTTPServer(('127.0.0.1',0),Handler);threading.Thread(target=server.serve_forever,daemon=True).start()
 result={'passed':False,'productChanges':False,'engineArtifactId':lock['artifactId'],'engineSelectedWasmSHA256':lock['selectedWasmSHA256'],'rows':[], 'scope':'Bounded synthetic desktop sandboxed Chrome WebGL API requests. No cache policy changes, no forced GC. Not iPhone, GPU residency, RSS, or user-crash proof.','memoryScope':'Exported WASM capacity does not shrink and is not live allocation. Texture size sums are requested base-level RGBA8 estimates, not physical memory. deleteTexture requests do not prove driver completion.','instrumentationScope':'Scalar IDs/WeakMaps only; no copied upload pixel payloads and no getError calls.'}
 try:
  with sync_playwright() as pw:
   browser=pw.chromium.launch(channel='chrome',headless=True,chromium_sandbox=True)
   result.update(browserVersion=browser.version,sandboxRequested=True,extraLaunchArguments=[])
   try:
    for case in manifest['cases']:
     context=browser.new_context(viewport={'width':400,'height':280},device_scale_factor=1)
     context.route('**/*',lambda route: route.continue_() if urlparse(route.request.url).hostname=='127.0.0.1' else route.abort())
     page=context.new_page();page.set_default_timeout(45000);wasm=[]
     def response_seen(response):
      if urlparse(response.url).path.endswith('.wasm'):wasm.append({'name':pathlib.PurePosixPath(urlparse(response.url).path).name,'sha256':sha(response.body())})
     page.on('response',response_seen)
     row={'case':case['name'],'fixture':case['file'],'states':[],'wasm':wasm};result['rows'].append(row)
     def capture(label,visible=False):
      page.evaluate('window.settled()');path=out/(case['name']+'-'+label+'.png')
      page.locator('#host').screenshot(path=str(path));state=page.evaluate('window.snapshot()')
      state.update(label=label,png=path.name)
      pixels=Image.open(path).convert('RGBA');state['rgbaSHA256']=sha(pixels.tobytes())
      assert pixels.size==(320,240)
      if visible:assert len(set(pixels.crop((32,32,96,96)).getdata()))>8,'Expected synthetic picture not rendered'
      assert not state['overflow'] and not state['gl']['overflow']
      assert not state['errors'],'Page runtime errors'
      assert 'webgl' in state.get('actualRenderer','').lower()
      if not label.startswith('removed-'):assert all(not c['losses'] and not c['restores'] for c in state['gl']['contexts']),'Unexpected context event before teardown'
      assert all(not c['thrown'] for c in state['gl']['contexts']),'Wrapped API threw'
      row['states'].append(state);return state
     try:
      page.goto(f'http://127.0.0.1:{server.server_port}/');page.wait_for_function('window.runtimeReady===true')
      page.evaluate('f=>window.start(f)',case['file']);page.locator('#play').click()
      for step in case['steps']:
       if step.get('key'):
        page.evaluate('window.player.focus()');page.keyboard.press(step['key'])
       page.wait_for_function('(text)=>evidence.traces.some(t=>t===text)',arg=step['trace'])
       if step.get('waitMs'):page.wait_for_timeout(step['waitMs'])
       if step.get('visible'):page.wait_for_function('window.targetFrameObserved()')
       state=capture(step['label'],step.get('visible',False))
       assert state['traceAttached'] and state['instanceTraceAttachments']==1
       assert state['memories'] and any(m.get('reachable') for m in state['memories'])
      # Bounded natural frames/time observation: no forced JS or Ruffle GC.
      page.wait_for_timeout(1500);capture('natural-idle')
      page.evaluate('window.removePlayer()');capture('removed-2raf')
      page.wait_for_timeout(1500);capture('removed-idle')
      assert wasm and all(w['sha256']==lock['selectedWasmSHA256'] for w in wasm)
      final=row['states'][-1]
      expected_keys=[{'key':s['key'],'trusted':True} for s in case['steps'] if s.get('key')]
      assert final['keys']==expected_keys,'Trusted keyboard protocol mismatch'
      if case.get('uniqueImages'):
       for cycle in range(1,case['cycles']+1):
        for resource in range(1,case['uniqueImages']+1):
         assert f"TEXTURE_LIFETIME {case['name']} settled resource={resource} cycle={cycle}" in final['traces'],'Missing actual timeline traversal'
      if case.get('loadCycles'):
       for cycle in range(1,case['loadCycles']+1):
        for event in ['loaded','unloaded']:
         assert f"TEXTURE_LIFETIME {case['name']} {event}={cycle}" in final['traces'],'Missing actual Loader cycle'
       assert sum(t==f"TEXTURE_LIFETIME {case['name']} ping=retained-child-alive" for t in final['traces'])==case['retainedReferences']
      assert any(e.get('width')==512 and e.get('height')==512 and e['name'] in ['texImage2D','texSubImage2D','texStorage2D'] for e in row['states'][-1]['gl']['events']),'No actual target texture requests'
      # Collection/retention is a measured result, never force a preferred outcome.
      row['measured']=True
     except Exception as e:
      row['failure']=type(e).__name__+': '+str(e)[:1500]
      try:row['failureObservation']=page.evaluate('window.snapshot()');page.screenshot(path=str(out/(case['name']+'-failure.png')))
      except Exception:row['failureObservationUnavailable']=True
      raise
     finally:context.close()
    result['passed']=True;result['classification']='bounded_api_lifecycle_observation_complete_not_stability_acceptance'
   finally:browser.close()
 finally:
  server.shutdown();result['serverRequests']=requests;(out/'result.json').write_text(json.dumps(result,indent=2)+'\n')
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--runtime',type=pathlib.Path,required=True);p.add_argument('--fixtures',type=pathlib.Path,required=True);p.add_argument('--out',type=pathlib.Path,required=True);run(p.parse_args())

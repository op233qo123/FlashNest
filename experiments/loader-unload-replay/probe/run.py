#!/usr/bin/env python3
"""Neutral Loader mechanism observation, not an application compatibility pass."""
import argparse,base64,functools,hashlib,http.server,json,os,pathlib,shutil,tempfile,threading,time
from playwright.sync_api import sync_playwright
from PIL import Image
import make_probe
ROOT=pathlib.Path(__file__).resolve().parent
sha=lambda b:hashlib.sha256(b).hexdigest()
UNSAFE=['--enable-unsafe-swiftshader','--unsafely-disable-devtools-self-xss-warnings']
FORBIDDEN=UNSAFE+['--no-sandbox','--disable-setuid-sandbox','--disable-gpu-sandbox']

from validate import validate

def main():
    p=argparse.ArgumentParser();p.add_argument('--runtime-root',type=pathlib.Path,required=True);p.add_argument('--output',type=pathlib.Path,required=True);p.add_argument('--runtime-lock',type=pathlib.Path,default=ROOT/'runtime-lock.json');p.add_argument('--expect',choices=('baseline','candidate'),required=True);a=p.parse_args()
    lock=json.loads(a.runtime_lock.read_text());expected=lock['runtimeFiles']
    actual={f.relative_to(a.runtime_root).as_posix():sha(f.read_bytes()) for f in a.runtime_root.rglob('*') if f.is_file()}
    assert len(expected)==12 and actual==expected,'Exact accepted runtime inventory required'
    fixtures=make_probe.fixtures()
    result={'schema':'neutral-loader-unload-regression-v1','expect':a.expect,'runtimeLockSHA256':sha(a.runtime_lock.read_bytes()),'validationPassed':False,'applicationPass':False,'runtimeFiles':expected,
        'selectedWasmSHA256':lock['selectedWasmSHA256'],'fixtureFiles':{n:sha(b) for n,b in fixtures.items()},'rows':[],
        'sourceFiles':{f.name:sha(f.read_bytes()) for f in sorted(ROOT.iterdir()) if f.is_file() and f.suffix in ('.py','.html','.json','.yml','.md')},
        'head':os.environ.get('GITHUB_SHA'),'runID':os.environ.get('GITHUB_RUN_ID'),
        'privateGameInputs':False,'engineChanged':a.expect=='candidate','flashReferenceRun':False,
        'scope':'Neutral Chrome/WebGL Loader event observation only; not private game/iOS compatibility'}
    with tempfile.TemporaryDirectory() as tmp:
        root=pathlib.Path(tmp);shutil.copytree(a.runtime_root,root/'runtime');(root/'fixtures').mkdir();shutil.copyfile(ROOT/'probe.html',root/'probe.html')
        for n,b in fixtures.items():(root/'fixtures'/n).write_bytes(b)
        class Quiet(http.server.SimpleHTTPRequestHandler):
            def log_message(self,*args):pass
            def do_GET(self):
                if self.path.endswith('/delayed-first.swf'):
                    time.sleep(3);self.path='/fixtures/first.swf'
                if self.path.endswith('/missing.swf'):
                    self.send_response(404);self.end_headers();self.wfile.write(b'neutral missing fixture');return
                try:super().do_GET()
                except (BrokenPipeError,ConnectionResetError):pass
        server=http.server.ThreadingHTTPServer(('127.0.0.1',0),functools.partial(Quiet,directory=str(root)))
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start();origin=f'http://127.0.0.1:{server.server_port}'
        try:
            with sync_playwright() as pw:
                browser=pw.chromium.launch(channel='chrome',headless=True,chromium_sandbox=True,ignore_default_args=UNSAFE)
                try:
                    cdp=browser.new_browser_cdp_session();flags=cdp.send('Browser.getBrowserCommandLine')['arguments'];gpu=cdp.send('SystemInfo.getInfo')['gpu'];cdp.detach()
                    assert not any(f.split('=')[0] in FORBIDDEN for f in flags),'Unsafe effective browser flag'
                    result['browser']={'version':browser.version,'sandboxRequested':True,'effectiveCommandLine':flags,'gpu':gpu}
                    for arm in make_probe.MODES:
                        row={'arm':arm,'responses':[],'requests':[],'requestFailures':[],'errors':[],'runtimeErrors':[],'console':[],'remoteRequests':[]};result['rows'].append(row)
                        context=browser.new_context(viewport={'width':400,'height':300},device_scale_factor=1);page=context.new_page()
                        def route(route):
                            if not route.request.url.startswith(origin+'/'):row['remoteRequests'].append(route.request.url);route.abort()
                            else:route.continue_()
                        context.route('**/*',route)
                        page.on('pageerror',lambda e:row['errors'].append(str(e)[:1000]))
                        page.on('request',lambda request:row['requests'].append({'name':request.url.rsplit('/',1)[-1].split('?')[0],'resourceType':request.resource_type}))
                        page.on('requestfailed',lambda request:row['requestFailures'].append({'name':request.url.rsplit('/',1)[-1].split('?')[0],'failure':str(request.failure)[:500]}))
                        def console(msg):
                            if len(row['console'])<80:row['console'].append({'type':msg.type,'text':msg.text[:1000]})
                            if msg.type=='error' and not (arm=='failed-load' and '404' in msg.text):row['errors'].append(msg.text[:1000])
                            if '%cERROR%c' in msg.text:row['runtimeErrors'].append(msg.text[:1000])
                        page.on('console',console)
                        def response(r):
                            name=r.url.rsplit('/',1)[-1]
                            if not name.endswith(('.wasm','.swf')):return
                            b=r.body();record={'name':name,'status':r.status,'bytes':len(b),'sha256':sha(b)}
                            if name.endswith('.swf'):
                                assert len(b)<=8192;record['bodyBase64']=base64.b64encode(b).decode()
                                if name=='missing.swf':assert arm=='failed-load' and r.status==404 and b==b'neutral missing fixture'
                                elif name=='delayed-first.swf':assert arm=='incomplete-load' and b==fixtures['first.swf']
                                else:assert name in fixtures and b==fixtures[name],'Neutral fixture response differs'
                            else:assert name==lock['selectedWasm'] and sha(b)==lock['selectedWasmSHA256'],'Actual selected WASM differs'
                            assert r.status==200 or (arm=='failed-load' and name=='missing.swf' and r.status==404),'Resource HTTP failed';row['responses'].append(record)
                        page.on('response',response)
                        try:
                            page.goto(origin+'/probe.html?variant='+arm)
                            page.wait_for_function("evidence.traces.some(t=>t.message==='UNLOAD_CALL_RETURNED') || evidence.error",timeout=30000)
                            assert not page.evaluate('evidence.error')
                            started=time.monotonic();page.wait_for_timeout(5500);row['observationSecondsAfterUnloadReturn']=time.monotonic()-started
                            row['snapshot']=page.evaluate('evidence');row['metadata']=page.evaluate('player.ruffle().metadata');row['renderer']=page.evaluate('actualRenderer()')
                            image=a.output.with_name(a.output.stem+'-'+arm+'.png');image.parent.mkdir(parents=True,exist_ok=True)
                            page.locator('ruffle-player').screenshot(path=str(image));row['screenshot']={'file':image.name,'sha256':sha(image.read_bytes()),'renderedFrameAssertion':False}
                            pixels=Image.open(image).convert('RGBA');assert pixels.size==(160,120)
                            row['pixels']={'nextOrRetainedAt8x8':list(pixels.getpixel((8,8))),'keptOldAt136x8':list(pixels.getpixel((136,8)))}
                            assert any(r['name']==lock['selectedWasm'] for r in row['responses']),'No actual WASM response'
                        except Exception as error:
                            row['failure']=str(error)[:2000]
                            try:row['snapshot']=page.evaluate('evidence');row['renderer']=page.evaluate('actualRenderer()')
                            except Exception:pass
                            raise
                        finally:context.close()
                    result['mechanismOutcome']=validate(result['rows'],a.expect);result['validationPassed']=True
                finally:browser.close()
        except Exception as error:result['failure']=str(error)[:2000];raise
        finally:
            server.shutdown();server.server_close();thread.join();a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({'validationPassed':True,'mechanismOutcome':result['mechanismOutcome'],'applicationPass':False}))
if __name__=='__main__':main()

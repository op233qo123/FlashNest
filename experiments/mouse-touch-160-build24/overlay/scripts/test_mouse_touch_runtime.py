#!/usr/bin/env python3
"""Neutral generated AVM1 + actual bundled WASM. Requires preinstalled Playwright.
No user assets, downloads or mocks. Launches sandboxed Chromium (never --no-sandbox).
This supplements, never substitutes for, native WKWebView/device touch testing.
Run after staging the delivered app/runtime plus mouse-touch overlay.
"""
import functools, hashlib, http.server, json, os, pathlib, shutil, struct, sys, tempfile, threading, time
from playwright.sync_api import sync_playwright
from mouse_clicks_runtime import run_shell_probe
ROOT = pathlib.Path(__file__).resolve().parents[1]
def action(op, body=b''):
    return bytes([op]) + (struct.pack('<H',len(body))+body if op>=128 else b'')
def push(s): return action(0x96,b'\0'+s.encode()+b'\0')
def integer(i): return action(0x96,b'\x07'+struct.pack('<i',i))
def variable(s): return push(s)+action(0x1c)
def member(s): return variable('_root')+push(s)+action(0x4e)
def trace(s): return push(s)+action(0x26)
def handler(name, body, target="_root"):
    body+=b'\0'
    return variable(target)+push(name)+action(0x9b,b'\0'+struct.pack('<HH',0,len(body)))+body+action(0x4f)
def tag(n,b=b''): return struct.pack('<H',(n<<6)|min(63,len(b)))+(struct.pack('<I',len(b)) if len(b)>=63 else b'')+b
def fixture():
    code=push('__mouseListener')+integer(0)+action(0x43)+action(0x1d)
    code+=handler('onMouseMove',trace('MOVE'),'__mouseListener')+handler('onMouseDown',trace('DOWN'),'__mouseListener')+handler('onMouseUp',trace('UP'),'__mouseListener')
    code+=variable('__mouseListener')+integer(1)+variable('Mouse')+push('addListener')+action(0x52)+action(0x17)
    position=push('POSITION:')+member('_xmouse')+action(0x47)+push(',')+action(0x47)+member('_ymouse')+action(0x47)+action(0x26)
    code+=handler('onEnterFrame',position)+trace('READY')+action(0x07)+b'\0'
    bits='01110'+''.join(format(x,'014b') for x in (0,6400,0,4800));bits+='0'*(-len(bits)%8)
    body=int(bits,2).to_bytes(len(bits)//8,'big')+struct.pack('<HH',4*256,1)+tag(9,bytes([30,70,100]))+tag(12,code)+tag(1)+tag(0)
    return b'FWS\x07'+struct.pack('<I',len(body)+8)+body
def wait(page, expression, *, timeout=30000, arg=None):
    # Poll through the automation protocol, not Playwright's in-page eval-based
    # waitForFunction. The production CSP stays unchanged; bypass_csp is never set.
    deadline=time.monotonic()+timeout/1000
    while time.monotonic()<deadline:
        if page.evaluate(expression, arg):return
        time.sleep(0.05)
    print(json.dumps({'failureEvidence':page.evaluate("({raw:window.__raw,events:window.__dom,diagnostics:window.__diag})")}), file=sys.stderr)
    raise TimeoutError('Runtime condition did not become true: '+expression)
class Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self,*args): pass
EVENT = """([type,id,x,y])=>{const c=document.querySelector('ruffle-player').shadowRoot.querySelector('canvas');c.dispatchEvent(new PointerEvent(type,{pointerId:id,pointerType:'touch',clientX:x,clientY:y,bubbles:true,composed:true,cancelable:true}));}"""
with tempfile.TemporaryDirectory(prefix='flashnest-mouse-') as td:
    web=pathlib.Path(td)/'fixture/web';shutil.copytree(ROOT/'App/Resources/Web',web)
    assert (web/'runtime/ruffle.js').exists(),'Stage the hash-verified delivered runtime first'
    runtime_files=json.loads((ROOT/'runtime.files.json').read_text())
    assert len(runtime_files)==12
    assert {p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in (web/'runtime').iterdir() if p.is_file()}==runtime_files
    game=pathlib.Path(td)/'fixture/games/11111111-1111-4111-8111-111111111111';game.mkdir(parents=True);(game/'main.swf').write_bytes(fixture())
    server=http.server.ThreadingHTTPServer(('127.0.0.1',0),functools.partial(Quiet,directory=td));threading.Thread(target=server.serve_forever,daemon=True).start()
    try:
        with sync_playwright() as p:
            executable=os.environ.get('CHROMIUM_EXECUTABLE')
            if not executable and pathlib.Path('/usr/bin/chromium').exists(): executable='/usr/bin/chromium'
            browser=p.chromium.launch(executable_path=executable,headless=True,chromium_sandbox=True,ignore_default_args=['--enable-unsafe-swiftshader','--unsafely-disable-devtools-self-xss-warnings'])
            cdp=browser.new_browser_cdp_session()
            arguments=cdp.send('Browser.getBrowserCommandLine')['arguments']
            forbidden={'--no-sandbox','--disable-setuid-sandbox','--disable-gpu-sandbox','--enable-unsafe-swiftshader','--unsafely-disable-devtools-self-xss-warnings'}
            assert arguments and not any(a.split('=')[0] in forbidden for a in arguments)
            sandbox={'requested':True,'forbiddenFlagsAbsent':True,'effectiveCommandLine':arguments}
            results=[]
            for width,height,dpr,sampling in [(800,600,1,'1'),(390,844,3,'1'),(844,390,3,'1'),(800,600,3,'0.5')]:
                context=browser.new_context(viewport={'width':width,'height':height},device_scale_factor=dpr)
                page=context.new_page();errors=[];requests=[];wasm={};page.on('pageerror',lambda e:errors.append(str(e)))
                page.on('request',lambda r:requests.append(r.url))
                def response(r):
                    name=r.url.split('/')[-1]
                    if name.endswith('.wasm'):
                        assert r.status==200 and name in runtime_files
                        wasm[name]=hashlib.sha256(r.body()).hexdigest()
                page.on('response',response)
                page.add_init_script("window.__diag=[];window.webkit={messageHandlers:{flashnest:{postMessage:m=>window.__diag.push(m)}}}")
                page.goto(f'http://127.0.0.1:{server.server_port}/fixture/web/index.html?package=11111111-1111-4111-8111-111111111111&entry=main.swf&mouseTouch=1&renderScale={sampling}')
                wait(page,"window.__diag.some(m=>m.type==='loaded')",timeout=60000)
                page.get_by_role('button',name='Play / enable audio').click()
                wait(page,"window.__diag.some(m=>m.message==='SWF: READY')",timeout=15000)
                page.evaluate("""()=>{window.__raw=[];const api=document.querySelector('ruffle-player').ruffle();const original=api.traceObserver;api.traceObserver=message=>{window.__raw.push(String(message));if(window.__raw.length>256)window.__raw.shift();if(typeof original==='function')original(message);};window.__dom=[];const c=document.querySelector('ruffle-player').shadowRoot.querySelector('canvas');for(const n of ['pointerdown','pointermove','pointerup'])c.addEventListener(n,e=>window.__dom.push({type:n,pointer:e.pointerType,x:e.offsetX,y:e.offsetY,button:e.button,buttons:e.buttons}));}""")
                r=page.locator('ruffle-player').evaluate("e=>{const r=e.shadowRoot.querySelector('canvas').getBoundingClientRect();return {x:r.x,y:r.y,w:r.width,h:r.height}}")
                scale=min(r['w']/320,r['h']/240);ox=(r['w']-320*scale)/2;oy=(r['h']-240*scale)/2
                cx=(r['w']-1)/2;cy=(r['h']-1)/2
                for x,y in [(2,2),(318,2),(318,238),(2,238)]:
                    targetx=ox+x*scale;targety=oy+y*scale
                    page.evaluate("window.__dom=[];window.__raw=[]")
                    page.evaluate(EVENT,['pointerdown',1,r['x']+cx,r['y']+cy])
                    page.evaluate(EVENT,['pointermove',1,r['x']+targetx,r['y']+targety])
                    page.evaluate(EVENT,['pointerup',1,r['x']+targetx,r['y']+targety])
                    wait(page,"([x,y])=>window.__raw.some(m=>{if(!m.startsWith('POSITION:'))return false;const a=m.slice(9).split(',').map(Number);return Math.abs(a[0]-x)<2&&Math.abs(a[1]-y)<2})",arg=[x,y],timeout=5000)
                    messages=page.evaluate('window.__raw');events=page.evaluate('window.__dom')
                    assert 'MOVE' in messages and 'DOWN' not in messages,(messages,events)
                    assert events and all(e['pointer']=='mouse' and e['buttons']==0 for e in events),events
                    cx,cy=targetx,targety
                page.evaluate('window.__dom=[];window.__raw=[]')
                page.evaluate(EVENT,['pointerdown',1,100,100]);page.evaluate(EVENT,['pointerup',1,100,100])
                wait(page,"window.__raw.some(m=>m==='DOWN')",timeout=5000)
                assert page.evaluate("window.__raw.filter(m=>m==='DOWN').length") == 1
                page.evaluate('window.__dom=[];window.__raw=[]')
                for e in [('pointerdown',1,100,100),('pointerdown',2,130,100),('pointerup',1,100,100),('pointerup',2,130,100)]:page.evaluate(EVENT,list(e))
                clicks=page.evaluate("window.__dom.filter(e=>e.type==='pointerdown'||e.type==='pointerup')")
                assert [e['button'] for e in clicks]==[2,2],clicks
                assert not errors,errors
                assert wasm and all(runtime_files[n]==h for n,h in wasm.items()),wasm
                assert all(u.startswith(f'http://127.0.0.1:{server.server_port}/') for u in requests),requests
                results.append({'viewport':[width,height],'dpr':dpr,'sampling':sampling,'corners':4,'leftClick':True,'rightDOMPair':True,'selectedWasm':wasm})
                context.close()
            swf_clicks=run_shell_probe(browser,pathlib.Path(td),f'http://127.0.0.1:{server.server_port}',runtime_files)
            browser.close();print(json.dumps({'swfClicks':swf_clicks,'result':'PASS','actualRuffle':True,'nativeTouchCertified':False,'runtimeFiles':runtime_files,'sandbox':sandbox,'head':os.environ.get('GITHUB_SHA'),'runID':os.environ.get('GITHUB_RUN_ID'),'cases':results}))
    finally:server.shutdown()

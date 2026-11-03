"""Additional real-shell, real-WASM, SWF-level mouse acceptance.

Called by test_mouse_touch_runtime.py after its original matrix. Browser-native
touch through CDP is not native iOS certification. No game/private assets.
"""
import time, hashlib, os, json, sys
from pathlib import Path
from mouse_probe_avm2 import fixture

def wait(page, expression, timeout=20):
    deadline=time.monotonic()+timeout
    while time.monotonic()<deadline:
        if page.evaluate(expression): return
        time.sleep(.03)
    raise AssertionError(('SWF mouse probe timeout',expression,page.evaluate('({diag:window.__diag,traces:window.__mouseRaw})')))

# Bounded diagnostics are emitted to stderr only. A failing acceptance case is
# never replaced by a successful retry or positive control.
OBSERVE = """()=>{
 window.__mouseRaw=[];window.__mouseDOM=[];
 const host=document.querySelector('ruffle-player'), api=host.ruffle();
 const prior=api.traceObserver;
 api.traceObserver=m=>{window.__mouseRaw.push(String(m));if(window.__mouseRaw.length>256)window.__mouseRaw.shift();if(typeof prior==='function')prior(m);};
 for(const type of ['pointerdown','pointerup','pointermove','pointerenter','pointercancel','touchstart','touchend','mousedown','mouseup','click'])
 window.addEventListener(type,e=>{
  const target=e.composedPath()[0];
  window.__mouseDOM.push({type,pointerType:e.pointerType,button:e.button,buttons:e.buttons,trusted:e.isTrusted,
   x:e.clientX,y:e.clientY,target:target?.tagName,targetID:target?.id,defaultPrevented:e.defaultPrevented,time:performance.now()});
  if(window.__mouseDOM.length>100)window.__mouseDOM.shift();
 },true);
}"""
SNAPSHOT = """()=>{
 const host=document.querySelector('ruffle-player'),canvas=host?.shadowRoot?.querySelector('canvas');
 const describe=e=>{if(!e)return null;const r=e.getBoundingClientRect(),s=getComputedStyle(e);return {tag:e.tagName,id:e.id,rect:{x:r.x,y:r.y,width:r.width,height:r.height},hidden:e.hidden,display:s.display,visibility:s.visibility,pointerEvents:s.pointerEvents};};
 const r=canvas?.getBoundingClientRect(),x=r?.x+r?.width/2,y=r?.y+r?.height/2;
 return {raw:window.__mouseRaw,dom:window.__mouseDOM,diag:window.__diag?.slice(-30),probeGeometry:window.__diag?.filter(m=>String(m.message).includes('PROBE_GEOMETRY')).slice(0,2),canvas:describe(canvas),host:describe(host),
  cursor:describe(document.querySelector('#mouse-touch-cursor')),active:describe(document.activeElement),
  centerHit:describe(document.elementFromPoint(x,y)),shadowCenterHit:describe(host?.shadowRoot?.elementFromPoint(x,y)),
  viewport:{width:innerWidth,height:innerHeight,dpr:devicePixelRatio},visibility:document.visibilityState};
}"""

def ordinary_mouse_control(browser, url):
    # Separate fresh movie/context: diagnostic only, not a warm-up for acceptance.
    context=browser.new_context(viewport={'width':800,'height':600},has_touch=True)
    try:
        page=context.new_page();errors=[];console=[]
        page.on('console',lambda m:console.append({'type':m.type,'text':m.text[:2000]}) if m.type in ('error','warning') and len(console)<30 else None)
        page.on('pageerror',lambda e:errors.append(str(e)))
        page.add_init_script("window.__diag=[];window.webkit={messageHandlers:{flashnest:{postMessage:m=>window.__diag.push(m)}}}")
        page.goto(url)
        wait(page,"window.__diag.some(m=>m.type==='loaded')",60)
        page.get_by_role('button',name='Play / enable audio').click()
        wait(page,"window.__diag.some(m=>m.message==='SWF: READY')",20)
        page.evaluate(OBSERVE)
        r=page.locator('ruffle-player').evaluate("e=>{const r=e.shadowRoot.querySelector('canvas').getBoundingClientRect();return{x:r.x,y:r.y,w:r.width,h:r.height}}")
        x=r['x']+r['w']/2;y=r['y']+r['h']/2
        page.mouse.click(x,y);time.sleep(.2)
        first=page.evaluate(SNAPSHOT)
        page.evaluate('window.__mouseRaw=[];window.__mouseDOM=[]')
        page.mouse.move(x+3,y);time.sleep(.2);page.mouse.click(x+3,y);time.sleep(.2)
        second=page.evaluate(SNAPSHOT)
        return {'firstOrdinaryMouse':first,'mouseAfterHoverAndFrame':second,'errors':errors,'console':console}
    finally:
        context.close()

def run_shell_probe(browser, directory, base_url, runtime_files):
    game_id='22222222-2222-4222-8222-222222222222'
    game=directory/'fixture/games'/game_id;game.mkdir(parents=True)
    (game/'main.swf').write_bytes(fixture())
    context=browser.new_context(viewport={'width':800,'height':600},has_touch=True)
    try:
        page=context.new_page();errors=[];requests=[];wasm={};console=[]
        page.on('console',lambda m:console.append({'type':m.type,'text':m.text[:2000]}) if m.type in ('error','warning') and len(console)<30 else None)
        page.on('pageerror',lambda e:errors.append(str(e)))
        page.on('request',lambda r:requests.append(r.url))
        def response(r):
            name=r.url.split('/')[-1]
            if name.endswith('.wasm'):
                assert r.status==200 and name in runtime_files
                wasm[name]=hashlib.sha256(r.body()).hexdigest()
        page.on('response',response)
        page.add_init_script("window.__diag=[];window.webkit={messageHandlers:{flashnest:{postMessage:m=>window.__diag.push(m)}}}")
        url=f'{base_url}/fixture/web/index.html?package={game_id}&entry=main.swf&mouseTouch=1&mouseOpacity=0.6'
        page.goto(url)
        wait(page,"window.__diag.some(m=>m.type==='loaded')",60)
        page.get_by_role('button',name='Play / enable audio').click()
        wait(page,"window.__diag.some(m=>m.message==='SWF: READY')",20)
        page.evaluate(OBSERVE)
        cdp=context.new_cdp_session(page)
        rect=page.locator('ruffle-player').evaluate("e=>{const r=e.shadowRoot.querySelector('canvas').getBoundingClientRect();return{x:r.x,y:r.y,w:r.width,h:r.height}}")
        # These fingers start well away from the bottom-centered right button.
        x=rect['x']+rect['w']*.4;y=rect['y']+rect['h']*.3
        def touch(kind,points):
            cdp.send('Input.dispatchTouchEvent',{'type':kind,'touchPoints':[{'id':i,'x':px,'y':py} for i,px,py in points]})
        def clear(): page.evaluate('window.__mouseRaw=[];window.__mouseDOM=[]')
        def tap():
            touch('touchStart',[(1,x,y)]);time.sleep(.06);touch('touchEnd',[])
        def cursor():
            return page.locator('#mouse-touch-cursor').evaluate('e=>[e.style.left,e.style.top]')
        cases=[]
        def check(name,expected):
            time.sleep(.15)
            raw=page.evaluate('window.__mouseRaw')
            events=[m for m in raw if m.startswith('EVENT:')]
            row={'name':name,'events':events,'expected':expected,'frameObservedPressed':'FRAME_PRESSED true' in raw}
            cases.append(row)
            if events!=expected:
                evidence={'failedCase':row,'original':page.evaluate(SNAPSHOT),'pageErrors':errors[:20],'console':console}
                try:
                    clear();tap();time.sleep(.2)
                    evidence['subsequentCanvasTap']=page.evaluate(SNAPSHOT)
                except Exception as error:
                    evidence['subsequentTapDiagnosticError']=str(error)
                try:
                    evidence['freshOrdinaryMouseControl']=ordinary_mouse_control(browser,url)
                except Exception as error:
                    evidence['ordinaryMouseDiagnosticError']=str(error)
                print(json.dumps({'swfClickFailureEvidence':evidence}),file=sys.stderr,flush=True)
                raise AssertionError(row)
        left=['EVENT:mouseDown','EVENT:mouseUp','EVENT:click']
        right=['EVENT:rightMouseDown','EVENT:rightMouseUp','EVENT:rightClick']
        clear();tap();check('first_canvas_tap_without_warmup_move',left)
        before=cursor();clear();touch('touchStart',[(1,x,y)]);touch('touchMove',[(1,x+4,y)]);touch('touchEnd',[])
        check('jitter_click_once',left);assert cursor()==before,('jitter moved cursor',before,cursor())
        clear();touch('touchStart',[(1,x,y)]);touch('touchMove',[(1,x+20,y)]);touch('touchEnd',[])
        check('slide_never_clicks',[]);assert cursor()!=before,'slide failed to move cursor'
        clear();tap();check('first_tap_after_slide',left)
        page.evaluate("document.querySelector('ruffle-player').blur()")
        clear();tap();check('first_tap_after_focus_loss',left)
        # Tap the genuine visible shell control. Never call the controller or
        # synthesize a trusted event: isTrusted must come from browser input.
        button=page.get_by_role('button',name='Right click',exact=True)
        assert button.is_visible() and button.is_enabled()
        before=cursor();clear();button.tap();check('visible_right_button_swf_events',right)
        assert cursor()==before,'right button moved pointer'
        clear();button.tap();check('repeat_right_button_no_left_leak',right)
        page.evaluate('window.FlashNest.setMouseRightButtonOpacity(0.25)')
        assert abs(float(button.evaluate('e=>getComputedStyle(e).opacity'))-.25)<.01
        clear();button.tap();check('transparent_right_button_swf_events',right)
        page.evaluate('window.FlashNest.pause()');assert not button.is_visible()
        page.evaluate('window.FlashNest.resume()');assert button.is_visible()
        clear();tap();check('first_tap_after_pause_resume',left)
        page.evaluate('window.FlashNest.setMouseTouchEnabled(false)');assert not button.is_visible()
        page.evaluate('window.FlashNest.setMouseTouchEnabled(true)');assert button.is_visible()
        clear();tap();check('first_tap_after_mode_toggle',left)
        assert not errors,errors
        assert all(url.startswith(base_url+'/') for url in requests),requests
        assert wasm and all(runtime_files[n]==h for n,h in wasm.items()),wasm
        source=Path(__file__).resolve().parent
        files=['test_mouse_touch_runtime.py','mouse_clicks_runtime.py','mouse_probe_abc.py','mouse_probe_avm2.py']
        sources={n:hashlib.sha256((source/n).read_bytes()).hexdigest() for n in files}
        return {'sourceFiles':sources,'selectedWasm':wasm,'runtimeFiles':runtime_files,'head':os.environ.get('GITHUB_SHA'),'runID':os.environ.get('GITHUB_RUN_ID'),'result':'PASS','actualShell':True,'actualSWFEvents':True,'browserTouch':'CDP','nativeTouchCertified':False,'cases':cases}
    finally:
        context.close()

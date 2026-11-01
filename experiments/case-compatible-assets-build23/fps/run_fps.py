#!/usr/bin/env python3
"""Actual pinned WASM in Chromium. Synthetic RAF is NOT a real 60/120Hz display test."""
import argparse, functools, hashlib, http.server, importlib.metadata, json, pathlib, shutil, tempfile, threading, time
from playwright.sync_api import sync_playwright
from make_fixture import make_swf

ROOT=pathlib.Path(__file__).resolve().parent
sha=lambda b:hashlib.sha256(b).hexdigest()

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--runtime',type=pathlib.Path,required=True)
    p.add_argument('--inputs',type=pathlib.Path,required=True,help='Exact build23 inputs.json')
    p.add_argument('--output',type=pathlib.Path,required=True)
    p.add_argument('--chromium',default=None)
    args=p.parse_args(); config=json.loads(args.inputs.read_text()); expected=config['runtimeFiles']
    actual={f.relative_to(args.runtime).as_posix():sha(f.read_bytes()) for f in args.runtime.rglob('*') if f.is_file()}
    assert len(expected)==12 and actual==expected,'Runtime must exactly match 12-file build23 input inventory'
    rows=[]; sandbox=None; page=None; errors=[]; fetched=[]; remote=[]; console=[]; scheduler=None; hz=None; override=None
    with tempfile.TemporaryDirectory() as tmp:
        root=pathlib.Path(tmp); shutil.copytree(args.runtime,root/'runtime')
        shutil.copyfile(ROOT/'probe.html',root/'probe.html'); fixture=make_swf(); (root/'neutral-24fps.swf').write_bytes(fixture)
        class Quiet(http.server.SimpleHTTPRequestHandler):
            def log_message(self,*args): pass
        server=http.server.ThreadingHTTPServer(('127.0.0.1',0),functools.partial(Quiet,directory=str(root)))
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        origin=f'http://127.0.0.1:{server.server_port}'
        try:
            with sync_playwright() as pw:
                # Playwright defaults this to False; keep Chromium's sandbox on.
                options={'headless':True,'chromium_sandbox':True}
                if args.chromium:options['executable_path']=args.chromium
                browser=pw.chromium.launch(**options)
                try:
                    session=browser.new_browser_cdp_session()
                    command_line=session.send('Browser.getBrowserCommandLine')['arguments']
                    forbidden=('--no-sandbox','--disable-setuid-sandbox','--disable-gpu-sandbox')
                    assert not any(arg.split('=')[0] in forbidden for arg in command_line),'Browser sandbox disabled'
                    sandbox={'requested':True,'effectiveCommandLine':command_line,
                        'forbiddenFlagsAbsent':True,'browserVersion':browser.version,
                        'playwrightVersion':importlib.metadata.version('playwright')}
                    session.detach()
                    for scheduler,hz,override in [('wall',None,None),('wall',None,24),('wall',None,48),('synthetic',60,None),('synthetic',120,None)]:
                        context=browser.new_context(); page=context.new_page(); errors=[]; fetched=[]; remote=[]; console=[]
                        def route(request):
                            if not request.request.url.startswith(origin+'/'):
                                remote.append(request.request.url);request.abort()
                            else:request.continue_()
                        context.route('**/*',route)
                        page.on('pageerror',lambda error:errors.append(str(error)))
                        def on_console(message):
                            if len(console)<80:console.append({'type':message.type,'text':message.text[:1000]})
                            if message.type=='error':errors.append(message.text[:1000])
                        page.on('console',on_console)
                        page.on('response',lambda response:fetched.append({'name':response.url.rsplit('/',1)[-1],'sha256':sha(response.body())}) if response.url.endswith('.wasm') else None)
                        url=origin+'/probe.html?scheduler='+scheduler+(f'&override={override}' if override else '')
                        page.goto(url)
                        deadline=time.monotonic()+45
                        while not page.evaluate('probe.ready && probe.ticks.length > 5'):
                            assert time.monotonic()<deadline,'Probe startup timeout'
                            assert not page.evaluate('probe.error'),page.evaluate('probe.error')
                            if scheduler=='synthetic':page.evaluate('(hz)=>advance(hz,1)',hz)
                            page.wait_for_timeout(20)
                        if scheduler=='wall':
                            start=page.evaluate('({count:probe.ticks.at(-1).count,wall:performance.now(),raf:probe.raf})')
                            page.wait_for_timeout(4500)
                            end=page.evaluate('({count:probe.ticks.at(-1).count,wall:performance.now(),raf:probe.raf})')
                            seconds=(end['wall']-start['wall'])/1000
                            observed=(end['count']-start['count'])/seconds
                            target=override or 24
                            assert abs(observed-target)<target*0.18,(scheduler,override,observed)
                            # Detect a broken sensitivity/control: explicit 48 must actually produce twice default.
                            row={'scheduler':'real-browser-wallclock','override':override,'expectedFPS':target,
                                'observedFPS':observed,'seconds':seconds,'frames':end['count']-start['count'],
                                'rafCallbacks':end['raf']-start['raf']}
                        else:
                            start=page.evaluate('({count:probe.ticks.at(-1).count,virtual:probe.virtualTime})')
                            # Process single callback batches; no browser event-loop/physical refresh claim.
                            page.evaluate('(hz)=>advance(hz,hz*10)',hz)
                            end=page.evaluate('({count:probe.ticks.at(-1).count,virtual:probe.virtualTime})')
                            frames=end['count']-start['count'];seconds=(end['virtual']-start['virtual'])/1000
                            assert abs(frames-24*seconds)<=2,(hz,frames,seconds)
                            row={'scheduler':'synthetic-RAF-timestamps','syntheticHz':hz,'virtualSeconds':seconds,
                                'frames':frames,'expectedFPS':24,'physicalDisplayTest':False}
                        assert not errors and not remote and not page.evaluate('probe.error'),(errors,remote,page.evaluate('probe.error'))
                        renderer=page.evaluate('actualRenderer()')
                        assert renderer in ('webgl','webgl2','experimental-webgl'),('Not actual WebGL',renderer)
                        assert page.evaluate('probe.ticks.every((tick,i)=>i===0 || tick.count===probe.ticks[i-1].count+1)'), 'Nonsequential ENTER_FRAME counter'
                        assert fetched and all(expected.get(w['name'])==w['sha256'] for w in fetched),'Actual WASM response differs'
                        metadata=page.evaluate('player.ruffle().metadata')
                        assert metadata and metadata.get('frameRate')==24,('Wrong fixture header metadata',metadata)
                        row.update(wasmResponses=fetched,metadata=metadata,actualRenderer=renderer,passed=True)
                        rows.append(row); context.close()
                except Exception as error:
                    snapshot=None
                    if page is not None:
                        try:
                            snapshot=page.evaluate("""() => ({probe:window.probe ? {...probe,ticks:probe.ticks.slice(-12)} : null,
                                metadata:window.player?.ruffle().metadata || null,
                                actualRenderer:window.actualRenderer?.() || null,
                                playing:window.player?.ruffle().isPlaying ?? null,
                                documentState:document.readyState})""")
                        except Exception as snapshot_error:snapshot={'snapshotError':str(snapshot_error)[:1000]}
                    failure={'schema':'neutral-frame-cadence-v1','passed':False,'error':str(error)[:2000],
                        'stage':{'scheduler':scheduler,'syntheticHz':hz,'override':override},
                        'completedRows':rows,'snapshot':snapshot,'console':console,'errors':errors[:40],
                        'remoteRequests':remote[:40],'wasmResponses':fetched,'sandbox':sandbox,
                        'runtimeFiles':expected,'inputsSHA256':sha(args.inputs.read_bytes()),
                        'fixtureSHA256':sha(fixture),'sourceFiles':{name:sha((ROOT/name).read_bytes()) for name in ('make_fixture.py','probe.html','run_fps.py')},
                        'privateGameInputs':False,'productFrameRateChanged':False}
                    args.output.parent.mkdir(parents=True,exist_ok=True)
                    args.output.write_text(json.dumps(failure,indent=2)+'\n')
                    print(json.dumps({'passed':False,'output':str(args.output),'error':str(error)[:500]}))
                    raise
                finally:browser.close()
        finally:server.shutdown();server.server_close();thread.join()
    defaults=[r for r in rows if r['scheduler']=='real-browser-wallclock']
    assert 1.65 < defaults[2]['observedFPS']/defaults[0]['observedFPS'] < 2.35,'48fps positive control not sensitive'
    result={'schema':'neutral-frame-cadence-v1','passed':True,'runtimeFiles':expected,
        'inputsSHA256':sha(args.inputs.read_bytes()),'fixtureSHA256':sha(fixture),'fixtureBytes':len(fixture),
        'rows':rows,'sandbox':sandbox,'sourceFiles':{name:sha((ROOT/name).read_bytes()) for name in ('make_fixture.py','probe.html','run_fps.py')},
        'limitations':['Desktop Chromium only; not WKWebView or physical iOS.',
        'Synthetic 60/120Hz rows inject timestamps; they do not establish real display refresh behavior.',
        'Neutral ENTER_FRAME fixture only; does not prove the reported game speed cause or fix it.'],
        'productFrameRateChanged':False,'privateGameInputs':False}
    args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({'passed':True,'rows':len(rows),'output':str(args.output)}))

if __name__=='__main__':main()

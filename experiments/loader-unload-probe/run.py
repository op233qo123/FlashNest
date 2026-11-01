#!/usr/bin/env python3
"""Neutral Loader mechanism observation, not an application compatibility pass."""
import argparse,base64,functools,hashlib,http.server,json,os,pathlib,shutil,tempfile,threading,time
from playwright.sync_api import sync_playwright
import make_probe
ROOT=pathlib.Path(__file__).resolve().parent
sha=lambda b:hashlib.sha256(b).hexdigest()
UNSAFE=['--enable-unsafe-swiftshader','--unsafely-disable-devtools-self-xss-warnings']
FORBIDDEN=UNSAFE+['--no-sandbox','--disable-setuid-sandbox','--disable-gpu-sandbox']

def validate(rows):
    for row in rows:
        traces=[r['message'] for r in row['snapshot']['traces']]
        row['traceMessages']=traces
        for msg in ['FIRST_COMPLETE','PRE_CONTENT_PARENT_LOADER true','PRE_CONTENT_INFO_MATCH true','TRANSITION_ENTER_FRAME','PRE_LOADER_PARENT_NULL true','UNLOAD_CALL_BEGIN','UNLOAD_CALL_RETURNED']:
            assert traces.count(msg)==1,(row['arm'],'Invalid precondition',msg,traces)
        assert not row['snapshot']['error'] and not row['snapshot']['overflow']
        assert not any(m.startswith('LOAD_ERROR') for m in traces)
        assert not any(m.endswith(' false') and (m.startswith('PRE_') or '_INFO_MATCH' in m) for m in traces),'Identity/precondition failed'
        assert traces.count('FIRST_CHILD_CONSTRUCTED')==1
        assert traces.index('FIRST_CHILD_CONSTRUCTED')<traces.index('INIT')<traces.index('FIRST_COMPLETE')
        assert row['observationSecondsAfterUnloadReturn']>=5
        assert traces.index('FIRST_COMPLETE')<traces.index('TRANSITION_ENTER_FRAME')<traces.index('UNLOAD_CALL_BEGIN')<traces.index('UNLOAD_CALL_RETURNED')
        assert row['renderer'] in ('webgl','webgl2','experimental-webgl'),('Actual WebGL required',row['renderer'])
        assert not row['errors'] and not row['remoteRequests'] and not row['requestFailures'],row
    control,moved=rows
    ct=control['traceMessages'];mt=moved['traceMessages']
    for msg in ['PRE_ATTACHED_CONTENT_PARENT_LOADER true','UNLOAD_BEGIN','UNLOAD_LISTENER_REMOVED','FRESH_LOADER_CREATED','UNLOAD_END','NEXT_CHILD_CONSTRUCTED','NEXT_COMPLETE']:
        assert ct.count(msg)==1,('Baseline control failed',msg,ct)
    assert ct.count('INIT')==2 and ct.count('INIT_INFO_MATCH true')==2 and ct.count('COMPLETE_INFO_MATCH true')==2
    assert ct.index('NEXT_CHILD_CONSTRUCTED')<ct.index('NEXT_COMPLETE')
    assert ct.index('UNLOAD_CALL_BEGIN')<ct.index('UNLOAD_BEGIN')<ct.index('UNLOAD_END')<ct.index('UNLOAD_CALL_RETURNED')
    for msg in ['PRE_CONTENT_PARENT_HOLDER true','PRE_MOVED_PARENT_NULL true','PRE_HOLDER_EMPTY true']:
        assert mt.count(msg)==1,('Moved-content precondition invalid',msg,mt)
    def swfs(row):return [r['name'] for r in row['responses'] if r['name'].endswith('.swf')]
    def swf_requests(row):return [r['name'] for r in row['requests'] if r['name'].endswith('.swf')]
    assert swfs(control)==swf_requests(control)==['attached-control.swf','first.swf','next.swf'],swfs(control)
    if 'UNLOAD_BEGIN' not in mt:
        assert mt.count('INIT')==1 and mt.count('INIT_INFO_MATCH true')==1 and mt.count('COMPLETE_INFO_MATCH true')==1
        assert all(m not in mt for m in ['UNLOAD_END','UNLOAD_LISTENER_REMOVED','NEXT_BEGIN','REQUEST next.swf','NEXT_LOAD_RETURNED','FRESH_LOADER_CREATED','NEXT_COMPLETE','NEXT_CHILD_CONSTRUCTED'])
        assert swfs(moved)==swf_requests(moved)==['moved-removed.swf','first.swf'],swfs(moved)
        return 'reproduced-unload-omission-after-content-removal'
    assert mt.count('UNLOAD_BEGIN')==1 and mt.count('NEXT_COMPLETE')==1 and mt.count('FRESH_LOADER_CREATED')==1
    assert mt.count('INIT')==2 and mt.count('INIT_INFO_MATCH true')==2 and mt.count('COMPLETE_INFO_MATCH true')==2
    assert mt.count('NEXT_CHILD_CONSTRUCTED')==1 and mt.index('NEXT_CHILD_CONSTRUCTED')<mt.index('NEXT_COMPLETE')
    for msg in ['UNLOAD_LISTENER_REMOVED','UNLOAD_END','NEXT_BEGIN','NEXT_LOAD_RETURNED']:
        assert mt.count(msg)==1,('Incomplete moved-arm continuation',msg,mt)
    assert mt.index('UNLOAD_CALL_BEGIN')<mt.index('UNLOAD_BEGIN')<mt.index('UNLOAD_LISTENER_REMOVED')<mt.index('FRESH_LOADER_CREATED')<mt.index('UNLOAD_END')<mt.index('UNLOAD_CALL_RETURNED')
    assert swfs(moved)==swf_requests(moved)==['moved-removed.swf','first.swf','next.swf']
    return 'unload-omission-not-reproduced'

def main():
    p=argparse.ArgumentParser();p.add_argument('--runtime-root',type=pathlib.Path,required=True);p.add_argument('--output',type=pathlib.Path,required=True);a=p.parse_args()
    lock=json.loads((ROOT/'runtime-lock.json').read_text());expected=lock['runtimeFiles']
    actual={f.relative_to(a.runtime_root).as_posix():sha(f.read_bytes()) for f in a.runtime_root.rglob('*') if f.is_file()}
    assert len(expected)==12 and actual==expected,'Exact accepted runtime inventory required'
    fixtures={'first.swf':make_probe.child('FIRST_CHILD_CONSTRUCTED'),'next.swf':make_probe.child('NEXT_CHILD_CONSTRUCTED')}
    fixtures.update({arm+'.swf':make_probe.root(arm) for arm in ('attached-control','moved-removed')})
    result={'schema':'neutral-loader-unload-v1','validationPassed':False,'applicationPass':False,'runtimeFiles':expected,
        'selectedWasmSHA256':lock['selectedWasmSHA256'],'fixtureFiles':{n:sha(b) for n,b in fixtures.items()},'rows':[],
        'sourceFiles':{f.name:sha(f.read_bytes()) for f in sorted(ROOT.iterdir()) if f.is_file() and f.suffix in ('.py','.html','.json','.yml','.md')},
        'head':os.environ.get('GITHUB_SHA'),'runID':os.environ.get('GITHUB_RUN_ID'),
        'privateGameInputs':False,'engineChanged':False,'flashReferenceRun':False,
        'scope':'Neutral Chrome/WebGL Loader event observation only; not private game/iOS compatibility'}
    with tempfile.TemporaryDirectory() as tmp:
        root=pathlib.Path(tmp);shutil.copytree(a.runtime_root,root/'runtime');(root/'fixtures').mkdir();shutil.copyfile(ROOT/'probe.html',root/'probe.html')
        for n,b in fixtures.items():(root/'fixtures'/n).write_bytes(b)
        class Quiet(http.server.SimpleHTTPRequestHandler):
            def log_message(self,*args):pass
        server=http.server.ThreadingHTTPServer(('127.0.0.1',0),functools.partial(Quiet,directory=str(root)))
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start();origin=f'http://127.0.0.1:{server.server_port}'
        try:
            with sync_playwright() as pw:
                browser=pw.chromium.launch(channel='chrome',headless=True,chromium_sandbox=True,ignore_default_args=UNSAFE)
                try:
                    cdp=browser.new_browser_cdp_session();flags=cdp.send('Browser.getBrowserCommandLine')['arguments'];cdp.detach()
                    assert not any(f.split('=')[0] in FORBIDDEN for f in flags),'Unsafe effective browser flag'
                    result['browser']={'version':browser.version,'sandboxRequested':True,'effectiveCommandLine':flags}
                    for arm in ('attached-control','moved-removed'):
                        row={'arm':arm,'responses':[],'requests':[],'requestFailures':[],'errors':[],'console':[],'remoteRequests':[]};result['rows'].append(row)
                        context=browser.new_context();page=context.new_page()
                        def route(route):
                            if not route.request.url.startswith(origin+'/'):row['remoteRequests'].append(route.request.url);route.abort()
                            else:route.continue_()
                        context.route('**/*',route)
                        page.on('pageerror',lambda e:row['errors'].append(str(e)[:1000]))
                        page.on('request',lambda request:row['requests'].append({'name':request.url.rsplit('/',1)[-1].split('?')[0],'resourceType':request.resource_type}))
                        page.on('requestfailed',lambda request:row['requestFailures'].append({'name':request.url.rsplit('/',1)[-1].split('?')[0],'failure':str(request.failure)[:500]}))
                        def console(msg):
                            if len(row['console'])<80:row['console'].append({'type':msg.type,'text':msg.text[:1000]})
                            if msg.type=='error':row['errors'].append(msg.text[:1000])
                        page.on('console',console)
                        def response(r):
                            name=r.url.rsplit('/',1)[-1]
                            if not name.endswith(('.wasm','.swf')):return
                            b=r.body();record={'name':name,'status':r.status,'bytes':len(b),'sha256':sha(b)}
                            if name.endswith('.swf'):
                                assert len(b)<=8192;record['bodyBase64']=base64.b64encode(b).decode()
                                assert name in fixtures and b==fixtures[name],'Neutral fixture response differs'
                            else:assert name==lock['selectedWasm'] and sha(b)==lock['selectedWasmSHA256'],'Actual selected WASM differs'
                            assert r.status==200,'Resource HTTP failed';row['responses'].append(record)
                        page.on('response',response)
                        try:
                            page.goto(origin+'/probe.html?variant='+arm)
                            page.wait_for_function("evidence.traces.some(t=>t.message==='UNLOAD_CALL_RETURNED') || evidence.error",timeout=30000)
                            assert not page.evaluate('evidence.error')
                            started=time.monotonic();page.wait_for_timeout(5500);row['observationSecondsAfterUnloadReturn']=time.monotonic()-started
                            row['snapshot']=page.evaluate('evidence');row['metadata']=page.evaluate('player.ruffle().metadata');row['renderer']=page.evaluate('actualRenderer()')
                            image=a.output.with_name(a.output.stem+'-'+arm+'.png');image.parent.mkdir(parents=True,exist_ok=True)
                            page.locator('ruffle-player').screenshot(path=str(image));row['screenshot']={'file':image.name,'sha256':sha(image.read_bytes()),'renderedFrameAssertion':False}
                            assert any(r['name']==lock['selectedWasm'] for r in row['responses']),'No actual WASM response'
                        except Exception as error:
                            row['failure']=str(error)[:2000]
                            try:row['snapshot']=page.evaluate('evidence');row['renderer']=page.evaluate('actualRenderer()')
                            except Exception:pass
                            raise
                        finally:context.close()
                    result['mechanismOutcome']=validate(result['rows']);result['validationPassed']=True
                finally:browser.close()
        except Exception as error:result['failure']=str(error)[:2000];raise
        finally:
            server.shutdown();server.server_close();thread.join();a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({'validationPassed':True,'mechanismOutcome':result['mechanismOutcome'],'applicationPass':False}))
if __name__=='__main__':main()

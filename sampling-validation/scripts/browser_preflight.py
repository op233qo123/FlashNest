#!/usr/bin/env python3
"""Bounded setup probe only: never counts as geometry/input validation."""
import hashlib, importlib.metadata, json, os, pathlib, signal
from playwright.sync_api import sync_playwright
from evidence_budget import write_json
ROOT=pathlib.Path(__file__).resolve().parents[1]
report={'passed':False,'classification':'setup-failure','matrixCases':0,'runtimeGate':False,'channel':'chrome','chromiumSandbox':True,'imageVersionEnvironment':os.environ.get('ImageVersion'),'playwright':importlib.metadata.version('playwright')}
def timeout(*_): raise TimeoutError('preflight exceeded 60 seconds')
signal.signal(signal.SIGALRM,timeout);signal.alarm(60)
try:
 assert report['playwright']=='1.64.1'
 report['files']={}
 for name in ['/opt/google/chrome/chrome','/opt/google/chrome/chrome-sandbox','/etc/apparmor.d/chrome']:
  path=pathlib.Path(name);digest=hashlib.sha256()
  with path.open('rb') as f:
   while chunk:=f.read(1024*1024):digest.update(chunk)
  report['files'][name]={'sha256':digest.hexdigest(),'bytes':path.stat().st_size}
 with sync_playwright() as pw:
  browser=pw.chromium.launch(channel='chrome',chromium_sandbox=True,headless=True,timeout=30000,args=['--enable-unsafe-swiftshader'])
  report['browserVersion']=browser.version
  assert browser.version.split('.')[0]=='155','Unreviewed Chrome major; stop for compatibility review'
  context=browser.new_context();context.route('**/*',lambda route:route.abort())
  page=context.new_page();page.set_default_timeout(10000)
  page.set_content('<title>Synthetic setup only</title><canvas width="16" height="16"></canvas>')
  assert page.title()=='Synthetic setup only'
  report['webgl']=page.evaluate("""() => { const c=document.querySelector('canvas');const gl=c.getContext('webgl2')||c.getContext('webgl');return gl ? {width:gl.drawingBufferWidth,height:gl.drawingBufferHeight} : null; }""")
  assert report['webgl']=={'width':16,'height':16},'No usable synthetic WebGL drawing buffer'
  context.close();browser.close()
 report.update(passed=True,classification='setup-passed-not-matrix-validation')
except Exception as exc:
 report['error']=(type(exc).__name__+': '+str(exc))[:12000]
finally:
 signal.alarm(0)
 write_json(ROOT/'evidence/browser-preflight.json',json.dumps(report,indent=2)+'\n')
 print(json.dumps({'passed':report['passed'],'classification':report['classification'],'matrixCases':0}))
raise SystemExit(0 if report['passed'] else 1)

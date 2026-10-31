import json,pathlib
from playwright.sync_api import sync_playwright
out=pathlib.Path('texture-lifetime-evidence');out.mkdir(exist_ok=True)
r={'passed':False,'chromiumSandbox':True,'extraLaunchArguments':[],'scope':'setup only'}
try:
 with sync_playwright() as p:
  b=p.chromium.launch(channel='chrome',headless=True,chromium_sandbox=True)
  r['browserVersion']=b.version;c=b.new_context();page=c.new_page();page.set_content('<canvas width="16" height="16"></canvas>')
  r['webgl']=page.evaluate("() => {let g=document.querySelector('canvas').getContext('webgl2');return g?{width:g.drawingBufferWidth,height:g.drawingBufferHeight}:null}")
  assert r['webgl']=={'width':16,'height':16};c.close();b.close();r['passed']=True
finally:(out/'preflight.json').write_text(json.dumps(r,indent=2)+'\n')

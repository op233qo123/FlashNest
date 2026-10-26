#!/usr/bin/env python3
"""Requires preinstalled Playwright + Chromium. REAL runtime, no mock replacement.
Run serve_fixture.py first. Uses an ephemeral context and loopback fixture only.
"""
from playwright.sync_api import sync_playwright
import json, pathlib
ROOT=pathlib.Path(__file__).resolve().parents[1]
with sync_playwright() as p:
    browser=p.chromium.launch(executable_path='/usr/bin/chromium',headless=True)
    context=browser.new_context()
    page=context.new_page(); requests=[]; messages=[]
    page.on('request',lambda r: requests.append(r.url))
    page.on('console',lambda m: messages.append(m.text))
    page.add_init_script("window.webkit={messageHandlers:{flashnest:{postMessage:m=>{window.__diagnostics=(window.__diagnostics||[]);window.__diagnostics.push(m)}}}}")
    page.goto('http://127.0.0.1:8766/test/web/index.html?package=11111111-1111-4111-8111-111111111111&entry=main.swf')
    page.wait_for_function("(window.__diagnostics||[]).some(x=>x.type==='loaded')",timeout=45000)
    page.get_by_role('button',name='Play / enable audio').click()
    page.wait_for_function("(window.__diagnostics||[]).some(x=>x.message.includes('FLASHNEST_CHILD_OK'))",timeout=15000)
    page.wait_for_timeout(500)
    assert any('/runtime/' in u and u.endswith('.wasm') for u in requests),'No actual WASM loaded'
    assert any(u.endswith('/sub/child.swf') for u in requests),'No child SWF loaded'
    assert any(u.endswith('/sibling.txt') for u in requests),'No sibling text loaded'
    assert all(u.startswith('http://127.0.0.1:8766/') for u in requests),'Unexpected remote request'
    assert page.evaluate("document.querySelector('ruffle-player').ruffle().isPlaying"),'Movie not playing'
    page.get_by_role('button',name='Pause',exact=True).click()
    assert not page.evaluate("document.querySelector('ruffle-player').ruffle().isPlaying"),'Pause failed'
    page.get_by_role('button',name='Resume',exact=True).click()
    assert page.evaluate("document.querySelector('ruffle-player').ruffle().isPlaying"),'Resume failed'
    print(json.dumps({'result':'PASS','requests':requests,'diagnostics':page.evaluate('window.__diagnostics')},indent=2))
    page.screenshot(path=str(ROOT/'fixtures/runtime-test.png'))
    context.close(); browser.close()

#!/usr/bin/env python3
"""Actual pinned Ruffle SharedObject/browser smoke test, not mocked WASM.
Uses only a temporary loopback server and original repository SWF fixtures.
Chromium is not iOS WebKit; SharedObjectWebKitTests is the native acceptance gate.
"""
import base64
import json
import pathlib
import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import unquote, urlsplit
from playwright.sync_api import sync_playwright

ROOT = pathlib.Path(__file__).resolve().parents[1]
ID = '11111111-1111-4111-8111-111111111111'
OTHER_ID = '22222222-2222-4222-8222-222222222222'
CAP = 'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa'
OTHER_CAP = 'bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb'

class Handler(SimpleHTTPRequestHandler):
    def translate_path(self, request_path):
        parts = unquote(urlsplit(request_path).path).split('/')
        if len(parts) >= 4 and parts[2] == 'web':
            root, rest = ROOT / 'App/Resources/Web', parts[3:]
        elif len(parts) >= 5 and parts[2] == 'games':
            root, rest = ROOT / 'fixtures/shared-object', parts[4:]
        else:
            return '/nonexistent'
        target = root.joinpath(*rest).resolve()
        return str(target) if target.is_relative_to(root.resolve()) else '/nonexistent'
    def end_headers(self):
        self.send_header('X-Content-Type-Options', 'nosniff')
        super().end_headers()
    def log_message(self, *_):
        pass

def run():
    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f'http://127.0.0.1:{server.server_port}'
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(executable_path='/usr/bin/chromium', headless=True)
            contexts = []
            def page_for(movie, token=CAP, package=ID, restore=None, storage_only=False):
                context = browser.new_context(viewport={'width':390,'height':844}, is_mobile=True, has_touch=True)
                contexts.append(context)
                page = context.new_page()
                requests = []
                page.on('request', lambda request: requests.append(request.url))
                setup = "window.webkit={messageHandlers:{flashnest:{postMessage:m=>{(window.__messages ||= []).push(m)}}}}; localStorage.setItem('unrelated','keep');"
                if restore is not None:
                    setup += 'window.__FlashNestRestore=' + json.dumps(restore) + ';'
                page.add_init_script(setup)
                url = f'{base}/{token}/web/index.html?package={package}&entry={movie}'
                if storage_only:
                    url += '&storageOnly=1'
                page.goto(url)
                page.wait_for_function("(window.__messages||[]).some(m=>m.type==='saveReady')", timeout=45000)
                if not storage_only:
                    page.wait_for_function("(window.__messages||[]).some(m=>m.type==='loaded')", timeout=45000)
                    assert page.locator('#toolbar').count() == 0
                    assert page.locator('#controls').count() == 0
                    assert page.evaluate("document.getElementById('stage').getBoundingClientRect().height === innerHeight")
                    page.locator('#start').click()
                    page.wait_for_function("(window.__messages||[]).some(m=>m.message==='SWF: FLASHNEST_SAVE_READY')", timeout=15000)
                    assert page.locator('#start').is_hidden()
                assert all(request.startswith(base + '/') for request in requests), 'Unexpected remote resource request'
                return page, requests

            writer, _ = page_for('close-flush.swf')
            assert writer.evaluate("window.__messages.some(m=>m.message==='SWF: FLASHNEST_SAVE_BEFORE:undefined')")
            writer.evaluate('window.FlashNest.pause()')
            assert writer.evaluate("Object.keys(localStorage).filter(k=>k.startsWith('127.0.0.1/')).length") == 0, 'Suspend is not flush'
            capture = writer.evaluate('window.FlashNest.shutdownAndCapture()')
            assert len(capture['entries']) == 1
            saved = capture['entries'][0]
            assert saved['scope'] == 'origin' and saved['key'] == 'FlashNestFixture'
            data = base64.b64decode(saved['value'], validate=True)
            assert data[:2] == b'\x00\xbf' and data[6:10] == b'TCSO'
            assert writer.evaluate('window.FlashNest.shutdownAndCapture()') == capture
            assert writer.evaluate("localStorage.getItem('unrelated')") == 'keep'
            assert all(value not in json.dumps(capture) for value in (CAP, ID, '127.0.0.1'))
            writer.screenshot(path='/tmp/flashnest-fullscreen-shell.png')

            reader, _ = page_for('read-only.swf', OTHER_CAP, OTHER_ID, capture)
            assert reader.evaluate("window.__messages.some(m=>m.message==='SWF: FLASHNEST_SAVE_BEFORE:42')")
            assert reader.evaluate('window.FlashNest.shutdownAndCapture()')['entries'] == capture['entries']
            isolated, _ = page_for('read-only.swf')
            assert isolated.evaluate("window.__messages.some(m=>m.message==='SWF: FLASHNEST_SAVE_BEFORE:undefined')")
            isolated.evaluate('window.FlashNest.shutdownAndCapture()')
            explicit, _ = page_for('explicit-flush.swf')
            before = explicit.evaluate("Object.keys(localStorage).filter(k=>k.startsWith('127.0.0.1/')).map(k=>localStorage.getItem(k))")
            assert len(before) == 1
            assert explicit.evaluate('window.FlashNest.shutdownAndCapture()')['entries'][0]['value'] == before[0]
            storage_page, requests = page_for('read-only.swf', OTHER_CAP, OTHER_ID, capture, storage_only=True)
            assert not any('/runtime/' in request for request in requests), 'Storage-only mode must not execute a movie'
            assert storage_page.evaluate('window.FlashNest.shutdownAndCapture()') == capture
            for context in contexts:
                context.close()
            browser.close()
            print('PASS actual Ruffle: destroy flush, restore42 before movie, profile isolation, explicit flush bytes, storage-only mode, full-screen/no duplicate controls (Chromium; not iOS)')
    finally:
        server.shutdown()
        server.server_close()

if __name__ == '__main__':
    run()

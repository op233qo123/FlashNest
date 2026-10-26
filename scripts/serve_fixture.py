#!/usr/bin/env python3
"""Loopback-only development server; no production import server replacement."""
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from urllib.parse import urlsplit, unquote
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
ID='11111111-1111-4111-8111-111111111111'
class Handler(SimpleHTTPRequestHandler):
    def translate_path(self,path):
        path=unquote(urlsplit(path).path)
        if path.startswith('/test/web/'): base=ROOT/'App/Resources/Web'; rel=path[len('/test/web/'):]
        elif path.startswith('/test/games/'+ID+'/'): base=ROOT/'fixtures/multi-swf'; rel=path[len('/test/games/'+ID+'/'):]
        else: return '/nonexistent'
        result=(base/rel).resolve()
        return str(result) if result.is_relative_to(base.resolve()) else '/nonexistent'
    def end_headers(self):
        self.send_header('X-Content-Type-Options','nosniff'); super().end_headers()
print('http://127.0.0.1:8766/test/web/index.html?package='+ID+'&entry=main.swf',flush=True)
ThreadingHTTPServer(('127.0.0.1',8766),Handler).serve_forever()

"""Exact diagnostic-shell breadcrumbs; only applied in isolated staged host."""
import hashlib,difflib
from pathlib import Path
EXPECTED='5d37c3b3cafe20f788ae664c81b721400c10e0ca99f978efc890c5357575bd90'
ANCHORS={
 "    player.addEventListener('loadeddata', () => {\n":"loadeddata",
 "    await player.ruffle().load({url:url.href, base:new URL('./',url).href, publicPath:runtime.href,\n":"shell-load-call",
 "    } finally { window.clearTimeout?.(loadWatchdog); }\n":"shell-load-return"}
def transform(source):
 if hashlib.sha256(source).hexdigest()!=EXPECTED:raise ValueError('Exact production shell pin drift')
 text=source.decode();patched=text
 for anchor,phase in ANCHORS.items():
  if text.count(anchor)!=1:raise ValueError('Startup shell anchor drift')
  line="      try { window.FlashNestStartupJournal?.record('"+phase+"'); } catch (_) {}\n"
  patched=patched.replace(anchor,anchor+line if phase=='loadeddata' else line+anchor)
 return patched.encode(),''.join(difflib.unified_diff(text.splitlines(True),patched.splitlines(True),fromfile='shipping/shell.js',tofile='diagnostic/shell.js'))

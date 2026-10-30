"""Bounded synthetic evidence; exceeding a cap FAILS the test, never skips coverage."""
from pathlib import Path
MAX_ARTIFACT=128*1024*1024
MAX_PNG_TOTAL=80*1024*1024
MAX_JSON_FILE=16*1024*1024
MAX_LOG_FILE=2*1024*1024

def write_png(path,data):
    root=Path(__file__).resolve().parents[1]/'evidence'
    used=sum(p.stat().st_size for p in root.rglob('*.png') if p!=path)
    assert used+len(data)<=MAX_PNG_TOTAL, 'PNG evidence budget exceeded; test incomplete, not passed'
    path.write_bytes(data)

def write_json(path,data):
    encoded=data.encode()
    assert len(encoded)<=MAX_JSON_FILE, 'JSON evidence budget exceeded; test incomplete, not passed'
    path.write_bytes(encoded)

if __name__=='__main__':
    import sys,os
    if len(sys.argv)>1 and sys.argv[1]=='log':
        # Keep bounded prefix, then continue draining to avoid blocking the test.
        path=Path(sys.argv[2]);used=0;truncated=False
        with path.open('wb') as f:
            while chunk:=sys.stdin.buffer.read(65536):
                keep=chunk[:max(0,MAX_LOG_FILE-256-used)]
                if keep:f.write(keep);used+=len(keep)
                if len(keep)<len(chunk):truncated=True
            if truncated:f.write(b'\n[diagnostic log capped at 2 MiB; JSON/PNG test gates unchanged]\n')
        print(f'Bounded log retained: {path.name}; truncated={truncated}')
    else:
        root=Path(__file__).resolve().parents[1]/'evidence'
        size=sum(p.stat().st_size for p in root.rglob('*') if p.is_file())
        allowed=size<=MAX_ARTIFACT
        if output:=os.environ.get('GITHUB_OUTPUT'):
            with open(output,'a') as f:f.write('allowed='+str(allowed).lower()+'\n')
        print(f'Evidence bytes: {size}; maximum: {MAX_ARTIFACT}; allowed: {allowed}')
        assert allowed,'Artifact exceeds 128 MiB: do not upload'

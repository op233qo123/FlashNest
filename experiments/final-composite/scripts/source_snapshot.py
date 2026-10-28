"""Hash the entire tracked source plus declared new sources, excluding only seal."""
from pathlib import Path
import hashlib, subprocess
GENERATED_SEAL='web/version_seal.json'
def snapshot(source, expected_modified):
    source=Path(source)
    def git(*args):return subprocess.check_output(['git','-C',str(source),*args]).decode().splitlines()
    changed=set(git('diff','--name-only'))|set(git('ls-files','--others','--exclude-standard'))
    changed.discard(GENERATED_SEAL)
    if changed!=set(expected_modified):raise ValueError('Unexpected changed/untracked source paths: '+repr(changed ^ set(expected_modified)))
    paths=set(git('ls-files'))|set(expected_modified)
    paths.discard(GENERATED_SEAL)
    result={}
    for name in sorted(paths):
        f=source/name
        if f.is_symlink() or not f.is_file():raise ValueError('Missing/linked source: '+name)
        result[name]={'sha256':hashlib.sha256(f.read_bytes()).hexdigest(),'bytes':f.stat().st_size}
    return result

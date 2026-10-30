#!/usr/bin/env python3
"""Package-only byte/safety validators; never native acceptance."""
import hashlib,json,stat,struct,re,sys
from pathlib import Path,PurePosixPath
SHA=re.compile(r"^[0-9a-f]{64}$")
g=sys.modules[__name__]

def require(value, reason):
    if not value: raise ValueError(reason)

def digest(data): return hashlib.sha256(data).hexdigest()

def parse(data):
    def unique(pairs):
        out = {}
        for key, value in pairs:
            require(key not in out, 'Duplicate JSON key')
            out[key] = value
        return out
    return json.loads(data, object_pairs_hook=unique)

def load(path): return parse(Path(path).read_bytes())

def safe(name):
    require(isinstance(name, str) and name and '\\' not in name and ':' not in name, 'Unsafe path')
    p = PurePosixPath(name)
    require(not p.is_absolute() and '..' not in p.parts and p.as_posix() == name and not any(ord(c) < 32 for c in name), 'Unsafe path')
    return p

def file_map(root):
    root = Path(root)
    require(root.is_dir() and not root.is_symlink(), 'Regular source directory required')
    rows = {}
    for p in sorted(root.rglob('*')):
        require(not p.is_symlink(), 'Linked source forbidden')
        if p.is_file(): rows[p.relative_to(root).as_posix()] = digest(p.read_bytes())
        else: require(p.is_dir(), 'Nonregular source')
    return rows

def hash_map(rows):
    require(isinstance(rows, dict) and rows, 'Empty file inventory')
    for path, value in rows.items():
        safe(path); require(isinstance(value, str) and SHA.fullmatch(value), 'Invalid source digest')

def version(number): return f'{number >> 16}.{(number >> 8) & 255}' + (f'.{number & 255}' if number & 255 else '')

def device_macho(data, minimum='17.0', sdk='18.2'):
    g.require(len(data) >= 32,'Short Mach-O')
    magic,cpu,subtype,kind,count,size,flags,reserved = struct.unpack_from('<8I',data)
    g.require((magic,cpu,subtype,kind) == (0xfeedfacf,0x100000c,0,2),'Expected unsigned thin arm64 executable')
    g.require(0 < count <= 4096 and count*8 <= size <= len(data)-32,'Invalid command table')
    position=32; builds=[]
    for _ in range(count):
        g.require(position+8 <= 32+size,'Truncated command')
        command,length = struct.unpack_from('<II',data,position)
        g.require(length >= 8 and length % 8 == 0 and position+length <= 32+size,'Malformed load command')
        g.require(command != 0x1d,'Code signature forbidden')
        if command == 0x32:
            g.require(length >= 24,'Truncated build version')
            platform,low,high,tools = struct.unpack_from('<4I',data,position+8)
            g.require(length == 24+8*tools,'Malformed build version tools')
            builds.append((platform,version(low),version(high)))
        position += length
    g.require(position == 32+size and builds == [(2,minimum,sdk)],'Not exact iPhoneOS SDK/minimum')
    return {'architecture':'arm64','platform':'iPhoneOS','minimumOS':minimum,'sdk':sdk,'sha256':g.digest(data),'unsigned':True}

def safe_ipa_members(items):
    g.require(len(items)<10000 and sum(i.file_size for i in items)<300*1024*1024,'Oversized IPA')
    seen=set(); folded=set()
    for i in items:
        name=i.filename.rstrip('/') if i.is_dir() else i.filename; p=g.safe(name)
        g.require(name not in seen and name.casefold() not in folded,'Duplicate/case collision in IPA')
        seen.add(name);folded.add(name.casefold())
        g.require((p.parts[:2]==('Payload','FlashNest.app')) or (name=='Payload' and i.is_dir()),'Unexpected IPA root')
        g.require(stat.S_IFMT(i.external_attr>>16) in (0,stat.S_IFDIR,stat.S_IFREG),'Nonregular IPA entry')
        g.require(not any(part.lower() in {'experiments','fixtures','source-correspondence','_codesignature','nativesamplingvalidation','lateaudiodiagnostic','tests','uitests'} or part.lower().endswith(('.xctest','.appex')) for part in p.parts),'Test/signature/source payload forbidden')
        g.require(p.suffix.lower() not in {'.swf','.sol','.flashnestsave','.mobileprovision','.ips','.tracev3','.xcresult'},'Private/test payload extension forbidden')

def verify_outer_payload(app):
    # Exact known outputs from the frozen target's resource declarations. A new
    # legitimate compiler/dependency output requires review, never a wildcard.
    allowed = {'FlashNest','Info.plist','PkgInfo','Assets.car',
      'AppIcon60x60@2x.png','AppIcon60x60@3x.png','AppIcon76x76@2x~ipad.png',
      'en.lproj/Localizable.strings','zh-Hans.lproj/Localizable.strings',
      'ZIPFoundation_ZIPFoundation.bundle/Info.plist',
      'ZIPFoundation_ZIPFoundation.bundle/PrivacyInfo.xcprivacy'}
    actual = {p for p in g.file_map(app) if not p.startswith('Web/')}
    g.require(actual <= allowed, 'Unexpected outer App payload: '+repr(sorted(actual-allowed)))
    g.require({'FlashNest','Info.plist','Assets.car','en.lproj/Localizable.strings','zh-Hans.lproj/Localizable.strings'} <= actual, 'Required outer resources absent')
    return actual

def verify_sources(root, expected):
    for p,h in expected.items():
        f=root/p;g.require(f.is_file() and not f.is_symlink() and g.digest(f.read_bytes())==h,'Frozen source changed during build: '+p)
    expected_app={p[4:] for p in expected if p.startswith('App/')}
    actual_app=set(g.file_map(root/'App'))
    g.require(actual_app == expected_app|{'Info.plist'},'Unexpected executable App source/resource added')

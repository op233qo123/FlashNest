import ctypes as C,json,pathlib,hashlib
r=pathlib.Path(__file__).parent;lib=C.CDLL(str((r/'harness/target/release/libimage_decode_probe.so').resolve()))
lib.decode.argtypes=[C.c_uint,C.c_void_p,C.c_size_t,C.c_void_p,C.c_size_t,C.c_uint];lib.output_ptr.restype=C.c_void_p;lib.output_len.restype=C.c_size_t;lib.metric.restype=C.c_size_t
rows=[]
for case in json.loads((r/'fixtures/manifest.json').read_text()):
 j=C.create_string_buffer((r/'fixtures'/case['jpeg']).read_bytes());alpha=(r/'fixtures'/case['alpha']).read_bytes() if case['alpha'] else b'';a=C.create_string_buffer(alpha);out=[]
 for which in [0,1]:
  status=lib.decode(which,j,len(j)-1,a,len(alpha),int(case['alpha'] is not None));data=C.string_at(lib.output_ptr(),lib.output_len());info=[lib.output_info(k) for k in range(3)];metrics=[lib.metric(k) for k in range(5)];lib.output_drop();live=lib.metric(0);assert metrics[4]==0 and lib.metric(4)==0;out.append((status,data,info));rows.append({'case':case['name'],'variant':which,'status':status,'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest(),'info':info,'metrics':metrics,'live_after_drop':live})
 assert out[0]==out[1],case
(r/'host-results.json').write_text(json.dumps(rows,indent=2));print('PASS',len(rows)//2,'full byte/error pairs')

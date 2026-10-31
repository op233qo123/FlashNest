use std::alloc::{GlobalAlloc, Layout, System};
use std::sync::atomic::{AtomicBool,AtomicUsize,Ordering::Relaxed};
use ruffle_render::bitmap::Bitmap;
static ON:AtomicBool=AtomicBool::new(false);
static LIVE:AtomicUsize=AtomicUsize::new(0);
static PEAK:AtomicUsize=AtomicUsize::new(0);
static OVERLAP:AtomicUsize=AtomicUsize::new(0);
static MOVES:AtomicUsize=AtomicUsize::new(0);
static UNDERFLOW:AtomicUsize=AtomicUsize::new(0);
struct Track;
fn sub(n:usize){let _=LIVE.fetch_update(Relaxed,Relaxed,|v|{if v<n {UNDERFLOW.fetch_add(1,Relaxed);Some(0)} else {Some(v-n)}});}
fn add(n:usize){let live=LIVE.fetch_add(n,Relaxed)+n;PEAK.fetch_max(live,Relaxed);OVERLAP.fetch_max(live,Relaxed);}
unsafe impl GlobalAlloc for Track {
 unsafe fn alloc(&self,l:Layout)->*mut u8{let p=unsafe{System.alloc(l)};if !p.is_null()&&ON.load(Relaxed){add(l.size())}p}
 unsafe fn dealloc(&self,p:*mut u8,l:Layout){if ON.load(Relaxed){sub(l.size());}unsafe{System.dealloc(p,l)}}
 unsafe fn realloc(&self,p:*mut u8,l:Layout,n:usize)->*mut u8{let q=unsafe{System.realloc(p,l,n)};if !q.is_null()&&ON.load(Relaxed){if p!=q{MOVES.fetch_add(1,Relaxed);OVERLAP.fetch_max(LIVE.load(Relaxed)+n,Relaxed);}sub(l.size());add(n);}q}
}
#[global_allocator]static ALLOC:Track=Track;
static mut OUTPUT:Option<Bitmap<'static>>=None;
static mut ERROR:Option<String>=None;
#[unsafe(no_mangle)]pub extern "C" fn input_alloc(n:usize)->*mut u8{Box::into_raw(vec![0;n].into_boxed_slice()) as *mut u8}
#[unsafe(no_mangle)]pub unsafe extern "C" fn input_free(p:*mut u8,n:usize){unsafe{drop(Box::from_raw(std::ptr::slice_from_raw_parts_mut(p,n)))}}
#[unsafe(no_mangle)]pub unsafe extern "C" fn decode(which:u32,j:*const u8,jn:usize,a:*const u8,an:usize,has_alpha:u32)->u32{
 LIVE.store(0,Relaxed);PEAK.store(0,Relaxed);OVERLAP.store(0,Relaxed);MOVES.store(0,Relaxed);UNDERFLOW.store(0,Relaxed);ON.store(true,Relaxed);
 let jpeg=unsafe{std::slice::from_raw_parts(j,jn)};let alpha=if has_alpha==0{None}else{Some(unsafe{std::slice::from_raw_parts(a,an)})};
 let result=if which==0{ruffle_render::baseline_utils::decode_define_bits_jpeg(jpeg,alpha)}else{ruffle_render::utils::decode_define_bits_jpeg(jpeg,alpha)};
 match result{Ok(b)=>{unsafe{OUTPUT=Some(b)};0},Err(e)=>{unsafe{ERROR=Some(format!("{e:?}"))};1}}
}
#[unsafe(no_mangle)]pub unsafe extern "C" fn output_ptr()->*const u8 {unsafe{if let Some(b)=(&*std::ptr::addr_of!(OUTPUT)).as_ref(){b.data().as_ptr()}else{(&*std::ptr::addr_of!(ERROR)).as_ref().map_or(std::ptr::null(),|e|e.as_ptr())}}}
#[unsafe(no_mangle)]pub unsafe extern "C" fn output_len()->usize {unsafe{if let Some(b)=(&*std::ptr::addr_of!(OUTPUT)).as_ref(){b.data().len()}else{(&*std::ptr::addr_of!(ERROR)).as_ref().map_or(0,|e|e.len())}}}
#[unsafe(no_mangle)]pub unsafe extern "C" fn output_info(k:u32)->u32{unsafe{(&*std::ptr::addr_of!(OUTPUT)).as_ref().map_or(0,|b|match k{0=>b.width(),1=>b.height(),_=>b.format().bytes_per_pixel().map_or(0,|n|n.get() as u32)})}}
#[unsafe(no_mangle)]pub unsafe extern "C" fn output_drop(){unsafe{OUTPUT=None;ERROR=None};ON.store(false,Relaxed);}
#[unsafe(no_mangle)]pub extern "C" fn metric(k:u32)->usize{match k{0=>LIVE.load(Relaxed),1=>PEAK.load(Relaxed),2=>OVERLAP.load(Relaxed),3=>MOVES.load(Relaxed),_=>UNDERFLOW.load(Relaxed)}}

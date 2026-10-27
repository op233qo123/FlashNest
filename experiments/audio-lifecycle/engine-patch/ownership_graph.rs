//! Standalone ownership-pattern tests, not WebAudio or Ruffle runtime tests.
//! Proposed invocation after approval: rustc --test ownership_graph.rs && ./ownership_graph
//! Not compiled or executed in this source-only preparation.
use std::cell::{Cell, RefCell};
use std::rc::Rc;

struct BufferModel {
    callback: Option<Box<dyn FnMut()>>,
    drops: Rc<Cell<usize>>,
}
impl Drop for BufferModel {
    fn drop(&mut self) { self.drops.set(self.drops.get() + 1); }
}

#[test]
fn strong_self_capture_retains_buffer_after_owner_drop() {
    let drops = Rc::new(Cell::new(0));
    let buffer = Rc::new(RefCell::new(BufferModel { callback: None, drops: drops.clone() }));
    let captured = buffer.clone();
    buffer.borrow_mut().callback = Some(Box::new(move || { let _ = captured.borrow().drops.get(); }));
    let weak = Rc::downgrade(&buffer);
    assert_eq!(Rc::strong_count(&buffer), 2);
    drop(buffer);
    assert_eq!(drops.get(), 0);
    let retained = weak.upgrade().expect("Strong self-capture retains the buffer");
    // Break the intentionally-created test cycle so the test does not leak.
    retained.borrow_mut().callback = None;
    drop(retained);
    assert!(weak.upgrade().is_none());
    assert_eq!(drops.get(), 1);
}

#[test]
fn weak_self_capture_allows_owner_drop() {
    let drops = Rc::new(Cell::new(0));
    let buffer = Rc::new(RefCell::new(BufferModel { callback: None, drops: drops.clone() }));
    let captured = Rc::downgrade(&buffer);
    buffer.borrow_mut().callback = Some(Box::new(move || {
        if let Some(buffer) = captured.upgrade() { let _ = buffer.borrow().drops.get(); }
    }));
    let weak = Rc::downgrade(&buffer);
    assert_eq!(Rc::strong_count(&buffer), 1);
    drop(buffer);
    assert!(weak.upgrade().is_none());
    assert_eq!(drops.get(), 1);
}

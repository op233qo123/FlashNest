//! Isolated tests for original SWFs, not Adobe-reference goldens.
//! Staged only into a disposable checkout of the exact pinned Ruffle source.

use ruffle_core::backend::log::LogBackend;
use ruffle_core::limits::ExecutionLimit;
use ruffle_core::tag_utils::SwfMovie;
use ruffle_core::PlayerBuilder;
use std::cell::RefCell;
use std::path::PathBuf;
use std::rc::Rc;
use std::time::{Duration, Instant};

#[derive(Clone, Default)]
struct TraceLog(Rc<RefCell<String>>);

impl LogBackend for TraceLog {
    fn avm_trace(&self, message: &str) {
        let mut trace = self.0.borrow_mut();
        trace.push_str(message);
        trace.push('\n');
    }

    fn avm_warning(&self, message: &str) {
        self.avm_trace(&format!("AVM_WARNING: {message}"));
    }
}

const CONTROL: &[u8] =
    include_bytes!("../flashnest-frame-order-fixtures/control-no-child-goto.swf");
const NESTED: &[u8] =
    include_bytes!("../flashnest-frame-order-fixtures/nested-child-goto.swf");
const CONTROL_TRACE: &str =
    include_str!("../flashnest-frame-order-fixtures/control.txt");
const NESTED_BASELINE: &str =
    include_str!("../flashnest-frame-order-fixtures/nested-baseline.txt");
// This is an experimental repair target, NOT an observed Adobe output.
const NESTED_REPAIR_TARGET: &str =
    include_str!("../flashnest-frame-order-fixtures/nested-repair-target.txt");

fn capture(variant: &str, swf: &[u8]) -> String {
    let log = TraceLog::default();
    let movie = SwfMovie::from_data(
        swf,
        format!("file:///original-frame-order/{variant}.swf"),
        None,
        None,
    )
    .expect("parse original SWF");
    let player = PlayerBuilder::new()
        .with_movie(movie)
        .with_log(log.clone())
        .with_autoplay(true)
        .with_max_execution_duration(Duration::from_secs(2))
        .build();

    let deadline = Instant::now() + Duration::from_secs(5);
    let mut preloaded = false;
    for _ in 0..20 {
        let mut limit = ExecutionLimit::with_max_ops_and_time(10_000, Duration::from_millis(100));
        preloaded = player.lock().unwrap().preload(&mut limit);
        if preloaded || Instant::now() >= deadline {
            break;
        }
    }

    let mut trace = log.0.take();
    if preloaded {
        for _ in 0..20 {
            player.lock().unwrap().run_frame();
            trace.push_str(&log.0.take());
            // Finish this complete engine frame. A child script already queued
            // for tick 12 can run after FO_DONE and restart its opening loop.
            if trace.lines().any(|line| line.starts_with("FO_DONE "))
                || Instant::now() >= deadline
            {
                break;
            }
        }
    }

    let output = PathBuf::from(
        std::env::var_os("FRAME_ORDER_TRACE_DIR").expect("FRAME_ORDER_TRACE_DIR is required"),
    );
    std::fs::create_dir_all(&output).expect("create isolated trace directory");
    std::fs::write(output.join(format!("{variant}.trace.txt")), &trace)
        .expect("retain raw trace before assertions");
    println!("FRAME_ORDER_RUST_BEGIN {variant}\n{trace}FRAME_ORDER_RUST_END {variant}");

    assert!(preloaded, "original fixture preload did not complete");
    assert!(trace.len() <= 32_768, "unexpected trace growth");
    let ticks: Vec<u32> = trace
        .lines()
        .filter_map(|line| line.strip_prefix("FO_STATE "))
        .map(|line| line.split_whitespace().next().unwrap().parse().unwrap())
        .collect();
    assert_eq!(ticks, (1..=12).collect::<Vec<_>>(), "incomplete observation");
    assert_eq!(
        trace.lines().filter(|line| line.starts_with("FO_DONE 12 ")).count(),
        1,
        "missing or repeated observation boundary"
    );
    trace
}

fn phase() -> String {
    let phase = std::env::var("FRAME_ORDER_ENGINE_PHASE")
        .expect("FRAME_ORDER_ENGINE_PHASE must be baseline or patched");
    assert!(phase == "baseline" || phase == "patched", "invalid engine phase");
    phase
}

#[test]
fn control_is_unchanged() {
    let _ = phase();
    let trace = capture("control-no-child-goto", CONTROL);
    assert_eq!(trace, CONTROL_TRACE, "control differs from recorded pinned trace");
}

#[test]
fn nested_goto_obeys_selected_experimental_contract() {
    let phase = phase();
    let trace = capture("nested-child-goto", NESTED);
    let expected = if phase == "baseline" {
        NESTED_BASELINE
    } else {
        NESTED_REPAIR_TARGET
    };
    assert_eq!(
        trace, expected,
        "original fixture differs from the explicitly labeled {phase} expectation"
    );
}

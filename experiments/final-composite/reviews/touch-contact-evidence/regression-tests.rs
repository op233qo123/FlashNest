//! Targeted touch boundary regression: no synthetic mouse-move events.
use crate::backend::log::LogBackend;
use crate::{PlayerBuilder, PlayerEvent, events::MouseButton, tag_utils::SwfMovie};
use std::{cell::RefCell, rc::Rc};
#[derive(Clone, Default)]
struct Trace(Rc<RefCell<Vec<String>>>);
impl LogBackend for Trace {
    fn avm_trace(&self, message: &str) {
        self.0.borrow_mut().push(message.into());
    }
    fn avm_warning(&self, _message: &str) {}
}
fn run(touch: bool, points: &[(f64, f64, bool)], change_stage: bool) -> Vec<String> {
    let bytes: &[u8] = if change_stage {
        include_bytes!("touch_input_tests/touch-change-stage.swf")
    } else {
        include_bytes!("touch_input_tests/touch.swf")
    };
    let movie = SwfMovie::from_data(bytes, "file:///touch.swf".into(), None, None).unwrap();
    let log = Trace::default();
    let player = PlayerBuilder::new()
        .with_movie(movie)
        .with_log(log.clone())
        .with_viewport_dimensions(
            if change_stage { 800 } else { 640 },
            if change_stage { 600 } else { 480 },
            2.0,
        )
        .with_autoplay(true)
        .build();
    let mut player = player.lock().unwrap();
    player.run_frame();
    for &(x, y, down) in points {
        if down {
            if touch {
                player.handle_touch_start(x, y, MouseButton::Left, None);
            } else {
                player.handle_event(PlayerEvent::MouseDown {
                    x,
                    y,
                    button: MouseButton::Left,
                    index: None,
                });
            }
        } else if touch {
            player.handle_touch_end(x, y, MouseButton::Left);
        } else {
            player.handle_event(PlayerEvent::MouseUp {
                x,
                y,
                button: MouseButton::Left,
            });
        }
    }
    let result = log.0.borrow().clone();
    result
}
#[test]
fn touch_first_and_consecutive_down_current_without_move() {
    let result = run(
        true,
        &[
            (80., 40., true),
            (80., 40., false),
            (220., 180., true),
            (220., 180., false),
        ],
        false,
    );
    println!("{result:#?}");
    let downs: Vec<_> = result
        .iter()
        .filter(|s| s.starts_with("DENSITY|DOWN|"))
        .collect();
    assert_eq!(downs.len(), 2);
    assert!(downs[0].starts_with("DENSITY|DOWN|40|20|false|"));
    assert!(downs[1].starts_with("DENSITY|DOWN|110|90|true|"));
    assert_eq!(
        result
            .iter()
            .filter(|s| s.starts_with("DENSITY|PRESS|"))
            .count(),
        1
    );
    assert_eq!(
        result
            .iter()
            .filter(|s| s.starts_with("DENSITY|RELEASE|"))
            .count(),
        1
    );
    assert!(!result.iter().any(|s| s.starts_with("DENSITY|MOVE|")));
}
#[test]
fn touch_ordinary_mouse_known_negative_still_unchanged() {
    let result = run(
        false,
        &[
            (80., 40., true),
            (80., 40., false),
            (220., 180., true),
            (220., 180., false),
        ],
        false,
    );
    println!("{result:#?}");
    let downs: Vec<_> = result
        .iter()
        .filter(|s| s.starts_with("DENSITY|DOWN|"))
        .collect();
    assert!(downs[0].starts_with("DENSITY|DOWN|0|0|false|"));
    assert!(downs[1].starts_with("DENSITY|DOWN|40|20|false|"));
}
#[test]
fn touch_release_without_last_move_finalizes_current_endpoint() {
    let result = run(true, &[(220., 180., true), (260., 220., false)], false);
    println!("{result:#?}");
    assert_eq!(
        result.iter().map(String::as_str).collect::<Vec<_>>(),
        vec![
            "DENSITY|READY|320|240|showAll|",
            "DENSITY|DOWN|110|90|true|320|240|showAll|",
            "DENSITY|PRESS|110|90",
            "DENSITY|UP|130|110|120|90|320|240|showAll|",
            "DENSITY|RELEASE|130|110",
        ]
    );
}
#[test]
fn touch_stage_change_during_down_observation() {
    let result = run(true, &[(275., 225., true), (275., 225., false)], true);
    println!("{result:#?}");
    assert!(
        result
            .iter()
            .any(|s| s.starts_with("DENSITY|DOWN|110|90|true|"))
    );
    assert!(result.iter().any(|s| s == "DENSITY|PRESS|97.5|82.5"));
    assert!(
        result
            .iter()
            .any(|s| s.starts_with("DENSITY|UP|97.5|82.5|87.5|62.5|"))
    );
}

#[test]
fn touch_up_stop_then_start_new_drag_preserves_endpoint_and_next_delta() {
    let movie = SwfMovie::from_data(
        include_bytes!("touch_input_tests/touch-restart.swf"),
        "file:///restart.swf".into(),
        None,
        None,
    )
    .unwrap();
    let log = Trace::default();
    let player = PlayerBuilder::new()
        .with_movie(movie)
        .with_log(log.clone())
        .with_viewport_dimensions(640, 480, 2.0)
        .with_autoplay(true)
        .build();
    let mut player = player.lock().unwrap();
    player.run_frame();
    player.handle_touch_start(220., 180., MouseButton::Left, None);
    player.handle_touch_end(260., 220., MouseButton::Left);
    player.handle_event(PlayerEvent::MouseMove { x: 300., y: 260. });
    player.handle_touch_start(300., 260., MouseButton::Left, None);
    player.handle_touch_end(300., 260., MouseButton::Left);
    let result = log.0.borrow();
    println!("{result:#?}");
    assert!(
        result
            .iter()
            .any(|s| s.starts_with("DENSITY|UP|130|110|120|90|"))
    );
    assert_eq!(
        result
            .iter()
            .filter(|s| s.starts_with("DENSITY|SECOND|"))
            .map(String::as_str)
            .collect::<Vec<_>>(),
        vec!["DENSITY|SECOND|20|30", "DENSITY|SECOND|40|50"]
    );
    for (label, count) in [
        ("DOWN", 2),
        ("UP", 2),
        ("PRESS", 2),
        ("RELEASE", 2),
        ("MOVE", 1),
    ] {
        assert_eq!(
            result
                .iter()
                .filter(|s| s.starts_with(&format!("DENSITY|{label}|")))
                .count(),
            count,
            "{label}"
        );
    }
}

#[test]
fn touch_duplicate_unmatched_boundaries_preserve_existing_dispatch_counts() {
    // Existing input processing does not filter duplicate mouse boundaries.
    // At a stationary origin the new entrypoints must emit exactly the same traces.
    let points = [
        (0., 0., false),
        (0., 0., true),
        (0., 0., true),
        (0., 0., false),
        (0., 0., false),
    ];
    let mouse = run(false, &points, false);
    let touch = run(true, &points, false);
    assert_eq!(mouse, touch);
    assert_eq!(
        touch
            .iter()
            .filter(|s| s.starts_with("DENSITY|DOWN|"))
            .count(),
        2
    );
    assert_eq!(
        touch
            .iter()
            .filter(|s| s.starts_with("DENSITY|UP|"))
            .count(),
        3
    );
    assert!(
        !touch
            .iter()
            .any(|s| s.starts_with("DENSITY|PRESS|") || s.starts_with("DENSITY|MOVE|"))
    );
}

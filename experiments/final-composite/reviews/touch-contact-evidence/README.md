# Local synthetic touch regression evidence

The reviewed evidence keys preserve their original local provenance labels. Their exact bytes are copied beneath this directory; no private games, saves, reproduction videos, credentials or invalid shared-target log are included.

Runtime patch is separate from test-only code. To reproduce the six core tests, apply the five locked runtime patches to pinned upstream, copy regression-tests.rs to core/src/touch_input_tests.rs, copy make_fixture.py to core/src/touch_input_tests/make_fixture.py and execute it there to generate the three original synthetic SWFs, then add #[cfg(test)] mod touch_input_tests; to core/src/lib.rs. Use isolated target directories for before/after! Rust1.99.1 cargo test --locked -p ruffle_core --lib runs130tests; adding audio,mp3,aac,default_font runs134. The new six tests are included in those totals.

The accepted-before red control uses the original four patches and test-only forwarding handle_touch_start/end wrappers that invoke ordinary handle_event; four current-coordinate assertions fail and two compatibility controls pass. Golden replay patch changes only test dispatch under RUFFLE_TEST_TOUCH_BOUNDARIES and preserves all existing trace/handled/cursor assertions. Nine listed mouse goldens and the same nine touch replays pass. This is not native, browser or final IPA acceptance.

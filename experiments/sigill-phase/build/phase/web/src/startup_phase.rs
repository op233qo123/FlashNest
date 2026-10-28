// DIAGNOSTIC VARIANT ONLY. Fixed allowlist, no payload, no async/timers.
use wasm_bindgen::prelude::*;

#[wasm_bindgen(inline_js = r#"// Diagnostic-only, one-module/one-page startup receipts; no user data.
const phases = ["engine-second-start-call", "engine-second-start-return", "engine-audio-constructor-return", "engine-audio-constructor-error", "engine-core-build-return", "engine-initial-tick-call", "engine-initial-tick-return"];
let delivered = 0;
export function flashnestStartupPhase(code) {
  try {
    if (!Number.isInteger(code) || code < 0 || code >= phases.length) return;
    const bit = 1 << code;
    if (delivered & bit) return;
    // At-most-once attempt; absence of handler or delivery remains UNKNOWN.
    delivered |= bit;
    const journal = globalThis.FlashNestStartupJournal;
    if (journal && typeof journal.record === 'function') journal.record(phases[code]);
  } catch (_) { /* Diagnostic failure must not replace runtime error behavior. */ }
}
"#)]
extern "C" {
    #[wasm_bindgen(catch, js_name = flashnestStartupPhase)]
    fn receipt(code: u32) -> Result<(), JsValue>;
}

pub(crate) fn emit(code: u32) {
    let _ = receipt(code);
}

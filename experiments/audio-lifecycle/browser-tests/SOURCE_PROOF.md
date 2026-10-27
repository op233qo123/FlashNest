# Experimental WebAudio lifecycle repair — bounded evidence

Source pin: `89a7049965f3090e706265670df309a5128233ac`. The deployed runtime is not changed by these files. At preparation time the patch has source checks and JS/Python mocks only: no Rust build, browser execution, native execution, crash reproduction or Adobe reference run.

## Source-backed ownership defect

In pinned [`web/src/audio.rs`](https://github.com/ruffle-rs/ruffle/blob/89a7049965f3090e706265670df309a5128233ac/web/src/audio.rs#L128-L154), `Buffer` owns an `on_ended_handler` closure, and that closure captures a strong cloned `Rc<RefCell<Buffer>>`. Thus a buffer owns a closure that owns the same buffer. Dropping the backend's vector alone cannot reduce this self-cycle to zero. The existing `Buffer::drop` clears the current node's handler, but that drop is not reached solely by removing the backend's owning `Rc`s. This is a source-level ownership finding, not evidence that it caused a native process crash.

The backend creates and starts two buffer sources during construction even for a silent movie ([lines 49–82](https://github.com/ruffle-rs/ruffle/blob/89a7049965f3090e706265670df309a5128233ac/web/src/audio.rs#L49-L82)). Its existing drop requests `AudioContext.close()` without awaiting its Promise ([lines 109–112](https://github.com/ruffle-rs/ruffle/blob/89a7049965f3090e706265670df309a5128233ac/web/src/audio.rs#L109-L112)). Buffer playback attaches the callback before starting a source and stores that source only after start succeeds ([lines 239–267](https://github.com/ruffle-rs/ruffle/blob/89a7049965f3090e706265670df309a5128233ac/web/src/audio.rs#L239-L267)); a start error therefore also needs explicit detachment.

The experimental patch changes only `web/src/audio.rs`:

1. Capture `Weak`, upgrade it for callback duration, instead of owning a self-`Rc`.
2. Clear backend buffer owners before the existing close request, so reachable buffer drops detach current handlers first.
3. Detach the previous completed source when replacing it.
4. Detach the newly attached source if its start fails, before returning the error.

No decoder, mixer, adaptive timing, play/pause, RAF, visibility behavior or new Rust close-Promise task is introduced. While a callback is executing, its upgraded local `Rc` keeps the buffer alive until it returns; the patch does not directly invoke any dropped callback. This design still requires actual Rust/WASM and browser validation. The included pure-Rust ownership model is a small independent model, not a WebAudio or wasm-bindgen proof.

## Independent lifecycle boundaries

`ruffle-player` disconnection calls its inner destroy; inner destroy destroys and nulls the instance. The pinned visibility listener first checks `if (!this.instance) return` before touching the WASM instance, but remains registered on the document. This separate listener can retain the JavaScript inner object; JS player WeakRef noncollection is therefore not proof of an audio cycle, and the patch deliberately does not modify it. See pinned [element disconnect](https://github.com/ruffle-rs/ruffle/blob/89a7049965f3090e706265670df309a5128233ac/web/packages/core/src/ruffle-player-element.tsx#L99-L101), [visibility handler](https://github.com/ruffle-rs/ruffle/blob/89a7049965f3090e706265670df309a5128233ac/web/packages/core/src/internal/player/inner.tsx#L469-L495), and [destroy](https://github.com/ruffle-rs/ruffle/blob/89a7049965f3090e706265670df309a5128233ac/web/packages/core/src/internal/player/inner.tsx#L851-L859).

A player/core may remain owned by pending work after DOM removal. The gate therefore requires observing actual `AudioContext.close()` entry and settlement, rather than assuming that DOM removal synchronously frees every Rust owner. `close()` settlement does not establish GC or deallocation of all nodes/contexts ([Web Audio close contract](https://webaudio.github.io/web-audio-api/#dom-audiocontext-close)). No forced GC or WeakRef noncollection gate is used.

## Actual A/B gate, once built and separately authorized

Use exact immutable baseline and candidate JS/WASM inventories, same browser executable/driver, renderer `wgpu-webgl`, quality low. The original SWF37 fixture is silent, vector-only, with an AVM2 frame heartbeat; no game assets, storage, network loaders or audio tags. Any WebAudio sources observed are the runtime's own backend.

Normal arms perform eight create / trusted resume / trusted pause / trusted resume / remove cycles on one document for each runtime. Require natural source creation beyond the two constructor sources, a fresh call and its matching fulfilled Promise after each action, a fresh post-pause source, and original AVM2 heartbeat. Removal must produce exactly one close entry and a fulfilled close Promise per created backend. Failure to construct WebAudio, refill, detach the candidate, or observe close is a failure—not a successful expected baseline failure.

Only the explicit handler-detach property is an expected baseline failure: baseline retains at least one explicitly attached handler at close entry; candidate has zero. This test distinguishes explicit setter behavior without claiming JS garbage collection. It does not retain source nodes in normal arms, wrap `onended`, or change callback identity/receiver/Event. Observer maps use weak keys and metadata-only records.

Separate fresh-document fault arms inject a `start()` exception on the first or second constructor source. Pinned builder behavior is to log `Unable to create audio backend. No audio will be played.` and continue with `NullAudioBackend`, not reject the entire movie load ([builder fallback](https://github.com/ruffle-rs/ruffle/blob/89a7049965f3090e706265670df309a5128233ac/web/src/builder.rs#L631-L641)). Require that exact single fallback diagnostic, expected source/start count, close settlement, and still-running original movie. Styled tracing-wasm ERROR/WARN console logs are parsed using their exact pinned four-string signature; INFO and unrelated logs are not converted to errors.

A separately labeled synthetic-ended arm retains exactly one latest source node for both runtimes. After actual close settlement, it dispatches a synthetic `ended` Event through `dispatchEvent` (never directly calls a Rust callback). Baseline must attempt actual `createBufferSource` work during that event, measured before the native factory call; candidate must have no handler and no source attempt or created node. A closed-context factory error is recorded as an attempt, not mistaken for no callback. Unrelated runtime errors are never broadly waived. This is injected stale-event behavior, not a spontaneous browser failure reproduction.

## Native comparison required for any stability claim

After browser/source gates, an isolated WKWebView/iOS comparison should use the same original fixture and the exact baseline/candidate bundles, holding the host lifecycle implementation fixed. Exercise create/remove/recreate, trusted play, pause/resume, portrait/landscape and background/foreground; preserve raw WebContent termination reports and action timestamps. Distinguish renderer/context loss, explicit JS exceptions and native process termination. A same-player child Loader transition does not itself destroy WebAudioBackend; this patch's primary scope is whole-player teardown or constructor error.

Native crashes have been observed in both AVM1 and AVM2 content and early after process start; that evidence does not support an AVM2-only attribution or prove an accumulated teardown leak caused those crashes. Passing the proposed lifecycle gate would establish the bounded lifecycle behavior measured here—not prove the original native SIGBUS is fixed.

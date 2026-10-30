# Focused lazy Graphic actual-WebGL mechanism check — local preparation

Status: **NEVER RUN**. Candidate WASM does not yet exist here. Template dispatch is
false. No existing engine/native acceptance is inherited. No IPA/private assets.

Three tiny cases only, baseline and candidate each in a fresh browser context:
1. Eight unshown JPEG3/static shapes, one trusted Space displays one shape.
2. Forward bitmap reference ordering with the same one-Space display contract.
3. Two placements of one shared shape, trusted S/R/M/H: show, hide/reveal across
   frames, vector mask, scalar inside/outside shape hit test.

Both use identical WebGL preference, fixture bytes, 320x240 geometry and DPR1.
The harness captures complete canvas PNGs and exact RGBA hashes, compares A/B,
checks independent known center pixels (JPEG tolerance2), records actual fetched
WASM bytes against a mandatory SHA pin and rejects missing WebGL contexts,
exceptions/context loss/overflow. Inputs must be the exact trusted key sequence.

GPU observations are API call counts, NOT decode counts, residency or memory.
Wrappers preserve original arguments, receiver and result; no pixel readback is
injected into GL. 16x16 upload calls are classified by observed dimensions;
initial baseline must exceed candidate, candidate first use must add a call,
and shared repaint/mask/hit must add none after first display. The original full
call records remain available, including unrelated/background allocations.
The deterministic CPU decode-counter test remains separate evidence.

The existing official Chrome channel with sandbox enabled exercises actual WebGL,
not a hardware GPU or iOS WebKit. No frame timing or RSS conclusion is supported.
The original observer itself adds bounded overhead and is not production code.

Dependencies reuse existing pinned browser harness requirements. The authorized
runner must first pass the existing official Chrome/sandbox helper/AppArmor preflight; do not download a headless-shell replacement or change sandbox settings. Only after the candidate build: fill a
separate contract with exact complete runtime inventories, selected WASM SHAs,
and fixture-directory inventory, then set dispatchAllowed in that ephemeral
execution contract. Do not mutate the false template to suggest acceptance.

CLI: python run.py --contract CONTRACT --baseline-runtime BASELINE_RUNTIME
--candidate-runtime CANDIDATE_RUNTIME --fixtures FLAT_FIXTURE_DIR --output NEW_DIR
Flat fixture directory contains neutral-eight-jpeg3.swf,
neutral-forward-reference.swf, neutral-shared-boundaries.swf. Contract inventories
all files in each directory. Browser run writes terminal result.json even on
observation/assertion failure after startup. Candidate missing/pin mismatch fails
before browser launch.

Local checks: python test_contract.py; node test_page.cjs. These are contract/mock
checks, not browser execution or native acceptance. Scope remains three cases,
not the prior 290/198 matrices or a pressure test.

Only the observed WASM flavor is exercised. Building both flavors does not make
them both tested. This standalone page does not cover the complete App shell,
Swift/native lifecycle, save or audio behaviors. A case keeps one player for all
its phases; no phase recreates a player or resets caches. Renderer fallback,
missing selected identity, timeouts or semantic failures fail rather than skip.

Trace observation is installed at the pinned renderer-created log (the instance already exists) and reaffirmed after load. This avoids the accepted setter silently discarding pre-instance observers and catches constructor traces before load resolves. The log wrapper and extra observer can affect timing; this is an opt-in synthetic diagnostic, not zero-interference profiling.

The focused retry permits SwiftShader through the previously reviewed launch flag,
but does not force ANGLE: use actual observed renderer/context evidence rather than
claiming a particular physical or software GPU implementation.

# Parked half-resolution experiment — not shipped or passed

This directory is intentionally outside all release app, test, and helper-resource
paths in `project.yml`. It retains the original vector fixture and strict tests,
without converting the observed failures to a pass. No half-resolution setting,
query hook, or wrapper is included in the release candidate.

The complete runnable historical candidate (including native/web wiring and the
original file locations) is preserved on Git branch
`experiment/half-resolution-1.5.2`, commit
`06dd931f6512b2da5e55b90aaf909dc02f899cf2` (1.5.2 build 10). Check out that branch
in a separate worktree to reproduce its `FlashNest` and `FlashNestUI` schemes.
These archived generator/test files retain their original source and assumptions;
they are not a standalone runnable project at their relocated paths.

## Unresolved observed failures

- Build 9 core run `40428761697` / job `121941032641`: 100 tests, one failure.
  Exact iOS 18.2 run `40428815650` / job `121941213889` reproduced the missing
  canvas probe. The production-style trusted UI test was never reached.
- Build 10 strict root-metrics check failed **in normal mode, before child load**:
  requested WK frame 440×860; actual canvas CSS/visual 440×767 and backing
  1320×2301 at DPR 3. The test used a standalone UIWindow; automatic safe-area
  adjustment is a separate explanation to investigate, not proof that production
  fullscreen layout is wrong. Assertions were not relaxed to accept this.
- Build 10 crash report
  `com.apple.WebKit.GPU-2026-10-27-013538.ips` reports SIGABRT / METAL code 102:
  connection to SimMetalHost XPC service interrupted. Faulting stack passes
  `MTLSimulator_encountered_XPC_error`, `MTLSimArgumentEncoder.setBuffers`,
  `rx::ProgramExecutableMtl::setupDraw`, `drawElementsInstanced`, and
  `WebCore::GraphicsContextGLANGLE`. This is simulator GPU-host failure evidence,
  **not proof of device OOM**, and not fixed by parking this optional feature.

The fixture remains unchanged: five dynamic rectangles in the root and five in
an independent `_level1` child, corner/center coordinates, child key counters,
written SOL, and a noScale negative control. Level 1 has its own `_root`; its
shapes do not replace level 0's shapes. No malformed-fixture cause was established.

Any future proposal must independently pass actual canvas pixel measurements,
normal-mode parity, trusted UIKit corner/center hits, portrait/landscape rotation,
child and keyboard input, and disclosed noScale limitations before shipping.
The new required `LifecyclePlayerUITests` uses a **different**, simple no-vector
fixture only to validate requested save/background/restart UX; its result cannot
stand in for these unresolved rendering gates.

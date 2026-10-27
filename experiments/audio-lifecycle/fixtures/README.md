# Original silent WebAudio lifecycle diagnostic fixture

`silent.swf` is an original 799-byte SWF37 / AVM2 movie generated without a proprietary compiler. It draws a blue 320×240 rectangle, registers ENTER_FRAME, traces `AL_READY` on frame initialization and `AL_ACTIVE` on every heartbeat, and stops the one-frame timeline. The browser observer coalesces repeated `AL_ACTIVE` text while keeping its count. There are no sound tags, SharedObjects, network loaders, ExternalInterface calls or user-game assets.

The runtime itself creates its WebAudio ping-pong sources even though this movie is silent. That is the behavior the separate browser diagnostic observes. No claim of audible output or device playback follows from this movie.

Reproduce and structurally check without running a Flash runtime:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 make_fixture.py
PYTHONDONTWRITEBYTECODE=1 python3 validate_fixture.py
```

`abc_subset.py` is the unchanged original minimal assembler reused from earlier original diagnostic fixtures. `validate_fixture.py` separately parses the emitted SWF/ABC, checks branches/stack/scopes/classes and tag restrictions, and checks deterministic regeneration. The manifest and structural-validation record are not runtime or Adobe-reference results.

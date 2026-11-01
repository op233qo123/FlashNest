# Neutral frame-cadence check

This is an original, 574-byte, uncompressed SWF 37 / AS3 diagnostic. Its header is
24 fps. A single `ENTER_FRAME` listener increments and traces a counter; the
timeline is stopped deliberately to separate event cadence from timeline loops.
There are no game-derived assets, paths, names, bytecode, or inputs.

The minimal ABC writer is adapted from the repository's original frame-order
fixture writer. `make_fixture.py` deterministically produces the input at runtime;
no compiler or binary download is needed.

Run with Python 3, Playwright, and Chromium installed:

```sh
python run_fps.py --runtime /path/to/verified/runtime \
  --inputs /path/to/build23/inputs.json --output /path/to/fps-result.json
```

Optional `--chromium /path/to/chromium` selects a system executable. Chromium's
sandbox is explicitly enabled; do not disable it to obtain a pass. Use an
appropriate non-root CI runner supporting its sandbox.

The supplied runtime must exactly match all 12 `runtimeFiles` hashes in the
frozen build23 inputs. The receipt binds the inputs, generated fixture, and actual
fetched WASM bytes. CI must also pin that inputs file; a caller-created inventory
would not establish build23 identity.

Five isolated pages are tested:

1. Default `frameRate` omitted: measured wall-clock rate near 24.
2. Explicit 24: same wall-clock rate.
3. Explicit 48: near 48, and approximately twice default (sensitivity control).
4. Default, injected 60 Hz RAF timestamps: 240 +/- 2 events per 10 virtual seconds.
5. Default, injected 120 Hz RAF timestamps: same logical event count.

Wall-clock rows use the browser's real RAF and `performance.now()` over 4.5
seconds after startup; an 18% rate tolerance allows CI scheduling noise while
rejecting 24-to-60 or 24-to-48 acceleration. The synthetic rows replace RAF with a
manually pumped callback queue. They exercise the actual pinned WASM scheduler
with simulated elapsed timestamps, not a mock frame accumulator, but **are not
physical 60/120 Hz monitor tests**, do not simulate real thread contention, and
do not prove WKWebView/iOS behavior. No timing result here establishes the cause
of a particular game's speed anomaly.

No product `frameRate` is changed. The probe uses compatible WebGL and the app's
network restrictions, but plays automatically solely for measurement. All browser
requests are restricted to the temporary loopback origin. Browser contexts and
the temporary server are destroyed at completion.

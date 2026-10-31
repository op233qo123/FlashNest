# Bounded WebGL texture-lifetime measurement

Diagnostic source commit: `aff320837722c8ec96b664819d07dcde897fe3fa`.
[Successful CI run 41182014438](https://github.com/op233qo123/FlashNest/actions/runs/41182014438).
Artifact 13035252773, 107809 bytes, SHA256 `3c189f6fc8ec1c06479ffa493d76c0987961c63f2adfb665a19417f7ba47be3c` is preserved unchanged as `run-41182014438.zip`.

This measures the accepted baseline runtime, not a product patch. All four synthetic cases passed using sandboxed Chrome 156.0.8078.47 and actual WebGL2. Every selected WASM response was tied to an exact server request ID, URL/path/status and server-served byte hash, matching the pinned baseline runtime inventory. The selected WASM SHA256 was `0fabc6602d29091438c307ca715cf0973641b93cd2d7513798865cb8e1c3f054`.

## Observations

Counts below select actual 512x512 RGBA typed-array uploads (1048576 bytes), not same-sized internal render targets. A delete means a **deleteTexture request**, not proof of physical GPU memory release.

| Case | Uploads | Relevant observed deletion requests | WASM capacity after warm-up |
|---|---:|---|---:|
| Root, 16 distinct resources, 4 rounds | 16 total; no additional upload on repeated rounds | 0 after empty frame/idle; 16 after player removal | 309 pages |
| Root, 64 distinct resources, 2 rounds | 64 total; no additional upload on repeated round | 0 after empty frame/idle; 64 after player removal | 339 pages |
| Loader, 6 loads/unloads, no retained child | 6 | 6 by unloaded-six snapshot | 300 pages |
| Loader, retain 3 AS child objects | 6 initially; +3 on rehang | Initial 6 deleted by unloaded-six; new 3 deleted by normal-frames snapshot after dropping references | 300 pages |

One WASM page is 64 KiB. Capacity stays at the warmed-up value after deletion/removal; capacity is not live allocation, and this does not establish a leak. In the retained-child control, the AS objects remained callable and re-displayable although their initial textures had already received deletion requests. Rehang rebuilt textures. Dropping references was followed by deletion within the ordinary-frame window, with no forced GC or AS dispose.

This separates a bounded fixed-resource plateau, root-resource lifetime, and Loader/display-object texture rebuilding in these fixtures. It does not establish the memory policy safe for arbitrary content. One internal 320×240 render target lacked a delete request in each final snapshot; implicit context/browser cleanup is not measured. Expected base-level RGBA byte counts exclude mipmaps, driver allocations, and physical residency.

These short desktop Chromium tests do **not** reproduce or resolve the user's long-running iOS WebContent termination. No iOS memory-pressure evidence, native/CPU live heap census, decoded-image lifetime accounting, or physical GPU allocation measurement is provided. Further optimization needs a separately scoped lifetime/pressure test; these findings do not justify deleting resources still owned by live content.

## Reproduce analysis

```
unzip run-41182014438.zip -d extracted
python analyze_result.py extracted/browser/result.json > summary.json
```

Raw result JSON includes bounded events, traces, snapshots, exact server transfer evidence, and screenshots. The analysis only reads the artifact and does not modify test behavior.

## Diagnostic repairs and preserved failed evidence

- Run [41181436516](https://github.com/op233qo123/FlashNest/actions/runs/41181436516), commit `c4c8718d4fcef207066eda6e0f2ad97e1623bf4b`: root-16 completed, but response-body extraction for a streamed WASM response failed in Playwright. Diagnostic-only identity collection was replaced with exact server-byte and browser URL/status/request-ID cross-binding. Artifact 13035485964 SHA256 `a2a7713af0f720dcc78e842fa56442a8958f5bc41ed69e8144626a0ed1d26a71`.
- Run [41181747033](https://github.com/op233qo123/FlashNest/actions/runs/41181747033), commit `d175a1d38abfd6bfc27eb273b28b3de8228c765f`: both root cases completed, but the synthetic child URL resolved at the document root and returned 404. An exact hash-pinned `/texture-child.swf` alias fixed this diagnostic server route, not product loading behavior. Artifact 13035596588 SHA256 `6a50ba3d15cd3326b4308f2d33e6c4583f9455d4d2970de039688ee798df4e20`.

Runtime, synthetic fixtures, rendering and reclamation policy were unchanged by either repair. Failed archives are preserved alongside the successful archive for audit. Package and workflow remain at tested source; this evidence-only commit uses `[skip ci]`.

Main and v1.5.6 were checked unchanged at `985f25c44ead766b2c4f9bd77b82e7b92bf95cc0`; published IPA SHA256 remains `b4732541cd2c995c289027f136bcb9bbe44682ff45b448b889240b8d3f09d70b`. No package was released by this diagnostic task.

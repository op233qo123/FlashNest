# Vendored experimental Ruffle candidate

`ruffle-frame-order-40491098384.zip` is the exact original artifact from
https://github.com/op233qo123/FlashNest/actions/runs/40491098384 (artifact
`12729069965`), not a repacked or newly rebuilt runtime.

- Bytes: `10950405`
- SHA-256: `57d7eaed19edd006e2a33a9bfa816f22da8b1003becf3719dfca0c97cb38c4af`
- Base source: https://github.com/ruffle-rs/ruffle/tree/89a7049965f3090e706265670df309a5128233ac
- Experiment source: https://github.com/op233qo123/FlashNest/tree/f60ff6a99941937056eee5ad94ed4b4af9c72c99/experiments/frame-order

This **modified experimental** candidate is identified as `FlashNest experimental
Ruffle 0.7.1 frame-order guard de0acabdf957`, not an official stable Ruffle fix.
The application build verifies the locked archive offline and extracts its
runtime; this full ZIP also retains source correspondence and original evidence.
Do not replace it with only the WASM files, a fresh rebuild, or a mutable download.

The original ZIP includes complete runtime assets/source maps, Cargo/npm locks,
modified source and patch, build recipes/tools/provenance, upstream license texts,
59 JavaScript test results, and baseline/patched original and upstream checks.
Its historical build metadata is intentionally not rewritten during integration.
See `ruffle-frame-order-source/` for a compact archive index and reviewable patch.
The full supplementary JavaScript license/NOTICE texts remain in
`App/Resources/Web/licenses/`; they must accompany runtime redistribution.

See `App/Resources/Web/Ruffle-MODIFICATIONS.md` for exact hashes, the single native
candidate run, and limits. In particular, 31 upstream checks include two
preserved known failures; neither these checks nor one native pass prove complete
Adobe compatibility, fix intermittent WebKit crashes, or establish a game's
root cause. Release validation is separate. This directory is neither a complete
upstream/dependency source archive nor a legal-compliance certification.

# Separate SIGILL phase diagnostic engine build

LOCAL preparation only. No build, run, commit or remote action was performed by this author. Publish code files here under `experiments/sigill-phase/build/`, and workflow-draft.yml under a separately reviewed manual workflow path. Never publish historical logs, xcresult, game data or decoded archive. Exclude `__pycache__`.

The workflow performs a fresh official pinned Ruffle checkout, reconstructs three historical patches byte-for-byte, validates historical modified-source hashes and lockfiles, then installs only the four proposed web/src phase files. Its verifier checks every tracked changed path plus exact expected bytes and rejects unexpected tracked/untracked source. Shipping/candidate provenance code and approvals are unchanged. Build output has diagnostic-only version identity, new hashes and complete source correspondence.

Toolchain pins are inherited from the actual candidate recipe: Rust1.99.1, Node24.22.1, wasm-bindgen0.2.127, Binaryen129 checksum, Temurin21 checksum, clang18. Ordinary matched extensions/MVP glue+WASM build and all59 original core JS tests remain. This is not an audio-recovery/ownership acceptance run or a production promotion.

`build.sh SOURCE OUTPUT` checks exact tools and delegates to `provenance.py`. Do not call the old candidate provenance gate on this new runtime and weaken it to pass. The new verifier independently reconstructs and hashes its own expected source.

## Artifact contract

Artifact: `FlashNest-sigill-phase-diagnostic-engine`. GitHub upload receives `sigill-phase-engine/`; **ZIP root is expected to contain runtime/, provenance.json, etc. directly**, not a guaranteed enclosing directory. Native consumer must verify actual downloaded inventory and fail closed rather than guess prefixes.

- `runtime/`: whole selfhosted dist, copied recursively (includes maps/licenses/any nested resources).
- `runtime-manifest.json`: object of relative runtime path → `{sha256,bytes}` for ALL files; not only JS/WASM.
- `provenance.json`: schema1, kind=`sigill-phase-diagnostic-not-shipping`, status=`diagnostic-only-unpromoted`, upstreamCommit, inputsSHA256, experiment fields `GITHUB_SHA/GITHUB_RUN_ID/GITHUB_RUN_ATTEMPT`, modifiedSources, versionSeal, sourceDateEpoch, generatedInlineSnippetSources, toolVersions, completedUTC, files inventory excluding provenance.json itself.
- `generated-snippets/`: generated wasm-bindgen JS modules containing flashnestStartupPhase, retained alongside original source and bundle. Packaging fails if absent, or if final bundled JS lacks the fixed boundary strings. This attests packaging, not actual bridge delivery.
- `source-correspondence/`, `build-recipe/`: exact modified source, lockfiles, licenses, build scripts and pins.

Native observation must pin actual artifact ID, SHA256/bytes and source/workflow commit, then verify every inventory byte. No fallback to the old candidate artifact. Exactly-one-observation policy is owned by the separate native lane, not this build-only workflow.

Static validation: Python parse/compile and shell syntax only. No Rust compilation or generated snippet output exists yet. The next independent review must verify checkout/tool availability, patch reconstruction against the official full source, generated snippet glob behavior on real output, and consumer manifest alignment. Build failures remain failures; do not rerun a native observation automatically.

#!/usr/bin/env bash
# Local smoke build only: not release-equivalent (no JPEG-XR/MVP/wasm-opt).
# Prerequisites: official verified toolchain/dependencies already installed.
set -euo pipefail
root=$(cd -- "$(dirname -- "$0")/.." && pwd)
workspace=$(dirname "$root")
export PATH="$workspace/scene-resource-repair/toolchain/bin:$root/build-tools/bin:$PATH"
export CARGO_HOME="$workspace/scene-resource-repair/cargo-home"
export CARGO_TARGET_DIR="$root/target"
export RUSTFLAGS='--cfg=web_sys_unstable_apis --cfg=getrandom_backend="wasm_js" -Aunknown_lints -C target-feature=+bulk-memory,+simd128,+nontrapping-fptoint,+sign-ext,+reference-types'
test "$(rustc --version | awk '{print $2}')" = 1.99.1
test "$(wasm-bindgen --version)" = 'wasm-bindgen 0.2.127'
cargo build --manifest-path "$root/runtime-source/Cargo.toml" --locked --offline -j 1 --target wasm32-unknown-unknown --profile web-wasm-extensions -p ruffle_web
wasm-bindgen "$root/target/wasm32-unknown-unknown/web-wasm-extensions/ruffle_web.wasm" --target web --out-dir "$root/runtime-source/web/packages/core/dist" --out-name ruffle_web --reference-types
cd "$root/runtime-source/web"
CFG_RELEASE_CHANNEL=flashnest-low-sampling-local npm run build --workspace=ruffle-core --ignore-scripts
CFG_RELEASE_CHANNEL=flashnest-low-sampling-local npm run postbuild --workspace=ruffle-core
npm run build --workspace=ruffle-selfhosted

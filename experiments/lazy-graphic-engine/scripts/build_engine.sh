#!/usr/bin/env bash
# DRAFT: gated final source only. Never invoke for the currently ineligible lock.
set -euo pipefail
here=$(cd -- "$(dirname -- "$0")/.." && pwd)
python3 "$here/scripts/check_contract.py" --mode engine
source_dir=$(realpath "${1:?source checkout}"); out=$(realpath -m "${2:?fresh output}")
test ! -e "$out"; mkdir -p "$out"
test "$(rustc --version | awk '{print $2}')" = 1.99.1
test "$(node --version)" = v24.22.1
test "$(npm --version)" = 11.19.1
test "$(wasm-bindgen --version)" = 'wasm-bindgen 0.2.127'
wasm-opt --version | grep -Eq 'version 129([ (]|$)'
# Preserve upstream source-root target behavior. No smoke/custom-output fallback.
unset CARGO_TARGET_DIR CARGO_FLAGS RUSTFLAGS CARGO_ENCODED_RUSTFLAGS CARGO_BUILD_TARGET WASM_SOURCE
export SOURCE_DATE_EPOCH=1791399335 BUILD_WASM_MVP=true ENABLE_VERSION_SEAL=true
export CFG_RELEASE_CHANNEL=flashnest-composite-experimental CARGO_FEATURES=jpegxr CARGO_BUILD_JOBS=1 CARGO_INCREMENTAL=0
export CC=clang-18 CXX=clang++-18 LIBCLANG_PATH=/usr/lib/llvm-18/lib
python3 "$here/scripts/engine_receipt.py" prepare "$source_dir" "$out"
cd "$source_dir/web"
# npm ci must have been run against the unchanged exact lock.
( unset BUILD_WASM_MVP; npm run prebuild --workspace=ruffle-core; npm exec --workspace=ruffle-core -- tsc --build --force ) 2>&1 | tee "$out/core-types-preflight.log"
( npm run build --workspace=ruffle-core; npm run build --workspace=ruffle-selfhosted ) 2>&1 | tee "$out/build.log"
npm test --workspace=ruffle-core -- --reporter json --forbid-only --forbid-pending 2>&1 | tee "$out/core-js.log"
python3 "$here/scripts/engine_receipt.py" package "$source_dir" "$out"

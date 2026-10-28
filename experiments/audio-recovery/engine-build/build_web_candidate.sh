#!/usr/bin/env bash
# Isolated experimental build; no production runtime replacement.
set -euo pipefail
test "$#" -eq 2 || { echo "usage: $0 PATCHED_SOURCE OUTPUT" >&2; exit 2; }
source_dir=$(realpath "$1")
output=$(realpath -m "$2")
helper_dir=$(cd -- "$(dirname -- "$0")" && pwd)
test "$(rustc --version | awk '{print $2}')" = 1.99.1
test "$(node --version)" = v24.22.1
test "$(wasm-bindgen --version)" = 'wasm-bindgen 0.2.127'
wasm-opt --version | grep -Eq 'version 129([ (]|$)'
export SOURCE_DATE_EPOCH
SOURCE_DATE_EPOCH=$(python3 "$helper_dir/candidate_provenance.py" prepare "$source_dir" "$output")
export BUILD_WASM_MVP=true ENABLE_VERSION_SEAL=true
export CFG_RELEASE_CHANNEL=flashnest-audio-recovery-experimental
export CARGO_FEATURES=jpegxr CARGO_BUILD_JOBS=2
export CC=clang-18 CXX=clang++-18 LIBCLANG_PATH=/usr/lib/llvm-18/lib
# Core TypeScript imports the generated real WASM declarations. Generate the
# extensions binding first (unmodified upstream prebuild), then typecheck every
# core source before paying for the second MVP build. No ABI stubs are used.
(
    cd "$source_dir/web"
    test -d node_modules
    unset BUILD_WASM_MVP
    npm run prebuild --workspace=ruffle-core
    npm exec --workspace=ruffle-core -- tsc --build --force
) 2>&1 | tee "$output/core-types-preflight.log"
# Preserve the complete ordinary dual-WASM build, fresh declaration typecheck,
# packaging and unchanged 59-test gate. The extensions build is cached here.
(
    cd "$source_dir/web"
    test -d node_modules
    npm run build --workspace=ruffle-core
    npm run build --workspace=ruffle-selfhosted
) 2>&1 | tee "$output/build.log"
(
    cd "$source_dir/web"
    npm test --workspace=ruffle-core -- --reporter json --forbid-only --forbid-pending
) 2>&1 | tee "$output/core-js.log"
python3 "$helper_dir/../../audio-lifecycle/engine-build/check_js_results.py" "$output/core-js.log" "$output/core-js-summary.json"
python3 "$helper_dir/candidate_provenance.py" package "$source_dir" "$output"
echo 'Experimental candidate only; WebAudio ownership/browser gates, native validation and explicit promotion remain required.'

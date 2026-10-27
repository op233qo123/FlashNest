#!/usr/bin/env bash
# Build into an isolated artifact directory; never edits the application runtime.
set -euo pipefail
test "$#" -eq 3 || { echo "usage: $0 PINNED_PATCHED_SOURCE PATCH OUTPUT" >&2; exit 2; }
source_dir=$(realpath "$1")
patch=$(realpath "$2")
output=$(realpath -m "$3")
helper_dir=$(cd -- "$(dirname -- "$0")" && pwd)
test "$(rustc --version | awk '{print $2}')" = 1.99.1
test "$(node --version)" = v24.22.1
test "$(wasm-bindgen --version)" = 'wasm-bindgen 0.2.127'
wasm-opt --version | grep -Eq 'version 129([ (]|$)'
export SOURCE_DATE_EPOCH
SOURCE_DATE_EPOCH=$(python3 "$helper_dir/candidate_provenance.py" prepare "$source_dir" "$patch" "$output")
export BUILD_WASM_MVP=true
export ENABLE_VERSION_SEAL=true
export CFG_RELEASE_CHANNEL=flashnest-frame-order-experimental
export CARGO_FEATURES=jpegxr
export CARGO_BUILD_JOBS=2
export CC=clang-18
export CXX=clang++-18
export LIBCLANG_PATH=/usr/lib/llvm-18/lib
(
    cd "$source_dir/web"
    npm ci
    npm run build --workspace=ruffle-core
    npm run build --workspace=ruffle-selfhosted
    npm test --workspace=ruffle-core
) 2>&1 | tee "$output/build.log"
python3 "$helper_dir/candidate_provenance.py" package "$source_dir" "$patch" "$output"
echo 'Candidate artifact only: native WKWebView validation and explicit promotion remain required.'

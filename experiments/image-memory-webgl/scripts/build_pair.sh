#!/usr/bin/env bash
set -euo pipefail
prep=$(realpath "${1:?prep}"); src=$(realpath "${2:?source}"); out=$(realpath -m "${3:?output}")
test ! -e "$out"; mkdir -p "$out"
test "$(rustc --version | awk '{print $2}')" = 1.99.1
test "$(node --version)" = v24.22.1
test "$(npm --version)" = 11.19.1
test "$(wasm-bindgen --version)" = 'wasm-bindgen 0.2.127'
wasm-opt --version | grep -Eq 'version 129([ (]|$)'
unset CARGO_TARGET_DIR CARGO_FLAGS RUSTFLAGS CARGO_ENCODED_RUSTFLAGS CARGO_BUILD_TARGET WASM_SOURCE
export SOURCE_DATE_EPOCH=1791399335 BUILD_WASM_MVP=true ENABLE_VERSION_SEAL=true
export CFG_RELEASE_CHANNEL=flashnest-composite-experimental CARGO_FEATURES=jpegxr CARGO_BUILD_JOBS=1 CARGO_INCREMENTAL=0
export CC=clang-18 CXX=clang++-18 LIBCLANG_PATH=/usr/lib/llvm-18/lib
for variant in baseline candidate; do
  dest="$out/$variant"; mkdir -p "$dest"
  if test "$variant" = candidate; then
    git -C "$src" apply --check "$prep/product.patch"
    git -C "$src" apply "$prep/product.patch"
  fi
  python3 "$prep/scripts/receipt.py" prepare "$src" "$dest" "$variant"
  (
    cd "$src/web"
    # Remove generated outputs only, not source or lockfiles; ensure no baseline runtime leaks into candidate.
    rm -rf packages/core/dist packages/selfhosted/dist
    ( unset BUILD_WASM_MVP; npm run prebuild --workspace=ruffle-core; npm exec --workspace=ruffle-core -- tsc --build --force ) 2>&1 | tee "$dest/core-types-preflight.log"
    ( npm run build --workspace=ruffle-core; npm run build --workspace=ruffle-selfhosted ) 2>&1 | tee "$dest/build.log"
    npm test --workspace=ruffle-core -- --reporter json --forbid-only --forbid-pending 2>&1 | tee "$dest/core-js.log"
  )
  python3 "$prep/scripts/receipt.py" package "$src" "$dest" "$variant"
done

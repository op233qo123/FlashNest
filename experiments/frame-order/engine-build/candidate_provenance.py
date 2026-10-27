#!/usr/bin/env python3
"""Verify the isolated one-file derivative and package source correspondence."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

PIN = "89a7049965f3090e706265670df309a5128233ac"
MODIFIED = "core/src/display_object/movie_clip.rs"


def digest(data):
    return hashlib.sha256(data).hexdigest()


def command(args, cwd=None):
    return subprocess.check_output(args, cwd=cwd, stderr=subprocess.STDOUT).decode().strip()


def verify(source, patch):
    if command(["git", "rev-parse", "HEAD"], source) != PIN:
        raise SystemExit("Upstream source is not the declared pinned commit")
    changed = command(["git", "diff", "--name-only", "HEAD"], source).splitlines()
    if changed != [MODIFIED]:
        raise SystemExit(f"Unexpected tracked modifications: {changed}")
    original = subprocess.check_output(["git", "show", f"{PIN}:{MODIFIED}"], cwd=source)
    with tempfile.TemporaryDirectory(prefix="frame-order-patch-check-") as temporary:
        root = Path(temporary)
        destination = root / MODIFIED
        destination.parent.mkdir(parents=True)
        destination.write_bytes(original)
        subprocess.run(["git", "apply", "--check", str(patch)], cwd=root, check=True)
        subprocess.run(["git", "apply", str(patch)], cwd=root, check=True)
        # A second modified source file in the patch is rejected by the tracked
        # diff above and by the only expected reconstructed file below.
        files = sorted(str(p.relative_to(root)) for p in root.rglob("*") if p.is_file())
        if files != [MODIFIED]:
            raise SystemExit(f"Patch reconstructed unexpected files: {files}")
        expected = destination.read_bytes()
    if (source / MODIFIED).read_bytes() != expected:
        raise SystemExit("Patched source differs from applying the exact supplied patch")
    return {
        "upstreamCommit": PIN,
        "upstreamURL": f"https://github.com/ruffle-rs/ruffle/tree/{PIN}",
        "modifiedFile": MODIFIED,
        "originalFileSHA256": digest(original),
        "modifiedFileSHA256": digest(expected),
        "patchSHA256": digest(patch.read_bytes()),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("prepare", "package"))
    parser.add_argument("source", type=Path)
    parser.add_argument("patch", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    source, patch, output = args.source.resolve(), args.patch.resolve(), args.output.resolve()
    info = verify(source, patch)
    if args.mode == "prepare":
        if output.exists() and any(output.iterdir()):
            raise SystemExit("Refusing to reuse a nonempty candidate output directory")
        output.mkdir(parents=True, exist_ok=True)
        epoch = int(command(["git", "show", "-s", "--format=%ct", PIN], source))
        sealed_date = datetime.fromtimestamp(epoch, timezone.utc).isoformat().replace("+00:00", "Z")
        seal = {
            "version_number": "0.7.1",
            "version_name": f"FlashNest experimental Ruffle 0.7.1 frame-order guard {info['patchSHA256'][:12]}",
            "version_channel": "flashnest-frame-order-experimental",
            # Deterministic metadata date, not a claim about actual build time.
            "build_date": sealed_date,
            "commitHash": PIN,
            "version4": "0.7.1.0",
            "firefox_extension_id": "flashnest-frame-order-experimental",
        }
        (source / "web/version_seal.json").write_text(json.dumps(seal, sort_keys=True) + "\n")
        info.update({"status": "experimental-unpromoted", "versionSeal": seal,
                     "sourceDateEpoch": epoch,
                     "actualBuildStartedUTC": datetime.now(timezone.utc).isoformat(),
                     "reproducibility": "Pinned recipe and dependency locks; second-clean-build byte identity not yet verified",
                     "runnerImage": {key: os.environ.get(key) for key in ("ImageOS", "ImageVersion", "RUNNER_ARCH", "RUNNER_OS")}})
        (output / "provenance.json").write_text(json.dumps(info, indent=2) + "\n")
        print(epoch)
        return

    recorded = json.loads((output / "provenance.json").read_text())
    for key, value in info.items():
        if recorded.get(key) != value:
            raise SystemExit(f"Candidate source changed during build: {key}")
    runtime_source = source / "web/packages/selfhosted/dist"
    if not (runtime_source / "ruffle.js").is_file() or len(list(runtime_source.glob("*.wasm"))) != 2:
        raise SystemExit("Expected a complete dual-WASM selfhosted build")
    shutil.copytree(runtime_source, output / "runtime")
    correspondence = output / "source-correspondence"
    correspondence.mkdir()
    for filename in ("Cargo.lock", "Cargo.toml", "web/package-lock.json", "web/package.json",
                     "web/version_seal.json", MODIFIED, "LICENSE.md",
                     "web/packages/selfhosted/LICENSE_MIT", "web/packages/selfhosted/LICENSE_APACHE"):
        target = correspondence / filename
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source / filename, target)
    shutil.copyfile(patch, correspondence / "queued-goto-guard.patch")
    helper_dir = Path(__file__).resolve().parent
    for filename in ("build_web_candidate.sh", "candidate_provenance.py", "workflow-draft.yml"):
        shutil.copyfile(helper_dir / filename, correspondence / filename)
    (correspondence / "MODIFICATIONS.md").write_text(
        "# Experimental modified Ruffle build\n\n"
        f"Base: https://github.com/ruffle-rs/ruffle/tree/{PIN}\n\n"
        "This is not an official unmodified Ruffle binary. The supplied patch modifies "
        "queued-goto scheduling in `core/src/display_object/movie_clip.rs`. "
        "See the exact patch and provenance hashes. No other tracked upstream source was changed. "
        "Ruffle's existing copyrights, licenses, and dependency notices are retained. "
        "This candidate is not promoted into the application or approved by upstream.\n"
    )
    tools = {}
    for name, cmd in {
        "rustc": ["rustc", "-vV"], "cargo": ["cargo", "--version"],
        "node": ["node", "--version"], "npm": ["npm", "--version"],
        "java": ["java", "-version"], "clang": ["clang-18", "--version"],
        "wasmBindgen": ["wasm-bindgen", "--version"], "binaryen": ["wasm-opt", "--version"],
    }.items():
        tools[name] = command(cmd)
    recorded["toolVersions"] = tools
    recorded["completedUTC"] = datetime.now(timezone.utc).isoformat()
    recorded["ascJarSHA256"] = digest((source / "tools/asc/asc.jar").read_bytes())
    recorded["wasmFeatures"] = {"dualWasm": True, "additionalCargoFeatures": "jpegxr", "binaryenOptimization": True}
    recorded["files"] = {
        str(p.relative_to(output)): {"sha256": digest(p.read_bytes()), "bytes": p.stat().st_size}
        for p in sorted(output.rglob("*")) if p.is_file() and p.name != "provenance.json"
    }
    (output / "provenance.json").write_text(json.dumps(recorded, indent=2) + "\n")


if __name__ == "__main__":
    main()

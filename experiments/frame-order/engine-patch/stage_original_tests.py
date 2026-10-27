#!/usr/bin/env python3
"""Stage original-only integration tests into a disposable pinned Ruffle checkout."""
import argparse
import hashlib
import json
import shutil
import subprocess
from pathlib import Path


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def stage(checkout):
    here = Path(__file__).resolve().parent
    manifest = json.loads((here / "patch-manifest.json").read_text())
    checkout = checkout.resolve(strict=True)
    head = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=checkout, text=True
    ).strip()
    assert head == manifest["upstreamCommit"], "Ruffle source commit mismatch"
    source = checkout / manifest["upstreamSourcePath"]
    assert digest(source) == manifest["upstreamSourceSHA256"], "Not clean pinned source"
    assert digest(here / "queued-goto-guard.patch") == manifest["patchSHA256"]
    fixtures = here.parent / "fixtures"
    fixture_manifest = json.loads((fixtures / "manifest.json").read_text())
    expected_swfs = {
        "nested-child-goto.swf": "ae3e561e8695a0be147e2192cd6d067eaa9462daedf92213bed86c9e4c4a4d8b",
        "control-no-child-goto.swf": "dd85e9f2b63b32199b7d04def4efbd80ccf68fb42da63cfe987e94358c49f030",
    }
    assert fixture_manifest["swfVersion"] == 37
    assert fixture_manifest["referenceFlashRun"] is False
    assert set(fixture_manifest["files"]) == set(expected_swfs)
    for name, expected in expected_swfs.items():
        assert digest(fixtures / name) == expected, f"Original fixture changed: {name}"
        assert fixture_manifest["files"][name]["sha256"] == expected, name
        assert fixture_manifest["files"][name]["bytes"] == (fixtures / name).stat().st_size
    for name, expected in manifest["expectations"].items():
        assert digest(here / "expectations" / name) == expected["sha256"], name

    rust = checkout / "tests/tests/flashnest_frame_order.rs"
    staged = checkout / "tests/flashnest-frame-order-fixtures"
    assert not rust.exists() and not staged.exists(), "Refuse to overwrite existing tests"
    assert (checkout / "tests/Cargo.toml").is_file(), "Missing official test crate"
    staged.mkdir()
    for name in expected_swfs:
        shutil.copyfile(fixtures / name, staged / name)
    for name in manifest["expectations"]:
        shutil.copyfile(here / "expectations" / name, staged / name)
    shutil.copyfile(here / "flashnest_frame_order.rs", rust)
    print("Staged original-only tests; official fixtures and expected outputs unchanged")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("checkout", type=Path)
    stage(parser.parse_args().checkout)

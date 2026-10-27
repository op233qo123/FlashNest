#!/usr/bin/env python3
"""Check isolated patch/expectation integrity; optionally apply to a source-file copy."""
import argparse
import hashlib
import json
import shutil
import subprocess
import tempfile
from pathlib import Path


def digest(data):
    return hashlib.sha256(data).hexdigest()


def check(source_file=None):
    here = Path(__file__).resolve().parent
    manifest = json.loads((here / "patch-manifest.json").read_text())
    patch = here / "queued-goto-guard.patch"
    assert digest(patch.read_bytes()) == manifest["patchSHA256"]
    text = patch.read_text()
    assert text.count("--- a/") == text.count("+++ b/") == 1
    assert "+++ b/" + manifest["upstreamSourcePath"] in text
    assert "@@ -2495,6 +2495,14 @@" in text
    assert "+        if self.is_executing_avm2_frame_script() {" in text
    assert not any(line.startswith("-") and not line.startswith("---") for line in text.splitlines())
    traces = {}
    for name, expectation in manifest["expectations"].items():
        data = (here / "expectations" / name).read_bytes()
        assert digest(data) == expectation["sha256"], name
        lines = data.decode().splitlines()
        assert [int(line.split()[1]) for line in lines if line.startswith("FO_STATE ")] == list(range(1, 13))
        assert sum(line.startswith("FO_DONE 12 ") for line in lines) == 1
        traces[name] = data.decode()
    control = traces["control.txt"]
    repair = traces["nested-repair-target.txt"]
    assert repair == control.replace(
        "FO_VARIANT:control-no-child-goto", "FO_VARIANT:nested-child-goto"
    ).replace("FO_P1_END 0 1 1\n", "FO_B_RESET 1\nFO_P1_END 0 1 1\n")
    assert "FO_P2_TARGET" not in traces["nested-baseline.txt"]
    assert "FO_B_CLOSED_STOP" in traces["nested-baseline.txt"]
    assert "FO_P2_TARGET" in repair and "FO_B_CLOSED_STOP" not in repair
    for filename in ("stage_original_tests.py", "check_patch_bundle.py"):
        compile((here / filename).read_text(), filename, "exec")

    if source_file is not None:
        data = source_file.read_bytes()
        assert digest(data) == manifest["upstreamSourceSHA256"], "Source file is not pinned"
        with tempfile.TemporaryDirectory(prefix="frame-order-patch-") as tmp:
            root = Path(tmp)
            source = root / manifest["upstreamSourcePath"]
            source.parent.mkdir(parents=True)
            shutil.copyfile(source_file, source)
            subprocess.run(["git", "apply", "--check", str(patch)], cwd=root, check=True)
            subprocess.run(["git", "apply", str(patch)], cwd=root, check=True)
            assert digest(source.read_bytes()) == manifest["patchedSourceSHA256"]
            subprocess.run(["git", "apply", "--reverse", str(patch)], cwd=root, check=True)
            assert source.read_bytes() == data, "Reverse patch did not restore exact source"
    print("PASS isolated patch, labeled expectations, tick coverage, Python syntax"
          + (", exact source apply/reverse hashes" if source_file else ""))
    print("This is structural validation, not Rust compilation or runtime test success.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-file", type=Path)
    check(parser.parse_args().source_file)

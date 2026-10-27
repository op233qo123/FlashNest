#!/usr/bin/env python3
"""Run a fixed, unchanged upstream golden suite; zero tests/skips are failures."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import tomllib


def run_case(command, source, env, log_path, timeout=180):
    """Keep output on disk and terminate Cargo plus its descendants on timeout."""
    with log_path.open("w") as log_file:
        process = subprocess.Popen(command, cwd=source, env=env, stdout=log_file,
                                   stderr=subprocess.STDOUT, start_new_session=True)
        try:
            returncode = process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            process.wait(timeout=5)
            log_file.write(f"\nHARNESS_TIMEOUT: exact upstream test exceeded {timeout} seconds\n")
            returncode = 124
    return returncode, log_path.read_text(errors="replace")


def write_summary(evidence, pin, phase, results, config):
    expected = len(config["tests"]) + len(config["knownFailureTests"])
    complete = len(results) == expected
    (evidence / "summary.json").write_text(json.dumps({
        "sourceCommit": pin, "phase": phase, "tests": results,
        "allPassed": complete and all(row["passed"] for row in results),
        "suiteComplete": complete, "completedCount": len(results),
        "expectedCount": expected, "strictReferenceCount": len(config["tests"]),
        "knownFailurePreservationCount": len(config["knownFailureTests"]),
    }, indent=2) + "\n")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("evidence", type=Path)
    parser.add_argument("phase", choices=("baseline", "patched"))
    args = parser.parse_args()
    source = args.source.resolve()
    evidence = args.evidence.resolve() / args.phase / "upstream-goldens"
    evidence.mkdir(parents=True, exist_ok=True)
    config = json.loads(Path(__file__).with_name("adjacent-tests.json").read_text())
    pin = config["sourceCommit"]
    actual_head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=source, text=True).strip()
    if actual_head != pin:
        raise SystemExit(f"Wrong upstream source HEAD: {actual_head}")
    env = {**os.environ, "RUFFLE_TEST_OPTS": "--compile-mode=use-precompiled"}
    results = []
    failures = []
    known_failures = config["knownFailureTests"]
    selected = config["tests"] + known_failures
    write_summary(evidence, pin, args.phase, results, config)
    for name in selected:
        relative = Path("tests/tests/swfs") / name
        folder = source / relative
        options = tomllib.loads((folder / "test.toml").read_text())
        forbidden = ("ignore", "filter", "subtests", "image_comparisons", "player_options")
        if any(key in options for key in forbidden):
            raise SystemExit(f"Unexpected skip/non-strict/renderer configuration in {name}")
        expected_known_failure = name in known_failures
        if options.get("known_failure", False) is not expected_known_failure:
            raise SystemExit(f"Upstream known-failure annotation changed: {name}")
        subprocess.run(["git", "diff", "--exit-code", pin, "--", relative.as_posix()], cwd=source, check=True)
        hashes = {}
        filenames = ["test.toml", "test.swf", "output.txt"]
        if expected_known_failure:
            filenames.append("output.ruffle.txt")
        for filename in filenames:
            path = relative / filename
            data = (source / path).read_bytes()
            original = subprocess.check_output(["git", "show", f"{pin}:{path.as_posix()}"], cwd=source)
            if data != original:
                raise SystemExit(f"Upstream golden input was changed: {path}")
            hashes[filename] = hashlib.sha256(data).hexdigest()
        command = ["cargo", "test", "--locked", "-p", "tests", "--test", "tests", "--profile", "ci", name, "--", "--exact", "--test-threads=1"]
        log_path = evidence / (name.replace("/", "__") + ".log")
        returncode, log = run_case(command, source, env, log_path)
        passed = returncode == 0 and re.search(
            r"test result: ok\. 1 passed; 0 failed; 0 ignored;", log
        ) is not None
        row = {"name": name, "passed": passed, "returncode": returncode,
               "scope": "preserve-upstream-known-failure-and-ruffle-output" if expected_known_failure else "match-upstream-Flash-reference-output",
               "inputSHA256": hashes, "log": log_path.name, "command": command}
        results.append(row)
        write_summary(evidence, pin, args.phase, results, config)
        print(f"{'PASS' if passed else 'FAIL'} {args.phase} {name}", flush=True)
        if not passed:
            print(log[-6000:], flush=True)
            failures.append(name)
    if failures:
        raise SystemExit("Adjacent upstream failures: " + ", ".join(failures))


if __name__ == "__main__":
    main()

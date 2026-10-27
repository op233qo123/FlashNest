#!/usr/bin/env python3
"""Offline, fail-closed verification/staging of one explicitly locked derivative.

The caller must fetch GitHub API metadata through the authorized workflow. This
verifies the locked bytes and metadata correspondence; it is not a signature or
an independently reproducible-build proof. It never downloads or executes code.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
import zipfile

PIN = "89a7049965f3090e706265670df309a5128233ac"
PATCH = "de0acabdf957fccbc11966b67defd0a7f577cdc5a147db949e0a4f0e56c6331f"
ORIGINAL = "fc229d96ab6fced20391cf810d9d89a2118803cb7f5ce48ddf6967e52e35700a"
MODIFIED = "af780dae48b842e0756b8cd23f50a539737d0bcbbbdca970feb90f27725e96b0"
SOURCE_FILE = "core/src/display_object/movie_clip.rs"
REPOSITORY = "op233qo123/FlashNest"
WORKFLOW = ".github/workflows/experiment-frame-order-engine.yml"
ARTIFACT_NAME = "FlashNest-experimental-frame-order-engine"
CHANNEL = "flashnest-frame-order-experimental"
VERSION_NAME = "FlashNest experimental Ruffle 0.7.1 frame-order guard " + PATCH[:12]
FIXTURES = {
    "nested-child-goto.swf": "ae3e561e8695a0be147e2192cd6d067eaa9462daedf92213bed86c9e4c4a4d8b",
    "control-no-child-goto.swf": "dd85e9f2b63b32199b7d04def4efbd80ccf68fb42da63cfe987e94358c49f030",
}
EXPECTATIONS = {
    "nested-repair-target.txt": "57648847e013eb2aaa9e45a91eb0a55c66c97862defd8e3c1cd5b74ef4e3c2ae",
    "control.txt": "cb1f8c5a8f0770d7ed9c92fd3219dc11294746258fa9a4ec8558c82eda9626c0",
    "nested-baseline.txt": "1ef37bcc059380e33b2140536dea771d9b647b8a20bdf01c015a5493269d04ef",
}
REQUIRED_STEPS = (
    "Compile baseline headless test targets",
    "Verify baseline original traces and unchanged upstream goldens",
    "Apply only reviewed queued-goto guard",
    "Compile patched headless test targets",
    "Verify experimental repair target and unchanged upstream goldens",
    "Install pinned Node for optional candidate build",
    "Install optional web build tools",
    "Build isolated dual-WASM candidate (not promoted)",
)
LOCK_KEYS = {
    "schemaVersion", "repository", "workflowPath", "runID", "runAttempt", "headSHA",
    "artifactID", "artifactName", "artifactArchiveSHA256", "provenanceSHA256",
    "upstreamCommit", "patchSHA256", "originalSourceSHA256", "patchedSourceSHA256",
}
MAX_ARCHIVE = 256 * 1024 * 1024
MAX_EXPANDED = 768 * 1024 * 1024
MAX_FILE = 192 * 1024 * 1024


class VerificationError(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise VerificationError(message)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def file_hash(path):
    require(path.is_file() and not path.is_symlink(), f"Not a regular file: {path}")
    result = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            result.update(chunk)
    return result.hexdigest()


def no_duplicate_keys(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, f"Duplicate JSON key: {key}")
        result[key] = value
    return result


def read_json(path):
    require(path.is_file() and not path.is_symlink(), f"Not a regular JSON file: {path}")
    require(path.stat().st_size <= 8 * 1024 * 1024, f"Oversized JSON file: {path}")
    return json.loads(path.read_text(), object_pairs_hook=no_duplicate_keys)


def write_json(path, value):
    path.write_text(json.dumps(value, sort_keys=True, indent=2) + "\n")


def relative_path(name):
    require(isinstance(name, str) and name, "Missing relative path")
    require(not any(ord(c) < 32 for c in name) and "\\" not in name and ":" not in name,
            f"Unsafe path: {name!r}")
    path = PurePosixPath(name)
    require(not path.is_absolute() and all(part not in (".", "..") for part in path.parts), f"Unsafe path: {name}")
    require(path.as_posix() == name and not name.endswith("/"), f"Noncanonical file path: {name}")
    return path


def inventory(root):
    require(root.is_dir() and not root.is_symlink(), f"Not a regular directory: {root}")
    result = {}
    for path in sorted(root.rglob("*")):
        require(not path.is_symlink(), f"Symlink forbidden: {path}")
        if path.is_dir():
            continue
        require(path.is_file(), f"Non-regular file forbidden: {path}")
        name = path.relative_to(root).as_posix()
        relative_path(name)
        result[name] = {"sha256": file_hash(path), "bytes": path.stat().st_size}
    return result


def validate_lock(lock):
    require(isinstance(lock, dict) and set(lock) == LOCK_KEYS, "Unexpected/missing lock fields")
    require(type(lock["schemaVersion"]) is int, "Invalid lock schema type")
    expected = {"schemaVersion": 1, "repository": REPOSITORY, "workflowPath": WORKFLOW,
                "artifactName": ARTIFACT_NAME, "upstreamCommit": PIN, "patchSHA256": PATCH,
                "originalSourceSHA256": ORIGINAL, "patchedSourceSHA256": MODIFIED}
    for key, value in expected.items():
        require(lock.get(key) == value, f"Wrong lock {key}")
    for key in ("runID", "runAttempt", "artifactID"):
        require(type(lock[key]) is int and lock[key] > 0, f"Invalid lock {key}")
    for key in ("artifactArchiveSHA256", "provenanceSHA256"):
        require(isinstance(lock[key], str) and re.fullmatch(r"[0-9a-f]{64}", lock[key]), f"Invalid lock {key}")
    require(isinstance(lock["headSHA"], str) and re.fullmatch(r"[0-9a-f]{40}", lock["headSHA"]), "Invalid experiment head SHA")


def verify_metadata(lock, run, artifact, jobs):
    validate_lock(lock)
    expected_run = {"id": lock["runID"], "run_attempt": lock["runAttempt"], "head_sha": lock["headSHA"],
                    "path": WORKFLOW, "event": "workflow_dispatch", "status": "completed", "conclusion": "success"}
    for key, value in expected_run.items():
        require(run.get(key) == value, f"Wrong run metadata {key}")
    require(run.get("repository", {}).get("full_name") == REPOSITORY, "Wrong run repository")
    require(run.get("head_repository", {}).get("full_name") == REPOSITORY, "Fork/foreign run rejected")
    require(artifact.get("id") == lock["artifactID"] and artifact.get("name") == ARTIFACT_NAME, "Wrong artifact identity")
    require(artifact.get("expired") is False, "Expired/unknown artifact status")
    require(artifact.get("digest") == "sha256:" + lock["artifactArchiveSHA256"], "Artifact API digest does not match reviewed lock")
    require(artifact.get("workflow_run", {}).get("id") == lock["runID"], "Artifact belongs to another run")
    require(artifact.get("workflow_run", {}).get("head_sha") == lock["headSHA"], "Artifact belongs to another head")
    require(type(artifact.get("size_in_bytes")) is int and 0 < artifact["size_in_bytes"] <= MAX_ARCHIVE, "Invalid artifact size")
    rows = jobs.get("jobs")
    require(jobs.get("total_count") == 1 and isinstance(rows, list) and len(rows) == 1, "Expected one complete build job, not a partial job page")
    job = rows[0]
    require(job.get("name") == "validate-and-build" and job.get("run_id") == lock["runID"], "Wrong build job")
    require(job.get("status") == "completed" and job.get("conclusion") == "success", "Build job did not succeed")
    if "run_attempt" in job:
        require(job["run_attempt"] == lock["runAttempt"], "Job attempt differs")
    for name in REQUIRED_STEPS:
        matches = [step for step in job.get("steps", []) if step.get("name") == name]
        require(len(matches) == 1 and matches[0].get("status") == "completed" and matches[0].get("conclusion") == "success",
                f"Required build step missing, skipped, incomplete, or failed: {name}")


def extract_archive(archive, destination, expected_hash, expected_size):
    require(archive.is_file() and not archive.is_symlink(), "Archive must be a regular file")
    require(archive.stat().st_size == expected_size <= MAX_ARCHIVE, "Archive size differs from API metadata")
    require(file_hash(archive) == expected_hash, "Archive SHA256 differs from reviewed lock")
    require(not destination.exists(), "Refusing to overwrite extracted input")
    with zipfile.ZipFile(archive) as bundle:
        entries = bundle.infolist()
        require(0 < len(entries) <= 4096, "Unexpected archive entry count")
        require(sum(entry.file_size for entry in entries) <= MAX_EXPANDED, "Expanded archive exceeds bound")
        names = set()
        for entry in entries:
            name = entry.filename[:-1] if entry.is_dir() else entry.filename
            relative_path(name)
            require(name not in names, f"Duplicate archive path: {name}")
            names.add(name)
            mode = stat.S_IFMT(entry.external_attr >> 16)
            require(mode in (0, stat.S_IFREG, stat.S_IFDIR), f"Archive symlink/special file forbidden: {name}")
            require(not entry.flag_bits & 1 and entry.file_size <= MAX_FILE, f"Encrypted/oversized archive entry: {name}")
            require(name.split("/")[0] in ("frame-order-engine-candidate", "frame-order-engine-evidence"), "Unexpected artifact root")
        destination.mkdir(parents=True)
        for entry in entries:
            target = destination.joinpath(*PurePosixPath(entry.filename).parts)
            if entry.is_dir():
                target.mkdir(parents=True, exist_ok=True)
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                with bundle.open(entry) as source, target.open("xb") as output:
                    shutil.copyfileobj(source, output, length=1024 * 1024)


def verify_candidate(candidate, provenance_hash):
    provenance_path = candidate / "provenance.json"
    require(file_hash(provenance_path) == provenance_hash, "Provenance SHA differs from reviewed lock")
    provenance = read_json(provenance_path)
    expected = {"upstreamCommit": PIN, "upstreamURL": f"https://github.com/ruffle-rs/ruffle/tree/{PIN}",
                "modifiedFile": SOURCE_FILE, "originalFileSHA256": ORIGINAL, "modifiedFileSHA256": MODIFIED,
                "patchSHA256": PATCH, "status": "experimental-unpromoted"}
    for key, value in expected.items():
        require(provenance.get(key) == value, f"Candidate provenance mismatch: {key}")
    files = provenance.get("files")
    require(isinstance(files, dict) and files, "Candidate has no file inventory")
    for name, row in files.items():
        relative_path(name)
        require(isinstance(row, dict) and set(row) == {"sha256", "bytes"}, "Malformed candidate file record")
        require(type(row["bytes"]) is int and row["bytes"] >= 0 and re.fullmatch(r"[0-9a-f]{64}", str(row["sha256"])), "Invalid candidate file record")
    actual = inventory(candidate)
    actual.pop("provenance.json")
    require(actual == files, "Candidate file inventory/size/hash differs, or extra/missing file")
    correspondence = candidate / "source-correspondence"
    for name in ("Cargo.lock", "Cargo.toml", "web/package-lock.json", "web/package.json",
                 "web/version_seal.json", SOURCE_FILE, "LICENSE.md",
                 "web/packages/selfhosted/LICENSE_MIT", "web/packages/selfhosted/LICENSE_APACHE",
                 "queued-goto-guard.patch", "build_web_candidate.sh", "candidate_provenance.py",
                 "workflow-draft.yml", "MODIFICATIONS.md"):
        path = correspondence / name
        require(path.is_file() and not path.is_symlink() and path.stat().st_size > 0, f"Missing source correspondence: {name}")
    require(file_hash(correspondence / SOURCE_FILE) == MODIFIED, "Patched source hash mismatch")
    require(file_hash(correspondence / "queued-goto-guard.patch") == PATCH, "Patch bytes mismatch")
    seal = read_json(correspondence / "web/version_seal.json")
    require(seal == provenance.get("versionSeal"), "Version seal differs from provenance")
    expected_seal = {"version_number": "0.7.1", "version_name": VERSION_NAME, "version_channel": CHANNEL,
                     "commitHash": PIN, "version4": "0.7.1.0", "firefox_extension_id": CHANNEL}
    require(set(seal) == set(expected_seal) | {"build_date"}, "Unexpected version seal fields")
    for key, value in expected_seal.items():
        require(seal.get(key) == value, f"Candidate must identify itself as experimental: {key}")
    epoch = provenance.get("sourceDateEpoch")
    require(type(epoch) is int and epoch > 0, "Invalid source-date epoch")
    expected_date = datetime.fromtimestamp(epoch, timezone.utc).isoformat().replace("+00:00", "Z")
    require(seal["build_date"] == expected_date, "Version seal date/epoch mismatch")
    require(provenance.get("wasmFeatures") == {"dualWasm": True, "additionalCargoFeatures": "jpegxr", "binaryenOptimization": True}, "Unexpected candidate build features")
    runtime = candidate / "runtime"
    runtime_files = inventory(runtime)
    require(len([name for name in runtime_files if name.endswith(".wasm")]) == 2, "Expected both WASM variants")
    require(read_json(runtime / "package.json").get("version") == "0.7.1", "Unexpected upstream package base version")
    script = (runtime / "ruffle.js").read_text()
    for key, expected_value in {"versionNumber": "0.7.1", "versionName": VERSION_NAME, "versionChannel": CHANNEL, "commitHash": PIN}.items():
        values = re.findall(r'(?:\b' + key + r'|"' + key + r'")\s*:\s*("(?:\\.|[^"\\])*")', script)
        require(len(values) == 1 and json.loads(values[0]) == expected_value, f"Runtime JS does not embed the expected derivative identity: {key}")
    for name in ("LICENSE_MIT", "LICENSE_APACHE"):
        require((runtime / name).is_file() and (runtime / name).stat().st_size > 0, f"Missing candidate license: {name}")
    return provenance, runtime_files


def successful_log(path, count):
    text = path.read_text(errors="strict")
    pattern = rf"test result: ok\. {count} passed; 0 failed; 0 ignored;"
    require(len(re.findall(pattern, text)) == 1, f"Missing/ambiguous successful test count: {path.name}")
    require("HARNESS_TIMEOUT" not in text and "test result: FAILED" not in text, f"Failed/timed-out gate: {path.name}")


def verify_gates(evidence, experiment, lock):
    recorded = {}
    for line in (evidence / "run.txt").read_text().splitlines():
        require("=" in line, "Malformed build run identity")
        key, value = line.split("=", 1)
        require(key not in recorded, "Duplicate build run identity key")
        recorded[key] = value
    for key, value in {"repository": REPOSITORY, "experimentCommit": lock["headSHA"],
                       "runID": str(lock["runID"]), "runAttempt": str(lock["runAttempt"])}.items():
        require(recorded.get(key) == value, f"Evidence belongs to another build: {key}")
    config = read_json(experiment / "engine-build/adjacent-tests.json")
    require((evidence / "experiment/engine-build/adjacent-tests.json").read_bytes() ==
            (experiment / "engine-build/adjacent-tests.json").read_bytes(), "Build used another adjacent-test selection")
    require(config.get("sourceCommit") == PIN and len(config.get("tests", [])) == 29 and len(config.get("knownFailureTests", [])) == 2, "Unexpected reviewed adjacent suite")
    selected = config["tests"] + config["knownFailureTests"]
    require(len(set(selected)) == 31, "Duplicate reviewed suite cases")
    summaries = {}
    for phase in ("baseline", "patched"):
        successful_log(evidence / f"{phase}-original.log", 2)
        expected_nested = "nested-baseline.txt" if phase == "baseline" else "nested-repair-target.txt"
        for variant, golden in (("nested-child-goto", expected_nested), ("control-no-child-goto", "control.txt")):
            actual = evidence / phase / "original" / f"{variant}.trace.txt"
            require(file_hash(actual) == EXPECTATIONS[golden], f"Original {phase}/{variant} trace differs from frozen contract")
        folder = evidence / phase / "upstream-goldens"
        summary = read_json(folder / "summary.json")
        for key, value in {"sourceCommit": PIN, "phase": phase, "allPassed": True, "suiteComplete": True,
                           "completedCount": 31, "expectedCount": 31, "strictReferenceCount": 29,
                           "knownFailurePreservationCount": 2}.items():
            require(type(summary.get(key)) is type(value) and summary.get(key) == value,
                    f"Incomplete/incorrect {phase} gate summary: {key}")
        rows = summary.get("tests")
        require(isinstance(rows, list) and [row.get("name") for row in rows] == selected, f"Missing/reordered/duplicate {phase} cases")
        for row in rows:
            name = row["name"]
            known = name in config["knownFailureTests"]
            scope = "preserve-upstream-known-failure-and-ruffle-output" if known else "match-upstream-Flash-reference-output"
            require(row.get("passed") is True and row.get("returncode") == 0 and row.get("scope") == scope, f"Failed/misclassified {phase} case: {name}")
            log_name = name.replace("/", "__") + ".log"
            require(row.get("log") == log_name, "Unexpected per-case log path")
            successful_log(folder / log_name, 1)
            command = ["cargo", "test", "--locked", "-p", "tests", "--test", "tests", "--profile", "ci", name, "--", "--exact", "--test-threads=1"]
            require(row.get("command") == command, f"Unexpected gate command: {name}")
            inputs = row.get("inputSHA256", {})
            expected_inputs = {"test.toml", "test.swf", "output.txt"} | ({"output.ruffle.txt"} if known else set())
            require(set(inputs) == expected_inputs and all(re.fullmatch(r"[0-9a-f]{64}", str(v)) for v in inputs.values()), f"Missing golden input hashes: {name}")
        summaries[phase] = {"strictReferencePassed": 29, "knownFailurePreserved": 2, "originalFixturesPassed": 2,
                            "summarySHA256": file_hash(folder / "summary.json")}
    return summaries


def canonical_trace(lines, expected):
    """Stable first complete tick-12 window; preserve/report all later rows."""
    require(all(isinstance(line, str) for line in lines), "Non-string trace row")
    boundaries = [index for index, line in enumerate(lines) if line.startswith("FO_DONE ")]
    require(len(boundaries) == 1, "Missing/repeated observation boundary")
    boundary = boundaries[0]
    require(re.fullmatch(r"FO_DONE 12 \d+ \d+", lines[boundary]) is not None, "Invalid tick-12 boundary")
    end = boundary + 3
    require(len(lines) >= end and lines[boundary + 1:end] == ["FO_B_LOOP 7", "FO_B_OPENING 5"], "Missing/reordered immediate post-DONE queued-script pair")
    canonical = lines[:end]
    require(canonical == expected, "Experimental trace contract mismatch (no pre-DONE filtering)")
    tail = lines[end:]
    require(len(tail) % 2 == 0 and all(tail[i:i + 2] == ["FO_B_LOOP 7", "FO_B_OPENING 5"] for i in range(0, len(tail), 2)), "Unexpected post-window trace tail")
    return {"canonicalRowCount": len(canonical), "postWindowLoopPairs": len(tail) // 2, "canonicalLines": canonical, "postWindowTail": tail}


def stage_verified(args):
    lock = read_json(args.lock)
    run, artifact, jobs = map(read_json, (args.run_metadata, args.artifact_metadata, args.jobs_metadata))
    verify_metadata(lock, run, artifact, jobs)
    stage = args.stage.absolute()
    require(not stage.exists(), "Stage must not exist; no silent reuse or deletion")
    stage.mkdir(parents=True)
    extracted = stage / "verified-artifact"
    extract_archive(args.archive, extracted, lock["artifactArchiveSHA256"], artifact["size_in_bytes"])
    candidate = extracted / "frame-order-engine-candidate"
    evidence = extracted / "frame-order-engine-evidence"
    experiment = args.repo_root.resolve() / "experiments/frame-order"
    provenance, runtime_files = verify_candidate(candidate, lock["provenanceSHA256"])
    gates = verify_gates(evidence, experiment, lock)
    for name, expected in FIXTURES.items():
        require(file_hash(experiment / "fixtures" / name) == expected, f"Original fixture changed: {name}")
    for name, expected in EXPECTATIONS.items():
        require(file_hash(experiment / "engine-patch/expectations" / name) == expected, f"Frozen expectation changed: {name}")

    web_source = args.repo_root.resolve() / "App/Resources/Web"
    # Do not alter App or merge old official WASM/chunks into the candidate.
    shell_files = {name: value for name, value in inventory(web_source).items() if not name.startswith("runtime/")}
    web = stage / "Web"
    web.mkdir()
    for name in shell_files:
        target = web / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(web_source / name, target)
    shutil.copytree(candidate / "runtime", web / "runtime")
    resource = stage / "frame-order-candidate"
    resource.mkdir()
    for name in FIXTURES:
        shutil.copyfile(experiment / "fixtures" / name, resource / name)
    for name in ("control.txt", "nested-repair-target.txt"):
        shutil.copyfile(experiment / "engine-patch/expectations" / name, resource / name)
    shutil.copyfile(candidate / "provenance.json", resource / "provenance.json")
    shutil.copytree(candidate / "source-correspondence", resource / "source-correspondence")
    shutil.copyfile(args.lock, resource / "candidate.lock.json")
    resource_files = inventory(resource)
    pin = {
        "schemaVersion": 1, "runtimeKind": CHANNEL, "upstreamBaseVersion": "0.7.1",
        "experimentalVersionName": VERSION_NAME, "upstreamSourceCommit": PIN,
        "patchSHA256": PATCH, "originalSourceSHA256": ORIGINAL, "patchedSourceSHA256": MODIFIED,
        "provenanceSHA256": lock["provenanceSHA256"], "lockSHA256": file_hash(args.lock),
        "sourceBuild": lock, "gateSummary": gates, "versionSeal": provenance["versionSeal"],
        "runtimeFiles": runtime_files, "shellFiles": shell_files, "resourceFiles": resource_files,
        "fixtures": {name: resource_files[name] for name in FIXTURES},
        "expectations": {"control-no-child-goto": {"file": "control.txt", "sha256": EXPECTATIONS["control.txt"], "kind": "unchanged recorded pinned control, not Adobe output"},
                         "nested-child-goto": {"file": "nested-repair-target.txt", "sha256": EXPECTATIONS["nested-repair-target.txt"], "kind": "experimental repair target, not Adobe output"}},
        "attestationLimit": "Authenticated workflow chain-of-custody; not a signature, independent clean-build reproduction, upstream approval, or user-game proof",
    }
    pin_path = resource / "candidate-pin.json"
    write_json(pin_path, pin)
    pin_hash = file_hash(pin_path)
    (stage / "FrameOrderCandidateIdentity.generated.swift").write_text(
        "// Generated ONLY after locked artifact/metadata/source/gate verification.\n"
        "enum FrameOrderCandidateIdentity {\n"
        f'    static let pinSHA256 = "{pin_hash}"\n'
        f'    static let lockSHA256 = "{file_hash(args.lock)}"\n'
        "}\n"
    )
    write_json(stage / "verification.json", {"verified": True, "pinSHA256": pin_hash,
        "runtimeKind": CHANNEL, "sourceBuild": lock, "gates": gates,
        "productionFilesModified": False, "nativeExecutionPerformed": False})
    print(json.dumps({"verified": True, "pinSHA256": pin_hash, "stage": str(stage), "nativeExecutionPerformed": False}))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact-zip", "--archive", dest="archive", type=Path, required=True)
    for name in ("lock", "run-metadata", "artifact-metadata", "jobs-metadata", "stage", "repo-root"):
        parser.add_argument("--" + name, type=Path, required=True)
    try:
        stage_verified(parser.parse_args())
    except (VerificationError, OSError, ValueError, KeyError, TypeError, zipfile.BadZipFile) as error:
        raise SystemExit(f"CANDIDATE VERIFICATION FAILED: {error}") from error


if __name__ == "__main__":
    main()

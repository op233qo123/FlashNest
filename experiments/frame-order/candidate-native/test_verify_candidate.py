#!/usr/bin/env python3
"""Pure plumbing/negative tests with synthetic artifacts; never runs Ruffle.

Only the synthetic source hash is mocked for full staging tests. Production
constants, original fixture/contract hashes, and reviewed patch bytes are fixed.
"""
from copy import deepcopy
from datetime import datetime, timezone
import importlib.util
import json
from pathlib import Path
import shutil
import stat
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import zipfile

HERE = Path(__file__).resolve().parent
EXPERIMENT = HERE.parent
spec = importlib.util.spec_from_file_location("candidate_verify", HERE / "verify_candidate.py")
v = importlib.util.module_from_spec(spec)
spec.loader.exec_module(v)


def write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data.encode() if isinstance(data, str) else data)


def lock_template():
    return {"schemaVersion": 1, "repository": v.REPOSITORY, "workflowPath": v.WORKFLOW,
            "runID": 42, "runAttempt": 1, "headSHA": "f" * 40, "artifactID": 43,
            "artifactName": v.ARTIFACT_NAME, "artifactArchiveSHA256": "a" * 64,
            "provenanceSHA256": "b" * 64, "upstreamCommit": v.PIN, "patchSHA256": v.PATCH,
            "originalSourceSHA256": v.ORIGINAL, "patchedSourceSHA256": v.MODIFIED}


def metadata(lock):
    run = {"id": lock["runID"], "run_attempt": lock["runAttempt"], "head_sha": lock["headSHA"],
           "path": v.WORKFLOW, "event": "workflow_dispatch", "status": "completed", "conclusion": "success",
           "repository": {"full_name": v.REPOSITORY}, "head_repository": {"full_name": v.REPOSITORY}}
    artifact = {"id": lock["artifactID"], "name": v.ARTIFACT_NAME, "expired": False,
                "digest": "sha256:" + lock["artifactArchiveSHA256"], "size_in_bytes": 100,
                "workflow_run": {"id": lock["runID"], "head_sha": lock["headSHA"]}}
    jobs = {"total_count": 1, "jobs": [{"name": "validate-and-build", "run_id": lock["runID"],
            "run_attempt": lock["runAttempt"], "status": "completed", "conclusion": "success",
            "steps": [{"name": name, "status": "completed", "conclusion": "success"} for name in v.REQUIRED_STEPS]}]}
    return run, artifact, jobs


class MetadataTests(unittest.TestCase):
    def test_valid_identity(self):
        lock = lock_template()
        v.verify_metadata(lock, *metadata(lock))

    def test_lock_requires_exact_schema_and_reviewed_patch(self):
        for key, value in (("schemaVersion", True), ("runID", None), ("headSHA", "main"),
                           ("artifactArchiveSHA256", "0"), ("patchSHA256", "0" * 64),
                           ("patchedSourceSHA256", "0" * 64), ("upstreamCommit", "0" * 40)):
            with self.subTest(key=key):
                lock = lock_template(); lock[key] = value
                with self.assertRaises(v.VerificationError): v.validate_lock(lock)
        lock = lock_template(); lock["unexpected"] = True
        with self.assertRaises(v.VerificationError): v.validate_lock(lock)

    def test_run_failure_fork_head_attempt_workflow_rejected(self):
        lock = lock_template()
        for key, value in (("status", "in_progress"), ("conclusion", "failure"),
                           ("head_sha", "e" * 40), ("run_attempt", 2), ("path", "foreign.yml"),
                           ("head_repository", {"full_name": "other/fork"})):
            with self.subTest(key=key):
                run, artifact, jobs = metadata(lock); run[key] = value
                with self.assertRaises(v.VerificationError): v.verify_metadata(lock, run, artifact, jobs)

    def test_artifact_drift_expiry_wrong_run_rejected(self):
        lock = lock_template()
        for key, value in (("id", 44), ("expired", True), ("digest", "sha256:" + "0" * 64),
                           ("workflow_run", {"id": 99, "head_sha": lock["headSHA"]})):
            with self.subTest(key=key):
                run, artifact, jobs = metadata(lock); artifact[key] = value
                with self.assertRaises(v.VerificationError): v.verify_metadata(lock, run, artifact, jobs)

    def test_jobs_zero_partial_skipped_duplicate_rejected(self):
        lock = lock_template()
        for mutation in (lambda j: j.update(total_count=2), lambda j: j.update(jobs=[]),
                         lambda j: j["jobs"][0]["steps"].pop(),
                         lambda j: j["jobs"][0]["steps"][0].update(conclusion="skipped"),
                         lambda j: j["jobs"][0]["steps"].append(deepcopy(j["jobs"][0]["steps"][0]))):
            run, artifact, jobs = metadata(lock); mutation(jobs)
            with self.assertRaises(v.VerificationError): v.verify_metadata(lock, run, artifact, jobs)


class ArchiveTests(unittest.TestCase):
    def test_safe_archive_and_hash_size_rejections(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); archive = root / "artifact.zip"
            with zipfile.ZipFile(archive, "w") as z: z.writestr("frame-order-engine-candidate/file.txt", "original")
            v.extract_archive(archive, root / "good", v.file_hash(archive), archive.stat().st_size)
            self.assertEqual((root / "good/frame-order-engine-candidate/file.txt").read_text(), "original")
            with self.assertRaises(v.VerificationError): v.extract_archive(archive, root / "bad", "0" * 64, archive.stat().st_size)
            with self.assertRaises(v.VerificationError): v.extract_archive(archive, root / "bad", v.file_hash(archive), archive.stat().st_size + 1)

    def test_traversal_absolute_backslash_unknown_duplicate_symlink(self):
        cases = ["../escape", "/absolute", "frame-order-engine-candidate/../escape", "frame-order-engine-candidate\\escape", "other-root/a", "frame-order-engine-candidate//a"]
        for name in cases:
            with self.subTest(name=name), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp); archive = root / "artifact.zip"
                with zipfile.ZipFile(archive, "w") as z: z.writestr(name, "x")
                with self.assertRaises(v.VerificationError): v.extract_archive(archive, root / "out", v.file_hash(archive), archive.stat().st_size)
        for kind in ("duplicate", "symlink"):
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp); archive = root / "artifact.zip"
                with zipfile.ZipFile(archive, "w") as z:
                    entry = zipfile.ZipInfo("frame-order-engine-candidate/a")
                    if kind == "symlink": entry.external_attr = (stat.S_IFLNK | 0o777) << 16
                    z.writestr(entry, "target")
                    if kind == "duplicate": z.writestr(entry, "second")
                with self.assertRaises(v.VerificationError): v.extract_archive(archive, root / "out", v.file_hash(archive), archive.stat().st_size)

    def test_directory_inventory_does_not_follow_symlinks(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); (root / "link").symlink_to("/does-not-exist")
            with self.assertRaises(v.VerificationError): v.inventory(root)

    def test_duplicate_json_keys_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "a.json"; path.write_text('{"schemaVersion":1,"schemaVersion":2}')
            with self.assertRaises(v.VerificationError): v.read_json(path)


def make_candidate(root):
    candidate = root / "frame-order-engine-candidate"
    modified = b"Synthetic source ONLY for verification unit tests\n"
    write(candidate / "source-correspondence" / v.SOURCE_FILE, modified)
    source_hash = v.digest(modified)
    write(candidate / "source-correspondence/queued-goto-guard.patch", (EXPERIMENT / "engine-patch/queued-goto-guard.patch").read_bytes())
    seal = {"version_number": "0.7.1", "version_name": v.VERSION_NAME, "version_channel": v.CHANNEL,
            "commitHash": v.PIN, "version4": "0.7.1.0", "firefox_extension_id": v.CHANNEL,
            "build_date": datetime.fromtimestamp(1, timezone.utc).isoformat().replace("+00:00", "Z")}
    (candidate / "source-correspondence/web").mkdir(parents=True, exist_ok=True)
    v.write_json(candidate / "source-correspondence/web/version_seal.json", seal)
    for name in ("Cargo.lock", "Cargo.toml", "web/package-lock.json", "web/package.json", "LICENSE.md",
                 "web/packages/selfhosted/LICENSE_MIT", "web/packages/selfhosted/LICENSE_APACHE", "build_web_candidate.sh",
                 "candidate_provenance.py", "workflow-draft.yml", "MODIFICATIONS.md"):
        write(candidate / "source-correspondence" / name, "Synthetic correspondence unit-test data\n")
    script = "const identity={" + ",".join(key + ":" + json.dumps(value) for key, value in {
        "versionNumber": "0.7.1", "versionName": v.VERSION_NAME, "versionChannel": v.CHANNEL, "commitHash": v.PIN}.items()) + "};"
    write(candidate / "runtime/ruffle.js", script)
    write(candidate / "runtime/one.wasm", b"synthetic-wasm-one-not-executed")
    write(candidate / "runtime/two.wasm", b"synthetic-wasm-two-not-executed")
    write(candidate / "runtime/package.json", '{"version":"0.7.1"}')
    for name in ("LICENSE_MIT", "LICENSE_APACHE"): write(candidate / "runtime" / name, "Synthetic license test text")
    provenance = {"upstreamCommit": v.PIN, "upstreamURL": f"https://github.com/ruffle-rs/ruffle/tree/{v.PIN}",
        "modifiedFile": v.SOURCE_FILE, "originalFileSHA256": v.ORIGINAL, "modifiedFileSHA256": source_hash,
        "patchSHA256": v.PATCH, "status": "experimental-unpromoted", "versionSeal": seal, "sourceDateEpoch": 1,
        "wasmFeatures": {"dualWasm": True, "additionalCargoFeatures": "jpegxr", "binaryenOptimization": True}}
    return candidate, source_hash, provenance


def seal_candidate(candidate, provenance):
    files = v.inventory(candidate); files.pop("provenance.json", None)
    provenance["files"] = files
    v.write_json(candidate / "provenance.json", provenance)
    return v.file_hash(candidate / "provenance.json")


class CandidateTests(unittest.TestCase):
    def test_inventory_and_metadata_tampering_rejected(self):
        for mutation, reseal in (("runtime", False), ("extra", False), ("missing", False),
                                 ("identity", True), ("patch", True), ("source", True),
                                 ("seal", True), ("features", True), ("provenance", False)):
            with self.subTest(mutation=mutation), tempfile.TemporaryDirectory() as tmp:
                candidate, source_hash, provenance = make_candidate(Path(tmp))
                old_hash = seal_candidate(candidate, provenance)
                with patch.object(v, "MODIFIED", source_hash):
                    v.verify_candidate(candidate, old_hash)
                    if mutation == "runtime": write(candidate / "runtime/one.wasm", "tamper")
                    elif mutation == "extra": write(candidate / "runtime/extra.js", "tamper")
                    elif mutation == "missing": (candidate / "runtime/two.wasm").unlink()
                    elif mutation == "identity": write(candidate / "runtime/ruffle.js", (candidate / "runtime/ruffle.js").read_text().replace(v.CHANNEL, "stable"))
                    elif mutation == "patch": write(candidate / "source-correspondence/queued-goto-guard.patch", "tampered patch")
                    elif mutation == "source": write(candidate / "source-correspondence" / v.SOURCE_FILE, "tampered source")
                    elif mutation == "seal": provenance["versionSeal"]["version_channel"] = "stable"
                    elif mutation == "features": provenance["wasmFeatures"]["dualWasm"] = False
                    elif mutation == "provenance": write(candidate / "provenance.json", (candidate / "provenance.json").read_text() + " ")
                    expected_hash = seal_candidate(candidate, provenance) if reseal else old_hash
                    with self.assertRaises(v.VerificationError): v.verify_candidate(candidate, expected_hash)


def make_gate_evidence(root, experiment, lock):
    evidence = root / "frame-order-engine-evidence"
    write(evidence / "run.txt", f"repository={v.REPOSITORY}\nexperimentCommit={lock['headSHA']}\nrunID={lock['runID']}\nrunAttempt={lock['runAttempt']}\n")
    config = v.read_json(experiment / "engine-build/adjacent-tests.json")
    write(evidence / "experiment/engine-build/adjacent-tests.json", (experiment / "engine-build/adjacent-tests.json").read_bytes())
    for phase in ("baseline", "patched"):
        write(evidence / f"{phase}-original.log", "test result: ok. 2 passed; 0 failed; 0 ignored; 0 measured;\n")
        for variant, golden in (("control-no-child-goto", "control.txt"), ("nested-child-goto", "nested-baseline.txt" if phase == "baseline" else "nested-repair-target.txt")):
            write(evidence / phase / "original" / f"{variant}.trace.txt", (experiment / "engine-patch/expectations" / golden).read_bytes())
        rows = []
        for name in config["tests"] + config["knownFailureTests"]:
            known = name in config["knownFailureTests"]
            log_name = name.replace("/", "__") + ".log"
            write(evidence / phase / "upstream-goldens" / log_name, "test result: ok. 1 passed; 0 failed; 0 ignored; 0 measured;\n")
            inputs = ["test.toml", "test.swf", "output.txt"] + (["output.ruffle.txt"] if known else [])
            rows.append({"name": name, "passed": True, "returncode": 0,
                "scope": "preserve-upstream-known-failure-and-ruffle-output" if known else "match-upstream-Flash-reference-output",
                "inputSHA256": {name: "a" * 64 for name in inputs}, "log": log_name,
                "command": ["cargo", "test", "--locked", "-p", "tests", "--test", "tests", "--profile", "ci", name, "--", "--exact", "--test-threads=1"]})
        v.write_json(evidence / phase / "upstream-goldens/summary.json", {"sourceCommit": v.PIN, "phase": phase,
            "tests": rows, "allPassed": True, "suiteComplete": True, "completedCount": 31, "expectedCount": 31,
            "strictReferenceCount": 29, "knownFailurePreservationCount": 2})
    return evidence


class GateTests(unittest.TestCase):
    def test_complete_gates_and_partial_skips_trace_drift_rejected(self):
        for mutation in (None, "partial", "skip", "scope", "trace", "attempt", "selection"):
            with self.subTest(mutation=mutation), tempfile.TemporaryDirectory() as tmp:
                evidence = make_gate_evidence(Path(tmp), EXPERIMENT, lock_template())
                summary_path = evidence / "patched/upstream-goldens/summary.json"
                summary = v.read_json(summary_path)
                if mutation == "partial": summary["suiteComplete"] = False
                elif mutation == "skip": summary["tests"][0]["passed"] = False
                elif mutation == "scope": summary["tests"][-1]["scope"] = "match-upstream-Flash-reference-output"
                elif mutation == "trace": write(evidence / "patched/original/nested-child-goto.trace.txt", "changed")
                elif mutation == "attempt": write(evidence / "run.txt", (evidence / "run.txt").read_text().replace("runAttempt=1", "runAttempt=2"))
                elif mutation == "selection": write(evidence / "experiment/engine-build/adjacent-tests.json", "{}")
                v.write_json(summary_path, summary)
                if mutation is None: self.assertEqual(v.verify_gates(evidence, EXPERIMENT, lock_template())["patched"]["strictReferencePassed"], 29)
                else:
                    with self.assertRaises(v.VerificationError): v.verify_gates(evidence, EXPERIMENT, lock_template())


class TraceTests(unittest.TestCase):
    def test_exact_window_and_extra_complete_loops(self):
        for name in ("control.txt", "nested-repair-target.txt"):
            expected = (EXPERIMENT / "engine-patch/expectations" / name).read_text().splitlines()
            self.assertEqual(v.canonical_trace(expected, expected)["postWindowLoopPairs"], 0)
            extra = ["FO_B_LOOP 7", "FO_B_OPENING 5"] * 3
            result = v.canonical_trace(expected + extra, expected)
            self.assertEqual(result["postWindowTail"], extra)
            self.assertEqual(result["postWindowLoopPairs"], 3)

    def test_missing_reordered_unexpected_and_partial_rows_rejected(self):
        expected = (EXPERIMENT / "engine-patch/expectations/nested-repair-target.txt").read_text().splitlines()
        cases = [expected[:-2], expected + ["FO_DONE 12 2 7"], expected[:4] + ["SURPRISE"] + expected[4:],
                 expected[:4] + expected[5:6] + expected[4:5] + expected[6:],
                 expected[:-2] + ["FO_B_OPENING 5", "FO_B_LOOP 7"],
                 expected + ["FO_B_LOOP 7"], expected + ["SURPRISE", "FO_B_OPENING 5"],
                 [line.replace("FO_DONE 12", "FO_DONE 11") for line in expected]]
        for rows in cases:
            with self.subTest(rows=rows):
                with self.assertRaises(v.VerificationError): v.canonical_trace(rows, expected)


class FullStagingTests(unittest.TestCase):
    def test_synthetic_stage_is_deterministic_and_no_production_file_changes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); artifact_root = root / "artifact"
            candidate, source_hash, provenance = make_candidate(artifact_root)
            provenance_hash = seal_candidate(candidate, provenance)
            fake_repo = root / "repo"
            experiment = fake_repo / "experiments/frame-order"
            for name in ("engine-build/adjacent-tests.json", *["engine-patch/expectations/" + name for name in v.EXPECTATIONS],
                         *["fixtures/" + name for name in v.FIXTURES]):
                write(experiment / name, (EXPERIMENT / name).read_bytes())
            write(fake_repo / "App/Resources/Web/index.html", "<html>original shell</html>")
            write(fake_repo / "App/Resources/Web/shell.js", "// original shell; not executed")
            write(fake_repo / "App/Resources/Web/runtime/old.wasm", "must not be overlaid")
            before = v.inventory(fake_repo)
            with patch.object(v, "MODIFIED", source_hash):
                lock = lock_template(); lock["provenanceSHA256"] = provenance_hash
                make_gate_evidence(artifact_root, experiment, lock)
                archive = root / "artifact.zip"
                with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as bundle:
                    for path in sorted(artifact_root.rglob("*")):
                        if path.is_file(): bundle.write(path, path.relative_to(artifact_root))
                lock["artifactArchiveSHA256"] = v.file_hash(archive)
                run, artifact, jobs = metadata(lock); artifact["size_in_bytes"] = archive.stat().st_size
                for name, value in (("lock", lock), ("run", run), ("artifact", artifact), ("jobs", jobs)):
                    v.write_json(root / (name + ".json"), value)
                def args(stage): return SimpleNamespace(archive=archive, lock=root / "lock.json", run_metadata=root / "run.json",
                    artifact_metadata=root / "artifact.json", jobs_metadata=root / "jobs.json", stage=root / stage, repo_root=fake_repo)
                v.stage_verified(args("stage1")); v.stage_verified(args("stage2"))
                self.assertEqual((root / "stage1/frame-order-candidate/candidate-pin.json").read_bytes(),
                                 (root / "stage2/frame-order-candidate/candidate-pin.json").read_bytes())
                self.assertEqual((root / "stage1/FrameOrderCandidateIdentity.generated.swift").read_bytes(),
                                 (root / "stage2/FrameOrderCandidateIdentity.generated.swift").read_bytes())
                self.assertFalse((root / "stage1/Web/runtime/old.wasm").exists())
                self.assertEqual(v.inventory(fake_repo), before)
                with self.assertRaises(v.VerificationError): v.stage_verified(args("stage1"))


if __name__ == "__main__":
    unittest.main(verbosity=2)

#!/usr/bin/env python3
"""Create an opt-in XcodeGen spec without editing App, Tests, or project.yml."""
import argparse
from pathlib import Path


def project_spec(original: str) -> str:
    web = "      - path: App/Resources/Web\n"
    tests = "    sources:\n      - Tests\n"
    info = "    info:\n      path: App/Info.plist\n"
    if original.count(web) != 1 or original.count(tests) != 1 or original.count(info) != 1:
        raise ValueError("Project resource/test anchors changed; refusing implicit staging")
    result = original.replace(web, "      - path: candidate-native-stage/Web\n")
    result = result.replace(info, "    info:\n      path: candidate-native-stage/Info.plist\n")
    result = result.replace(tests, tests +
        "      - experiments/frame-order/candidate-native/FrameOrderCandidateRuntimeTests.swift\n"
        "      - candidate-native-stage/FrameOrderCandidateIdentity.generated.swift\n"
        "      - path: candidate-native-stage/frame-order-candidate\n"
        "        type: folder\n"
        "        buildPhase: resources\n")
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, required=True)
    args = parser.parse_args()
    root = args.repo_root.resolve()
    output = root / "candidate-native-project.yml"
    if output.exists():
        raise SystemExit("Refusing to overwrite an existing temporary project spec")
    for relative in ("candidate-native-stage/Web/runtime/ruffle.js",
                     "candidate-native-stage/frame-order-candidate",
                     "candidate-native-stage/FrameOrderCandidateIdentity.generated.swift",
                     "experiments/frame-order/candidate-native/FrameOrderCandidateRuntimeTests.swift"):
        if not (root / relative).exists():
            raise SystemExit(f"Missing verified candidate stage input: {relative}")
    output.write_text(project_spec((root / "project.yml").read_text()))
    print("Created isolated candidate-native-project.yml; App and default Tests unchanged")


if __name__ == "__main__":
    main()

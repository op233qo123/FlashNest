import unittest
from pathlib import Path

from stage_project import project_spec


class StageProjectTests(unittest.TestCase):
    def test_resource_repointing_is_only_in_returned_copy(self):
        path = Path(__file__).resolve().parents[3] / "project.yml"
        before = path.read_bytes()
        spec = project_spec(before.decode())
        self.assertEqual(path.read_bytes(), before)
        self.assertNotIn("      - path: App/Resources/Web\n", spec)
        self.assertEqual(spec.count("      - path: candidate-native-stage/Web\n"), 1)
        self.assertEqual(spec.count("      - Tests\n"), 1)
        self.assertEqual(spec.count("FrameOrderCandidateRuntimeTests.swift"), 1)
        self.assertEqual(spec.count("FrameOrderCandidateIdentity.generated.swift"), 1)
        self.assertEqual(spec.count("      - path: candidate-native-stage/frame-order-candidate\n"), 1)
        self.assertIn("      - path: fixtures\n", spec)
        self.assertNotIn("      path: App/Info.plist\n", spec)
        self.assertIn("      path: candidate-native-stage/Info.plist\n", spec)

    def test_missing_or_duplicated_anchors_fail_closed(self):
        minimal = "      - path: App/Resources/Web\n    sources:\n      - Tests\n    info:\n      path: App/Info.plist\n"
        for altered in ("", minimal.replace("App/Resources/Web", "Elsewhere"),
                        minimal + minimal, minimal.replace("      - Tests\n", "")):
            with self.subTest(altered=altered), self.assertRaises(ValueError):
                project_spec(altered)


if __name__ == "__main__":
    unittest.main()

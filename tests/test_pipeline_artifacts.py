from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from tools.pipeline_common import artifacts


class PipelineArtifactTests(unittest.TestCase):
    def test_json_roundtrip_is_stable_and_keeps_non_ascii(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "nested/value.json"
            artifacts.write_json_atomic(path, {"中文": [2, 1]})
            self.assertEqual(artifacts.read_json(path), {"中文": [2, 1]})
            self.assertTrue(path.read_bytes().endswith(b"\n"))
            first = path.read_bytes()
            artifacts.write_json_atomic(path, {"中文": [2, 1]})
            self.assertEqual(path.read_bytes(), first)

    def test_repo_path_rejects_absolute_and_parent_escape(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for value in ("../escape.json", "/tmp/escape.json"):
                with self.assertRaises(artifacts.ArtifactError):
                    artifacts.resolve_repo_path(root, value)

    def test_manifest_build_and_verify(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "a.txt").write_text("甲", encoding="utf-8")
            (root / "nested").mkdir()
            (root / "nested/b.txt").write_text("乙", encoding="utf-8")
            manifest = artifacts.build_manifest(root, ["nested/b.txt", "a.txt"])
            self.assertEqual([row["path"] for row in manifest], ["a.txt", "nested/b.txt"])
            self.assertEqual(artifacts.verify_manifest(root, manifest)["passed"], True)
            (root / "a.txt").write_text("漂移", encoding="utf-8")
            result = artifacts.verify_manifest(root, manifest)
            self.assertFalse(result["passed"])
            self.assertEqual(
                {row["reason"] for row in result["errors"]},
                {"bytes_mismatch", "sha256_mismatch"},
            )

    def test_manifest_rejects_duplicate_paths(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "a.txt").write_text("a", encoding="utf-8")
            with self.assertRaises(artifacts.ArtifactError):
                artifacts.build_manifest(root, ["a.txt", "a.txt"])


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import json
import tempfile
import unittest
import zipfile
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

    def test_repo_relative_identity_is_stable_and_rejects_escape(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            nested = root / "nested/value.json"
            self.assertEqual(
                artifacts.repo_relative_identity(root, nested),
                "nested/value.json",
            )
            self.assertEqual(
                artifacts.repo_relative_identity(root, "nested\\value.json"),
                "nested/value.json",
            )
            for value in (root, root.parent / "escape.json", "../escape.json"):
                with self.assertRaises(artifacts.ArtifactError):
                    artifacts.repo_relative_identity(root, value)

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

    def test_verified_zip_has_manifest_sha_and_crc_receipt(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "bundle.zip"
            receipt = artifacts.write_verified_zip(
                path,
                {
                    "a.txt": "甲".encode(),
                    "nested/b.json": b'{"b": 2}\n',
                },
                metadata={"purpose": "test"},
            )

            self.assertTrue(receipt["passed"])
            self.assertTrue(receipt["crc_passed"])
            self.assertEqual(receipt["payload_count"], 2)
            with zipfile.ZipFile(path) as archive:
                self.assertIsNone(archive.testzip())
                self.assertEqual(
                    set(archive.namelist()),
                    {
                        "a.txt",
                        "nested/b.json",
                        artifacts.ZIP_MANIFEST_NAME,
                        artifacts.ZIP_SHA256SUMS_NAME,
                    },
                )
                manifest = json.loads(
                    archive.read(artifacts.ZIP_MANIFEST_NAME)
                )
                self.assertEqual(manifest["file_count"], 2)
                self.assertEqual(
                    manifest["metadata"]["purpose"],
                    "test",
                )

    def test_verified_zip_rejects_tampered_member(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            original = root / "original.zip"
            tampered = root / "tampered.zip"
            artifacts.write_verified_zip(original, {"a.txt": b"original"})
            with zipfile.ZipFile(original) as source, zipfile.ZipFile(
                tampered,
                "w",
            ) as target:
                for name in source.namelist():
                    data = source.read(name)
                    if name == "a.txt":
                        data = b"tampered"
                    target.writestr(name, data)

            receipt = artifacts.verify_zip_archive(tampered)
            self.assertFalse(receipt["passed"])
            reasons = {row["reason"] for row in receipt["errors"]}
            self.assertIn("manifest_sha256_mismatch", reasons)
            self.assertIn("sha256sums_mismatch", reasons)

    def test_verified_zip_rejects_unsafe_or_reserved_members(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "bundle.zip"
            for payloads in (
                {"../escape.txt": b"x"},
                {"/absolute.txt": b"x"},
                {"C:/windows-absolute.txt": b"x"},
                {"nested//noncanonical.txt": b"x"},
                {artifacts.ZIP_MANIFEST_NAME: b"x"},
            ):
                with self.subTest(payloads=payloads):
                    with self.assertRaises(artifacts.ArtifactError):
                        artifacts.write_verified_zip(path, payloads)

    def test_zip_verifier_rejects_self_consistent_unsafe_paths(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            for index, member in enumerate(
                ("../escape.txt", "C:/windows-absolute.txt")
            ):
                with self.subTest(member=member):
                    path = Path(temporary) / f"unsafe-{index}.zip"
                    payload = b"not allowed outside the extraction root"
                    manifest = (
                        json.dumps(
                            {
                                "schema_version": artifacts.ZIP_MANIFEST_SCHEMA,
                                "file_count": 1,
                                "files": [
                                    {
                                        "path": member,
                                        "bytes": len(payload),
                                        "sha256": artifacts.sha256_bytes(payload),
                                    }
                                ],
                                "metadata": {},
                            },
                            ensure_ascii=False,
                            indent=2,
                            sort_keys=True,
                        )
                        + "\n"
                    ).encode("utf-8")
                    sums = (
                        f"{artifacts.sha256_bytes(payload)}  {member}\n"
                        f"{artifacts.sha256_bytes(manifest)}  "
                        f"{artifacts.ZIP_MANIFEST_NAME}\n"
                    ).encode("utf-8")
                    with zipfile.ZipFile(path, "w") as archive:
                        archive.writestr(member, payload)
                        archive.writestr(
                            artifacts.ZIP_MANIFEST_NAME,
                            manifest,
                        )
                        archive.writestr(
                            artifacts.ZIP_SHA256SUMS_NAME,
                            sums,
                        )

                    receipt = artifacts.verify_zip_archive(path)
                    self.assertFalse(receipt["passed"])
                    reasons = {
                        row["reason"] for row in receipt["errors"]
                    }
                    self.assertIn("unsafe_archive_member_path", reasons)
                    self.assertIn("unsafe_manifest_member_path", reasons)
                    self.assertIn(
                        "unsafe_sha256sums_member_path",
                        reasons,
                    )

    def test_zip_verifier_rejects_self_consistent_manifest_contract_drift(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "invalid-contract.zip"
            payload = b"valid payload"
            manifest = (
                json.dumps(
                    {
                        "schema_version": "bogus-schema",
                        "file_count": 999,
                        "files": [
                            {
                                "path": "payload.txt",
                                "bytes": len(payload),
                                "sha256": artifacts.sha256_bytes(payload),
                            }
                        ],
                        "metadata": {},
                    },
                    ensure_ascii=False,
                    indent=2,
                    sort_keys=True,
                )
                + "\n"
            ).encode("utf-8")
            sums = (
                f"{artifacts.sha256_bytes(payload)}  payload.txt\n"
                f"{artifacts.sha256_bytes(manifest)}  "
                f"{artifacts.ZIP_MANIFEST_NAME}\n"
            ).encode("utf-8")
            with zipfile.ZipFile(path, "w") as archive:
                archive.writestr("payload.txt", payload)
                archive.writestr(artifacts.ZIP_MANIFEST_NAME, manifest)
                archive.writestr(artifacts.ZIP_SHA256SUMS_NAME, sums)

            receipt = artifacts.verify_zip_archive(path)
            self.assertFalse(receipt["passed"])
            reasons = {row["reason"] for row in receipt["errors"]}
            self.assertIn("manifest_schema_version_mismatch", reasons)
            self.assertIn("manifest_file_count_mismatch", reasons)


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import os
from pathlib import Path

import pytest

from tools.experiment_workspace_modules.contracts import (
    ContractError,
    allowlist_contract_sha256,
    parse_plan,
)
from tools.experiment_workspace_modules.security import (
    SecurityError,
    read_regular_file,
    sensitive_rule_for,
)


def _minimum_plan() -> dict:
    return {
        "allowlist_contract_id": "experiment-materialize-allowlist-v1",
        "allowlist_contract_sha256": allowlist_contract_sha256(),
        "capability_limits": {
            "delete_source": False,
            "external_removal": False,
            "materialize_only": True,
            "model_api": False,
            "network": False,
            "notion_write": False,
            "physical_move": False,
            "preflight": False,
        },
        "contract_version": "experiment-materialize-plan-v1",
        "expected_head_sha": "a" * 40,
        "items": [
            {
                "bytes": 2,
                "destination": "workspace/program/a.py",
                "role": "program",
                "sha256": "b" * 64,
                "source": "tools/a.py",
                "source_type": "file",
            }
        ],
        "materializer_bundle_sha256": "c" * 64,
        "plan_id": "test-plan",
        "revision": 1,
        "run_id": "test-run",
        "s0_receipt": {
            "path": (
                "TEMP/restructure_wave_preflight/test/receipt.json"
            ),
            "sha256": "d" * 64,
            "wave_plan_path": (
                "TEMP/restructure_wave_preflight/test/plan.json"
            ),
            "wave_plan_sha256": "e" * 64,
        },
    }


@pytest.mark.parametrize(
    "source",
    [
        "/tmp/a.py",
        "../tools/a.py",
        "tools/../a.py",
        "foundation/a.py",
        "runs/a.py",
        "analysis_library/a.py",
        r"tools\a.py",
        "tools/.git/config",
        "tools/TEMP/result.json",
        "config/__pycache__/secret.pyc",
    ],
)
def test_plan_rejects_sources_outside_the_allowlist(source: str) -> None:
    value = _minimum_plan()
    value["items"][0]["source"] = source
    with pytest.raises(ContractError, match="SOURCE_PATH_NOT_ALLOWED"):
        parse_plan(value)


@pytest.mark.parametrize(
    ("role", "destination"),
    [
        ("program", "../program.py"),
        ("program", "workspace/api/provider.json"),
        ("api", "workspace/program/provider.json"),
        ("unknown", "workspace/program/a.py"),
        ("input", "inputs"),
    ],
)
def test_plan_rejects_destination_role_escape(
    role: str,
    destination: str,
) -> None:
    value = _minimum_plan()
    value["items"][0]["role"] = role
    value["items"][0]["destination"] = destination
    with pytest.raises(ContractError):
        parse_plan(value)


def test_read_regular_file_rejects_symlink_component(tmp_path: Path) -> None:
    real = tmp_path / "real"
    real.mkdir()
    (real / "a.txt").write_text("ok", encoding="utf-8")
    (tmp_path / "linked").symlink_to(real, target_is_directory=True)

    with pytest.raises(SecurityError, match="SYMLINK_REJECTED"):
        read_regular_file(tmp_path, "linked/a.txt")


def test_read_regular_file_rejects_hardlink(tmp_path: Path) -> None:
    source = tmp_path / "source.txt"
    source.write_text("ok", encoding="utf-8")
    os.link(source, tmp_path / "second.txt")

    with pytest.raises(SecurityError, match="HARDLINK_REJECTED"):
        read_regular_file(tmp_path, "source.txt")


@pytest.mark.parametrize(
    ("path", "data", "rule"),
    [
        ("config/.env", b"MODE=test\n", "SENSITIVE_FILENAME"),
        (
            "config/request.txt",
            b"Authorization: Bearer not-a-real-token\n",
            "AUTHORIZATION_HEADER",
        ),
        (
            "config/request.json",
            b'{"Authorization": "Bearer not-a-real-secret-token"}',
            "AUTHORIZATION_HEADER",
        ),
        (
            "config/request.txt",
            b"Bearer not-a-real-secret-token",
            "BEARER_TOKEN",
        ),
        (
            "config/request.txt",
            b"x-api-key: not-a-real-secret\n",
            "API_KEY_HEADER",
        ),
        (
            "config/private.pem",
            b"-----BEGIN PRIVATE KEY-----\n",
            "SENSITIVE_FILENAME",
        ),
        (
            "config/request.json",
            b'{"api_key": "not-a-real-secret-value"}',
            "ASSIGNED_SECRET",
        ),
        (
            "config/path.txt",
            b'"/Users/example/private/input.txt"',
            "PRIVATE_ABSOLUTE_PATH",
        ),
    ],
)
def test_sensitive_scan_returns_rule_id_without_secret(
    path: str,
    data: bytes,
    rule: str,
) -> None:
    assert sensitive_rule_for(path, data) == rule


def test_sensitive_scan_accepts_empty_secret_placeholder() -> None:
    assert sensitive_rule_for(
        "config/request.json",
        b'{"api_key": ""}',
    ) is None

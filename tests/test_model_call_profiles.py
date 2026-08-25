from __future__ import annotations

import hashlib
import json
import os
import shutil
import socket
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Callable

import pytest

from tools import model_call_profiles as profiles
from tools.experiment_workspace_modules.contracts import (
    ALLOWLIST_CONTRACT_ID,
    CAPABILITY_LIMITS,
    PLAN_CONTRACT_VERSION,
    ContractError,
    allowlist_contract_sha256,
    parse_plan,
)


PROJECT_ROOT = profiles.ROOT
CURRENT_BUNDLE_ID = "wave2_synthetic_json_probe_v1"
CURRENT_RESOLVED_GOLDEN = {
    "contract_version": "model-call-resolved-bundle-v1",
    "bundle_id": CURRENT_BUNDLE_ID,
    "profile_id": "qianwen_qwen3_7_flash_json_object_no_thinking",
    "status": "candidate_only_not_wired_to_default_chain",
    "capability_limits": {
        "offline_resolve_only": True,
        "network": False,
        "credential_read": False,
        "request_send": False,
        "model_api": False,
        "notion_write": False,
    },
    "items": [
        {
            "role": "api",
            "source": (
                "config/model_call_profiles/contracts/"
                "qianwen_qwen3_7_flash_json_object_no_thinking/bundle.json"
            ),
            "destination": "workspace/api/contract_bundle.json",
            "bytes": 1952,
            "sha256": (
                "8167fde67c4e6f562c590057a5ee992e1d255951c1a30be5c6c53153fde20c9d"
            ),
            "source_type": "file",
        },
        {
            "role": "api",
            "source": (
                "config/model_call_profiles/contracts/"
                "qianwen_qwen3_7_flash_json_object_no_thinking/"
                "normalization.json"
            ),
            "destination": "workspace/api/normalization.json",
            "bytes": 1231,
            "sha256": (
                "f708694509f805f39df951fdb9e61aa674021e538680ad194c40524ffb2ad770"
            ),
            "source_type": "file",
        },
        {
            "role": "api",
            "source": (
                "config/model_call_profiles/profiles/"
                "qianwen_qwen3_7_flash_json_object_no_thinking.json"
            ),
            "destination": "workspace/api/profile.json",
            "bytes": 1958,
            "sha256": (
                "2b2197f89497dde034df53f7961913a93f617718151b692788942990aed045e7"
            ),
            "source_type": "file",
        },
        {
            "role": "api",
            "source": "config/providers/provider_access_policy.json",
            "destination": "workspace/api/provider_access_policy.json",
            "bytes": 2309,
            "sha256": (
                "2849a80e3bb436d723f866bb1e232beeb5c6fa2bf1bec7a4b53e63f23aa78b3b"
            ),
            "source_type": "file",
        },
        {
            "role": "api",
            "source": "config/providers/qianwen_platform_multi_model.json",
            "destination": "workspace/api/provider_config.json",
            "bytes": 4269,
            "sha256": (
                "0f673dd581a779386b8853c3291ee3eb92d202674e60f021ca06c2cd5b5dbf1d"
            ),
            "source_type": "file",
        },
        {
            "role": "context",
            "source": ("config/context_recipes/wave2_synthetic_json_probe_v1.json"),
            "destination": "workspace/context/recipe.json",
            "bytes": 1934,
            "sha256": (
                "b1ea603ea0d26eadb733ddae43d4b57c49c332d7c8f4976cf5175eb1125f2b8a"
            ),
            "source_type": "file",
        },
        {
            "role": "prompt",
            "source": ("config/prompts/wave2_synthetic_json_probe_v1/manifest.json"),
            "destination": "workspace/prompts/manifest.json",
            "bytes": 911,
            "sha256": (
                "6caf692289f23fc363474f49d3b347e627d13f6f6c07665aaf7b760ebfa479d3"
            ),
            "source_type": "file",
        },
        {
            "role": "prompt",
            "source": "config/prompts/wave2_synthetic_json_probe_v1/prompt.md",
            "destination": "workspace/prompts/prompt.md",
            "bytes": 601,
            "sha256": (
                "145bbf8e9dfd2c3546206f900ac038ab0e83ef6f4dc900455f8996ecf38b307a"
            ),
            "source_type": "file",
        },
        {
            "role": "schema",
            "source": "config/context_recipes/context_recipe.schema.json",
            "destination": "workspace/schemas/context_recipe.schema.json",
            "bytes": 5484,
            "sha256": (
                "5ec995e0da484a37246abd3a30024447db920e7ccb33f1ef827d65294826ff7a"
            ),
            "source_type": "file",
        },
        {
            "role": "schema",
            "source": (
                "config/model_call_profiles/contracts/contract_bundle.schema.json"
            ),
            "destination": "workspace/schemas/contract_bundle.schema.json",
            "bytes": 9663,
            "sha256": (
                "9b087327929b8cba5aa5169556c1183a1c9703620be72d495268ac0416e7b9c7"
            ),
            "source_type": "file",
        },
        {
            "role": "schema",
            "source": "config/model_call_profiles/profile.schema.json",
            "destination": "workspace/schemas/model_call_profile.schema.json",
            "bytes": 6916,
            "sha256": (
                "7c6360752b8c157ba00ee9d23cd8a2b23afd147133f26f96d950b0477d3c9978"
            ),
            "source_type": "file",
        },
        {
            "role": "schema",
            "source": "config/prompts/prompt_manifest.schema.json",
            "destination": "workspace/schemas/prompt_manifest.schema.json",
            "bytes": 2785,
            "sha256": (
                "a344ab412905133bfabea176d885df00216f16b0458d5e1da7c7993124dbb376"
            ),
            "source_type": "file",
        },
        {
            "role": "schema",
            "source": (
                "config/model_call_profiles/contracts/"
                "qianwen_qwen3_7_flash_json_object_no_thinking/"
                "request_envelope.schema.json"
            ),
            "destination": "workspace/schemas/request_envelope.schema.json",
            "bytes": 1913,
            "sha256": (
                "a35bb542923f86a4fc5c0365cfde8c52ce09c4cda604b7f99cf8f4549947138e"
            ),
            "source_type": "file",
        },
        {
            "role": "schema",
            "source": (
                "config/model_call_profiles/contracts/"
                "qianwen_qwen3_7_flash_json_object_no_thinking/"
                "response_envelope.schema.json"
            ),
            "destination": "workspace/schemas/response_envelope.schema.json",
            "bytes": 3525,
            "sha256": (
                "759b80a0cd1a3e5dc759f990426b79e5489e971a4aafbfbc9fd270caaebf67bb"
            ),
            "source_type": "file",
        },
        {
            "role": "schema",
            "source": ("config/contracts/wave2_synthetic_json_probe_v1.schema.json"),
            "destination": "workspace/schemas/task_output.schema.json",
            "bytes": 890,
            "sha256": (
                "9784db4ce48f1eb8cacd6d3470e483c72312a117959a5dfa60d6a54dc5332487"
            ),
            "source_type": "file",
        },
    ],
}


def _write_json(path: Path, value: dict[str, Any]) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _fixture_registry(root: Path) -> dict[str, Any]:
    return _read_json(root / "config/model_call_profiles/registry.json")


def _save_fixture_registry(root: Path, registry: dict[str, Any]) -> None:
    _write_json(root / "config/model_call_profiles/registry.json", registry)


def _bundle_row(
    registry: dict[str, Any],
    bundle_id: str = CURRENT_BUNDLE_ID,
) -> dict[str, Any]:
    matches = [row for row in registry["rule_bundles"] if row["bundle_id"] == bundle_id]
    assert len(matches) == 1
    return matches[0]


def _material_item(
    row: dict[str, Any],
    source: str,
) -> dict[str, Any]:
    matches = [item for item in row["materialize_items"] if item["source"] == source]
    assert len(matches) == 1
    return matches[0]


def _set_main_reference_digest(
    row: dict[str, Any],
    field: str,
    digest: str,
) -> None:
    row[field]["sha256"] = digest
    _material_item(row, row[field]["path"])["sha256"] = digest


def _install_bundle_fixture(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> Path:
    root = tmp_path / "repo"
    root.mkdir(parents=True)
    shutil.copytree(PROJECT_ROOT / "config", root / "config")
    config_root = root / "config/model_call_profiles"
    monkeypatch.setattr(profiles, "ROOT", root)
    monkeypatch.setattr(profiles, "CONFIG_ROOT", config_root)
    monkeypatch.setattr(
        profiles,
        "REGISTRY_PATH",
        config_root / "registry.json",
    )
    monkeypatch.setattr(
        profiles,
        "PROFILE_SCHEMA_PATH",
        config_root / "profile.schema.json",
    )
    monkeypatch.setattr(
        profiles,
        "CONTRACT_BUNDLE_SCHEMA_PATH",
        config_root / "contracts/contract_bundle.schema.json",
    )
    monkeypatch.setattr(
        profiles,
        "PROMPT_MANIFEST_SCHEMA_PATH",
        root / "config/prompts/prompt_manifest.schema.json",
    )
    monkeypatch.setattr(
        profiles,
        "CONTEXT_RECIPE_SCHEMA_PATH",
        root / "config/context_recipes/context_recipe.schema.json",
    )

    registry = _fixture_registry(root)
    schema_sources = {
        path.relative_to(root).as_posix()
        for path in profiles._fixed_validation_schema_paths().values()
    }
    for row in registry["rule_bundles"]:
        for source in schema_sources:
            _material_item(row, source)["sha256"] = _sha256(root / source)
    _save_fixture_registry(root, registry)
    return root


def _expected_resolved(
    root: Path,
    row: dict[str, Any],
) -> dict[str, Any]:
    return {
        "contract_version": "model-call-resolved-bundle-v1",
        "bundle_id": row["bundle_id"],
        "profile_id": row["profile_id"],
        "status": row["status"],
        "capability_limits": deepcopy(profiles.RESOLVED_CAPABILITY_LIMITS),
        "items": [
            {
                "role": item["role"],
                "source": item["source"],
                "destination": item["destination"],
                "bytes": (root / item["source"]).stat().st_size,
                "sha256": item["sha256"],
                "source_type": "file",
            }
            for item in sorted(
                row["materialize_items"],
                key=lambda value: value["destination"],
            )
        ],
    }


def _add_second_bundle(
    root: Path,
    *,
    bundle_id: str = "alternate_json_probe_v1",
) -> dict[str, Any]:
    registry = _fixture_registry(root)
    original = _bundle_row(registry)
    new_row = deepcopy(original)
    new_row["bundle_id"] = bundle_id

    old_prompt_dir = root / f"config/prompts/{CURRENT_BUNDLE_ID}"
    new_prompt_dir = root / f"config/prompts/{bundle_id}"
    shutil.copytree(old_prompt_dir, new_prompt_dir)
    prompt_path = new_prompt_dir / "prompt.md"
    manifest_path = new_prompt_dir / "manifest.json"
    manifest = _read_json(manifest_path)
    old_manifest_source = original["prompt_manifest"]["path"]
    old_prompt_source = manifest["prompt_file"]["path"]
    new_manifest_source = manifest_path.relative_to(root).as_posix()
    new_prompt_source = prompt_path.relative_to(root).as_posix()
    manifest["prompt_id"] = bundle_id
    manifest["prompt_file"]["path"] = new_prompt_source
    manifest["prompt_file"]["sha256"] = _sha256(prompt_path)
    _write_json(manifest_path, manifest)
    manifest_digest = _sha256(manifest_path)

    old_context_source = original["context_recipe"]["path"]
    context_path = root / f"config/context_recipes/{bundle_id}.json"
    context = _read_json(root / old_context_source)
    context["recipe_id"] = bundle_id
    context["prompt_manifest"] = {
        "path": new_manifest_source,
        "sha256": manifest_digest,
    }
    _write_json(context_path, context)
    context_source = context_path.relative_to(root).as_posix()
    context_digest = _sha256(context_path)

    new_row["prompt_manifest"] = {
        "path": new_manifest_source,
        "sha256": manifest_digest,
    }
    new_row["context_recipe"] = {
        "path": context_source,
        "sha256": context_digest,
    }
    replacements = {
        old_manifest_source: (new_manifest_source, manifest_digest),
        old_prompt_source: (new_prompt_source, _sha256(prompt_path)),
        old_context_source: (context_source, context_digest),
    }
    for item in new_row["materialize_items"]:
        replacement = replacements.get(item["source"])
        if replacement is not None:
            item["source"], item["sha256"] = replacement
    new_row["materialize_items"].sort(key=lambda item: item["destination"])

    registry["rule_bundles"] = [new_row, *registry["rule_bundles"]]
    _save_fixture_registry(root, registry)
    return new_row


def _reseal_context(
    root: Path,
    mutate: Callable[[dict[str, Any]], None],
) -> None:
    registry = _fixture_registry(root)
    row = _bundle_row(registry)
    path = root / row["context_recipe"]["path"]
    context = _read_json(path)
    mutate(context)
    _write_json(path, context)
    _set_main_reference_digest(row, "context_recipe", _sha256(path))
    _save_fixture_registry(root, registry)


def _propagate_api_digest(
    root: Path,
    registry: dict[str, Any],
    row: dict[str, Any],
    api_digest: str,
) -> None:
    _set_main_reference_digest(row, "api_contract_bundle", api_digest)
    context_path = root / row["context_recipe"]["path"]
    context = _read_json(context_path)
    context["api_contract_bundle"]["sha256"] = api_digest
    _write_json(context_path, context)
    _set_main_reference_digest(row, "context_recipe", _sha256(context_path))
    _save_fixture_registry(root, registry)


def _reseal_api_bundle(
    root: Path,
    mutate: Callable[[dict[str, Any]], None],
) -> None:
    registry = _fixture_registry(root)
    row = _bundle_row(registry)
    api_path = root / row["api_contract_bundle"]["path"]
    api = _read_json(api_path)
    mutate(api)
    _write_json(api_path, api)
    _propagate_api_digest(root, registry, row, _sha256(api_path))


def _reseal_api_dependency(
    root: Path,
    dependency_name: str,
    mutate: Callable[[dict[str, Any]], None],
) -> None:
    registry = _fixture_registry(root)
    row = _bundle_row(registry)
    api_path = root / row["api_contract_bundle"]["path"]
    api = _read_json(api_path)
    dependency_path = root / api[dependency_name]["path"]
    dependency = _read_json(dependency_path)
    mutate(dependency)
    _write_json(dependency_path, dependency)
    dependency_digest = _sha256(dependency_path)
    api[dependency_name]["sha256"] = dependency_digest
    _material_item(row, api[dependency_name]["path"])["sha256"] = dependency_digest
    _write_json(api_path, api)
    _propagate_api_digest(root, registry, row, _sha256(api_path))


def _reseal_task_schema(
    root: Path,
    mutate: Callable[[dict[str, Any]], None],
) -> None:
    registry = _fixture_registry(root)
    row = _bundle_row(registry)
    task_path = root / row["task_output_schema"]["path"]
    task = _read_json(task_path)
    mutate(task)
    _write_json(task_path, task)
    task_digest = _sha256(task_path)
    _set_main_reference_digest(row, "task_output_schema", task_digest)

    prompt_path = root / row["prompt_manifest"]["path"]
    prompt = _read_json(prompt_path)
    prompt["task_output_schema"]["sha256"] = task_digest
    _write_json(prompt_path, prompt)
    prompt_digest = _sha256(prompt_path)
    _set_main_reference_digest(row, "prompt_manifest", prompt_digest)

    context_path = root / row["context_recipe"]["path"]
    context = _read_json(context_path)
    context["task_output_schema"]["sha256"] = task_digest
    context["prompt_manifest"]["sha256"] = prompt_digest
    _write_json(context_path, context)
    _set_main_reference_digest(row, "context_recipe", _sha256(context_path))
    _save_fixture_registry(root, registry)


def _assert_bundle_rejected(fragment: str | None = None) -> None:
    errors = profiles.validate_all_rule_bundles()
    assert len(errors) == 1
    if fragment is not None:
        assert fragment in errors[0]


def test_all_model_call_profiles_are_mechanically_valid() -> None:
    assert profiles.validate_all_profiles() == []


def test_qwen_thinking_profile_keeps_reasoning_and_avoids_incompatible_json_mode() -> (
    None
):
    profile = profiles.load_profile("qianwen_qwen3_7_flash_thinking_prompt_json")
    request = profiles.render_qianwen_request(
        profile,
        [
            {"role": "system", "content": "只返回 JSON 对象。"},
            {"role": "user", "content": "抽取本章事实。"},
        ],
    )
    body = request["body"]
    assert body["model"] == "qwen3.7-flash"
    assert body["temperature"] == 0.2
    assert body["stream"] is True
    assert body["enable_thinking"] is True
    assert body["thinking_budget"] == 32768
    assert body["stream_options"] == {"include_usage": True}
    assert "response_format" not in body
    assert "max_tokens" not in body
    assert request["expected_response_model"] == "qwen3.7-flash"


def test_qwen_json_object_profile_closes_thinking_and_omits_output_cap() -> None:
    profile = profiles.load_profile("qianwen_qwen3_7_flash_json_object_no_thinking")
    request = profiles.render_qianwen_request(
        profile,
        [{"role": "user", "content": "请只输出 JSON。"}],
    )
    body = request["body"]
    assert body["enable_thinking"] is False
    assert body["response_format"] == {"type": "json_object"}
    assert body["stream"] is False
    assert "max_tokens" not in body
    assert "thinking_budget" not in body


def test_agent_plan_profiles_keep_legacy_render_contract() -> None:
    cases = [
        (
            "agent_plan_deepseek_v4_flash_high_json_object",
            "deepseek-v4-flash-modelhub",
            "deepseek-v4-flash-260425",
            "high",
        ),
        (
            "agent_plan_deepseek_v4_pro_high_json_object",
            "deepseek-v4-pro-modelhub",
            "deepseek-v4-pro-260425",
            "high",
        ),
        (
            "agent_plan_minimax_m3_thinking_json_object",
            "minimax-m3-modelhub",
            "minimax-m3",
            None,
        ),
    ]
    for profile_id, request_model, response_model, effort in cases:
        profile = profiles.load_profile(profile_id)
        preview = profiles.render_agent_plan_command(
            profile,
            prompt="抽取本章事实，只返回 JSON。",
        )
        argv = preview["argv"]
        assert argv[:12] == [
            "env",
            "-u",
            "ARK_API_KEY",
            "-u",
            "ARK_BASE_URL",
            "-u",
            "ARK_REGION",
            "-u",
            "ARK_PROFILE",
            "-u",
            "VOLCENGINE_AGENT_PLAN_API_KEY",
            "arkcli",
        ]
        assert argv[argv.index("--model") + 1] == request_model
        assert preview["expected_response_model"] == response_model
        assert "--max-output-tokens" not in argv
        if effort is None:
            assert "--reasoning-effort" not in argv
        else:
            assert argv[argv.index("--reasoning-effort") + 1] == effort


def test_registry_keeps_legacy_preferred_profiles_and_cli_shape(
    capsys: pytest.CaptureFixture[str],
) -> None:
    registry = profiles.load_registry()
    assert registry["preferred_profiles"] == {
        "qwen3.7-flash": "qianwen_qwen3_7_flash_thinking_prompt_json",
        "deepseek-v4-flash": "agent_plan_deepseek_v4_flash_high_json_object",
        "deepseek-v4-pro": "agent_plan_deepseek_v4_pro_high_json_object",
        "minimax-m3": "agent_plan_minimax_m3_thinking_json_object",
    }
    assert profiles.command_list(SimpleNamespace()) == 0
    lines = capsys.readouterr().out.splitlines()
    assert len(lines) == 5
    assert all(len(line.split("\t")) == 3 for line in lines)
    parsed = profiles.parser().parse_args(["show", lines[0].split("\t")[1]])
    assert parsed.command == "show"
    parsed = profiles.parser().parse_args(
        [
            "render",
            "qianwen_qwen3_7_flash_json_object_no_thinking",
            "--input",
            "payload.json",
        ]
    )
    assert parsed.command == "render"


def test_generic_schemas_accept_current_data_and_contain_no_route_constants() -> None:
    registry = profiles.load_registry()
    row = _bundle_row(registry)
    pairs = [
        (
            profiles.CONTRACT_BUNDLE_SCHEMA_PATH,
            PROJECT_ROOT / row["api_contract_bundle"]["path"],
        ),
        (
            profiles.CONTEXT_RECIPE_SCHEMA_PATH,
            PROJECT_ROOT / row["context_recipe"]["path"],
        ),
    ]
    for schema_path, instance_path in pairs:
        schema = _read_json(schema_path)
        instance = _read_json(instance_path)
        DraftValidator = profiles.Draft202012Validator
        DraftValidator.check_schema(schema)
        assert list(DraftValidator(schema).iter_errors(instance)) == []
        text = schema_path.read_text(encoding="utf-8").casefold()
        for forbidden in ("qianwen", "qwen3", "dashscope", "wave2", "synthetic_case"):
            assert forbidden not in text


def test_current_registered_rule_bundle_is_live_valid() -> None:
    assert profiles.validate_all_rule_bundles() == []
    assert profiles.resolve_rule_bundle(CURRENT_BUNDLE_ID) == CURRENT_RESOLVED_GOLDEN


def test_current_bundle_has_full_resolved_json_regression(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _install_bundle_fixture(tmp_path, monkeypatch)
    assert len(CURRENT_RESOLVED_GOLDEN["items"]) == 15
    assert profiles.resolve_rule_bundle(CURRENT_BUNDLE_ID) == CURRENT_RESOLVED_GOLDEN
    assert (
        profiles.command_resolve_bundle(SimpleNamespace(bundle_id=CURRENT_BUNDLE_ID))
        == 0
    )
    assert capsys.readouterr().out == (
        json.dumps(CURRENT_RESOLVED_GOLDEN, ensure_ascii=False, indent=2) + "\n"
    )


def test_second_data_only_bundle_validates_lists_and_resolves(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    root = _install_bundle_fixture(tmp_path, monkeypatch)
    before = profiles.resolve_rule_bundle(CURRENT_BUNDLE_ID)
    second = _add_second_bundle(root)

    assert profiles.validate_all_rule_bundles() == []
    assert [row["bundle_id"] for row in profiles.list_rule_bundles()] == [
        "alternate_json_probe_v1",
        CURRENT_BUNDLE_ID,
    ]
    assert profiles.resolve_rule_bundle(second["bundle_id"]) == _expected_resolved(
        root,
        second,
    )
    assert profiles.resolve_rule_bundle(CURRENT_BUNDLE_ID) == before

    assert profiles.command_validate(SimpleNamespace()) == 0
    assert "5 个模型调用档和 2 个规则包" in capsys.readouterr().out
    assert profiles.command_list_bundles(SimpleNamespace()) == 0
    lines = capsys.readouterr().out.splitlines()
    assert [line.split("\t")[1] for line in lines] == [
        "alternate_json_probe_v1",
        CURRENT_BUNDLE_ID,
    ]
    assert (
        profiles.command_show_bundle(SimpleNamespace(bundle_id=second["bundle_id"]))
        == 0
    )
    assert json.loads(capsys.readouterr().out) == second


def test_context_recipe_can_add_finite_slots_and_messages_without_code_change(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_bundle_fixture(tmp_path, monkeypatch)

    def mutate(context: dict[str, Any]) -> None:
        context["input_slots"]["auxiliary"] = {
            "required": True,
            "content_type": "text/plain",
            "serialization": "utf8",
            "max_bytes": 256,
        }
        context["message_plan"].append(
            {"role": "user", "content_from": "input_slots.auxiliary"}
        )
        context["assembly_policy"]["mode"] = "strict_three_messages"

    _reseal_context(profiles.ROOT, mutate)
    assert profiles.validate_all_rule_bundles() == []


def test_destination_names_are_derived_from_data(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = _install_bundle_fixture(tmp_path, monkeypatch)
    registry = _fixture_registry(root)
    row = _bundle_row(registry)
    prompt_item = next(
        item
        for item in row["materialize_items"]
        if item["role"] == "prompt" and item["destination"].endswith("manifest.json")
    )
    prompt_item["destination"] = "workspace/prompts/renamed.json"
    row["materialize_items"].sort(key=lambda item: item["destination"])
    _save_fixture_registry(root, registry)
    resolved = profiles.resolve_rule_bundle(CURRENT_BUNDLE_ID)
    assert any(
        item["destination"] == "workspace/prompts/renamed.json"
        for item in resolved["items"]
    )


def test_resolved_items_bridge_into_experiment_workspace_plan(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_bundle_fixture(tmp_path, monkeypatch)
    resolved = profiles.resolve_rule_bundle(CURRENT_BUNDLE_ID)
    additions = [
        {
            "role": "input",
            "source": "tests/fixtures/experiment_workspace/input.json",
            "destination": "inputs/case.json",
            "bytes": 2,
            "sha256": "1" * 64,
            "source_type": "file",
        },
        {
            "role": "program",
            "source": "tools/model_call_profiles.py",
            "destination": "workspace/program/model_call_profiles.py",
            "bytes": 2,
            "sha256": "2" * 64,
            "source_type": "file",
        },
    ]
    plan = {
        "contract_version": PLAN_CONTRACT_VERSION,
        "plan_id": "resolver bridge",
        "run_id": "resolver_bridge_r01",
        "revision": 1,
        "expected_head_sha": "a" * 40,
        "s0_receipt": {
            "path": "TEMP/restructure_wave_preflight/receipt.json",
            "sha256": "b" * 64,
            "wave_plan_path": "TEMP/restructure_wave_preflight/plan.json",
            "wave_plan_sha256": "c" * 64,
        },
        "materializer_bundle_sha256": "d" * 64,
        "allowlist_contract_id": ALLOWLIST_CONTRACT_ID,
        "allowlist_contract_sha256": allowlist_contract_sha256(),
        "capability_limits": CAPABILITY_LIMITS,
        "items": sorted(
            [*resolved["items"], *additions],
            key=lambda item: item["destination"],
        ),
    }
    parsed = parse_plan(plan)
    assert len(parsed.items) == len(resolved["items"]) + 2

    with pytest.raises(ContractError, match="PLAN_SHAPE_INVALID"):
        parse_plan(resolved)
    unsorted = deepcopy(plan)
    unsorted["items"] = [*resolved["items"], *additions]
    with pytest.raises(ContractError, match="ITEMS_NOT_SORTED"):
        parse_plan(unsorted)


def test_missing_and_extra_material_are_rejected(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = _install_bundle_fixture(tmp_path, monkeypatch)
    registry = _fixture_registry(root)
    row = _bundle_row(registry)
    prompt_source = _read_json(root / row["prompt_manifest"]["path"])["prompt_file"][
        "path"
    ]
    row["materialize_items"] = [
        item for item in row["materialize_items"] if item["source"] != prompt_source
    ]
    _save_fixture_registry(root, registry)
    _assert_bundle_rejected("缺少物化项")

    root = _install_bundle_fixture(tmp_path / "extra", monkeypatch)
    registry = _fixture_registry(root)
    row = _bundle_row(registry)
    extra_path = root / "config/prompts/extra.md"
    extra_path.write_text("JSON\n", encoding="utf-8")
    row["materialize_items"].append(
        {
            "source": "config/prompts/extra.md",
            "destination": "workspace/prompts/extra.md",
            "role": "prompt",
            "sha256": _sha256(extra_path),
        }
    )
    row["materialize_items"].sort(key=lambda item: item["destination"])
    _save_fixture_registry(root, registry)
    _assert_bundle_rejected("多出")


def test_cross_references_and_unknown_fields_are_rejected(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = _install_bundle_fixture(tmp_path, monkeypatch)
    _reseal_context(
        root,
        lambda value: value.__setitem__(
            "profile_id",
            "qianwen_qwen3_7_flash_thinking_prompt_json",
        ),
    )
    _assert_bundle_rejected("context_recipe.profile_id")

    root = _install_bundle_fixture(tmp_path / "unknown", monkeypatch)
    registry = _fixture_registry(root)
    _bundle_row(registry)["unexpected"] = True
    _save_fixture_registry(root, registry)
    _assert_bundle_rejected("Additional properties")


@pytest.mark.parametrize(
    "bad_path",
    [
        "/tmp/outside.json",
        "config/prompts/../outside.json",
    ],
)
def test_absolute_and_parent_paths_are_rejected(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    bad_path: str,
) -> None:
    root = _install_bundle_fixture(tmp_path, monkeypatch)
    registry = _fixture_registry(root)
    row = _bundle_row(registry)
    row["materialize_items"][0]["source"] = bad_path
    _save_fixture_registry(root, registry)
    _assert_bundle_rejected()


@pytest.mark.parametrize("link_kind", ["symlink", "hardlink", "fifo"])
def test_nonregular_and_linked_sources_are_rejected(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    link_kind: str,
) -> None:
    root = _install_bundle_fixture(tmp_path, monkeypatch)
    registry = _fixture_registry(root)
    row = _bundle_row(registry)
    manifest = _read_json(root / row["prompt_manifest"]["path"])
    source = root / manifest["prompt_file"]["path"]
    original = source.read_bytes()
    backup = source.with_name(f"{link_kind}_target.md")
    backup.write_bytes(original)
    source.unlink()
    if link_kind == "symlink":
        source.symlink_to(backup.name)
    elif link_kind == "hardlink":
        os.link(backup, source)
    else:
        os.mkfifo(source)
    _assert_bundle_rejected()


def test_symlinked_parent_directory_is_rejected(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = _install_bundle_fixture(tmp_path, monkeypatch)
    prompt_dir = root / f"config/prompts/{CURRENT_BUNDLE_ID}"
    real_dir = prompt_dir.with_name(f"{CURRENT_BUNDLE_ID}_real")
    prompt_dir.rename(real_dir)
    prompt_dir.symlink_to(real_dir.name, target_is_directory=True)
    _assert_bundle_rejected("父目录不得是软链")


def test_sha_drift_and_read_race_are_rejected(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = _install_bundle_fixture(tmp_path, monkeypatch)
    registry = _fixture_registry(root)
    row = _bundle_row(registry)
    row["materialize_items"][0]["sha256"] = "0" * 64
    _save_fixture_registry(root, registry)
    _assert_bundle_rejected("SHA")

    root = _install_bundle_fixture(tmp_path / "race", monkeypatch)
    registry = _fixture_registry(root)
    target = _read_json(root / _bundle_row(registry)["prompt_manifest"]["path"])[
        "prompt_file"
    ]["path"]
    original_read = profiles._read_registered_bytes
    calls = 0

    def racing_read(path: str) -> bytes:
        nonlocal calls
        raw = original_read(path)
        if path == target:
            calls += 1
            if calls > 1:
                return raw + b" "
        return raw

    monkeypatch.setattr(profiles, "_read_registered_bytes", racing_read)
    _assert_bundle_rejected("发生变化")


@pytest.mark.parametrize(
    "dependency_name",
    ["request_envelope_schema", "response_envelope_schema"],
)
def test_api_schemas_reject_external_references(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    dependency_name: str,
) -> None:
    root = _install_bundle_fixture(tmp_path, monkeypatch)
    _reseal_api_dependency(
        root,
        dependency_name,
        lambda value: value.__setitem__("$ref", "https://example.invalid/x"),
    )
    _assert_bundle_rejected("禁止外部 Schema 引用")


def test_task_schema_rejects_external_references_and_invalid_draft_schema(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = _install_bundle_fixture(tmp_path, monkeypatch)
    _reseal_task_schema(
        root,
        lambda value: value.__setitem__("$ref", "https://example.invalid/x"),
    )
    _assert_bundle_rejected("禁止外部 Schema 引用")

    root = _install_bundle_fixture(tmp_path / "invalid", monkeypatch)
    _reseal_api_dependency(
        root,
        "request_envelope_schema",
        lambda value: value.__setitem__("type", "not-a-json-schema-type"),
    )
    _assert_bundle_rejected("不是有效的 Draft 2020-12 Schema")


@pytest.mark.parametrize(
    "mutate",
    [
        pytest.param(
            lambda value: value["properties"]["temperature"].__setitem__(
                "const",
                0.9,
            ),
            id="temperature-const-drift",
        ),
        pytest.param(
            lambda value: (
                value["properties"]["temperature"].clear()
                or value["properties"]["temperature"].__setitem__("type", "number")
            ),
            id="temperature-no-longer-frozen",
        ),
        pytest.param(
            lambda value: value["properties"]["temperature"].__setitem__(
                "type",
                "string",
            ),
            id="temperature-const-conflicts-with-type",
        ),
        pytest.param(
            lambda value: value["properties"]["model"].__setitem__(
                "pattern",
                "^never-the-registered-model$",
            ),
            id="model-const-conflicts-with-pattern",
        ),
        pytest.param(
            lambda value: value["properties"]["stream"].__setitem__(
                "const",
                True,
            ),
            id="stream-const-drift",
        ),
        pytest.param(
            lambda value: value["required"].remove("stream"),
            id="stream-not-required",
        ),
        pytest.param(
            lambda value: value["properties"]["enable_thinking"].__setitem__(
                "const",
                True,
            ),
            id="scalar-provider-parameter-drift",
        ),
        pytest.param(
            lambda value: value["properties"]["response_format"]["properties"][
                "type"
            ].__setitem__("const", "other"),
            id="nested-provider-parameter-drift",
        ),
        pytest.param(
            lambda value: value["properties"]["response_format"]["properties"][
                "type"
            ].__setitem__("maxLength", 0),
            id="nested-provider-value-is-unsatisfiable",
        ),
        pytest.param(
            lambda value: value["properties"]["response_format"].__setitem__(
                "const",
                {"type": "not-json-object"},
            ),
            id="provider-object-const-conflicts-with-actual-value",
        ),
        pytest.param(
            lambda value: value["properties"]["response_format"].__setitem__(
                "additionalProperties",
                True,
            ),
            id="nested-provider-parameter-expansion",
        ),
        pytest.param(
            lambda value: value.__setitem__("additionalProperties", True),
            id="request-expansion",
        ),
        pytest.param(
            lambda value: value.__setitem__("maxProperties", 0),
            id="request-root-is-unsatisfiable",
        ),
        pytest.param(
            lambda value: value["properties"]["messages"].__setitem__(
                "type",
                "string",
            ),
            id="messages-reject-actual-array",
        ),
        pytest.param(
            lambda value: value["$defs"]["message"]["properties"]["role"].__setitem__(
                "enum",
                ["assistant"],
            ),
            id="messages-reject-context-roles",
        ),
        pytest.param(
            lambda value: value["$defs"]["message"]["properties"][
                "content"
            ].__setitem__("pattern", "JSON"),
            id="messages-reject-valid-input-slot-sample",
        ),
        pytest.param(
            lambda value: value["properties"]["messages"].__setitem__(
                "items",
                {"$ref": "#/$defs/missing"},
            ),
            id="missing-message-ref-fails-closed",
        ),
        pytest.param(
            lambda value: value["properties"].__setitem__(
                "max_tokens",
                {"type": "integer"},
            ),
            id="forbidden-request-property",
        ),
    ],
)
def test_profile_to_request_schema_drift_is_rejected_after_full_reseal(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    mutate: Callable[[dict[str, Any]], None],
) -> None:
    root = _install_bundle_fixture(tmp_path, monkeypatch)
    _reseal_api_dependency(root, "request_envelope_schema", mutate)
    _assert_bundle_rejected()


@pytest.mark.parametrize(
    "mutation",
    ["add-unknown", "delete-known", "override-core"],
)
def test_profile_provider_parameters_must_exactly_match_request_schema(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    mutation: str,
) -> None:
    root = _install_bundle_fixture(tmp_path, monkeypatch)

    def mutate(profile: dict[str, Any]) -> None:
        parameters = profile["json_output"]["provider_parameters"]
        if mutation == "add-unknown":
            parameters["unregistered_flag"] = False
        elif mutation == "delete-known":
            del parameters["enable_thinking"]
        else:
            parameters["model"] = profile["model_binding"]["request_model_id"]

    _reseal_api_dependency(root, "profile", mutate)
    _assert_bundle_rejected()


@pytest.mark.parametrize(
    "mutate",
    [
        pytest.param(
            lambda value: value["$defs"]["choice"]["properties"][
                "finish_reason"
            ].__setitem__("const", "length"),
            id="finish-reason-drift",
        ),
        pytest.param(
            lambda value: value["$defs"]["choice"]["properties"][
                "finish_reason"
            ].__setitem__("enum", ["length"]),
            id="finish-reason-const-conflicts-with-enum",
        ),
        pytest.param(
            lambda value: value["$defs"]["assistant_message"]["properties"][
                "role"
            ].__setitem__("const", "user"),
            id="assistant-role-drift",
        ),
        pytest.param(
            lambda value: value["$defs"]["assistant_message"]["properties"][
                "content"
            ].__setitem__("type", "number"),
            id="content-type-drift",
        ),
        pytest.param(
            lambda value: value["$defs"]["assistant_message"]["properties"][
                "content"
            ].__setitem__("maxLength", 0),
            id="content-length-is-unsatisfiable",
        ),
        pytest.param(
            lambda value: value["$defs"]["assistant_message"]["properties"][
                "content"
            ].__setitem__("const", 7),
            id="content-type-conflicts-with-const",
        ),
        pytest.param(
            lambda value: value["$defs"]["assistant_message"]["properties"][
                "content"
            ].__setitem__("const", "{}"),
            id="content-cannot-carry-valid-task-output",
        ),
        pytest.param(
            lambda value: value["properties"]["choices"].__setitem__(
                "maxItems",
                2,
            ),
            id="choice-count-drift",
        ),
        pytest.param(
            lambda value: value["$defs"]["assistant_message"]["required"].remove(
                "role"
            ),
            id="assistant-role-not-required",
        ),
        pytest.param(
            lambda value: value.__setitem__("maxProperties", 1),
            id="response-root-is-unsatisfiable",
        ),
    ],
)
def test_response_schema_gate_drift_is_rejected_after_full_reseal(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    mutate: Callable[[dict[str, Any]], None],
) -> None:
    root = _install_bundle_fixture(tmp_path, monkeypatch)
    _reseal_api_dependency(root, "response_envelope_schema", mutate)
    _assert_bundle_rejected()


@pytest.mark.parametrize(
    "mutate",
    [
        pytest.param(
            lambda value: value["envelope_gates"].__setitem__(
                "choice_count",
                2,
            ),
            id="normalization-choice-count-drift",
        ),
        pytest.param(
            lambda value: value["envelope_gates"].__setitem__(
                "finish_reason",
                "length",
            ),
            id="normalization-finish-reason-drift",
        ),
        pytest.param(
            lambda value: value["envelope_gates"].__setitem__(
                "assistant_role",
                "user",
            ),
            id="normalization-role-drift",
        ),
        pytest.param(
            lambda value: value.__setitem__(
                "source_json_pointer",
                "/choices/0/message/missing",
            ),
            id="pointer-missing",
        ),
        pytest.param(
            lambda value: value.__setitem__(
                "source_json_pointer",
                "/choices/1/message/content",
            ),
            id="pointer-out-of-range",
        ),
        pytest.param(
            lambda value: value.__setitem__(
                "source_json_pointer",
                "/choices/-/message/content",
            ),
            id="pointer-dash",
        ),
        pytest.param(
            lambda value: value.__setitem__(
                "source_json_pointer",
                "/choices/0/message/bad~2escape",
            ),
            id="pointer-invalid-escape",
        ),
    ],
)
def test_normalization_gate_and_pointer_drift_is_rejected_after_full_reseal(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    mutate: Callable[[dict[str, Any]], None],
) -> None:
    root = _install_bundle_fixture(tmp_path, monkeypatch)
    _reseal_api_dependency(root, "normalization_policy", mutate)
    _assert_bundle_rejected()


def test_response_contract_follows_chained_local_refs(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = _install_bundle_fixture(tmp_path, monkeypatch)

    def mutate(response: dict[str, Any]) -> None:
        original = response["$defs"]["choice"]
        response["$defs"]["choice_inner"] = original
        response["$defs"]["choice"] = {"$ref": "#/$defs/choice_inner"}

    _reseal_api_dependency(root, "response_envelope_schema", mutate)
    assert profiles.validate_all_rule_bundles() == []


def test_response_contract_decodes_uri_fragment_before_json_pointer(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = _install_bundle_fixture(tmp_path, monkeypatch)
    _reseal_api_dependency(
        root,
        "response_envelope_schema",
        lambda value: value["properties"]["choices"].__setitem__(
            "items",
            {"$ref": "#%2F%24defs%2Fchoice"},
        ),
    )
    assert profiles.validate_all_rule_bundles() == []


def test_response_contract_preserves_percent_encoded_pointer_tokens(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = _install_bundle_fixture(tmp_path, monkeypatch)

    def mutate(response: dict[str, Any]) -> None:
        response["$defs"]["choice%25"] = response["$defs"].pop("choice")
        response["properties"]["choices"]["items"] = {"$ref": "#/$defs/choice%2525"}

    _reseal_api_dependency(root, "response_envelope_schema", mutate)
    assert profiles.validate_all_rule_bundles() == []


@pytest.mark.parametrize(
    ("reference", "target_key"),
    [
        ("#/%ZZ", "%ZZ"),
        ("#/%2", "%2"),
        ("#/%FF", "\ufffd"),
    ],
)
def test_response_contract_rejects_invalid_uri_fragment_encoding(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    reference: str,
    target_key: str,
) -> None:
    root = _install_bundle_fixture(tmp_path, monkeypatch)

    def mutate(response: dict[str, Any]) -> None:
        response[target_key] = deepcopy(response["$defs"]["choice"])
        response["properties"]["choices"]["items"] = {"$ref": reference}

    _reseal_api_dependency(root, "response_envelope_schema", mutate)
    _assert_bundle_rejected()


@pytest.mark.parametrize(
    "mutation",
    [
        "missing",
        "anchor",
        "bad-pointer",
        "self-cycle",
        "root-cycle",
        "nested-id",
    ],
)
def test_optional_response_refs_are_audited_before_runtime(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    mutation: str,
) -> None:
    root = _install_bundle_fixture(tmp_path, monkeypatch)

    def mutate(response: dict[str, Any]) -> None:
        if mutation == "missing":
            replacement = {"$ref": "#/$defs/missing"}
        elif mutation == "anchor":
            replacement = {"$ref": "#unknownAnchor"}
        elif mutation == "bad-pointer":
            replacement = {"$ref": "#/$defs/bad~2name"}
        elif mutation == "self-cycle":
            replacement = {"$ref": "#/properties/system_fingerprint"}
        elif mutation == "root-cycle":
            replacement = {"$ref": "#"}
        else:
            response["$defs"]["nested_scope"] = {
                "$id": "nested-scope",
                "type": "string",
            }
            replacement = {"$ref": "#/$defs/nested_scope"}
        response["properties"]["system_fingerprint"] = replacement

    _reseal_api_dependency(root, "response_envelope_schema", mutate)
    _assert_bundle_rejected()


def test_oversized_ref_array_index_fails_closed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = _install_bundle_fixture(tmp_path, monkeypatch)

    def mutate(response: dict[str, Any]) -> None:
        response["x-array"] = [{"type": "string"}]
        response["properties"]["choices"]["items"] = {"$ref": f"#/x-array/{'9' * 5000}"}

    _reseal_api_dependency(root, "response_envelope_schema", mutate)
    _assert_bundle_rejected()


def test_response_witness_accepts_a_satisfiable_string_pattern(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = _install_bundle_fixture(tmp_path, monkeypatch)
    _reseal_api_dependency(
        root,
        "response_envelope_schema",
        lambda value: value["properties"]["id"].__setitem__("pattern", "^ok$"),
    )
    assert profiles.validate_all_rule_bundles() == []


def test_response_and_task_witness_must_pass_as_one_response(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = _install_bundle_fixture(tmp_path, monkeypatch)

    def mutate(response: dict[str, Any]) -> None:
        response["properties"]["choices"]["contains"] = {
            "type": "object",
            "required": ["message"],
            "properties": {
                "message": {
                    "type": "object",
                    "required": ["content"],
                    "properties": {
                        "content": {"const": "x"},
                    },
                },
            },
        }

    _reseal_api_dependency(root, "response_envelope_schema", mutate)
    _assert_bundle_rejected()


def test_normalization_pointer_must_select_parseable_content(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = _install_bundle_fixture(tmp_path, monkeypatch)
    _reseal_api_dependency(
        root,
        "response_envelope_schema",
        lambda value: value["$defs"]["assistant_message"]["properties"][
            "role"
        ].__setitem__("type", "string"),
    )
    _reseal_api_dependency(
        root,
        "normalization_policy",
        lambda value: value.__setitem__(
            "source_json_pointer",
            "/choices/0/message/role",
        ),
    )
    _assert_bundle_rejected()


def test_json_pointer_decoding_and_retry_consistency_are_strict(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = _install_bundle_fixture(tmp_path, monkeypatch)
    assert profiles._decode_json_pointer(
        "/a~1b/m~0n",
        label="pointer",
    ) == ["a/b", "m~n"]
    with pytest.raises(profiles.ProfileError, match="非法 JSON Pointer 转义"):
        profiles._decode_json_pointer("/bad~2value", label="pointer")

    registry = _fixture_registry(root)
    row = _bundle_row(registry)
    api = _read_json(root / row["api_contract_bundle"]["path"])
    profile = _read_json(root / api["profile"]["path"])
    normalization = _read_json(root / api["normalization_policy"]["path"])
    profiles._validate_retry_consistency(
        registry,
        profile,
        normalization,
        label="retry",
    )
    normalization["recovery"]["parse_retry_count"] = 999
    profiles._validate_retry_consistency(
        registry,
        profile,
        normalization,
        label="retry",
    )
    normalization["recovery"]["request_retry_count"] += 1
    with pytest.raises(profiles.ProfileError, match="request_retry_count"):
        profiles._validate_retry_consistency(
            registry,
            profile,
            normalization,
            label="retry",
        )


def test_normalization_is_validated_through_explicit_composite_schema(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = _install_bundle_fixture(tmp_path, monkeypatch)
    _reseal_api_dependency(
        root,
        "normalization_policy",
        lambda value: value.__setitem__("unexpected", True),
    )
    _assert_bundle_rejected("Additional properties")


@pytest.mark.parametrize(
    "credential_name",
    [
        "secret_access_key",
        "access_key",
        "auth_token",
        "credential_blob",
    ],
)
def test_provider_inline_credential_name_variants_are_rejected(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    credential_name: str,
) -> None:
    root = _install_bundle_fixture(tmp_path, monkeypatch)
    _reseal_api_dependency(
        root,
        "provider_config",
        lambda value: value.__setitem__(credential_name, "inline-secret"),
    )
    _assert_bundle_rejected("禁止内嵌凭证字段")


def test_profile_schema_inline_credentials_https_and_capability_expansion_fail(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = _install_bundle_fixture(tmp_path, monkeypatch)
    _reseal_api_dependency(
        root,
        "profile",
        lambda value: value.__setitem__("unexpected", True),
    )
    _assert_bundle_rejected("Additional properties")

    root = _install_bundle_fixture(tmp_path / "profile_credential", monkeypatch)
    _reseal_api_dependency(
        root,
        "profile",
        lambda value: value["json_output"]["provider_parameters"].__setitem__(
            "auth_token",
            "inline-secret",
        ),
    )
    _assert_bundle_rejected("禁止内嵌凭证字段")

    root = _install_bundle_fixture(tmp_path / "credential", monkeypatch)

    def add_credential(api: dict[str, Any]) -> None:
        api["auth"]["credential_value"] = "inline-secret"

    _reseal_api_bundle(root, add_credential)
    _assert_bundle_rejected("Additional properties")

    root = _install_bundle_fixture(tmp_path / "private_token", monkeypatch)
    _reseal_api_dependency(
        root,
        "provider_config",
        lambda value: value.__setitem__("private_token", "inline-secret"),
    )
    _assert_bundle_rejected("禁止内嵌凭证字段")

    root = _install_bundle_fixture(tmp_path / "http", monkeypatch)
    _reseal_api_bundle(
        root,
        lambda value: value["api_address"].__setitem__(
            "base_url",
            "http://example.invalid/v1",
        ),
    )
    _assert_bundle_rejected("does not match")

    root = _install_bundle_fixture(tmp_path / "capability", monkeypatch)
    _reseal_context(
        root,
        lambda value: value["capability_limits"].__setitem__(
            "network",
            True,
        ),
    )
    _assert_bundle_rejected("False was expected")


def test_global_fail_closed_when_sibling_bundle_is_broken(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = _install_bundle_fixture(tmp_path, monkeypatch)
    second = _add_second_bundle(root)
    registry = _fixture_registry(root)
    _bundle_row(registry, second["bundle_id"])["materialize_items"][0]["sha256"] = (
        "0" * 64
    )
    _save_fixture_registry(root, registry)
    with pytest.raises(profiles.ProfileError):
        profiles.resolve_rule_bundle(CURRENT_BUNDLE_ID)


def test_bundle_resolver_reads_no_environment_network_or_provider_and_writes_nothing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = _install_bundle_fixture(tmp_path, monkeypatch)
    before = {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in root.rglob("*")
        if path.is_file()
    }

    class ForbiddenEnvironment(dict[str, str]):
        def __getitem__(self, key: str) -> str:
            raise AssertionError(f"resolver read environment: {key}")

        def get(self, key: str, default: Any = None) -> Any:
            raise AssertionError(f"resolver read environment: {key}")

    def forbidden(*_: Any, **__: Any) -> Any:
        raise AssertionError("resolver crossed an offline boundary")

    monkeypatch.setattr(profiles.os, "environ", ForbiddenEnvironment())
    monkeypatch.setattr(profiles, "load_provider", forbidden)
    monkeypatch.setattr(profiles, "render", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)

    assert profiles.validate_all_rule_bundles() == []
    assert profiles.list_rule_bundles()
    assert profiles.load_rule_bundle(CURRENT_BUNDLE_ID)
    assert profiles.resolve_rule_bundle(CURRENT_BUNDLE_ID)
    after = {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in root.rglob("*")
        if path.is_file()
    }
    assert after == before


def test_bundle_cli_unknown_id_keeps_error_return_contract(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _install_bundle_fixture(tmp_path, monkeypatch)
    monkeypatch.setattr(
        profiles.sys,
        "argv",
        ["model_call_profiles.py", "resolve-bundle", "missing"],
    )
    assert profiles.main() == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == "FAIL 找不到规则包：missing\n"

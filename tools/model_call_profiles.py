#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import stat
import sys
from copy import deepcopy
from pathlib import Path, PurePosixPath
from typing import Any
from urllib.parse import quote, unquote_to_bytes

from jsonschema import Draft202012Validator, FormatChecker

try:
    from tools.experiment_workspace_modules.contracts import (
        DESTINATION_ROOTS_BY_ROLE as _SHARED_DESTINATION_ROOTS,
    )
except ModuleNotFoundError:  # pragma: no cover - direct script execution
    from experiment_workspace_modules.contracts import (
        DESTINATION_ROOTS_BY_ROLE as _SHARED_DESTINATION_ROOTS,
    )


ROOT = Path(__file__).resolve().parents[1]
CONFIG_ROOT = ROOT / "config/model_call_profiles"
REGISTRY_PATH = CONFIG_ROOT / "registry.json"
PROFILE_SCHEMA_PATH = CONFIG_ROOT / "profile.schema.json"
CONTRACT_BUNDLE_SCHEMA_PATH = CONFIG_ROOT / "contracts/contract_bundle.schema.json"
PROMPT_MANIFEST_SCHEMA_PATH = ROOT / "config/prompts/prompt_manifest.schema.json"
CONTEXT_RECIPE_SCHEMA_PATH = ROOT / "config/context_recipes/context_recipe.schema.json"

SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
SAFE_ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9._-]{0,119}$")
REFERENCE_KEYS = {"path", "sha256"}
MATERIALIZE_ITEM_KEYS = {"destination", "role", "sha256", "source"}
RULE_BUNDLE_ROW_KEYS = {
    "api_contract_bundle",
    "bundle_id",
    "context_recipe",
    "materialize_items",
    "profile_id",
    "prompt_manifest",
    "status",
    "task_output_schema",
}
REGISTRY_KEYS = {
    "automatic_retries",
    "default_output_token_policy",
    "default_temperature",
    "preferred_profiles",
    "profiles",
    "rule_bundles",
    "schema_version",
    "status",
}
MATERIALIZE_DESTINATION_ROOTS = dict(_SHARED_DESTINATION_ROOTS)
RESOLVED_CAPABILITY_LIMITS = {
    "offline_resolve_only": True,
    "network": False,
    "credential_read": False,
    "request_send": False,
    "model_api": False,
    "notion_write": False,
}
API_BUNDLE_REFERENCE_KEYS = (
    "profile",
    "provider_config",
    "provider_access_policy",
    "request_envelope_schema",
    "response_envelope_schema",
    "normalization_policy",
)
MAIN_REFERENCE_ROOTS = {
    "api_contract_bundle": "config/model_call_profiles/contracts",
    "prompt_manifest": "config/prompts",
    "context_recipe": "config/context_recipes",
    "task_output_schema": "config/contracts",
}
INLINE_CREDENTIAL_KEYS = {
    "access_token",
    "access_key",
    "api_key",
    "api_key_value",
    "auth_token",
    "authorization",
    "bearer_token",
    "client_secret",
    "credential",
    "credential_blob",
    "credential_data",
    "credentials",
    "credential_value",
    "password",
    "passphrase",
    "private_key",
    "private_token",
    "refresh_token",
    "secret",
    "secret_access_key",
    "secret_key",
    "token",
}
INLINE_CREDENTIAL_PATTERN = re.compile(
    r"(?:^|_)(?:"
    r"(?:api|auth|access|bearer|client|credential|private|refresh|secret)"
    r"(?:_[a-z0-9]+){0,3}_(?:blob|data|key|secret|token|value)|"
    r"passphrase|password"
    r")(?:$|_)"
)
SAFE_CREDENTIAL_METADATA_SUFFIXES = (
    "_env",
    "_environment_variable",
    "_forbidden",
    "_mode",
    "_name",
    "_reference",
    "_required",
    "_source",
    "_supported",
)
REQUEST_CORE_FIELDS = {
    "messages",
    "model",
    "stream",
    "temperature",
}
SCHEMA_PROOF_BRANCH_KEYS = {
    "$dynamicRef",
    "allOf",
    "anyOf",
    "dependentSchemas",
    "else",
    "if",
    "not",
    "oneOf",
    "patternProperties",
    "then",
    "unevaluatedProperties",
}
SCHEMA_REF_ANNOTATION_KEYS = {
    "$comment",
    "default",
    "deprecated",
    "description",
    "examples",
    "readOnly",
    "title",
    "writeOnly",
}
SCHEMA_MAPPING_KEYWORDS = (
    "$defs",
    "dependentSchemas",
    "patternProperties",
    "properties",
)
SCHEMA_SINGLE_KEYWORDS = (
    "additionalProperties",
    "contains",
    "contentSchema",
    "else",
    "if",
    "items",
    "not",
    "propertyNames",
    "then",
    "unevaluatedItems",
    "unevaluatedProperties",
)
SCHEMA_SEQUENCE_KEYWORDS = (
    "allOf",
    "anyOf",
    "oneOf",
    "prefixItems",
)


def _fixed_validation_schema_paths() -> dict[str, Path]:
    return {
        "contract_bundle": CONTRACT_BUNDLE_SCHEMA_PATH,
        "context_recipe": CONTEXT_RECIPE_SCHEMA_PATH,
        "profile": PROFILE_SCHEMA_PATH,
        "prompt_manifest": PROMPT_MANIFEST_SCHEMA_PATH,
    }


RULE_BUNDLE_ROW_SCHEMA: dict[str, Any] = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "type": "object",
    "additionalProperties": False,
    "required": sorted(RULE_BUNDLE_ROW_KEYS),
    "properties": {
        "bundle_id": {"$ref": "#/$defs/safe_id"},
        "profile_id": {"$ref": "#/$defs/safe_id"},
        "status": {"type": "string", "minLength": 1, "maxLength": 160},
        "api_contract_bundle": {"$ref": "#/$defs/reference"},
        "prompt_manifest": {"$ref": "#/$defs/reference"},
        "context_recipe": {"$ref": "#/$defs/reference"},
        "task_output_schema": {"$ref": "#/$defs/reference"},
        "materialize_items": {
            "type": "array",
            "minItems": 1,
            "maxItems": 256,
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": sorted(MATERIALIZE_ITEM_KEYS),
                "properties": {
                    "source": {"$ref": "#/$defs/repo_relative_path"},
                    "destination": {"$ref": "#/$defs/repo_relative_path"},
                    "role": {
                        "enum": sorted(MATERIALIZE_DESTINATION_ROOTS),
                    },
                    "sha256": {"$ref": "#/$defs/sha256"},
                },
            },
        },
    },
    "$defs": {
        "safe_id": {
            "type": "string",
            "pattern": r"^[a-z0-9][a-z0-9._-]{0,119}$",
        },
        "repo_relative_path": {
            "type": "string",
            "minLength": 1,
            "maxLength": 240,
            "pattern": (
                r"^(?!/)(?!.*//)(?!.*(?:^|/)\.\.?(?:/|$))"
                r"(?!.*\\)[A-Za-z0-9._/-]+$"
            ),
        },
        "sha256": {
            "type": "string",
            "pattern": r"^[0-9a-f]{64}$",
        },
        "reference": {
            "type": "object",
            "additionalProperties": False,
            "required": sorted(REFERENCE_KEYS),
            "properties": {
                "path": {"$ref": "#/$defs/repo_relative_path"},
                "sha256": {"$ref": "#/$defs/sha256"},
            },
        },
    },
}


class ProfileError(RuntimeError):
    pass


def _is_repo_relative_path(value: object) -> bool:
    if (
        not isinstance(value, str)
        or not value
        or "\\" in value
        or "//" in value
        or "\x00" in value
    ):
        return False
    pure = PurePosixPath(value)
    return not pure.is_absolute() and all(
        part not in {"", ".", ".."} for part in value.split("/")
    )


def _registered_source_path_is_allowed(value: object) -> bool:
    return (
        _is_repo_relative_path(value)
        and isinstance(value, str)
        and value.startswith("config/")
    )


def _constant_repo_relative(path: Path, *, label: str) -> str:
    root = Path(os.path.abspath(ROOT))
    absolute = Path(os.path.abspath(path))
    try:
        relative = absolute.relative_to(root).as_posix()
    except ValueError as exc:
        raise ProfileError(f"{label} 必须位于仓库内") from exc
    if not _registered_source_path_is_allowed(relative):
        raise ProfileError(f"{label} 不是允许读取的仓库相对路径：{relative}")
    return relative


def _stat_signature(value: os.stat_result) -> tuple[int, ...]:
    return (
        value.st_dev,
        value.st_ino,
        value.st_mode,
        value.st_nlink,
        value.st_size,
        value.st_mtime_ns,
        value.st_ctime_ns,
    )


def _open_directory_chain(root: Path, parts: tuple[str, ...]) -> int:
    flags = os.O_RDONLY
    if hasattr(os, "O_DIRECTORY"):
        flags |= os.O_DIRECTORY
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    descriptor = os.open(root, flags)
    try:
        for part in parts:
            visible = os.stat(part, dir_fd=descriptor, follow_symlinks=False)
            if stat.S_ISLNK(visible.st_mode):
                raise ProfileError(f"登记文件的父目录不得是软链：{part}")
            if not stat.S_ISDIR(visible.st_mode):
                raise ProfileError(f"登记文件的父路径不是目录：{part}")
            next_descriptor = os.open(part, flags, dir_fd=descriptor)
            opened = os.fstat(next_descriptor)
            if not stat.S_ISDIR(opened.st_mode):
                os.close(next_descriptor)
                raise ProfileError(f"登记文件的父路径不是目录：{part}")
            if (
                visible.st_dev,
                visible.st_ino,
            ) != (
                opened.st_dev,
                opened.st_ino,
            ):
                os.close(next_descriptor)
                raise ProfileError(f"登记文件的父目录打开前被替换：{part}")
            os.close(descriptor)
            descriptor = next_descriptor
    except BaseException:
        os.close(descriptor)
        raise
    return descriptor


def _read_registered_bytes(relative_path: str) -> bytes:
    if not _registered_source_path_is_allowed(relative_path):
        raise ProfileError(f"登记文件必须是 config/ 下的仓库相对路径：{relative_path}")
    relative = PurePosixPath(relative_path)
    root = Path(os.path.abspath(ROOT))
    directory_descriptor: int | None = None
    descriptor: int | None = None
    try:
        directory_descriptor = _open_directory_chain(
            root,
            tuple(relative.parts[:-1]),
        )
        visible_before = os.stat(
            relative.name,
            dir_fd=directory_descriptor,
            follow_symlinks=False,
        )
        if stat.S_ISLNK(visible_before.st_mode):
            raise ProfileError(f"登记文件本身不得是软链：{relative_path}")
        if not stat.S_ISREG(visible_before.st_mode):
            raise ProfileError(f"登记文件必须是普通文件：{relative_path}")
        if visible_before.st_nlink != 1:
            raise ProfileError(f"登记文件不得是硬链接：{relative_path}")

        flags = os.O_RDONLY
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        descriptor = os.open(relative.name, flags, dir_fd=directory_descriptor)
        opened_before = os.fstat(descriptor)
        if not stat.S_ISREG(opened_before.st_mode):
            raise ProfileError(f"登记文件必须是普通文件：{relative_path}")
        if opened_before.st_nlink != 1:
            raise ProfileError(f"登记文件不得是硬链接：{relative_path}")
        if (
            visible_before.st_dev,
            visible_before.st_ino,
        ) != (
            opened_before.st_dev,
            opened_before.st_ino,
        ):
            raise ProfileError(f"登记文件打开前被替换：{relative_path}")

        chunks: list[bytes] = []
        while True:
            chunk = os.read(descriptor, 1024 * 1024)
            if not chunk:
                break
            chunks.append(chunk)

        opened_after = os.fstat(descriptor)
        if opened_after.st_nlink != 1:
            raise ProfileError(f"登记文件读取期间变成硬链接：{relative_path}")
        if _stat_signature(opened_after) != _stat_signature(opened_before):
            raise ProfileError(f"登记文件读取期间发生变化：{relative_path}")
        visible_after = os.stat(
            relative.name,
            dir_fd=directory_descriptor,
            follow_symlinks=False,
        )
        if _stat_signature(visible_after) != _stat_signature(opened_after):
            raise ProfileError(f"登记文件读取期间被替换：{relative_path}")
        return b"".join(chunks)
    except FileNotFoundError as exc:
        raise ProfileError(f"找不到登记文件：{relative_path}") from exc
    except OSError as exc:
        raise ProfileError(f"无法安全读取登记文件：{relative_path}") from exc
    finally:
        if descriptor is not None:
            os.close(descriptor)
        if directory_descriptor is not None:
            os.close(directory_descriptor)


def _decode_json_object(raw: bytes, *, label: str) -> dict[str, Any]:
    def reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        value: dict[str, Any] = {}
        for key, item in pairs:
            if key in value:
                raise ValueError(f"重复字段：{key}")
            value[key] = item
        return value

    def reject_non_finite(value: str) -> None:
        raise ValueError(f"非有限数字：{value}")

    try:
        value = json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=reject_duplicate_keys,
            parse_constant=reject_non_finite,
        )
    except UnicodeDecodeError as exc:
        raise ProfileError(f"登记文件不是 UTF-8：{label}") from exc
    except (json.JSONDecodeError, ValueError) as exc:
        raise ProfileError(f"JSON 格式错误：{label}: {exc}") from exc
    if not isinstance(value, dict):
        raise ProfileError(f"配置顶层必须是 JSON 对象：{label}")
    return value


def _sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


class _BundleReader:
    def __init__(self) -> None:
        self._bytes: dict[str, bytes] = {}
        self._digests: dict[str, str] = {}

    def read(self, reference: dict[str, Any], *, label: str) -> bytes:
        reference = _require_exact_keys(
            reference,
            REFERENCE_KEYS,
            label=label,
        )
        path = reference.get("path")
        digest = reference.get("sha256")
        if not _registered_source_path_is_allowed(path):
            raise ProfileError(f"{label}.path 不是允许的仓库相对路径：{path}")
        if not isinstance(digest, str) or SHA256_PATTERN.fullmatch(digest) is None:
            raise ProfileError(f"{label}.sha256 不是 64 位小写 SHA-256")
        assert isinstance(path, str)
        if path not in self._bytes:
            raw = _read_registered_bytes(path)
            self._bytes[path] = raw
            self._digests[path] = _sha256_bytes(raw)
        if self._digests[path] != digest:
            raise ProfileError(f"{label} 的 SHA-256 漂移：{path}")
        return self._bytes[path]

    def read_json(
        self,
        reference: dict[str, Any],
        *,
        label: str,
    ) -> dict[str, Any]:
        raw = self.read(reference, label=label)
        return _decode_json_object(raw, label=reference["path"])

    def bytes_for(self, path: str) -> bytes:
        try:
            return self._bytes[path]
        except KeyError as exc:
            raise ProfileError(f"登记来源尚未安全读取：{path}") from exc

    def track_snapshot(self, path: str, raw: bytes) -> None:
        if path in self._bytes and self._bytes[path] != raw:
            raise ProfileError(f"登记文件快照冲突：{path}")
        self._bytes[path] = raw
        self._digests[path] = _sha256_bytes(raw)

    def verify_unchanged(self) -> None:
        for path in sorted(self._bytes):
            raw = _read_registered_bytes(path)
            if raw != self._bytes[path] or _sha256_bytes(raw) != self._digests[path]:
                raise ProfileError(f"登记文件在规则包解析期间发生变化：{path}")


def read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ProfileError(f"找不到配置文件：{path}") from exc
    except json.JSONDecodeError as exc:
        raise ProfileError(f"JSON 格式错误：{path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ProfileError(f"配置顶层必须是 JSON 对象：{path}")
    return value


def load_registry() -> dict[str, Any]:
    return read_json(REGISTRY_PATH)


def registry_rows() -> list[dict[str, Any]]:
    registry = load_registry()
    rows = registry.get("profiles")
    if not isinstance(rows, list):
        raise ProfileError("registry.json 的 profiles 必须是数组")
    return rows


def _load_registry_secure_snapshot() -> tuple[dict[str, Any], str, bytes]:
    relative = _constant_repo_relative(REGISTRY_PATH, label="模型调用登记表")
    raw = _read_registered_bytes(relative)
    return _decode_json_object(raw, label=relative), relative, raw


def _load_registry_secure() -> dict[str, Any]:
    registry, _, _ = _load_registry_secure_snapshot()
    return registry


def rule_bundle_rows() -> list[dict[str, Any]]:
    registry = _load_registry_secure()
    rows = registry.get("rule_bundles")
    if not isinstance(rows, list):
        raise ProfileError("registry.json 的 rule_bundles 必须是数组")
    if not all(isinstance(row, dict) for row in rows):
        raise ProfileError("registry.json 的 rule_bundles 每项必须是对象")
    return rows


def _validation_messages(
    instance: dict[str, Any],
    schema: dict[str, Any],
    *,
    label: str,
) -> list[str]:
    try:
        Draft202012Validator.check_schema(schema)
    except Exception as exc:
        return [f"{label} 使用的 Draft 2020-12 Schema 无效：{exc}"]
    validator = Draft202012Validator(
        schema,
        format_checker=FormatChecker(),
    )
    errors: list[str] = []
    for error in sorted(
        validator.iter_errors(instance),
        key=lambda item: tuple(str(part) for part in item.path),
    ):
        location = ".".join(str(part) for part in error.path) or "$"
        errors.append(f"{label}: {location}: {error.message}")
    return errors


def _validate_instance(
    instance: dict[str, Any],
    schema: dict[str, Any],
    *,
    label: str,
) -> None:
    errors = _validation_messages(instance, schema, label=label)
    if errors:
        raise ProfileError("\n".join(errors))


def _reject_external_schema_references(value: Any, *, label: str) -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            if key in {"$ref", "$dynamicRef"} and (
                not isinstance(item, str) or not item.startswith("#")
            ):
                raise ProfileError(f"{label} 禁止外部 Schema 引用：{key}")
            _reject_external_schema_references(item, label=label)
    elif isinstance(value, list):
        for item in value:
            _reject_external_schema_references(item, label=label)


def _validate_schema_document(schema: dict[str, Any], *, label: str) -> None:
    if schema.get("$schema") != "https://json-schema.org/draft/2020-12/schema":
        raise ProfileError(f"{label} 必须声明 Draft 2020-12")
    _reject_external_schema_references(schema, label=label)
    try:
        Draft202012Validator.check_schema(schema)
    except Exception as exc:
        raise ProfileError(f"{label} 不是有效的 Draft 2020-12 Schema：{exc}") from exc


def _require_exact_keys(
    value: object,
    expected: set[str],
    *,
    label: str,
) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != expected:
        actual = sorted(value) if isinstance(value, dict) else type(value).__name__
        raise ProfileError(
            f"{label} 字段必须恰好是 {sorted(expected)}，实际为 {actual}"
        )
    return value


def _strictly_equal(left: Any, right: Any) -> bool:
    if type(left) is not type(right):
        return False
    if isinstance(left, dict):
        return left.keys() == right.keys() and all(
            _strictly_equal(left[key], right[key]) for key in left
        )
    if isinstance(left, (list, tuple)):
        return len(left) == len(right) and all(
            _strictly_equal(a, b) for a, b in zip(left, right, strict=True)
        )
    return left == right


def _expect_equal(actual: Any, expected: Any, *, label: str) -> None:
    if not _strictly_equal(actual, expected):
        raise ProfileError(f"{label} 不一致：实际={actual!r}，应为={expected!r}")


def _path_is_below(path: str, root: str) -> bool:
    return path.startswith(f"{root}/")


def _validate_rule_bundle_row_shape(
    row: dict[str, Any],
    *,
    label: str,
) -> None:
    errors = _validation_messages(row, RULE_BUNDLE_ROW_SCHEMA, label=label)
    if errors:
        raise ProfileError("\n".join(errors))
    _require_exact_keys(row, RULE_BUNDLE_ROW_KEYS, label=label)
    for reference_name, expected_root in MAIN_REFERENCE_ROOTS.items():
        reference = _require_exact_keys(
            row[reference_name],
            REFERENCE_KEYS,
            label=f"{label}.{reference_name}",
        )
        if not _path_is_below(reference["path"], expected_root):
            raise ProfileError(
                f"{label}.{reference_name}.path 必须位于 {expected_root}/ 下"
            )

    items = row["materialize_items"]
    destinations = [item["destination"] for item in items]
    sources = [item["source"] for item in items]
    if destinations != sorted(destinations):
        raise ProfileError(f"{label}.materialize_items 必须按 destination 排序")
    if len(destinations) != len(set(destinations)):
        raise ProfileError(f"{label}.materialize_items 存在重复 destination")
    if len(sources) != len(set(sources)):
        raise ProfileError(f"{label}.materialize_items 存在重复 source")
    if len(destinations) != len({value.casefold() for value in destinations}):
        raise ProfileError(f"{label}.materialize_items 存在大小写碰撞 destination")
    if len(sources) != len({value.casefold() for value in sources}):
        raise ProfileError(f"{label}.materialize_items 存在大小写碰撞 source")

    for index, item in enumerate(items):
        item_label = f"{label}.materialize_items[{index}]"
        _require_exact_keys(item, MATERIALIZE_ITEM_KEYS, label=item_label)
        source = item["source"]
        destination = item["destination"]
        role = item["role"]
        if not _registered_source_path_is_allowed(source):
            raise ProfileError(f"{item_label}.source 不是允许的仓库相对路径：{source}")
        expected_root = MATERIALIZE_DESTINATION_ROOTS[role]
        if (
            not _is_repo_relative_path(destination)
            or destination == expected_root
            or not _path_is_below(destination, expected_root)
        ):
            raise ProfileError(f"{item_label}.destination 没有落在 {expected_root}/ 下")


def _validate_registry_document(registry: dict[str, Any]) -> None:
    _require_exact_keys(registry, REGISTRY_KEYS, label="registry.json")
    if registry["schema_version"] != "model-call-profile-registry-v1":
        raise ProfileError("registry.json 的 schema_version 不受支持")
    if not isinstance(registry["status"], str) or not registry["status"]:
        raise ProfileError("registry.json 的 status 必须是非空字符串")
    temperature = registry["default_temperature"]
    if not isinstance(temperature, (int, float)) or isinstance(temperature, bool):
        raise ProfileError("registry.json 的 default_temperature 必须是数字")
    retries = registry["automatic_retries"]
    if not isinstance(retries, int) or isinstance(retries, bool) or retries < 0:
        raise ProfileError("registry.json 的 automatic_retries 必须是非负整数")
    if (
        not isinstance(registry["default_output_token_policy"], str)
        or not registry["default_output_token_policy"]
    ):
        raise ProfileError(
            "registry.json 的 default_output_token_policy 必须是非空字符串"
        )

    profiles = registry["profiles"]
    if not isinstance(profiles, list) or not profiles:
        raise ProfileError("registry.json 的 profiles 必须是非空数组")
    profile_ids: list[str] = []
    profile_paths: list[str] = []
    for index, row in enumerate(profiles):
        label = f"profiles[{index}]"
        row = _require_exact_keys(
            row,
            {"profile_id", "path", "role"},
            label=label,
        )
        profile_id = row["profile_id"]
        path = row["path"]
        if (
            not isinstance(profile_id, str)
            or SAFE_ID_PATTERN.fullmatch(profile_id) is None
        ):
            raise ProfileError(f"{label}.profile_id 格式不合法")
        if (
            not _registered_source_path_is_allowed(path)
            or not _path_is_below(
                path,
                "config/model_call_profiles/profiles",
            )
            or not path.endswith(".json")
        ):
            raise ProfileError(f"{label}.path 不在调用档目录内")
        if not isinstance(row["role"], str) or not row["role"]:
            raise ProfileError(f"{label}.role 必须是非空字符串")
        profile_ids.append(profile_id)
        profile_paths.append(path)
    if len(profile_ids) != len(set(profile_ids)):
        raise ProfileError("registry.json 存在重复 profile_id")
    if len(profile_paths) != len(set(profile_paths)):
        raise ProfileError("registry.json 存在重复 profile path")

    preferred = registry["preferred_profiles"]
    if not isinstance(preferred, dict):
        raise ProfileError("registry.json 的 preferred_profiles 必须是对象")
    for model_name, profile_id in preferred.items():
        if (
            not isinstance(model_name, str)
            or not model_name
            or not isinstance(profile_id, str)
            or profile_id not in profile_ids
        ):
            raise ProfileError(f"registry.json 的推荐调用档指向无效：{model_name!r}")

    rows = registry["rule_bundles"]
    if not isinstance(rows, list) or not rows:
        raise ProfileError("registry.json 的 rule_bundles 必须是非空数组")
    bundle_ids: list[str] = []
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            raise ProfileError("registry.json 的 rule_bundles 每项必须是对象")
        _validate_rule_bundle_row_shape(row, label=f"rule_bundles[{index}]")
        if row["status"] != registry["status"]:
            raise ProfileError(
                f"rule_bundles[{row['bundle_id']}].status 与登记表不一致"
            )
        if row["profile_id"] not in profile_ids:
            raise ProfileError(f"规则包指向未登记调用档：{row['profile_id']}")
        bundle_ids.append(row["bundle_id"])
    if len(bundle_ids) != len(set(bundle_ids)):
        raise ProfileError("registry.json 存在重复 bundle_id")


def _registered_profile_row(
    registry: dict[str, Any],
    profile_id: str,
) -> dict[str, Any]:
    matches = [row for row in registry["profiles"] if row["profile_id"] == profile_id]
    if len(matches) != 1:
        raise ProfileError(
            f"规则包 profile_id 在 profiles 中必须恰好出现一次：{profile_id}"
        )
    return matches[0]


def _reject_inline_credentials(value: Any, *, label: str) -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            normalized = key.casefold()
            safe_metadata = normalized.endswith(SAFE_CREDENTIAL_METADATA_SUFFIXES)
            if normalized in INLINE_CREDENTIAL_KEYS or (
                not safe_metadata
                and INLINE_CREDENTIAL_PATTERN.search(normalized) is not None
            ):
                raise ProfileError(f"{label} 禁止内嵌凭证字段：{key}")
            _reject_inline_credentials(item, label=label)
    elif isinstance(value, list):
        for item in value:
            _reject_inline_credentials(item, label=label)


def _decode_json_pointer(pointer: object, *, label: str) -> list[str]:
    if not isinstance(pointer, str) or not pointer.startswith("/"):
        raise ProfileError(f"{label} 必须是以 / 开头的 JSON Pointer")
    tokens: list[str] = []
    for raw_token in pointer.split("/")[1:]:
        if re.search(r"~(?:[^01]|$)", raw_token) is not None:
            raise ProfileError(f"{label} 含有非法 JSON Pointer 转义")
        tokens.append(raw_token.replace("~1", "/").replace("~0", "~"))
    return tokens


def _array_index_within_length(token: str, length: int, *, label: str) -> int:
    if re.fullmatch(r"(?:0|[1-9][0-9]*)", token) is None:
        raise ProfileError(f"{label} 含有非法数组下标")
    if length <= 0:
        raise ProfileError(f"{label} 数组下标越界")
    maximum = str(length - 1)
    if len(token) > len(maximum) or (len(token) == len(maximum) and token > maximum):
        raise ProfileError(f"{label} 数组下标越界")
    return int(token)


def _json_pointer_value(
    document: Any,
    pointer: str,
    *,
    label: str,
) -> Any:
    if pointer == "":
        return document
    value = document
    for token in _decode_json_pointer(pointer, label=label):
        if isinstance(value, dict):
            if token not in value:
                raise ProfileError(f"{label} 指向不存在的字段：{token}")
            value = value[token]
            continue
        if isinstance(value, list):
            index = _array_index_within_length(
                token,
                len(value),
                label=label,
            )
            value = value[index]
            continue
        raise ProfileError(f"{label} 无法继续解析：{token}")
    return value


def _replace_json_pointer_value(
    document: Any,
    tokens: list[str],
    replacement: Any,
    *,
    label: str,
) -> None:
    if not tokens:
        raise ProfileError(f"{label} 不得替换根节点")
    current = document
    for token in tokens[:-1]:
        if isinstance(current, dict):
            if token not in current:
                raise ProfileError(f"{label} 指向不存在的字段：{token}")
            current = current[token]
        elif isinstance(current, list):
            index = _array_index_within_length(
                token,
                len(current),
                label=label,
            )
            current = current[index]
        else:
            raise ProfileError(f"{label} 无法继续解析：{token}")
    final = tokens[-1]
    if isinstance(current, dict):
        if final not in current:
            raise ProfileError(f"{label} 指向不存在的字段：{final}")
        current[final] = replacement
        return
    if isinstance(current, list):
        index = _array_index_within_length(
            final,
            len(current),
            label=label,
        )
        current[index] = replacement
        return
    raise ProfileError(f"{label} 无法替换末端值")


def _decode_uri_fragment(fragment: str, *, label: str) -> str:
    if re.search(r"%(?![0-9A-Fa-f]{2})", fragment) is not None:
        raise ProfileError(f"{label} 含有非法 URI percent 编码")
    try:
        return unquote_to_bytes(fragment).decode("utf-8", errors="strict")
    except UnicodeDecodeError as exc:
        raise ProfileError(f"{label} percent 解码后不是合法 UTF-8") from exc


def _resolve_local_schema_node(
    document: dict[str, Any],
    node: object,
    *,
    label: str,
) -> dict[str, Any]:
    if not isinstance(node, dict):
        raise ProfileError(f"{label} 必须是 Schema 对象")
    current = node
    seen: set[str] = set()
    while "$ref" in current:
        siblings = set(current) - {"$ref"} - SCHEMA_REF_ANNOTATION_KEYS
        if siblings:
            raise ProfileError(
                f"{label} 的 $ref 带有无法安全合并的约束：{sorted(siblings)}"
            )
        reference = current["$ref"]
        if not isinstance(reference, str) or not reference.startswith("#"):
            raise ProfileError(f"{label} 只允许本地 JSON Pointer $ref")
        fragment = _decode_uri_fragment(
            reference[1:],
            label=f"{label}.$ref",
        )
        if fragment and not fragment.startswith("/"):
            raise ProfileError(f"{label} 只允许本地 JSON Pointer $ref")
        if reference in seen:
            raise ProfileError(f"{label} 出现循环 $ref：{reference}")
        seen.add(reference)
        current = _json_pointer_value(
            document,
            fragment,
            label=f"{label}.$ref",
        )
        if not isinstance(current, dict):
            raise ProfileError(f"{label} 的 $ref 目标不是 Schema 对象")
    if current is not document and "$id" in current:
        raise ProfileError(f"{label} 不支持证明路径中的嵌套 $id")
    if "$dynamicRef" in current:
        raise ProfileError(f"{label} 不支持 $dynamicRef")
    return current


def _validate_local_schema_reference_graph(
    document: dict[str, Any],
    *,
    label: str,
) -> None:
    def walk(
        node: object,
        *,
        node_label: str,
        root: bool = False,
        ancestors: frozenset[int] = frozenset(),
    ) -> None:
        if not isinstance(node, dict):
            return
        identity = id(node)
        if identity in ancestors:
            raise ProfileError(f"{node_label} 含有循环 Schema 引用")
        next_ancestors = ancestors | {identity}
        if not root and "$id" in node:
            raise ProfileError(f"{node_label} 不支持嵌套 $id")
        if "$dynamicRef" in node:
            raise ProfileError(f"{node_label} 不支持 $dynamicRef")
        if "$ref" in node:
            target = _resolve_local_schema_node(
                document,
                node,
                label=node_label,
            )
            walk(
                target,
                node_label=f"{node_label}.$ref_target",
                ancestors=next_ancestors,
            )
        for keyword in SCHEMA_MAPPING_KEYWORDS:
            children = node.get(keyword)
            if not isinstance(children, dict):
                continue
            for name, child in children.items():
                walk(
                    child,
                    node_label=f"{node_label}.{keyword}.{name}",
                    ancestors=next_ancestors,
                )
        for keyword in SCHEMA_SINGLE_KEYWORDS:
            child = node.get(keyword)
            if isinstance(child, dict):
                walk(
                    child,
                    node_label=f"{node_label}.{keyword}",
                    ancestors=next_ancestors,
                )
        for keyword in SCHEMA_SEQUENCE_KEYWORDS:
            children = node.get(keyword)
            if not isinstance(children, list):
                continue
            for index, child in enumerate(children):
                walk(
                    child,
                    node_label=f"{node_label}.{keyword}[{index}]",
                    ancestors=next_ancestors,
                )

    walk(document, node_label=label, root=True)


def _schema_validation_errors(
    document: dict[str, Any],
    node: dict[str, Any],
    instance: Any,
) -> list[Any]:
    def normalize_local_refs(value: dict[str, Any]) -> dict[str, Any]:
        normalized = deepcopy(value)
        for key in ("$ref", "$dynamicRef"):
            child = value.get(key)
            if not isinstance(child, str) or not child.startswith("#"):
                continue
            fragment = _decode_uri_fragment(
                child[1:],
                label=f"Schema.{key}",
            )
            if fragment == "" or fragment.startswith("/"):
                normalized[key] = f"#{quote(fragment, safe='/~')}"
        for keyword in SCHEMA_MAPPING_KEYWORDS:
            children = value.get(keyword)
            if not isinstance(children, dict):
                continue
            normalized[keyword] = {
                name: normalize_local_refs(child)
                if isinstance(child, dict)
                else deepcopy(child)
                for name, child in children.items()
            }
        for keyword in SCHEMA_SINGLE_KEYWORDS:
            child = value.get(keyword)
            if isinstance(child, dict):
                normalized[keyword] = normalize_local_refs(child)
        for keyword in SCHEMA_SEQUENCE_KEYWORDS:
            children = value.get(keyword)
            if not isinstance(children, list):
                continue
            normalized[keyword] = [
                normalize_local_refs(child)
                if isinstance(child, dict)
                else deepcopy(child)
                for child in children
            ]
        return normalized

    normalized_document = normalize_local_refs(document)
    normalized_node = normalize_local_refs(node)
    validator = Draft202012Validator(
        normalized_document,
        format_checker=FormatChecker(),
    ).evolve(schema=normalized_node)
    try:
        return sorted(
            validator.iter_errors(instance),
            key=lambda item: tuple(str(part) for part in item.path),
        )
    except Exception as exc:
        raise ProfileError(f"Schema 局部验收无法完成：{exc}") from exc


def _assert_schema_accepts_value(
    document: dict[str, Any],
    node: dict[str, Any],
    instance: Any,
    *,
    label: str,
) -> None:
    errors = _schema_validation_errors(document, node, instance)
    if errors:
        details = "; ".join(error.message for error in errors)
        raise ProfileError(f"{label} 不接受合同声明的实际值：{details}")


def _reject_schema_proof_branches(
    schema: dict[str, Any],
    *,
    label: str,
) -> None:
    found = sorted(SCHEMA_PROOF_BRANCH_KEYS.intersection(schema))
    if found:
        raise ProfileError(f"{label} 含有无法机械证明的 Schema 分支：{found}")


def _required_object_property_schema(
    document: dict[str, Any],
    node: object,
    property_name: str,
    *,
    label: str,
) -> dict[str, Any]:
    resolved = _resolve_local_schema_node(document, node, label=label)
    _reject_schema_proof_branches(resolved, label=label)
    if resolved.get("type") != "object":
        raise ProfileError(f"{label} 必须精确声明 type=object")
    properties = resolved.get("properties")
    if not isinstance(properties, dict) or property_name not in properties:
        raise ProfileError(f"{label} 缺少 properties.{property_name}")
    required = resolved.get("required")
    if not isinstance(required, list) or property_name not in required:
        raise ProfileError(f"{label} 必须把 {property_name} 列入 required")
    child = properties[property_name]
    if not isinstance(child, dict):
        raise ProfileError(f"{label}.properties.{property_name} 必须是 Schema 对象")
    return child


def _required_property_const(
    document: dict[str, Any],
    node: object,
    property_name: str,
    *,
    label: str,
) -> Any:
    child = _required_object_property_schema(
        document,
        node,
        property_name,
        label=label,
    )
    resolved = _resolve_local_schema_node(
        document,
        child,
        label=f"{label}.properties.{property_name}",
    )
    _reject_schema_proof_branches(
        resolved,
        label=f"{label}.properties.{property_name}",
    )
    if "const" not in resolved:
        raise ProfileError(f"{label}.properties.{property_name} 必须用 const 冻结")
    _assert_schema_accepts_value(
        document,
        child,
        resolved["const"],
        label=f"{label}.properties.{property_name}",
    )
    return resolved["const"]


def _validate_exact_value_schema(
    document: dict[str, Any],
    node: object,
    expected: Any,
    *,
    label: str,
) -> None:
    resolved = _resolve_local_schema_node(document, node, label=label)
    _reject_schema_proof_branches(resolved, label=label)
    _assert_schema_accepts_value(
        document,
        node,
        expected,
        label=label,
    )
    if not isinstance(expected, dict):
        if "const" not in resolved:
            raise ProfileError(f"{label} 必须用 const 精确冻结")
        _expect_equal(resolved["const"], expected, label=f"{label}.const")
        return

    if resolved.get("type") != "object":
        raise ProfileError(f"{label} 必须精确声明 type=object")
    if resolved.get("additionalProperties") is not False:
        raise ProfileError(f"{label}.additionalProperties 必须是 false")
    properties = resolved.get("properties")
    required = resolved.get("required")
    if not isinstance(properties, dict) or set(properties) != set(expected):
        raise ProfileError(f"{label}.properties 必须与实际对象字段完全相等")
    if (
        not isinstance(required, list)
        or len(required) != len(set(required))
        or set(required) != set(expected)
    ):
        raise ProfileError(f"{label}.required 必须与实际对象字段完全相等")
    for key, value in expected.items():
        _validate_exact_value_schema(
            document,
            properties[key],
            value,
            label=f"{label}.properties.{key}",
        )


def _validate_profile_request_contract(
    profile: dict[str, Any],
    request_schema: dict[str, Any],
    *,
    label: str,
) -> None:
    root = _resolve_local_schema_node(
        request_schema,
        request_schema,
        label=label,
    )
    _reject_schema_proof_branches(root, label=label)
    if root.get("type") != "object":
        raise ProfileError(f"{label} 顶层必须精确声明 type=object")
    if root.get("additionalProperties") is not False:
        raise ProfileError(f"{label}.additionalProperties 必须是 false")
    properties = root.get("properties")
    required = root.get("required")
    if not isinstance(properties, dict):
        raise ProfileError(f"{label}.properties 必须是对象")

    provider_parameters = profile["json_output"]["provider_parameters"]
    collisions = sorted(REQUEST_CORE_FIELDS.intersection(provider_parameters))
    if collisions:
        raise ProfileError(f"{label} 的供应商参数覆盖核心字段：{collisions}")
    expected_fields = REQUEST_CORE_FIELDS | set(provider_parameters)
    if set(properties) != expected_fields:
        missing = sorted(expected_fields - set(properties))
        extra = sorted(set(properties) - expected_fields)
        raise ProfileError(
            f"{label}.properties 与实际发送字段不一致：缺少={missing}，多出={extra}"
        )
    if (
        not isinstance(required, list)
        or len(required) != len(set(required))
        or set(required) != expected_fields
    ):
        raise ProfileError(f"{label}.required 必须与实际发送字段完全相等")

    expected_consts = {
        "model": profile["model_binding"]["request_model_id"],
        "temperature": profile["sampling"]["temperature"],
        "stream": profile["streaming"]["enabled"],
    }
    for field, expected in expected_consts.items():
        actual = _required_property_const(
            request_schema,
            root,
            field,
            label=label,
        )
        _expect_equal(
            actual,
            expected,
            label=f"{label}.properties.{field}.const",
        )
    for key, expected in provider_parameters.items():
        child = _required_object_property_schema(
            request_schema,
            root,
            key,
            label=label,
        )
        _validate_exact_value_schema(
            request_schema,
            child,
            expected,
            label=f"{label}.properties.{key}",
        )

    forbidden = set(profile["json_output"]["forbidden_request_fields"])
    forbidden_collisions = sorted(forbidden.intersection(properties))
    if forbidden_collisions:
        raise ProfileError(
            f"{label}.properties 出现调用档禁止字段：{forbidden_collisions}"
        )


def _schema_witness(
    document: dict[str, Any],
    node: object,
    *,
    label: str,
    ancestors: frozenset[int] = frozenset(),
) -> Any:
    resolved = _resolve_local_schema_node(document, node, label=label)
    _reject_schema_proof_branches(resolved, label=label)
    identity = id(resolved)
    if identity in ancestors:
        raise ProfileError(f"{label} 含有递归 Schema，无法有限证明")
    next_ancestors = ancestors | {identity}

    if "const" in resolved:
        witness = deepcopy(resolved["const"])
    elif "enum" in resolved:
        enum = resolved["enum"]
        if not isinstance(enum, list) or not enum:
            raise ProfileError(f"{label}.enum 必须是非空数组")
        accepted = [
            deepcopy(candidate)
            for candidate in enum
            if not _schema_validation_errors(document, resolved, candidate)
        ]
        if not accepted:
            raise ProfileError(f"{label}.enum 没有可满足当前 Schema 的值")
        witness = accepted[0]
    else:
        schema_type = resolved.get("type")
        if not isinstance(schema_type, str):
            raise ProfileError(f"{label} 必须用单一 type 或 const 证明可满足性")
        if schema_type == "object":
            properties = resolved.get("properties")
            required = resolved.get("required", [])
            if not isinstance(properties, dict) or not isinstance(required, list):
                raise ProfileError(f"{label} 的对象字段声明不完整")
            witness = {}
            for key in required:
                if not isinstance(key, str) or key not in properties:
                    raise ProfileError(f"{label} 的必填字段没有明确 Schema：{key}")
                witness[key] = _schema_witness(
                    document,
                    properties[key],
                    label=f"{label}.properties.{key}",
                    ancestors=next_ancestors,
                )
        elif schema_type == "array":
            minimum = resolved.get("minItems", 0)
            if not isinstance(minimum, int) or isinstance(minimum, bool) or minimum < 0:
                raise ProfileError(f"{label}.minItems 必须是非负整数")
            witness = [
                _schema_witness(
                    document,
                    _array_item_schema(
                        document,
                        resolved,
                        index,
                        label=label,
                    ),
                    label=f"{label}[{index}]",
                    ancestors=next_ancestors,
                )
                for index in range(minimum)
            ]
        elif schema_type == "string":
            minimum = resolved.get("minLength", 0)
            if not isinstance(minimum, int) or isinstance(minimum, bool) or minimum < 0:
                raise ProfileError(f"{label}.minLength 必须是非负整数")
            maximum = resolved.get("maxLength")
            if maximum is not None and (
                not isinstance(maximum, int)
                or isinstance(maximum, bool)
                or maximum < minimum
            ):
                raise ProfileError(f"{label}.maxLength 不能小于 minLength")
            seed_values = ("", "x", "a", "0", "ok", "json", "{}", "[]")
            candidates = [
                candidate
                for candidate in seed_values
                if len(candidate) >= minimum
                and (maximum is None or len(candidate) <= maximum)
            ]
            for fill in ("x", "a", "0"):
                for length in range(minimum, minimum + 129):
                    if maximum is not None and length > maximum:
                        break
                    candidates.append(fill * length)
            accepted = [
                candidate
                for candidate in candidates
                if not _schema_validation_errors(document, resolved, candidate)
            ]
            if not accepted:
                raise ProfileError(f"{label} 找不到有限可验证的字符串见证")
            witness = accepted[0]
        elif schema_type == "integer":
            minimum = resolved.get("minimum", 0)
            if not isinstance(minimum, (int, float)) or isinstance(minimum, bool):
                raise ProfileError(f"{label}.minimum 必须是数字")
            witness = int(minimum)
            if witness < minimum:
                witness += 1
        elif schema_type == "number":
            minimum = resolved.get("minimum", 0)
            if not isinstance(minimum, (int, float)) or isinstance(minimum, bool):
                raise ProfileError(f"{label}.minimum 必须是数字")
            witness = minimum
        elif schema_type == "boolean":
            witness = False
        elif schema_type == "null":
            witness = None
        else:
            raise ProfileError(f"{label} 使用了不支持证明的 type：{schema_type}")

    _assert_schema_accepts_value(
        document,
        resolved,
        witness,
        label=label,
    )
    return witness


def _sample_input_slot_content(slot: dict[str, Any], *, label: str) -> str:
    def sample_for_type(value_type: object) -> Any:
        return {
            "array": [],
            "boolean": False,
            "integer": 0,
            "null": None,
            "number": 0,
            "object": {},
            "string": "x",
        }.get(value_type, "x")

    def sample_object(required_key_field: str) -> dict[str, Any]:
        required_keys = slot.get(required_key_field, [])
        if not isinstance(required_keys, list):
            raise ProfileError(f"{label}.{required_key_field} 必须是数组")
        value: dict[str, Any] = {}
        for key in required_keys:
            if not isinstance(key, str):
                raise ProfileError(f"{label}.{required_key_field} 只能包含字符串")
            nested_required = f"{key}_required_keys"
            if nested_required in slot:
                value[key] = sample_object(nested_required)
                continue
            value_type = slot.get(f"{key}_type")
            if value_type is None and f"{key}_max_items" in slot:
                value_type = "array"
            value[key] = sample_for_type(value_type)
        return value

    content_type = slot["content_type"]
    if content_type == "application/json":
        top_level_type = slot.get("top_level_type", "object")
        if top_level_type == "object":
            instance = sample_object("required_keys")
        else:
            instance = sample_for_type(top_level_type)
        content = json.dumps(
            instance,
            ensure_ascii=False,
            separators=(",", ":"),
        )
    else:
        content = "x"
    if len(content.encode("utf-8")) > slot["max_bytes"]:
        raise ProfileError(f"{label} 的最小输入样本超过 max_bytes")
    return content


def _validate_request_instance_contract(
    profile: dict[str, Any],
    request_schema: dict[str, Any],
    context: dict[str, Any],
    prompt_text: str,
    *,
    label: str,
) -> None:
    messages = []
    for index, item in enumerate(context["message_plan"]):
        source = item["content_from"]
        if source == "prompt_manifest.prompt_file":
            content = prompt_text
        else:
            slot_name = source.removeprefix("input_slots.")
            content = _sample_input_slot_content(
                context["input_slots"][slot_name],
                label=f"{label}.message_plan[{index}].{slot_name}",
            )
        messages.append({"role": item["role"], "content": content})
    request = {
        "model": profile["model_binding"]["request_model_id"],
        "messages": messages,
        "temperature": profile["sampling"]["temperature"],
        "stream": profile["streaming"]["enabled"],
        **profile["json_output"]["provider_parameters"],
    }
    _assert_schema_accepts_value(
        request_schema,
        request_schema,
        request,
        label=label,
    )


def _array_item_schema(
    document: dict[str, Any],
    array_schema: dict[str, Any],
    index: int,
    *,
    label: str,
) -> dict[str, Any]:
    prefix_items = array_schema.get("prefixItems")
    if prefix_items is not None:
        if not isinstance(prefix_items, list):
            raise ProfileError(f"{label}.prefixItems 必须是数组")
        if index < len(prefix_items):
            return _resolve_local_schema_node(
                document,
                prefix_items[index],
                label=f"{label}.prefixItems[{index}]",
            )
    items = array_schema.get("items")
    if items is False or not isinstance(items, dict):
        raise ProfileError(f"{label} 没有覆盖下标 {index} 的 items Schema")
    return _resolve_local_schema_node(
        document,
        items,
        label=f"{label}.items",
    )


def _validate_response_normalization_contract(
    response_schema: dict[str, Any],
    normalization: dict[str, Any],
    task_schema: dict[str, Any],
    *,
    label: str,
) -> None:
    response_witness = _schema_witness(
        response_schema,
        response_schema,
        label=f"{label}.satisfiability",
    )
    gates = normalization["envelope_gates"]
    response_model = _required_property_const(
        response_schema,
        response_schema,
        "model",
        label=label,
    )
    _expect_equal(
        response_model,
        gates["expected_model"],
        label=f"{label}.properties.model.const",
    )

    tokens = _decode_json_pointer(
        normalization["source_json_pointer"],
        label=f"{label}.source_json_pointer",
    )
    if not tokens:
        raise ProfileError(f"{label}.source_json_pointer 不得指向响应根节点")
    current = _resolve_local_schema_node(
        response_schema,
        response_schema,
        label=label,
    )
    array_frames: list[tuple[dict[str, Any], int, dict[str, Any]]] = []
    content_parent: dict[str, Any] | None = None
    for position, token in enumerate(tokens):
        current = _resolve_local_schema_node(
            response_schema,
            current,
            label=f"{label}.source_json_pointer[{position}]",
        )
        _reject_schema_proof_branches(
            current,
            label=f"{label}.source_json_pointer[{position}]",
        )
        if current.get("type") == "array":
            minimum = current.get("minItems")
            if not isinstance(minimum, int) or isinstance(minimum, bool):
                raise ProfileError(
                    f"{label}.source_json_pointer 的数组 minItems 无法证明"
                )
            index = _array_index_within_length(
                token,
                minimum,
                label=f"{label}.source_json_pointer",
            )
            item_schema = _array_item_schema(
                response_schema,
                current,
                index,
                label=f"{label}.source_json_pointer[{position}]",
            )
            array_frames.append((current, index, item_schema))
            current = item_schema
            continue
        if current.get("type") != "object":
            raise ProfileError(
                f"{label}.source_json_pointer 无法从当前 Schema 进入 {token}"
            )
        properties = current.get("properties")
        required = current.get("required")
        if not isinstance(properties, dict) or token not in properties:
            raise ProfileError(f"{label}.source_json_pointer 指向不存在的字段：{token}")
        if not isinstance(required, list) or token not in required:
            raise ProfileError(f"{label}.source_json_pointer 指向非必有字段：{token}")
        if position == len(tokens) - 1:
            content_parent = current
        child = properties[token]
        if not isinstance(child, dict):
            raise ProfileError(f"{label}.source_json_pointer 字段 Schema 无效：{token}")
        current = child

    if len(array_frames) != 1:
        raise ProfileError(f"{label}.source_json_pointer 必须穿过恰好一个选择数组")
    choice_array, choice_index, choice_schema = array_frames[0]
    choice_count = gates["choice_count"]
    _expect_equal(
        choice_array.get("minItems"),
        choice_count,
        label=f"{label}.choice_array.minItems",
    )
    _expect_equal(
        choice_array.get("maxItems"),
        choice_count,
        label=f"{label}.choice_array.maxItems",
    )
    if choice_index >= choice_count:
        raise ProfileError(f"{label}.source_json_pointer 选择下标越界")
    finish_reason = _required_property_const(
        response_schema,
        choice_schema,
        "finish_reason",
        label=f"{label}.choice",
    )
    _expect_equal(
        finish_reason,
        gates["finish_reason"],
        label=f"{label}.choice.finish_reason.const",
    )
    if content_parent is None:
        raise ProfileError(f"{label}.source_json_pointer 没有内容父对象")
    assistant_role = _required_property_const(
        response_schema,
        content_parent,
        "role",
        label=f"{label}.message",
    )
    _expect_equal(
        assistant_role,
        gates["assistant_role"],
        label=f"{label}.message.role.const",
    )
    content_schema = _resolve_local_schema_node(
        response_schema,
        current,
        label=f"{label}.content",
    )
    _reject_schema_proof_branches(content_schema, label=f"{label}.content")
    _expect_equal(
        content_schema.get("type"),
        normalization["input_type"],
        label=f"{label}.content.type",
    )
    task_witness = _schema_witness(
        task_schema,
        task_schema,
        label=f"{label}.task_output_satisfiability",
    )
    parse_top_level = normalization["parse"]["required_top_level_type"]
    _expect_equal(
        task_schema.get("type"),
        parse_top_level,
        label=f"{label}.parse.required_top_level_type",
    )
    parse_witness = json.dumps(
        task_witness,
        ensure_ascii=False,
        separators=(",", ":"),
    )
    _assert_schema_accepts_value(
        response_schema,
        current,
        parse_witness,
        label=f"{label}.content",
    )
    response_with_task_output = deepcopy(response_witness)
    _replace_json_pointer_value(
        response_with_task_output,
        tokens,
        parse_witness,
        label=f"{label}.source_json_pointer",
    )
    _assert_schema_accepts_value(
        response_schema,
        response_schema,
        response_with_task_output,
        label=f"{label}.response_with_task_output",
    )


def _validate_retry_consistency(
    registry: dict[str, Any],
    profile: dict[str, Any],
    normalization: dict[str, Any],
    *,
    label: str,
) -> None:
    expected = profile["sampling"]["automatic_retries"]
    _expect_equal(
        registry["automatic_retries"],
        expected,
        label=f"{label}.registry.automatic_retries",
    )
    recovery = normalization["recovery"]
    for field in ("automatic_retry_count", "request_retry_count"):
        _expect_equal(
            recovery[field],
            expected,
            label=f"{label}.normalization_policy.recovery.{field}",
        )


def _validate_provider_policy(
    policy: dict[str, Any],
    *,
    selected_provider: str,
    label: str,
) -> None:
    if policy.get("default_chain_changed") is not False:
        raise ProfileError(f"{label}.default_chain_changed 必须是 false")
    providers = policy.get("providers")
    if not isinstance(providers, dict):
        raise ProfileError(f"{label}.providers 必须是对象")
    selected = providers.get(selected_provider)
    if not isinstance(selected, dict):
        raise ProfileError(f"{label} 缺少当前供应商策略：{selected_provider}")
    for provider_name, row in providers.items():
        if not isinstance(row, dict):
            raise ProfileError(f"{label}.providers.{provider_name} 必须是对象")
        action = row.get("default_action")
        if not isinstance(action, str) or not action.startswith("deny"):
            raise ProfileError(f"{label}.providers.{provider_name} 默认动作必须是 deny")
        if row.get("may_replace_default_chain") is True:
            raise ProfileError(f"{label}.providers.{provider_name} 不得替换默认链")


def _validate_context_sources(
    context: dict[str, Any],
    prompt: dict[str, Any],
    *,
    label: str,
) -> None:
    slots = context["input_slots"]
    referenced_slots: set[str] = set()
    prompt_reference_seen = False
    for index, message in enumerate(context["message_plan"]):
        source = message["content_from"]
        if source == "prompt_manifest.prompt_file":
            prompt_reference_seen = True
            if message["role"] != prompt["message_role"]:
                raise ProfileError(
                    f"{label}.message_plan[{index}] 的角色与提示词清单不一致"
                )
            continue
        prefix = "input_slots."
        slot = source[len(prefix) :]
        if slot not in slots:
            raise ProfileError(
                f"{label}.message_plan[{index}] 指向不存在的输入槽：{slot}"
            )
        referenced_slots.add(slot)
    if not prompt_reference_seen:
        raise ProfileError(f"{label}.message_plan 未引用提示词文件")
    missing = sorted(set(slots) - referenced_slots)
    if missing:
        raise ProfileError(f"{label}.message_plan 未使用输入槽：{missing}")


def _load_and_validate_rule_bundle(
    registry: dict[str, Any],
    row: dict[str, Any],
) -> tuple[dict[str, Any], _BundleReader]:
    bundle_id = row["bundle_id"]
    label = f"rule_bundles[{bundle_id}]"
    reader = _BundleReader()
    items_by_source = {item["source"]: item for item in row["materialize_items"]}
    closure: dict[str, str] = {}

    def add_reference(
        reference: dict[str, Any],
        *,
        reference_label: str,
        required_root: str | None = None,
    ) -> bytes:
        reference = _require_exact_keys(
            reference,
            REFERENCE_KEYS,
            label=reference_label,
        )
        path = reference["path"]
        digest = reference["sha256"]
        if required_root is not None and not _path_is_below(path, required_root):
            raise ProfileError(f"{reference_label}.path 必须位于 {required_root}/ 下")
        previous = closure.get(path)
        if previous is not None and previous != digest:
            raise ProfileError(f"{reference_label} 与已有引用 SHA 冲突：{path}")
        item = items_by_source.get(path)
        if item is None:
            raise ProfileError(f"{reference_label} 缺少物化项：{path}")
        if item["sha256"] != digest:
            raise ProfileError(f"{reference_label} 与物化项 SHA 不一致：{path}")
        closure[path] = digest
        return reader.read(reference, label=reference_label)

    fixed_schemas: dict[str, dict[str, Any]] = {}
    for name, schema_path in _fixed_validation_schema_paths().items():
        source = _constant_repo_relative(
            schema_path,
            label=f"{label}.{name}_schema",
        )
        item = items_by_source.get(source)
        if item is None:
            raise ProfileError(f"{label} 缺少固定验证 Schema：{source}")
        raw = add_reference(
            {"path": source, "sha256": item["sha256"]},
            reference_label=f"{label}.{name}_schema",
        )
        schema = _decode_json_object(raw, label=source)
        _validate_schema_document(
            schema,
            label=f"{label}.{name}_schema",
        )
        fixed_schemas[name] = schema

    api = reader.read_json(
        row["api_contract_bundle"],
        label=f"{label}.api_contract_bundle",
    )
    add_reference(
        row["api_contract_bundle"],
        reference_label=f"{label}.api_contract_bundle",
        required_root=MAIN_REFERENCE_ROOTS["api_contract_bundle"],
    )
    prompt = reader.read_json(
        row["prompt_manifest"],
        label=f"{label}.prompt_manifest",
    )
    add_reference(
        row["prompt_manifest"],
        reference_label=f"{label}.prompt_manifest",
        required_root=MAIN_REFERENCE_ROOTS["prompt_manifest"],
    )
    context = reader.read_json(
        row["context_recipe"],
        label=f"{label}.context_recipe",
    )
    add_reference(
        row["context_recipe"],
        reference_label=f"{label}.context_recipe",
        required_root=MAIN_REFERENCE_ROOTS["context_recipe"],
    )
    task_schema = reader.read_json(
        row["task_output_schema"],
        label=f"{label}.task_output_schema",
    )
    add_reference(
        row["task_output_schema"],
        reference_label=f"{label}.task_output_schema",
        required_root=MAIN_REFERENCE_ROOTS["task_output_schema"],
    )

    _validate_instance(
        api,
        fixed_schemas["contract_bundle"],
        label=f"{label}.api_contract_bundle",
    )
    _validate_instance(
        prompt,
        fixed_schemas["prompt_manifest"],
        label=f"{label}.prompt_manifest",
    )
    _validate_instance(
        context,
        fixed_schemas["context_recipe"],
        label=f"{label}.context_recipe",
    )
    _validate_schema_document(
        task_schema,
        label=f"{label}.task_output_schema",
    )

    api_documents: dict[str, dict[str, Any]] = {}
    for name in API_BUNDLE_REFERENCE_KEYS:
        raw = add_reference(
            api[name],
            reference_label=f"{label}.api_contract_bundle.{name}",
        )
        api_documents[name] = _decode_json_object(
            raw,
            label=api[name]["path"],
        )

    prompt_raw = add_reference(
        prompt["prompt_file"],
        reference_label=f"{label}.prompt_manifest.prompt_file",
        required_root="config/prompts",
    )
    add_reference(
        prompt["task_output_schema"],
        reference_label=f"{label}.prompt_manifest.task_output_schema",
        required_root="config/contracts",
    )
    for name, root in MAIN_REFERENCE_ROOTS.items():
        context_field = {
            "api_contract_bundle": "api_contract_bundle",
            "prompt_manifest": "prompt_manifest",
            "task_output_schema": "task_output_schema",
        }.get(name)
        if context_field is not None:
            add_reference(
                context[context_field],
                reference_label=f"{label}.context_recipe.{context_field}",
                required_root=root,
            )

    actual_sources = set(items_by_source)
    expected_sources = set(closure)
    missing = sorted(expected_sources - actual_sources)
    extra = sorted(actual_sources - expected_sources)
    if missing or extra:
        raise ProfileError(
            f"{label}.materialize_items 与引用闭包不一致：缺少={missing}，多出={extra}"
        )

    profile = api_documents["profile"]
    provider = api_documents["provider_config"]
    provider_policy = api_documents["provider_access_policy"]
    request_schema = api_documents["request_envelope_schema"]
    response_schema = api_documents["response_envelope_schema"]
    normalization = api_documents["normalization_policy"]

    _validate_instance(
        profile,
        fixed_schemas["profile"],
        label=f"{label}.profile",
    )
    _validate_schema_document(
        request_schema,
        label=f"{label}.request_envelope_schema",
    )
    _validate_schema_document(
        response_schema,
        label=f"{label}.response_envelope_schema",
    )
    for schema_name, schema_document in (
        ("request_envelope_schema", request_schema),
        ("response_envelope_schema", response_schema),
        ("task_output_schema", task_schema),
    ):
        _validate_local_schema_reference_graph(
            schema_document,
            label=f"{label}.{schema_name}",
        )
    normalization_defs = fixed_schemas["contract_bundle"].get("$defs")
    if (
        not isinstance(normalization_defs, dict)
        or "normalization_document" not in normalization_defs
    ):
        raise ProfileError(
            f"{label}.contract_bundle_schema 缺少 normalization_document"
        )
    normalization_schema = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$defs": deepcopy(normalization_defs),
        "$ref": "#/$defs/normalization_document",
    }
    _validate_schema_document(
        normalization_schema,
        label=f"{label}.normalization_wrapper_schema",
    )
    _validate_instance(
        normalization,
        normalization_schema,
        label=f"{label}.normalization_policy",
    )
    _reject_inline_credentials(api, label=f"{label}.api_contract_bundle")
    _reject_inline_credentials(profile, label=f"{label}.profile")
    _reject_inline_credentials(provider, label=f"{label}.provider_config")
    _reject_inline_credentials(
        provider_policy,
        label=f"{label}.provider_access_policy",
    )
    _validate_provider_policy(
        provider_policy,
        selected_provider=api["provider"],
        label=f"{label}.provider_access_policy",
    )

    profile_row = _registered_profile_row(registry, row["profile_id"])
    _expect_equal(
        api["profile_id"],
        row["profile_id"],
        label=f"{label}.api_contract_bundle.profile_id",
    )
    _expect_equal(
        profile["profile_id"],
        row["profile_id"],
        label=f"{label}.profile.profile_id",
    )
    _expect_equal(
        api["profile"],
        {"path": profile_row["path"], "sha256": api["profile"]["sha256"]},
        label=f"{label}.api_contract_bundle.profile.path",
    )
    _expect_equal(
        profile["provider_config"],
        api["provider_config"]["path"],
        label=f"{label}.profile.provider_config",
    )
    _expect_equal(
        profile["provider"],
        api["provider"],
        label=f"{label}.profile.provider",
    )
    _expect_equal(
        profile["transport"],
        api["transport"],
        label=f"{label}.profile.transport",
    )
    _expect_equal(
        profile["model_binding"]["request_model_id"],
        api["request_model_id"],
        label=f"{label}.profile.request_model_id",
    )
    _expect_equal(
        profile["model_binding"]["expected_response_model"],
        api["expected_response_model"],
        label=f"{label}.profile.expected_response_model",
    )

    optional_provider_matches = {
        "provider": api["provider"],
        "base_url": api["api_address"]["base_url"],
        "endpoint": api["api_address"]["endpoint"],
        "api_key_env": api["auth"]["api_key_env"],
        "response_format_compatibility": api["transport"],
    }
    for key, expected in optional_provider_matches.items():
        if key in provider:
            _expect_equal(
                provider[key],
                expected,
                label=f"{label}.provider_config.{key}",
            )
    models = provider.get("models")
    if models is not None:
        if not isinstance(models, list):
            raise ProfileError(f"{label}.provider_config.models 必须是数组")
        matches = [
            item
            for item in models
            if isinstance(item, dict)
            and item.get("model_id") == api["request_model_id"]
        ]
        if len(matches) != 1:
            raise ProfileError(f"{label}.provider_config 中请求模型必须恰好出现一次")
        model_row = matches[0]
        if model_row.get("call_ready") is not True:
            raise ProfileError(f"{label}.provider_config 未把请求模型标为可调用")
        expected_model = model_row.get(
            "expected_response_model",
            model_row.get("model_id"),
        )
        _expect_equal(
            expected_model,
            api["expected_response_model"],
            label=f"{label}.provider_config.expected_response_model",
        )

    _validate_profile_request_contract(
        profile,
        request_schema,
        label=f"{label}.request_envelope_schema",
    )
    _expect_equal(
        normalization["envelope_gates"]["expected_model"],
        api["expected_response_model"],
        label=f"{label}.normalization_policy.expected_model",
    )
    _validate_response_normalization_contract(
        response_schema,
        normalization,
        task_schema,
        label=f"{label}.response_envelope_schema",
    )
    _validate_retry_consistency(
        registry,
        profile,
        normalization,
        label=label,
    )
    task_top_level = task_schema.get("type")
    if isinstance(task_top_level, str):
        _expect_equal(
            normalization["parse"]["required_top_level_type"],
            task_top_level,
            label=f"{label}.normalization_policy.required_top_level_type",
        )

    _expect_equal(
        prompt["prompt_id"],
        row["bundle_id"],
        label=f"{label}.prompt_manifest.prompt_id",
    )
    _expect_equal(
        prompt["status"],
        row["status"],
        label=f"{label}.prompt_manifest.status",
    )
    _expect_equal(
        prompt["task_output_schema"],
        row["task_output_schema"],
        label=f"{label}.prompt_manifest.task_output_schema",
    )
    _expect_equal(
        context["recipe_id"],
        row["bundle_id"],
        label=f"{label}.context_recipe.recipe_id",
    )
    _expect_equal(
        context["status"],
        row["status"],
        label=f"{label}.context_recipe.status",
    )
    _expect_equal(
        context["profile_id"],
        row["profile_id"],
        label=f"{label}.context_recipe.profile_id",
    )
    for name in (
        "api_contract_bundle",
        "prompt_manifest",
        "task_output_schema",
    ):
        _expect_equal(
            context[name],
            row[name],
            label=f"{label}.context_recipe.{name}",
        )
    _expect_equal(
        context["capability_limits"],
        RESOLVED_CAPABILITY_LIMITS,
        label=f"{label}.context_recipe.capability_limits",
    )
    _validate_context_sources(
        context,
        prompt,
        label=f"{label}.context_recipe",
    )

    try:
        prompt_text = prompt_raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ProfileError(f"{label}.prompt_file 不是 UTF-8") from exc
    if not prompt_text.strip():
        raise ProfileError(f"{label}.prompt_file 不得为空")
    if (
        profile["json_output"]["prompt_must_contain_json"]
        and "json" not in prompt_text.casefold()
    ):
        raise ProfileError(f"{label}.prompt_file 必须满足调用档声明的 JSON 提示约束")
    _validate_request_instance_contract(
        profile,
        request_schema,
        context,
        prompt_text,
        label=f"{label}.request_envelope_schema.actual_request",
    )

    for index, item in enumerate(row["materialize_items"]):
        reader.read(
            {"path": item["source"], "sha256": item["sha256"]},
            label=f"{label}.materialize_items[{index}]",
        )
    reader.verify_unchanged()
    return row, reader


def _validated_rule_bundles() -> list[tuple[dict[str, Any], _BundleReader]]:
    registry, registry_path, registry_raw = _load_registry_secure_snapshot()
    _validate_registry_document(registry)
    validated = [
        _load_and_validate_rule_bundle(registry, row)
        for row in sorted(
            registry["rule_bundles"],
            key=lambda item: item["bundle_id"],
        )
    ]
    for _, reader in validated:
        reader.track_snapshot(registry_path, registry_raw)
        reader.verify_unchanged()
    return validated


def validate_all_rule_bundles() -> list[str]:
    try:
        _validated_rule_bundles()
    except ProfileError as exc:
        return [str(exc)]
    return []


def list_rule_bundles() -> list[dict[str, str]]:
    return [
        {
            "bundle_id": row["bundle_id"],
            "profile_id": row["profile_id"],
            "status": row["status"],
        }
        for row, _ in _validated_rule_bundles()
    ]


def load_rule_bundle(bundle_id: str) -> dict[str, Any]:
    matches = [
        row for row, _ in _validated_rule_bundles() if row["bundle_id"] == bundle_id
    ]
    if len(matches) != 1:
        raise ProfileError(f"找不到规则包：{bundle_id}")
    return deepcopy(matches[0])


def resolve_rule_bundle(bundle_id: str) -> dict[str, Any]:
    matches = [
        (row, reader)
        for row, reader in _validated_rule_bundles()
        if row["bundle_id"] == bundle_id
    ]
    if len(matches) != 1:
        raise ProfileError(f"找不到规则包：{bundle_id}")
    row, reader = matches[0]
    reader.verify_unchanged()
    return {
        "contract_version": "model-call-resolved-bundle-v1",
        "bundle_id": row["bundle_id"],
        "profile_id": row["profile_id"],
        "status": row["status"],
        "capability_limits": deepcopy(RESOLVED_CAPABILITY_LIMITS),
        "items": [
            {
                "role": item["role"],
                "source": item["source"],
                "destination": item["destination"],
                "bytes": len(reader.bytes_for(item["source"])),
                "sha256": item["sha256"],
                "source_type": "file",
            }
            for item in sorted(
                row["materialize_items"],
                key=lambda value: value["destination"],
            )
        ],
    }


def profile_paths() -> list[Path]:
    paths: list[Path] = []
    for row in registry_rows():
        raw_path = row.get("path")
        if not isinstance(raw_path, str) or not raw_path:
            raise ProfileError("registry.json 中存在空的 profile path")
        path = (ROOT / raw_path).resolve()
        if not path.is_relative_to(CONFIG_ROOT.resolve()):
            raise ProfileError(f"配置路径越出 model_call_profiles：{raw_path}")
        paths.append(path)
    return paths


def load_profile(profile_id: str) -> dict[str, Any]:
    for row, path in zip(registry_rows(), profile_paths(), strict=True):
        if row.get("profile_id") == profile_id:
            profile = read_json(path)
            if profile.get("profile_id") != profile_id:
                raise ProfileError(
                    f"登记 ID 与文件内 ID 不一致：{profile_id} / "
                    f"{profile.get('profile_id')}"
                )
            return profile
    raise ProfileError(f"找不到模型调用档：{profile_id}")


def load_provider(profile: dict[str, Any]) -> dict[str, Any]:
    raw_path = profile["provider_config"]
    path = (ROOT / raw_path).resolve()
    providers_root = (ROOT / "config/providers").resolve()
    if not path.is_relative_to(providers_root):
        raise ProfileError(f"供应商配置路径越界：{raw_path}")
    provider = read_json(path)
    if provider.get("provider") != profile.get("provider"):
        raise ProfileError(f"{profile['profile_id']} 的供应商名与 {raw_path} 不一致")
    return provider


def find_provider_model(
    provider: dict[str, Any],
    request_model_id: str,
) -> dict[str, Any]:
    models = provider.get("models")
    if not isinstance(models, list):
        raise ProfileError("供应商配置缺少 models 数组")
    matches = [
        row
        for row in models
        if isinstance(row, dict) and row.get("model_id") == request_model_id
    ]
    if len(matches) != 1:
        raise ProfileError(
            f"请求模型 {request_model_id} 在供应商目录中必须恰好出现一次，"
            f"现在是 {len(matches)} 次"
        )
    return matches[0]


def _validate_registry() -> list[str]:
    errors: list[str] = []
    registry = load_registry()
    rows = registry.get("profiles", [])
    ids = [row.get("profile_id") for row in rows if isinstance(row, dict)]
    if len(ids) != len(set(ids)):
        errors.append("registry.json 存在重复 profile_id")
    preferred = registry.get("preferred_profiles", {})
    if not isinstance(preferred, dict):
        errors.append("registry.json 的 preferred_profiles 必须是对象")
    else:
        for model_name, profile_id in preferred.items():
            if profile_id not in ids:
                errors.append(f"{model_name} 指向不存在的配置档 {profile_id}")
    return errors


def validate_profile(
    profile: dict[str, Any],
    *,
    path: Path | None = None,
) -> list[str]:
    errors: list[str] = []
    label = str(path or profile.get("profile_id") or "<unknown>")
    schema = read_json(PROFILE_SCHEMA_PATH)
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    for error in sorted(
        validator.iter_errors(profile),
        key=lambda item: list(item.path),
    ):
        location = ".".join(str(part) for part in error.path) or "$"
        errors.append(f"{label}: {location}: {error.message}")
    if errors:
        return errors

    try:
        provider = load_provider(profile)
        binding = profile["model_binding"]
        provider_model = find_provider_model(provider, binding["request_model_id"])
    except ProfileError as exc:
        return [f"{label}: {exc}"]

    if provider_model.get("call_ready") is not True:
        errors.append(f"{label}: 供应商目录没有把该模型标为可调用")
    expected = provider_model.get(
        "expected_response_model",
        provider_model.get("model_id"),
    )
    if expected != binding["expected_response_model"]:
        errors.append(
            f"{label}: 期望响应模型不一致：profile={binding['expected_response_model']} "
            f"provider={expected}"
        )

    sampling = profile["sampling"]
    thinking = sampling["thinking"]
    output = profile["json_output"]
    provider_parameters = output["provider_parameters"]
    forbidden = set(output["forbidden_request_fields"])
    present_forbidden = forbidden.intersection(provider_parameters)
    if present_forbidden:
        errors.append(
            f"{label}: provider_parameters 出现被禁止字段 {sorted(present_forbidden)}"
        )
    if sampling["output_token_limit"]["send_parameter"] is not False:
        errors.append(f"{label}: 当前配置不得发送客户端输出 token 上限")

    if profile["provider"] == "qianwen_platform":
        if profile["transport"] != "openai_chat_completions":
            errors.append(f"{label}: 千问档必须使用 Chat Completions")
        if thinking["enabled"]:
            if provider_parameters.get("enable_thinking") is not True:
                errors.append(f"{label}: 思考档必须显式 enable_thinking=true")
            if "response_format" in provider_parameters:
                errors.append(f"{label}: 千问思考档禁止同时发送 response_format")
            if profile["streaming"]["enabled"] is not True:
                errors.append(f"{label}: 当前千问思考档必须使用流式返回")
        else:
            if provider_parameters.get("enable_thinking") is not False:
                errors.append(f"{label}: JSON Object 档必须显式关闭思考")
            if provider_parameters.get("response_format") != {"type": "json_object"}:
                errors.append(f"{label}: 非思考档必须发送 JSON Object 约束")

    if profile["provider"] == "volcengine_agent_plan":
        arkcli = profile.get("arkcli")
        if not isinstance(arkcli, dict):
            errors.append(f"{label}: Agent Plan 档缺少 arkcli 配置")
            return errors
        if profile["transport"] != "arkcli_responses":
            errors.append(f"{label}: Agent Plan 档必须使用 Responses 传输")
        if provider.get("arkcli_profile") != arkcli.get("profile"):
            errors.append(f"{label}: arkcli profile 与供应商配置不一致")
        credential = provider.get("credential_source")
        if not isinstance(credential, dict):
            errors.append(f"{label}: Agent Plan 供应商配置缺少凭证来源")
        else:
            if credential.get("mode") != "arkcli_profile_managed":
                errors.append(f"{label}: Agent Plan 必须由 arkcli profile 管理凭证")
            if credential.get("profile") != arkcli.get("profile"):
                errors.append(f"{label}: 凭证 profile 与模型档不一致")
            if credential.get("unset_environment_before_call") != arkcli.get(
                "unset_environment"
            ):
                errors.append(f"{label}: 环境覆盖清单与供应商配置不一致")
        if arkcli.get("credential_source") != "arkcli_profile_managed":
            errors.append(f"{label}: 模型档不得改用环境变量 API Key")
        required_unset = {
            "ARK_API_KEY",
            "ARK_BASE_URL",
            "ARK_REGION",
            "ARK_PROFILE",
            "VOLCENGINE_AGENT_PLAN_API_KEY",
        }
        if set(arkcli.get("unset_environment", [])) != required_unset:
            errors.append(f"{label}: Agent Plan 环境覆盖清单不完整")
        if arkcli.get("thinking") != ("enabled" if thinking["enabled"] else "disabled"):
            errors.append(f"{label}: arkcli thinking 与 sampling 不一致")
        if arkcli.get("reasoning_effort") != thinking["effort"]:
            errors.append(f"{label}: arkcli reasoning effort 与 sampling 不一致")
        if arkcli.get("text_format") != "json_object":
            errors.append(f"{label}: 当前首轮只允许已验证的 JSON Object 档")
        if binding["request_model_id"].startswith("deepseek-v4-"):
            if thinking["effort"] != "high":
                errors.append(f"{label}: DeepSeek V4 首轮冻结为 High")
        if binding["request_model_id"] == "minimax-m3-modelhub":
            if thinking["effort"] is not None:
                errors.append(f"{label}: MiniMax M3 不得强塞未经确认的思考档位")
            expected_mode = (
                "provider_json_object_hint_exact_fence_normalization_local_schema"
            )
            if output["mode"] != expected_mode:
                errors.append(f"{label}: MiniMax M3 不得冒充供应商强制 JSON")
            expected_normalization = {
                "provider_guarantees_raw_json": False,
                "accepted_raw_shapes": [
                    "raw_json_object",
                    "exact_single_lowercase_json_fence",
                ],
                "allow_prefix_or_suffix_prose": False,
                "raw_receipt_may_be_reclassified": False,
                "normalized_status_name": "normalized_quality_pass",
            }
            if output.get("normalization_policy") != expected_normalization:
                errors.append(f"{label}: MiniMax M3 精确围栏标准化策略漂移")
        elif "normalization_policy" in output:
            errors.append(f"{label}: 非 MiniMax 档不得继承围栏标准化策略")

    return errors


def validate_all_profiles() -> list[str]:
    errors = _validate_registry()
    for path in profile_paths():
        try:
            profile = read_json(path)
        except ProfileError as exc:
            errors.append(str(exc))
            continue
        errors.extend(validate_profile(profile, path=path))
    return errors


def _contains_json_word(value: Any) -> bool:
    return "json" in json.dumps(value, ensure_ascii=False).lower()


def render_qianwen_request(
    profile: dict[str, Any],
    messages: list[dict[str, Any]],
) -> dict[str, Any]:
    if profile["provider"] != "qianwen_platform":
        raise ProfileError("这不是千问调用档")
    if not isinstance(messages, list) or not messages:
        raise ProfileError("千问预览输入必须包含非空 messages 数组")
    if profile["json_output"]["prompt_must_contain_json"] and not _contains_json_word(
        messages
    ):
        raise ProfileError("Prompt 必须明确包含 JSON 一词")
    provider = load_provider(profile)
    body: dict[str, Any] = {
        "model": profile["model_binding"]["request_model_id"],
        "messages": deepcopy(messages),
        "temperature": profile["sampling"]["temperature"],
        "stream": profile["streaming"]["enabled"],
    }
    body.update(deepcopy(profile["json_output"]["provider_parameters"]))
    forbidden = set(profile["json_output"]["forbidden_request_fields"])
    present = forbidden.intersection(body)
    if present:
        raise ProfileError(f"请求体出现被禁止字段：{sorted(present)}")
    return {
        "provider": profile["provider"],
        "transport": profile["transport"],
        "method": "POST",
        "url": provider["base_url"].rstrip("/") + provider["endpoint"],
        "api_key_env": provider["api_key_env"],
        "expected_response_model": profile["model_binding"]["expected_response_model"],
        "body": body,
    }


def render_agent_plan_command(
    profile: dict[str, Any],
    *,
    prompt: str,
    instructions: str | None = None,
) -> dict[str, Any]:
    if profile["provider"] != "volcengine_agent_plan":
        raise ProfileError("这不是 Agent Plan 调用档")
    if not prompt.strip():
        raise ProfileError("Agent Plan 预览输入必须包含非空 prompt")
    prompt_scope = {"prompt": prompt, "instructions": instructions or ""}
    if profile["json_output"]["prompt_must_contain_json"] and not _contains_json_word(
        prompt_scope
    ):
        raise ProfileError("Prompt 或 instructions 必须明确包含 JSON 一词")
    provider = load_provider(profile)
    arkcli = profile["arkcli"]
    unset_environment = list(arkcli["unset_environment"])
    unset_arguments = [
        argument for variable in unset_environment for argument in ("-u", variable)
    ]
    argv = [
        "env",
        *unset_arguments,
        "arkcli",
        "+chat",
        prompt,
        "--profile",
        arkcli["profile"],
        "--model",
        profile["model_binding"]["request_model_id"],
        "--temperature",
        str(profile["sampling"]["temperature"]),
        "--thinking",
        arkcli["thinking"],
        "--text-format",
        arkcli["text_format"],
        "--format",
        "json",
        "--no-progress",
    ]
    if instructions:
        argv.extend(["--instructions", instructions])
    if arkcli["reasoning_effort"] is not None:
        argv.extend(["--reasoning-effort", arkcli["reasoning_effort"]])
    if profile["streaming"]["enabled"]:
        argv.extend(["--stream", "--include-events"])
    if "--max-output-tokens" in argv:
        raise ProfileError("当前配置禁止发送 --max-output-tokens")
    return {
        "provider": profile["provider"],
        "transport": profile["transport"],
        "base_url": provider["base_url"],
        "credential_source": arkcli["credential_source"],
        "unset_environment": unset_environment,
        "expected_response_model": profile["model_binding"]["expected_response_model"],
        "argv": argv,
    }


def render(profile: dict[str, Any], input_payload: dict[str, Any]) -> dict[str, Any]:
    errors = validate_profile(profile)
    if errors:
        raise ProfileError("\n".join(errors))
    if profile["provider"] == "qianwen_platform":
        return render_qianwen_request(profile, input_payload.get("messages"))
    return render_agent_plan_command(
        profile,
        prompt=str(input_payload.get("prompt", "")),
        instructions=input_payload.get("instructions"),
    )


def command_validate(_: argparse.Namespace) -> int:
    errors = [*validate_all_profiles(), *validate_all_rule_bundles()]
    if errors:
        for error in errors:
            print(f"FAIL {error}", file=sys.stderr)
        return 1
    print(
        f"PASS 已校验 {len(profile_paths())} 个模型调用档和 "
        f"{len(rule_bundle_rows())} 个规则包；"
        "全程离线，未读取凭证，未发模型请求。"
    )
    return 0


def command_list(_: argparse.Namespace) -> int:
    registry = load_registry()
    preferred = set(registry.get("preferred_profiles", {}).values())
    for row in registry_rows():
        marker = "推荐" if row["profile_id"] in preferred else "对照"
        print(f"{marker}\t{row['profile_id']}\t{row['role']}")
    return 0


def command_show(args: argparse.Namespace) -> int:
    print(json.dumps(load_profile(args.profile_id), ensure_ascii=False, indent=2))
    return 0


def command_render(args: argparse.Namespace) -> int:
    profile = load_profile(args.profile_id)
    input_payload = read_json(Path(args.input).expanduser().resolve())
    result = render(profile, input_payload)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def command_list_bundles(_: argparse.Namespace) -> int:
    for row in list_rule_bundles():
        print(f"{row['status']}\t{row['bundle_id']}\t{row['profile_id']}")
    return 0


def command_show_bundle(args: argparse.Namespace) -> int:
    value = load_rule_bundle(args.bundle_id)
    print(json.dumps(value, ensure_ascii=False, indent=2))
    return 0


def command_resolve_bundle(args: argparse.Namespace) -> int:
    value = resolve_rule_bundle(args.bundle_id)
    print(json.dumps(value, ensure_ascii=False, indent=2))
    return 0


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(
        description="离线检查和预览模型调用配置；不会发送模型请求。"
    )
    commands = value.add_subparsers(dest="command", required=True)
    validate = commands.add_parser("validate", help="校验全部配置")
    validate.set_defaults(func=command_validate)
    list_command = commands.add_parser("list", help="列出配置档")
    list_command.set_defaults(func=command_list)
    show = commands.add_parser("show", help="查看一个配置档")
    show.add_argument("profile_id")
    show.set_defaults(func=command_show)
    render_command = commands.add_parser("render", help="生成请求预览，不发网")
    render_command.add_argument("profile_id")
    render_command.add_argument("--input", required=True)
    render_command.set_defaults(func=command_render)
    list_bundles = commands.add_parser("list-bundles", help="列出离线规则包")
    list_bundles.set_defaults(func=command_list_bundles)
    show_bundle = commands.add_parser(
        "show-bundle",
        help="查看一个离线规则包登记",
    )
    show_bundle.add_argument("bundle_id")
    show_bundle.set_defaults(func=command_show_bundle)
    resolve_bundle = commands.add_parser(
        "resolve-bundle",
        help="解析为可放进 S0 物化计划的离线 items",
    )
    resolve_bundle.add_argument("bundle_id")
    resolve_bundle.set_defaults(func=command_resolve_bundle)
    return value


def main() -> int:
    args = parser().parse_args()
    try:
        return int(args.func(args))
    except ProfileError as exc:
        print(f"FAIL {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

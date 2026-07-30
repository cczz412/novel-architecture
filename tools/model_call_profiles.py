#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from copy import deepcopy
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker


ROOT = Path(__file__).resolve().parents[1]
CONFIG_ROOT = ROOT / "config/model_call_profiles"
REGISTRY_PATH = CONFIG_ROOT / "registry.json"
PROFILE_SCHEMA_PATH = CONFIG_ROOT / "profile.schema.json"


class ProfileError(RuntimeError):
    pass


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
        raise ProfileError(
            f"{profile['profile_id']} 的供应商名与 {raw_path} 不一致"
        )
    return provider


def find_provider_model(
    provider: dict[str, Any], request_model_id: str
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


def validate_profile(profile: dict[str, Any], *, path: Path | None = None) -> list[str]:
    errors: list[str] = []
    label = str(path or profile.get("profile_id") or "<unknown>")
    schema = read_json(PROFILE_SCHEMA_PATH)
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    for error in sorted(validator.iter_errors(profile), key=lambda item: list(item.path)):
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
        "expected_response_model", provider_model.get("model_id")
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
            f"{label}: provider_parameters 出现被禁止字段 "
            f"{sorted(present_forbidden)}"
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
            if provider_parameters.get("response_format") != {
                "type": "json_object"
            }:
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
        if arkcli.get("thinking") != (
            "enabled" if thinking["enabled"] else "disabled"
        ):
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
                "provider_json_object_hint_exact_fence_"
                "normalization_local_schema"
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
    profile: dict[str, Any], messages: list[dict[str, Any]]
) -> dict[str, Any]:
    if profile["provider"] != "qianwen_platform":
        raise ProfileError("这不是千问调用档")
    if not isinstance(messages, list) or not messages:
        raise ProfileError("千问预览输入必须包含非空 messages 数组")
    if (
        profile["json_output"]["prompt_must_contain_json"]
        and not _contains_json_word(messages)
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
        "expected_response_model": profile["model_binding"][
            "expected_response_model"
        ],
        "body": body,
    }


def render_agent_plan_command(
    profile: dict[str, Any], *, prompt: str, instructions: str | None = None
) -> dict[str, Any]:
    if profile["provider"] != "volcengine_agent_plan":
        raise ProfileError("这不是 Agent Plan 调用档")
    if not prompt.strip():
        raise ProfileError("Agent Plan 预览输入必须包含非空 prompt")
    prompt_scope = {"prompt": prompt, "instructions": instructions or ""}
    if (
        profile["json_output"]["prompt_must_contain_json"]
        and not _contains_json_word(prompt_scope)
    ):
        raise ProfileError("Prompt 或 instructions 必须明确包含 JSON 一词")
    provider = load_provider(profile)
    arkcli = profile["arkcli"]
    unset_environment = list(arkcli["unset_environment"])
    unset_arguments = [
        argument
        for variable in unset_environment
        for argument in ("-u", variable)
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
        "expected_response_model": profile["model_binding"][
            "expected_response_model"
        ],
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
    errors = validate_all_profiles()
    if errors:
        for error in errors:
            print(f"FAIL {error}", file=sys.stderr)
        return 1
    print(f"PASS 已校验 {len(profile_paths())} 个模型调用档；未发模型请求。")
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

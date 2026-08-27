"""CCZ-57 / GH#176: M3 A-stage deterministic, zero-network shell."""

from __future__ import annotations

import hashlib
import json
import os
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

SCHEMA_VERSION = "m3-zero-api-shell-r01"
TOOL_BUNDLE_ID = "baseline-r01.1"
PROVIDER_PROTOCOLS = frozenset({"openrouter_chat_completions", "ark_responses"})
VISIBLE_TOOLS = (
    "read_current_c2_segment",
    "submit_baseline_candidate",
    "request_human_review",
    "declare_no_progress",
)
REVISION_KEYS = frozenset({"chapter_id", "revision_no", "revision_text_sha256"})
C1_KEYS = frozenset(
    {
        "contract",
        "version",
        "id",
        "title",
        "kind",
        "text",
        "added_at",
        "chapter_revision_ref",
    }
)
RUN_IDENTITY_KEYS = frozenset(
    {
        "run_id",
        "provider_protocol",
        "model",
        "upstream_identity",
        "reasoning",
        "config",
    }
)
TOOL_IDENTITY_CONFIG_KEYS = frozenset(
    {
        "tool_bundle_id",
        "tool_provider_payload_sha256",
        "tool_internal_schema_sha256",
    }
)
SENSITIVE_REQUEST_KEYS = frozenset(
    {
        "authorization",
        "headers",
        "api_key",
        "api-key",
        "apikey",
        "access_token",
        "secret",
        "cookie",
        "set-cookie",
        "x-api-key",
        "proxy-authorization",
    }
)
C3_KEYS = frozenset(
    {"contract", "version", "chapter_revision_ref", "text", "quote", "seg"}
)


class MechanicalGateError(ValueError):
    """A fail-closed mechanical gate rejected the supplied evidence."""

    PARENT_CODES = {
        "request_binding": "REQUEST_IDENTITY_MISMATCH",
        "provider_envelope": "PROVIDER_ENVELOPE_REJECTED",
    }

    def __init__(self, layer: str, code: str, detail: str = "") -> None:
        super().__init__(f"{layer}:{code}{':' + detail if detail else ''}")
        self.layer = layer
        self.code = code
        self.detail = detail

    def receipt(self) -> dict[str, str]:
        receipt = {"layer": self.layer, "code": self.code, "detail": self.detail}
        parent_code = self.PARENT_CODES.get(self.layer)
        if parent_code is not None:
            receipt["parent_code"] = parent_code
        return receipt


class NetworkAccessBlocked(RuntimeError):
    """The offline replay attempted a network-capable operation."""


class NetworkAuditGuard:
    """Fail closed on Python socket and child-process audit events."""

    BLOCKED_EXACT = frozenset(
        {
            "os.fork",
            "os.forkpty",
            "os.posix_spawn",
            "os.posix_spawnp",
            "os.spawn",
            "os.system",
            "subprocess.Popen",
        }
    )

    def __init__(self) -> None:
        self.active = False
        self.blocked_events: list[str] = []

    def _audit(self, event: str, _args: tuple[Any, ...]) -> None:
        if not self.active:
            return
        if (
            event.startswith("socket.")
            or event.startswith("os.exec")
            or event.startswith("subprocess.")
            or event in self.BLOCKED_EXACT
        ):
            self.blocked_events.append(event)
            raise NetworkAccessBlocked(f"OFFLINE_NETWORK_OR_PROCESS_BLOCKED:{event}")

    def __enter__(self) -> NetworkAuditGuard:
        sys.addaudithook(self._audit)
        self.active = True
        return self

    def __exit__(self, _exc_type, _exc, _traceback) -> None:
        self.active = False


def canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def strict_json_loads(raw: str | bytes, *, layer: str) -> Any:
    def reject_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise MechanicalGateError(layer, "DUPLICATE_JSON_KEY", key)
            result[key] = value
        return result

    try:
        return json.loads(raw, object_pairs_hook=reject_duplicates)
    except MechanicalGateError:
        raise
    except (json.JSONDecodeError, UnicodeDecodeError, TypeError) as exc:
        raise MechanicalGateError(layer, "INVALID_JSON", str(exc)) from exc


def _reject_sensitive_request_keys(value: object, *, layer: str) -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            if isinstance(key, str) and key.lower() in SENSITIVE_REQUEST_KEYS:
                raise MechanicalGateError(
                    layer, "REQUEST_CONTAINS_CREDENTIAL_MATERIAL", key
                )
            _reject_sensitive_request_keys(child, layer=layer)
    elif isinstance(value, list):
        for child in value:
            _reject_sensitive_request_keys(child, layer=layer)


def _load_safe_request_body(raw: bytes, *, layer: str) -> dict:
    try:
        request = strict_json_loads(raw, layer=layer)
    except MechanicalGateError as exc:
        raise MechanicalGateError(
            layer, "REQUEST_SHAPE_INVALID", f"{exc.code}:{exc.detail}"
        ) from exc
    if not isinstance(request, dict):
        raise MechanicalGateError(layer, "REQUEST_SHAPE_INVALID", "not_object")
    _reject_sensitive_request_keys(request, layer=layer)
    return request


def _require_exact_keys(value: object, keys: frozenset[str], *, layer: str) -> dict:
    if not isinstance(value, dict):
        raise MechanicalGateError(layer, "NOT_OBJECT")
    missing = sorted(keys - value.keys())
    extra = sorted(value.keys() - keys)
    if missing:
        raise MechanicalGateError(layer, "MISSING_FIELDS", ",".join(missing))
    if extra:
        raise MechanicalGateError(layer, "EXTRA_FIELDS", ",".join(extra))
    return value


def validate_revision_ref(value: object, *, layer: str = "revision") -> dict:
    ref = _require_exact_keys(value, REVISION_KEYS, layer=layer)
    chapter_id = ref["chapter_id"]
    revision_no = ref["revision_no"]
    digest = ref["revision_text_sha256"]
    if (
        not isinstance(chapter_id, str)
        or len(chapter_id) < 3
        or not chapter_id.startswith("c")
        or not chapter_id[1:].isdigit()
    ):
        raise MechanicalGateError(layer, "BAD_CHAPTER_ID")
    if isinstance(revision_no, bool) or not isinstance(revision_no, int) or revision_no < 1:
        raise MechanicalGateError(layer, "BAD_REVISION_NO")
    if (
        not isinstance(digest, str)
        or len(digest) != 64
        or any(char not in "0123456789abcdef" for char in digest)
    ):
        raise MechanicalGateError(layer, "BAD_REVISION_SHA256")
    return dict(ref)


def freeze_run_identity(value: object) -> dict:
    identity = _require_exact_keys(value, RUN_IDENTITY_KEYS, layer="run_identity")
    for key in ("run_id", "model"):
        if not isinstance(identity[key], str) or not identity[key].strip():
            raise MechanicalGateError("run_identity", "BAD_TEXT_FIELD", key)
    if identity["provider_protocol"] not in PROVIDER_PROTOCOLS:
        raise MechanicalGateError("run_identity", "UNKNOWN_PROTOCOL")
    for key in ("upstream_identity", "reasoning", "config"):
        if not isinstance(identity[key], dict):
            raise MechanicalGateError("run_identity", "BAD_OBJECT_FIELD", key)
    upstream = identity["upstream_identity"]
    expected_upstream_key = (
        "provider"
        if identity["provider_protocol"] == "openrouter_chat_completions"
        else "endpoint"
    )
    if set(upstream) != {expected_upstream_key}:
        raise MechanicalGateError(
            "run_identity", "BAD_UPSTREAM_IDENTITY", expected_upstream_key
        )
    if (
        not isinstance(upstream[expected_upstream_key], str)
        or not upstream[expected_upstream_key].strip()
    ):
        raise MechanicalGateError("run_identity", "EMPTY_UPSTREAM_IDENTITY")
    reasoning = identity["reasoning"]
    if not isinstance(reasoning.get("mode"), str) or not reasoning["mode"].strip():
        raise MechanicalGateError("run_identity", "REASONING_MODE_REQUIRED")
    config = identity["config"]
    if config.get("tool_bundle_id") != TOOL_BUNDLE_ID:
        raise MechanicalGateError("run_identity", "TOOL_BUNDLE_ID_MISMATCH")
    bundle = pack_tool_bundle(
        protocol=identity["provider_protocol"],
        exact_model_identity=(
            {
                "model": identity["model"],
                "provider": identity["upstream_identity"]["provider"],
            }
            if identity["provider_protocol"] == "openrouter_chat_completions"
            else {
                "model": identity["model"],
                "endpoint": identity["upstream_identity"]["endpoint"],
            }
        ),
    )
    expected_tool_hashes = {
        "tool_provider_payload_sha256": bundle["provider_payload_sha256"],
        "tool_internal_schema_sha256": bundle[
            "canonical_internal_schema_sha256"
        ],
    }
    for key, expected in expected_tool_hashes.items():
        if config.get(key) != expected:
            raise MechanicalGateError("run_identity", "TOOL_BUNDLE_HASH_MISMATCH", key)
    frozen_bytes = canonical_json_bytes(identity)
    return {
        "identity": strict_json_loads(frozen_bytes, layer="run_identity_canonical"),
        "canonical_sha256": sha256_bytes(frozen_bytes),
        "canonical_bytes": len(frozen_bytes),
    }


def provider_binding_from_run_identity(value: object) -> tuple[str, dict]:
    identity = freeze_run_identity(value)["identity"]
    protocol = identity["provider_protocol"]
    if protocol == "openrouter_chat_completions":
        response_identity = {
            "model": identity["model"],
            "provider": identity["upstream_identity"]["provider"],
        }
    else:
        response_identity = {
            "model": identity["model"],
            "endpoint": identity["upstream_identity"]["endpoint"],
        }
    return protocol, response_identity


def validate_c1(c1: object, *, current_revision_ref: object) -> dict:
    chapter = _require_exact_keys(c1, C1_KEYS, layer="c1")
    if chapter["contract"] != "C1_CHAPTER_DOC" or chapter["version"] != "v1":
        raise MechanicalGateError("c1", "IDENTITY_MISMATCH")
    ref = validate_revision_ref(chapter["chapter_revision_ref"], layer="c1_revision")
    current = validate_revision_ref(current_revision_ref, layer="current_revision")
    if ref != current:
        raise MechanicalGateError("current_revision", "STALE_OR_MISMATCH")
    if chapter["id"] != ref["chapter_id"]:
        raise MechanicalGateError("c1", "CHAPTER_ID_MISMATCH")
    if chapter["kind"] != "draft":
        raise MechanicalGateError("c1", "BAD_KIND")
    for key in ("title", "text", "added_at"):
        if not isinstance(chapter[key], str):
            raise MechanicalGateError("c1", "BAD_TEXT_FIELD", key)
    if sha256_bytes(chapter["text"].encode("utf-8")) != ref["revision_text_sha256"]:
        raise MechanicalGateError("c1", "REVISION_TEXT_HASH_MISMATCH")
    return dict(chapter)


def validate_c2(c2: object, *, current_revision_ref: object) -> dict:
    keys = frozenset(
        {
            "contract",
            "version",
            "chapter_revision_ref",
            "seg",
            "text",
            "start",
            "end",
            "halo_before",
            "halo_after",
        }
    )
    segment = _require_exact_keys(c2, keys, layer="c2")
    if segment["contract"] != "C2_SEGMENT" or segment["version"] != "v1":
        raise MechanicalGateError("c2", "IDENTITY_MISMATCH")
    ref = validate_revision_ref(segment["chapter_revision_ref"], layer="c2_revision")
    current = validate_revision_ref(current_revision_ref, layer="current_revision")
    if ref != current:
        raise MechanicalGateError("current_revision", "STALE_OR_MISMATCH")
    if (
        isinstance(segment["seg"], bool)
        or not isinstance(segment["seg"], int)
        or segment["seg"] < 1
    ):
        raise MechanicalGateError("c2", "BAD_SEG")
    if not all(isinstance(segment[key], str) for key in ("text", "halo_before", "halo_after")):
        raise MechanicalGateError("c2", "BAD_TEXT_OR_HALO")
    start, end = segment["start"], segment["end"]
    if (
        isinstance(start, bool)
        or not isinstance(start, int)
        or start < 0
        or isinstance(end, bool)
        or not isinstance(end, int)
        or end != start + len(segment["text"])
    ):
        raise MechanicalGateError("c2", "BAD_OFFSETS")
    return dict(segment)


@dataclass(frozen=True)
class RawAttemptReceipt:
    schema_version: str
    run_id: str
    attempt_no: int
    http_status: int
    request_sha256: str
    request_bytes: int
    response_sha256: str
    response_bytes: int
    run_identity_sha256: str
    run_identity_bytes: int


@dataclass(frozen=True)
class RequestBindingReceipt:
    schema_version: str
    binding_pass: bool
    provider_protocol: str
    tool_bundle_id: str
    request_sha256: str
    request_bytes: int
    run_identity_sha256: str
    config_sha256: str
    reasoning_sha256: str
    upstream_identity_sha256: str
    tool_provider_payload_sha256: str
    tool_internal_schema_sha256: str


class RawAttemptStore:
    """Append-only raw bytes. Existing attempts are never overwritten."""

    def __init__(self, root: Path) -> None:
        self.root = root

    def append(
        self,
        *,
        run_id: str,
        attempt_no: int,
        http_status: object,
        request: bytes,
        response: bytes,
        run_identity: object,
    ) -> RawAttemptReceipt:
        if not run_id or run_id in {".", ".."} or any(char in run_id for char in "/\\"):
            raise MechanicalGateError("attempt", "BAD_RUN_ID")
        if isinstance(attempt_no, bool) or not isinstance(attempt_no, int) or attempt_no < 1:
            raise MechanicalGateError("attempt", "BAD_ATTEMPT_NO")
        if (
            isinstance(http_status, bool)
            or not isinstance(http_status, int)
            or not 100 <= http_status <= 599
        ):
            raise MechanicalGateError("attempt", "BAD_HTTP_STATUS")
        # request.raw is a safe request body, never a full HTTP exchange. Refuse
        # malformed bodies and credential-bearing keys before any bytes hit disk.
        _load_safe_request_body(request, layer="request_storage")
        frozen_identity = freeze_run_identity(run_identity)
        if frozen_identity["identity"]["run_id"] != run_id:
            raise MechanicalGateError("attempt", "RUN_IDENTITY_MISMATCH")
        identity_bytes = canonical_json_bytes(frozen_identity["identity"])
        run_root = self.root / run_id
        try:
            run_root.mkdir(parents=True, mode=0o700, exist_ok=True)
        except OSError as exc:
            raise MechanicalGateError("attempt", "RUN_DIRECTORY_INVALID") from exc
        identity_path = run_root / "run_identity.json"
        try:
            self._exclusive_write(identity_path, identity_bytes)
        except FileExistsError:
            try:
                existing_identity = identity_path.read_bytes()
            except OSError as exc:
                raise MechanicalGateError("attempt", "RUN_IDENTITY_UNREADABLE") from exc
            if existing_identity != identity_bytes:
                raise MechanicalGateError("attempt", "RUN_IDENTITY_DRIFT")
        target = run_root / f"attempt-{attempt_no:04d}"
        try:
            target.mkdir(parents=True, mode=0o700, exist_ok=False)
        except FileExistsError as exc:
            raise MechanicalGateError("attempt", "IMMUTABLE_ALREADY_EXISTS") from exc
        receipt = RawAttemptReceipt(
            schema_version=SCHEMA_VERSION,
            run_id=run_id,
            attempt_no=attempt_no,
            http_status=http_status,
            request_sha256=sha256_bytes(request),
            request_bytes=len(request),
            response_sha256=sha256_bytes(response),
            response_bytes=len(response),
            run_identity_sha256=frozen_identity["canonical_sha256"],
            run_identity_bytes=frozen_identity["canonical_bytes"],
        )
        try:
            self._exclusive_write(target / "request.raw", request)
            self._exclusive_write(target / "response.raw", response)
            self._exclusive_write(target / "receipt.json", canonical_json_bytes(asdict(receipt)))
        except Exception:
            # Do not hide a partial append. Its directory remains occupied and must be audited.
            raise
        return receipt

    @staticmethod
    def _exclusive_write(path: Path, payload: bytes) -> None:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())


def verify_raw_attempt(path: Path) -> RawAttemptReceipt:
    receipt_raw = (path / "receipt.json").read_bytes()
    data = strict_json_loads(receipt_raw, layer="attempt_receipt")
    receipt = RawAttemptReceipt(**data)
    identity_payload = (path.parent / "run_identity.json").read_bytes()
    if (
        len(identity_payload) != receipt.run_identity_bytes
        or sha256_bytes(identity_payload) != receipt.run_identity_sha256
    ):
        raise MechanicalGateError(
            "attempt", "RAW_HASH_OR_SIZE_MISMATCH", "run_identity.json"
        )
    for name, expected_hash, expected_size in (
        ("request.raw", receipt.request_sha256, receipt.request_bytes),
        ("response.raw", receipt.response_sha256, receipt.response_bytes),
    ):
        payload = (path / name).read_bytes()
        if len(payload) != expected_size or sha256_bytes(payload) != expected_hash:
            raise MechanicalGateError("attempt", "RAW_HASH_OR_SIZE_MISMATCH", name)
    return receipt


def load_verified_run_identity(path: Path) -> dict:
    receipt = verify_raw_attempt(path)
    raw = (path.parent / "run_identity.json").read_bytes()
    identity = strict_json_loads(raw, layer="run_identity_file")
    frozen = freeze_run_identity(identity)
    if (
        frozen["canonical_sha256"] != receipt.run_identity_sha256
        or frozen["canonical_bytes"] != receipt.run_identity_bytes
    ):
        raise MechanicalGateError("attempt", "RUN_IDENTITY_RECEIPT_MISMATCH")
    return frozen["identity"]


def load_saved_attempt(path: Path) -> tuple[RawAttemptReceipt, dict, bytes, bytes]:
    receipt = verify_raw_attempt(path)
    identity = load_verified_run_identity(path)
    request_raw = (path / "request.raw").read_bytes()
    response_raw = (path / "response.raw").read_bytes()
    return receipt, identity, request_raw, response_raw


def validate_saved_request_binding(
    request_raw: bytes,
    frozen_run_identity: object,
) -> dict:
    """Bind a saved safe request body to the immutable run identity."""
    request = _load_safe_request_body(request_raw, layer="request_binding")
    frozen = freeze_run_identity(frozen_run_identity)
    identity = frozen["identity"]
    protocol = identity["provider_protocol"]
    config = identity["config"]
    request_config = {
        key: value for key, value in config.items() if key not in TOOL_IDENTITY_CONFIG_KEYS
    }
    common_keys = {"model", "reasoning", "tools", *request_config}
    if protocol == "openrouter_chat_completions":
        allowed_keys = common_keys | {"messages", "provider"}
        provider = request.get("provider")
        if not isinstance(provider, dict):
            raise MechanicalGateError(
                "request_binding", "REQUEST_UPSTREAM_MISMATCH", "provider"
            )
        if set(provider) != {"order", "allow_fallbacks"}:
            raise MechanicalGateError(
                "request_binding", "REQUEST_UPSTREAM_MISMATCH", "provider_shape"
            )
        expected_provider = identity["upstream_identity"]["provider"]
        if provider.get("order") != [expected_provider]:
            raise MechanicalGateError(
                "request_binding", "REQUEST_UPSTREAM_MISMATCH", "provider_order"
            )
        if provider.get("allow_fallbacks") is not False:
            raise MechanicalGateError(
                "request_binding", "REQUEST_FALLBACK_NOT_ALLOWED"
            )
        if not isinstance(request.get("messages"), list):
            raise MechanicalGateError(
                "request_binding", "REQUEST_SHAPE_INVALID", "messages"
            )
    elif protocol == "ark_responses":
        allowed_keys = common_keys | {"input", "endpoint"}
        if request.get("endpoint") != identity["upstream_identity"]["endpoint"]:
            raise MechanicalGateError(
                "request_binding", "REQUEST_UPSTREAM_MISMATCH", "endpoint"
            )
        if not isinstance(request.get("input"), list):
            raise MechanicalGateError(
                "request_binding", "REQUEST_SHAPE_INVALID", "input"
            )
    else:
        raise MechanicalGateError("request_binding", "REQUEST_PROTOCOL_MISMATCH")
    if set(request) != allowed_keys:
        detail = ",".join(sorted(set(request) ^ allowed_keys))
        raise MechanicalGateError("request_binding", "REQUEST_SHAPE_INVALID", detail)
    if request.get("model") != identity["model"]:
        raise MechanicalGateError("request_binding", "REQUEST_MODEL_MISMATCH")
    if request.get("reasoning") != identity["reasoning"]:
        raise MechanicalGateError("request_binding", "REQUEST_REASONING_MISMATCH")
    actual_config = {key: request.get(key) for key in request_config}
    if actual_config != request_config:
        raise MechanicalGateError("request_binding", "REQUEST_CONFIG_MISMATCH")
    tools = request.get("tools")
    if not isinstance(tools, list):
        raise MechanicalGateError("request_binding", "REQUEST_TOOL_BUNDLE_MISMATCH")
    tools_sha = sha256_bytes(canonical_json_bytes(tools))
    if tools_sha != config["tool_provider_payload_sha256"]:
        raise MechanicalGateError("request_binding", "REQUEST_TOOL_BUNDLE_MISMATCH")
    receipt = RequestBindingReceipt(
        schema_version="m3-request-binding-v1",
        binding_pass=True,
        provider_protocol=protocol,
        tool_bundle_id=TOOL_BUNDLE_ID,
        request_sha256=sha256_bytes(request_raw),
        request_bytes=len(request_raw),
        run_identity_sha256=frozen["canonical_sha256"],
        config_sha256=sha256_bytes(canonical_json_bytes(request_config)),
        reasoning_sha256=sha256_bytes(canonical_json_bytes(identity["reasoning"])),
        upstream_identity_sha256=sha256_bytes(
            canonical_json_bytes(identity["upstream_identity"])
        ),
        tool_provider_payload_sha256=tools_sha,
        tool_internal_schema_sha256=config["tool_internal_schema_sha256"],
    )
    return asdict(receipt)


def normalize_openrouter(response_raw: bytes) -> dict:
    response = strict_json_loads(response_raw, layer="provider_envelope")
    if not isinstance(response, dict) or not isinstance(response.get("choices"), list):
        raise MechanicalGateError("provider_envelope", "BAD_OPENROUTER_SHAPE")
    if len(response["choices"]) != 1 or not isinstance(response["choices"][0], dict):
        raise MechanicalGateError("provider_envelope", "EXPECTED_ONE_CHOICE")
    choice = response["choices"][0]
    message = choice.get("message")
    if not isinstance(message, dict):
        raise MechanicalGateError("provider_envelope", "MISSING_MESSAGE")
    tool_calls = []
    native_calls = message.get("tool_calls")
    if native_calls is None:
        native_calls = []
    if not isinstance(native_calls, list):
        raise MechanicalGateError("provider_envelope", "BAD_TOOL_CALLS")
    for item in native_calls:
        if not isinstance(item, dict) or item.get("type") != "function":
            raise MechanicalGateError("provider_envelope", "BAD_TOOL_CALL_TYPE")
        if not isinstance(item.get("function"), dict):
            raise MechanicalGateError("provider_envelope", "BAD_TOOL_CALL")
        function = item["function"]
        tool_calls.append(
            {
                "call_id": item.get("id"),
                "name": function.get("name"),
                "arguments_raw": function.get("arguments"),
            }
        )
    plain = message.get("content")
    if plain is not None and not isinstance(plain, str):
        raise MechanicalGateError("provider_envelope", "BAD_PLAIN_TEXT")
    finish_reason = choice.get("finish_reason")
    if (bool(native_calls) and finish_reason == "stop") or (
        not native_calls and finish_reason == "tool_calls"
    ):
        raise MechanicalGateError(
            "provider_envelope", "FINISH_TOOL_CALL_MISMATCH"
        )
    usage = response.get("usage")
    if usage is None:
        usage = {}
    if not isinstance(usage, dict):
        raise MechanicalGateError("provider_envelope", "BAD_USAGE")
    return _provider_turn(
        protocol="openrouter_chat_completions",
        response_id=response.get("id"),
        exact_model_identity={"model": response.get("model"), "provider": response.get("provider")},
        finish_reason=finish_reason,
        tool_calls=tool_calls,
        plain_text=plain,
        usage=usage,
    )


def normalize_ark(response_raw: bytes) -> dict:
    response = strict_json_loads(response_raw, layer="provider_envelope")
    if not isinstance(response, dict) or not isinstance(response.get("output"), list):
        raise MechanicalGateError("provider_envelope", "BAD_ARK_SHAPE")
    tool_calls = []
    text_parts = []
    for item in response["output"]:
        if not isinstance(item, dict):
            raise MechanicalGateError("provider_envelope", "BAD_ARK_OUTPUT_ITEM")
        if item.get("type") == "function_call":
            call_id = item.get("call_id")
            if not isinstance(call_id, str) or not call_id.strip():
                raise MechanicalGateError("provider_envelope", "BAD_ARK_CALL_ID")
            tool_calls.append(
                {
                    "call_id": call_id,
                    "name": item.get("name"),
                    "arguments_raw": item.get("arguments"),
                }
            )
        elif item.get("type") == "message":
            content = item.get("content")
            if content is None:
                content = []
            if not isinstance(content, list):
                raise MechanicalGateError("provider_envelope", "BAD_ARK_CONTENT")
            for part in content:
                if not isinstance(part, dict):
                    raise MechanicalGateError("provider_envelope", "BAD_ARK_CONTENT_PART")
                if part.get("type") not in {"output_text", "text"}:
                    raise MechanicalGateError(
                        "provider_envelope", "UNKNOWN_ARK_CONTENT_PART_TYPE"
                    )
                if not isinstance(part.get("text"), str):
                    raise MechanicalGateError("provider_envelope", "BAD_ARK_TEXT")
                text_parts.append(part["text"])
        else:
            raise MechanicalGateError("provider_envelope", "UNKNOWN_ARK_OUTPUT_TYPE")
    usage = response.get("usage")
    if usage is None:
        usage = {}
    if not isinstance(usage, dict):
        raise MechanicalGateError("provider_envelope", "BAD_USAGE")
    return _provider_turn(
        protocol="ark_responses",
        response_id=response.get("id"),
        exact_model_identity={"model": response.get("model"), "endpoint": response.get("endpoint")},
        finish_reason=response.get("status"),
        tool_calls=tool_calls,
        plain_text="".join(text_parts) or None,
        usage=usage,
    )


def _provider_turn(
    *,
    protocol: str,
    response_id: object,
    exact_model_identity: dict,
    finish_reason: object,
    tool_calls: list[dict],
    plain_text: str | None,
    usage: object,
) -> dict:
    if tool_calls:
        completion_kind = "TOOL_CALLS"
    elif plain_text:
        completion_kind = "PLAIN_TEXT"
    else:
        completion_kind = "EMPTY"
    return {
        "schema_version": "m3-provider-turn-v1",
        "provider_protocol": protocol,
        "provider_response_id": response_id,
        "exact_model_identity": exact_model_identity,
        "completion_kind": completion_kind,
        "finish_reason": finish_reason,
        "tool_calls": tool_calls,
        "plain_text": plain_text,
        "usage": usage,
    }


def _normalize_for_protocol(response_raw: bytes, protocol: str) -> dict:
    if protocol == "openrouter_chat_completions":
        return normalize_openrouter(response_raw)
    if protocol == "ark_responses":
        return normalize_ark(response_raw)
    raise MechanicalGateError("provider_envelope", "UNKNOWN_PROTOCOL")


def validate_saved_provider_turn(
    attempt_path: Path,
    *,
    current_revision_ref: object | None = None,
    visible_tools: tuple[str, ...] = VISIBLE_TOOLS,
) -> dict:
    receipt, frozen_run_identity, request_raw, response_raw = load_saved_attempt(
        attempt_path
    )
    validate_http_status(receipt.http_status)
    request_binding = validate_saved_request_binding(
        request_raw, frozen_run_identity
    )
    protocol, _expected_identity = provider_binding_from_run_identity(
        frozen_run_identity
    )
    turn = _normalize_for_protocol(response_raw, protocol)
    gate = validate_provider_turn(
        turn,
        frozen_run_identity=frozen_run_identity,
        current_revision_ref=current_revision_ref,
        visible_tools=visible_tools,
    )
    return {
        "attempt_receipt": asdict(receipt),
        "request_binding_receipt": request_binding,
        "provider_turn": turn,
        "gate": gate,
    }


def parse_legacy_extraction(attempt_path: Path) -> dict:
    """Parse old content JSON only; never treats it as an Agent action."""
    receipt, frozen_run_identity, request_raw, response_raw = load_saved_attempt(
        attempt_path
    )
    validate_http_status(receipt.http_status)
    request_binding = validate_saved_request_binding(
        request_raw, frozen_run_identity
    )
    protocol, _expected_identity = provider_binding_from_run_identity(
        frozen_run_identity
    )
    turn = _normalize_for_protocol(response_raw, protocol)
    validate_provider_turn_header(turn, frozen_run_identity=frozen_run_identity)
    if turn["tool_calls"]:
        raise MechanicalGateError("legacy_route", "NATIVE_TOOL_CALL_NOT_LEGACY_CONTENT")
    if not turn["plain_text"]:
        raise MechanicalGateError("legacy_route", "MISSING_CONTENT")
    payload = strict_json_loads(turn["plain_text"], layer="legacy_content")
    if not isinstance(payload, dict):
        raise MechanicalGateError("legacy_content", "NOT_OBJECT")
    return {
        "route": "legacy_content",
        "payload": payload,
        "provider_turn": turn,
        "attempt_receipt": asdict(receipt),
        "request_binding_receipt": request_binding,
    }


def preview_legacy_extraction_as_c3(
    attempt_path: Path,
    *,
    c2: object,
    current_revision_ref: object,
) -> dict:
    """Complete the old content route through outer JSON, facts shape, and evidence."""
    legacy = parse_legacy_extraction(attempt_path)
    payload = _require_exact_keys(legacy["payload"], frozenset({"facts"}), layer="legacy_schema")
    c3 = preview_c3(
        c2=c2,
        current_revision_ref=current_revision_ref,
        facts=payload["facts"],
    )
    return {**legacy, "c3_preview": c3, "mechanical_pass": True, "semantic_pass": None}


def tool_schemas() -> dict[str, dict]:
    revision = {
        "type": "object",
        "additionalProperties": False,
        "required": ["chapter_id", "revision_no", "revision_text_sha256"],
        "properties": {
            "chapter_id": {"type": "string", "pattern": "^c[0-9]{2,}$"},
            "revision_no": {"type": "integer", "minimum": 1},
            "revision_text_sha256": {"type": "string", "pattern": "^[0-9a-f]{64}$"},
        },
    }
    fact = {
        "type": "object",
        "additionalProperties": False,
        "required": ["text"],
        "properties": {
            "text": {"type": "string", "minLength": 1},
            "quote": {"type": "string"},
        },
    }
    return {
        "read_current_c2_segment": {
            "type": "object",
            "additionalProperties": False,
            "required": ["expected_revision_ref"],
            "properties": {"expected_revision_ref": revision},
        },
        "submit_baseline_candidate": {
            "type": "object",
            "additionalProperties": False,
            "required": ["expected_revision_ref", "facts"],
            "properties": {
                "expected_revision_ref": revision,
                "facts": {"type": "array", "items": fact},
            },
        },
        "request_human_review": {
            "type": "object",
            "additionalProperties": False,
            "required": ["reason", "summary"],
            "properties": {
                "reason": {
                    "type": "string",
                    "enum": ["AMBIGUOUS_SOURCE", "CONTRACT_CONFLICT", "OTHER"],
                },
                "summary": {"type": "string", "minLength": 1},
            },
        },
        "declare_no_progress": {
            "type": "object",
            "additionalProperties": False,
            "required": ["error_codes", "summary"],
            "properties": {
                "error_codes": {
                    "type": "array",
                    "minItems": 1,
                    "uniqueItems": True,
                    "items": {"type": "string", "minLength": 1},
                },
                "summary": {"type": "string", "minLength": 1},
            },
        },
    }


TOOL_DESCRIPTIONS = {
    "read_current_c2_segment": "读取当前唯一 C2 责任段。",
    "submit_baseline_candidate": "提交一次 baseline 事实候选，不做修补。",
    "request_human_review": "因明确歧义或合同冲突请求人工处理。",
    "declare_no_progress": "结构化声明无法继续。",
}


def validate_internal_tool_schemas(schemas: dict[str, dict]) -> None:
    if tuple(schemas) != VISIBLE_TOOLS:
        raise MechanicalGateError("tool_bundle", "WRONG_TOOL_SET_OR_ORDER")
    for name, schema in schemas.items():
        try:
            Draft202012Validator.check_schema(schema)
        except Exception as exc:
            raise MechanicalGateError("tool_schema", "INVALID_SCHEMA", name) from exc
        if "$ref" in canonical_json_bytes(schema).decode("utf-8"):
            raise MechanicalGateError("tool_schema", "UNRESOLVED_OR_EXTERNAL_REF", name)


def pack_tool_bundle(*, protocol: str, exact_model_identity: dict) -> dict:
    if protocol not in PROVIDER_PROTOCOLS:
        raise MechanicalGateError("tool_bundle", "UNKNOWN_PROTOCOL")
    schemas = tool_schemas()
    validate_internal_tool_schemas(schemas)
    internal = [
        {"name": name, "description": TOOL_DESCRIPTIONS[name], "parameters": schemas[name]}
        for name in VISIBLE_TOOLS
    ]
    if protocol == "openrouter_chat_completions":
        payload = [{"type": "function", "function": item} for item in internal]
    else:
        payload = [{"type": "function", **item} for item in internal]
    internal_bytes = canonical_json_bytes(internal)
    payload_bytes = canonical_json_bytes(payload)
    return {
        "bundle_contract": "M3_TOOL_SCHEMA_BUNDLE",
        "bundle_version": "r01.1",
        "provider_protocol": protocol,
        "exact_model_identity": exact_model_identity,
        "tool_bundle_id": TOOL_BUNDLE_ID,
        "canonical_internal_schema_sha256": sha256_bytes(internal_bytes),
        "provider_payload_sha256": sha256_bytes(payload_bytes),
        "compatibility_transform_version": "inline-basic-v1",
        "tool_names": list(VISIBLE_TOOLS),
        "canonical_internal_schema": internal,
        "provider_payload": payload,
    }


def validate_provider_turn_header(
    turn: object,
    *,
    frozen_run_identity: object,
) -> str:
    if not isinstance(turn, dict):
        raise MechanicalGateError("provider_turn", "NOT_OBJECT")
    expected_protocol, expected_model_identity = provider_binding_from_run_identity(
        frozen_run_identity
    )
    if turn.get("provider_protocol") != expected_protocol:
        raise MechanicalGateError("identity", "PROTOCOL_MISMATCH")
    if turn.get("exact_model_identity") != expected_model_identity:
        raise MechanicalGateError("identity", "EXACT_MODEL_MISMATCH")
    finish = turn.get("finish_reason")
    allowed_finish = (
        {"tool_calls", "stop"}
        if expected_protocol == "openrouter_chat_completions"
        else {"completed"}
    )
    if finish not in allowed_finish:
        code = (
            "TRUNCATED"
            if finish
            in {"length", "incomplete", "in_progress", "max_output_tokens", "queued"}
            else "BAD_COMPLETION"
        )
        raise MechanicalGateError("completion", code, str(finish))
    return expected_protocol


def validate_provider_turn(
    turn: object,
    *,
    frozen_run_identity: object,
    current_revision_ref: object | None = None,
    visible_tools: tuple[str, ...] = VISIBLE_TOOLS,
) -> dict:
    validate_provider_turn_header(turn, frozen_run_identity=frozen_run_identity)
    calls = turn.get("tool_calls")
    if not isinstance(calls, list):
        raise MechanicalGateError("tool_call", "NOT_ARRAY")
    if len(calls) > 1:
        raise MechanicalGateError("tool_call", "TOO_MANY_CALLS")
    if not calls:
        return {
            "mechanical_pass": True,
            "action": None,
            "plain_text_only": bool(turn.get("plain_text")),
            "semantic_pass": None,
        }
    call = calls[0]
    if not isinstance(call, dict):
        raise MechanicalGateError("tool_call", "NOT_OBJECT")
    call_id = call.get("call_id")
    if not isinstance(call_id, str) or not call_id.strip():
        raise MechanicalGateError("tool_call", "MISSING_CALL_ID")
    name = call.get("name")
    if name not in VISIBLE_TOOLS:
        raise MechanicalGateError("tool_call", "UNKNOWN_TOOL", str(name))
    if name not in visible_tools:
        raise MechanicalGateError("visibility", "TOOL_NOT_VISIBLE", str(name))
    arguments_raw = call.get("arguments_raw")
    if not isinstance(arguments_raw, str):
        raise MechanicalGateError("tool_arguments", "NOT_RAW_STRING")
    arguments = strict_json_loads(arguments_raw, layer="tool_arguments")
    validator = Draft202012Validator(tool_schemas()[name])
    errors = sorted(validator.iter_errors(arguments), key=lambda item: list(item.path))
    if errors:
        raise MechanicalGateError("tool_schema", "ARGUMENTS_INVALID", errors[0].message)
    expected_ref = arguments.get("expected_revision_ref")
    if expected_ref is not None:
        if current_revision_ref is None:
            raise MechanicalGateError("current_revision", "CURRENT_REF_REQUIRED")
        current = validate_revision_ref(current_revision_ref, layer="current_revision")
        supplied = validate_revision_ref(expected_ref, layer="tool_revision")
        if supplied != current:
            raise MechanicalGateError("current_revision", "STALE_OR_MISMATCH")
    return {
        "mechanical_pass": True,
        "action": {"call_id": call_id, "name": name, "arguments": arguments},
        "plain_text_only": False,
        "semantic_pass": None,
    }


def validate_http_status(status: object) -> None:
    if isinstance(status, bool) or not isinstance(status, int) or not 200 <= status < 300:
        raise MechanicalGateError("transport", "HTTP_NOT_SUCCESS", str(status))


def validate_tool_result_call_id(*, original_call_id: str, result_call_id: str) -> None:
    if original_call_id != result_call_id:
        raise MechanicalGateError("tool_result", "CALL_ID_MISMATCH")


def preview_c3(
    *, c2: object, current_revision_ref: object, facts: object
) -> list[dict]:
    segment = validate_c2(c2, current_revision_ref=current_revision_ref)
    if not isinstance(facts, list):
        raise MechanicalGateError("c3_preview", "FACTS_NOT_ARRAY")
    output = []
    for index, fact in enumerate(facts):
        if not isinstance(fact, dict):
            raise MechanicalGateError("c3_preview", "FACT_NOT_OBJECT", str(index))
        if not set(fact).issubset({"text", "quote"}) or "text" not in fact:
            raise MechanicalGateError("c3_preview", "BAD_FACT_FIELDS", str(index))
        text = fact["text"]
        quote = fact.get("quote")
        if not isinstance(text, str) or not text.strip():
            raise MechanicalGateError("c3_preview", "EMPTY_FACT_TEXT", str(index))
        if quote is not None and not isinstance(quote, str):
            raise MechanicalGateError("c3_preview", "BAD_QUOTE", str(index))
        if quote and quote not in segment["text"]:
            raise MechanicalGateError("evidence", "QUOTE_NOT_IN_RESPONSIBILITY_TEXT", str(index))
        item = {
            "contract": "C3_FACT_CANDIDATE",
            "version": "v1",
            "chapter_revision_ref": dict(segment["chapter_revision_ref"]),
            "text": text,
            "seg": segment["seg"],
        }
        if quote is not None:
            item["quote"] = quote
        if not set(item).issubset(C3_KEYS):
            raise MechanicalGateError("c3_preview", "INTERNAL_EXTRA_FIELD")
        output.append(item)
    return output

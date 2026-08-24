"""作者与项目绑定的最小本地工作区。

本模块只提供隔离句柄、受限逻辑键、本地原子提交和不可变上传存储。
它不接现有业务模块，也不把请求正文、显示名或调用方路径当作者身份。
"""

from __future__ import annotations

import copy
import fcntl
import hashlib
import hmac
import json
import os
import re
import secrets
import stat
import tempfile
import weakref
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator, Mapping, NamedTuple


LOGICAL_KEY_FILES = {
    "chapter_admission_operations": "chapter_admission_operations.json",
    "chapter_fact_handover_requests": "chapter_fact_handover_requests.json",
    "chapter_index": "chapter_index.json",
    "chapter_materials": "chapter_materials.json",
    "chapter_revisions": "chapter_revisions.json",
    "chapter_sources": "chapter_sources.json",
    "chapters": "chapters.json",
    "draft": "draft.json",
    "fact_candidate_runs": "fact_candidate_runs.json",
    "fact_candidates": "fact_candidates.json",
    "fact_materialization_runs": "fact_materialization_runs.json",
    "facts": "facts.json",
    "health_report": "health_report.json",
    "input_manifest": "input_manifest.json",
    "ledger_directory": "ledger_directory.json",
    "module_state": "module_state.json",
    "overview_cards": "overview_cards.json",
    "plan": "plan.json",
    "project_state": "project_state.json",
    "reconciliation": "reconciliation.json",
    "recall_handles": "recall_handles.json",
    "scene_cards": "scene_cards.json",
    "segments": "segments.json",
    "settings": "settings.json",
    "state": "state.json",
    "writing_check_results": "writing_check_results.json",
}
IMMUTABLE_KINDS = {"attachment", "module_blob", "raw_upload"}
IMMUTABLE_RECEIPT_KEYS = {
    "blob_id",
    "kind",
    "content_sha256",
    "size",
    "metadata_sha256",
}
PROJECT_ID_RE = re.compile(r"p_[0-9a-f]{32}\Z")
AUTHOR_ID_RE = re.compile(r"a_[0-9a-f]{32}\Z")
GENERATION_ID_RE = re.compile(r"g_[0-9a-f]{64}\Z")
SHA256_RE = re.compile(r"[0-9a-f]{64}\Z")
OPERATION_ID_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}\Z")


class WorkspaceError(RuntimeError):
    """工作区拒绝请求时返回稳定错误码。"""

    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


class AuthenticationError(WorkspaceError):
    """认证主体缺失或形状不合法。"""


class ProjectNotFoundError(WorkspaceError):
    """项目不存在；跨作者猜号也只返回这个错误。"""


class InvalidLogicalKeyError(WorkspaceError):
    """逻辑键不在固定白名单中。"""


class UnsafePathError(WorkspaceError):
    """路径、祖先或叶子触发本地安全拒绝。"""


class VersionConflictError(WorkspaceError):
    """乐观版本或 SHA 与当前可见状态不一致。"""


class OperationConflictError(WorkspaceError):
    """同一 operation_id 被不同请求复用。"""


class IntegrityError(WorkspaceError):
    """不可变对象、指针、manifest 或 blob 漂移。"""


class InjectedWorkspaceCrash(RuntimeError):
    """只供本模块定向故障恢复测试使用。"""


def _canonical_bytes(value: Any) -> bytes:
    try:
        text = json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
    except (TypeError, ValueError) as exc:
        raise WorkspaceError("PAYLOAD_NOT_JSON_SERIALIZABLE") from exc
    return (text + "\n").encode("utf-8")


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace(
        "+00:00", "Z"
    )


def _authenticated_author_id(authenticated_principal: Any) -> str:
    if not isinstance(authenticated_principal, str):
        raise AuthenticationError("AUTHENTICATED_PRINCIPAL_INVALID")
    principal = authenticated_principal.strip()
    if not principal or principal != authenticated_principal:
        raise AuthenticationError("AUTHENTICATED_PRINCIPAL_INVALID")
    digest = hashlib.sha256(
        b"author-workspace-v1\0" + principal.encode("utf-8")
    ).hexdigest()
    return f"a_{digest[:32]}"


def _validate_display_name(display_name: Any) -> str:
    if not isinstance(display_name, str):
        raise WorkspaceError("DISPLAY_NAME_INVALID")
    value = display_name.strip()
    if not value or len(value) > 200 or "\x00" in value:
        raise WorkspaceError("DISPLAY_NAME_INVALID")
    return value


def _validate_project_id(project_id: Any) -> str:
    if not isinstance(project_id, str) or PROJECT_ID_RE.fullmatch(project_id) is None:
        raise ProjectNotFoundError("PROJECT_NOT_FOUND")
    return project_id


def _validate_logical_key(logical_key: Any) -> str:
    if not isinstance(logical_key, str):
        raise InvalidLogicalKeyError("LOGICAL_KEY_NOT_ALLOWED")
    if (
        not logical_key
        or logical_key in {".", ".."}
        or ".." in logical_key
        or "/" in logical_key
        or "\\" in logical_key
        or Path(logical_key).is_absolute()
        or logical_key not in LOGICAL_KEY_FILES
    ):
        raise InvalidLogicalKeyError("LOGICAL_KEY_NOT_ALLOWED")
    return logical_key


def _validate_operation_id(operation_id: Any) -> str:
    if (
        not isinstance(operation_id, str)
        or OPERATION_ID_RE.fullmatch(operation_id) is None
    ):
        raise WorkspaceError("OPERATION_ID_INVALID")
    return operation_id


def _validate_immutable_kind(kind: Any) -> str:
    if not isinstance(kind, str) or kind not in IMMUTABLE_KINDS:
        raise WorkspaceError("IMMUTABLE_KIND_NOT_ALLOWED")
    return kind


# LOCAL_FILESYSTEM_ONLY: Path、flock、fsync 与权限实现全部集中在此后端。
class _LocalFilesystemBackend:
    def __init__(self, runtime_root: Path):
        if not runtime_root.is_absolute():
            raise UnsafePathError("RUNTIME_ROOT_MUST_BE_ABSOLUTE")
        current = Path(runtime_root.anchor)
        for part in runtime_root.parts[1:]:
            current = current / part
            self._reject_symlink(current)
        self.runtime_root = runtime_root
        self._failure_hook = None
        self._handle_secret = secrets.token_bytes(32)
        self._assert_safe_path(runtime_root)

    def _handle_binding_token(self, author_id: str, project_id: str) -> bytes:
        return hmac.digest(
            self._handle_secret,
            f"{author_id}\0{project_id}".encode("utf-8"),
            "sha256",
        )

    def _verify_handle_binding(
        self,
        author_id: str,
        project_id: str,
        binding_token: object,
    ) -> None:
        expected = self._handle_binding_token(author_id, project_id)
        if not isinstance(binding_token, bytes) or not hmac.compare_digest(
            binding_token,
            expected,
        ):
            raise AuthenticationError("AUTHOR_WORKSPACE_BINDING_INVALID")

    def _issue_workspace(
        self,
        author_id: str,
        project_id: str,
    ) -> "AuthorWorkspace":
        handle = object.__new__(AuthorWorkspace)
        _AUTHOR_WORKSPACE_BINDINGS[handle] = _AuthorWorkspaceBinding(
            backend=self,
            author_id=author_id,
            project_id=project_id,
            binding_token=self._handle_binding_token(author_id, project_id),
        )
        return handle

    def _assert_safe_path(self, path: Path) -> None:
        try:
            relative = path.relative_to(self.runtime_root)
        except ValueError as exc:
            raise UnsafePathError("PATH_OUTSIDE_RUNTIME_ROOT") from exc
        current = self.runtime_root
        self._reject_symlink(current)
        for part in relative.parts:
            current = current / part
            self._reject_symlink(current)

    @staticmethod
    def _reject_symlink(path: Path) -> None:
        try:
            mode = path.lstat().st_mode
        except FileNotFoundError:
            return
        if stat.S_ISLNK(mode):
            raise UnsafePathError("SYMLINK_NOT_ALLOWED")

    def _ensure_dir(self, path: Path) -> None:
        self._assert_safe_path(path)
        paths = [self.runtime_root]
        if path != self.runtime_root:
            current = self.runtime_root
            for part in path.relative_to(self.runtime_root).parts:
                current = current / part
                paths.append(current)
        for directory in paths:
            self._reject_symlink(directory)
            try:
                os.mkdir(directory, 0o700)
                self._fsync_directory(directory.parent)
            except FileExistsError:
                if not directory.is_dir():
                    raise UnsafePathError("DIRECTORY_REQUIRED")
            os.chmod(directory, 0o700, follow_symlinks=False)

    @staticmethod
    def _fsync_directory(path: Path) -> None:
        descriptor = os.open(path, os.O_RDONLY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)

    def _atomic_write(self, path: Path, payload: bytes) -> None:
        self._assert_safe_path(path)
        if not path.parent.is_dir():
            raise UnsafePathError("PARENT_DIRECTORY_MISSING")
        descriptor, temporary_name = tempfile.mkstemp(
            prefix=f".{path.name}.",
            suffix=".tmp",
            dir=path.parent,
        )
        temporary = Path(temporary_name)
        try:
            os.fchmod(descriptor, 0o600)
            with os.fdopen(descriptor, "wb", closefd=True) as handle:
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
            self._reject_symlink(path)
            os.replace(temporary, path)
            os.chmod(path, 0o600, follow_symlinks=False)
            self._fsync_directory(path.parent)
        finally:
            if temporary.exists():
                temporary.unlink()

    def _write_immutable(self, path: Path, payload: bytes) -> None:
        self._ensure_dir(path.parent)
        self._assert_safe_path(path)
        self._reject_symlink(path)
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        try:
            descriptor = os.open(path, flags, 0o600)
        except FileExistsError:
            if self._read_bytes(path) != payload:
                raise IntegrityError("IMMUTABLE_OBJECT_COLLISION")
            return
        try:
            os.fchmod(descriptor, 0o600)
            with os.fdopen(descriptor, "wb", closefd=True) as handle:
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
        finally:
            if descriptor >= 0:
                try:
                    os.close(descriptor)
                except OSError:
                    pass
        self._fsync_directory(path.parent)

    def _read_bytes(self, path: Path) -> bytes:
        self._assert_safe_path(path)
        self._reject_symlink(path)
        flags = os.O_RDONLY
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        try:
            descriptor = os.open(path, flags)
        except FileNotFoundError:
            raise
        try:
            if not stat.S_ISREG(os.fstat(descriptor).st_mode):
                raise UnsafePathError("REGULAR_FILE_REQUIRED")
            with os.fdopen(descriptor, "rb", closefd=True) as handle:
                return handle.read()
        finally:
            try:
                os.close(descriptor)
            except OSError:
                pass

    def _read_json(self, path: Path) -> Any:
        try:
            return json.loads(self._read_bytes(path))
        except json.JSONDecodeError as exc:
            raise IntegrityError("INVALID_WORKSPACE_JSON") from exc

    def _remove_file(self, path: Path) -> None:
        self._assert_safe_path(path)
        self._reject_symlink(path)
        try:
            path.unlink()
        except FileNotFoundError:
            return
        self._fsync_directory(path.parent)

    def _author_dir(self, author_id: str) -> Path:
        if AUTHOR_ID_RE.fullmatch(author_id) is None:
            raise AuthenticationError("AUTHOR_ID_INVALID")
        return self.runtime_root / "authors" / author_id

    def _project_dir(self, author_id: str, project_id: str) -> Path:
        return self._author_dir(author_id) / "projects" / project_id

    def create_project(self, author_id: str, display_name: str) -> "AuthorWorkspace":
        projects_dir = self._author_dir(author_id) / "projects"
        self._ensure_dir(projects_dir)
        for _ in range(32):
            project_id = f"p_{secrets.token_hex(16)}"
            project_dir = projects_dir / project_id
            self._assert_safe_path(project_dir)
            try:
                os.mkdir(project_dir, 0o700)
            except FileExistsError:
                continue
            os.chmod(project_dir, 0o700, follow_symlinks=False)
            self._fsync_directory(projects_dir)
            metadata = {
                "schema_version": "author-workspace-project-v1",
                "project_id": project_id,
                "author_id": author_id,
                "display_name": display_name,
                "created_at": _now(),
            }
            self._atomic_write(project_dir / "project.json", _canonical_bytes(metadata))
            return self._issue_workspace(author_id, project_id)
        raise WorkspaceError("PROJECT_ID_ALLOCATION_FAILED")

    def _require_project(self, author_id: str, project_id: str) -> Path:
        project_id = _validate_project_id(project_id)
        project_dir = self._project_dir(author_id, project_id)
        self._assert_safe_path(project_dir)
        metadata_path = project_dir / "project.json"
        self._assert_safe_path(metadata_path)
        if not project_dir.is_dir() or not metadata_path.exists():
            raise ProjectNotFoundError("PROJECT_NOT_FOUND")
        metadata = self._read_json(metadata_path)
        if (
            not isinstance(metadata, dict)
            or metadata.get("project_id") != project_id
            or metadata.get("author_id") != author_id
        ):
            raise ProjectNotFoundError("PROJECT_NOT_FOUND")
        return project_dir

    def open_project(self, author_id: str, project_id: str) -> "AuthorWorkspace":
        self._require_project(author_id, project_id)
        return self._issue_workspace(author_id, project_id)

    def list_projects(self, author_id: str) -> list[dict[str, Any]]:
        projects_dir = self._author_dir(author_id) / "projects"
        self._assert_safe_path(projects_dir)
        if not projects_dir.exists():
            return []
        if not projects_dir.is_dir():
            raise UnsafePathError("DIRECTORY_REQUIRED")
        projects: list[dict[str, Any]] = []
        with os.scandir(projects_dir) as entries:
            for entry in entries:
                if entry.is_symlink():
                    raise UnsafePathError("SYMLINK_NOT_ALLOWED")
                if not entry.is_dir(follow_symlinks=False):
                    continue
                if PROJECT_ID_RE.fullmatch(entry.name) is None:
                    continue
                project_dir = projects_dir / entry.name
                metadata_path = project_dir / "project.json"
                self._assert_safe_path(metadata_path)
                if not metadata_path.exists():
                    continue
                metadata = self._read_json(metadata_path)
                if not isinstance(metadata, dict):
                    raise IntegrityError("PROJECT_METADATA_INVALID")
                if metadata.get("author_id") != author_id:
                    raise IntegrityError("PROJECT_AUTHOR_BINDING_MISMATCH")
                projects.append(
                    {
                        "project_id": entry.name,
                        "display_name": metadata.get("display_name"),
                        "created_at": metadata.get("created_at"),
                    }
                )
        return sorted(projects, key=lambda item: item["project_id"])

    @contextmanager
    def _exclusive_lock(self, project_dir: Path) -> Iterator[None]:
        lock_path = project_dir / ".workspace.lock"
        self._assert_safe_path(lock_path)
        self._reject_symlink(lock_path)
        flags = os.O_RDWR | os.O_CREAT
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        descriptor = os.open(lock_path, flags, 0o600)
        try:
            os.fchmod(descriptor, 0o600)
            fcntl.flock(descriptor, fcntl.LOCK_EX)
            yield
        finally:
            fcntl.flock(descriptor, fcntl.LOCK_UN)
            os.close(descriptor)

    def _current_pointer_path(self, project_dir: Path) -> Path:
        return project_dir / "state" / "CURRENT.json"

    def _prepare_journal_path(self, project_dir: Path) -> Path:
        return project_dir / "transactions" / "prepare.json"

    def _receipt_path(self, project_dir: Path, operation_id: str) -> Path:
        digest = hashlib.sha256(operation_id.encode("utf-8")).hexdigest()
        return project_dir / "receipts" / f"op_{digest}.json"

    def _read_current_pointer(self, project_dir: Path) -> dict[str, Any] | None:
        pointer_path = self._current_pointer_path(project_dir)
        self._assert_safe_path(pointer_path)
        if not pointer_path.exists():
            return None
        pointer = self._read_json(pointer_path)
        if (
            not isinstance(pointer, dict)
            or GENERATION_ID_RE.fullmatch(str(pointer.get("generation_id"))) is None
            or SHA256_RE.fullmatch(str(pointer.get("manifest_sha256"))) is None
        ):
            raise IntegrityError("CURRENT_POINTER_INVALID")
        return pointer

    def _load_manifest(
        self,
        project_dir: Path,
        author_id: str,
        project_id: str,
    ) -> tuple[dict[str, Any] | None, dict[str, Any]]:
        pointer = self._read_current_pointer(project_dir)
        if pointer is None:
            return None, {"entries": {}}
        manifest_path = (
            project_dir
            / "generations"
            / pointer["generation_id"]
            / "manifest.json"
        )
        manifest_bytes = self._read_bytes(manifest_path)
        if _sha256_bytes(manifest_bytes) != pointer["manifest_sha256"]:
            raise IntegrityError("GENERATION_MANIFEST_SHA_MISMATCH")
        try:
            manifest = json.loads(manifest_bytes)
        except json.JSONDecodeError as exc:
            raise IntegrityError("GENERATION_MANIFEST_INVALID") from exc
        if (
            not isinstance(manifest, dict)
            or manifest.get("generation_id") != pointer["generation_id"]
            or manifest.get("author_id") != author_id
            or manifest.get("project_id") != project_id
            or not isinstance(manifest.get("entries"), dict)
        ):
            raise IntegrityError("GENERATION_MANIFEST_INVALID")
        return pointer, manifest

    def _read_entry(
        self,
        project_dir: Path,
        logical_key: str,
        entry: Mapping[str, Any],
    ) -> dict[str, Any]:
        blob_sha = str(entry.get("blob_sha256"))
        payload_sha = str(entry.get("payload_sha256"))
        version = entry.get("version")
        if (
            SHA256_RE.fullmatch(blob_sha) is None
            or SHA256_RE.fullmatch(payload_sha) is None
            or not isinstance(version, int)
            or isinstance(version, bool)
            or version <= 0
        ):
            raise IntegrityError("MANIFEST_ENTRY_INVALID")
        blob_path = project_dir / "blobs" / f"{blob_sha}.json"
        blob_bytes = self._read_bytes(blob_path)
        if _sha256_bytes(blob_bytes) != blob_sha:
            raise IntegrityError("STATE_BLOB_SHA_MISMATCH")
        try:
            envelope = json.loads(blob_bytes)
        except json.JSONDecodeError as exc:
            raise IntegrityError("STATE_BLOB_INVALID") from exc
        if (
            envelope.get("logical_key") != logical_key
            or envelope.get("version") != version
            or envelope.get("payload_sha256") != payload_sha
            or _sha256_bytes(_canonical_bytes(envelope.get("payload"))) != payload_sha
        ):
            raise IntegrityError("STATE_BLOB_INVALID")
        return {
            "logical_key": logical_key,
            "version": version,
            "sha256": payload_sha,
            "payload": copy.deepcopy(envelope["payload"]),
        }

    def read(
        self,
        author_id: str,
        project_id: str,
        logical_key: str,
    ) -> dict[str, Any] | None:
        project_dir = self._require_project(author_id, project_id)
        logical_key = _validate_logical_key(logical_key)
        _, manifest = self._load_manifest(project_dir, author_id, project_id)
        entry = manifest["entries"].get(logical_key)
        if entry is None:
            return None
        return self._read_entry(project_dir, logical_key, entry)

    @staticmethod
    def _normalize_expectations(
        mutation_keys: set[str],
        expected_versions: Mapping[str, Any],
    ) -> dict[str, dict[str, Any]]:
        if not isinstance(expected_versions, Mapping):
            raise VersionConflictError("EXPECTED_VERSIONS_INVALID")
        if set(expected_versions) != mutation_keys:
            raise VersionConflictError("EXPECTED_VERSION_KEYS_MISMATCH")
        normalized: dict[str, dict[str, Any]] = {}
        for key in sorted(mutation_keys):
            raw = expected_versions[key]
            if raw is None:
                version, expected_sha = 0, None
            elif isinstance(raw, int) and not isinstance(raw, bool):
                version, expected_sha = raw, None
            elif isinstance(raw, Mapping):
                if set(raw) - {"version", "sha256"}:
                    raise VersionConflictError("EXPECTED_VERSION_SHAPE_INVALID")
                version = raw.get("version")
                expected_sha = raw.get("sha256")
            else:
                raise VersionConflictError("EXPECTED_VERSION_SHAPE_INVALID")
            if (
                not isinstance(version, int)
                or isinstance(version, bool)
                or version < 0
            ):
                raise VersionConflictError("EXPECTED_VERSION_SHAPE_INVALID")
            if expected_sha is not None and (
                not isinstance(expected_sha, str)
                or SHA256_RE.fullmatch(expected_sha) is None
            ):
                raise VersionConflictError("EXPECTED_SHA_INVALID")
            normalized[key] = {"version": version, "sha256": expected_sha}
        return normalized

    def _maybe_fail(self, point: str) -> None:
        if self._failure_hook is not None:
            self._failure_hook(point)

    def _existing_receipt(
        self,
        project_dir: Path,
        operation_id: str,
        request_sha: str,
    ) -> dict[str, Any] | None:
        receipt_path = self._receipt_path(project_dir, operation_id)
        self._assert_safe_path(receipt_path)
        if not receipt_path.exists():
            return None
        receipt = self._read_json(receipt_path)
        if (
            receipt.get("operation_id") != operation_id
            or receipt.get("request_sha256") != request_sha
        ):
            raise OperationConflictError(
                "OPERATION_ID_REUSED_WITH_DIFFERENT_REQUEST"
            )
        return {**receipt, "replayed": True}

    def _recover_unlocked(self, project_dir: Path) -> dict[str, Any]:
        journal_path = self._prepare_journal_path(project_dir)
        self._assert_safe_path(journal_path)
        if not journal_path.exists():
            return {"status": "NO_RECOVERY_NEEDED"}
        journal = self._read_json(journal_path)
        if not isinstance(journal, dict) or journal.get("phase") != "PREPARED":
            raise IntegrityError("PREPARE_JOURNAL_INVALID")
        operation_id = _validate_operation_id(journal.get("operation_id"))
        new_pointer = journal.get("new_pointer")
        old_pointer = journal.get("old_pointer")
        receipt = journal.get("receipt")
        if not isinstance(new_pointer, dict) or not isinstance(receipt, dict):
            raise IntegrityError("PREPARE_JOURNAL_INVALID")
        current_pointer = self._read_current_pointer(project_dir)
        if current_pointer == new_pointer:
            receipt_path = self._receipt_path(project_dir, operation_id)
            self._assert_safe_path(receipt_path)
            if receipt_path.exists():
                existing = self._read_json(receipt_path)
                if existing != receipt:
                    raise IntegrityError("COMMIT_RECEIPT_DRIFT")
            else:
                self._ensure_dir(receipt_path.parent)
                self._atomic_write(receipt_path, _canonical_bytes(receipt))
            self._remove_file(journal_path)
            return {
                "status": "COMMIT_COMPLETED",
                "operation_id": operation_id,
                "generation_id": new_pointer["generation_id"],
            }
        if current_pointer == old_pointer:
            self._remove_file(journal_path)
            return {
                "status": "ROLLED_BACK",
                "operation_id": operation_id,
            }
        raise IntegrityError("RECOVERY_POINTER_DIVERGED")

    def recover(self, author_id: str, project_id: str) -> dict[str, Any]:
        project_dir = self._require_project(author_id, project_id)
        with self._exclusive_lock(project_dir):
            return self._recover_unlocked(project_dir)

    def commit(
        self,
        author_id: str,
        project_id: str,
        operation_id: str,
        mutations: Mapping[str, Any],
        expected_versions: Mapping[str, Any],
        *,
        _guard_versions: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        project_dir = self._require_project(author_id, project_id)
        operation_id = _validate_operation_id(operation_id)
        if not isinstance(mutations, Mapping) or not mutations:
            raise WorkspaceError("MUTATIONS_INVALID")
        validated_mutations = {
            _validate_logical_key(key): copy.deepcopy(value)
            for key, value in mutations.items()
        }
        if len(validated_mutations) != len(mutations):
            raise InvalidLogicalKeyError("LOGICAL_KEY_NOT_ALLOWED")
        expectations = self._normalize_expectations(
            set(validated_mutations), expected_versions
        )
        guards: dict[str, dict[str, Any]] = {}
        if _guard_versions is not None:
            if not isinstance(_guard_versions, Mapping) or not _guard_versions:
                raise VersionConflictError("GUARD_VERSIONS_INVALID")
            guard_keys = {_validate_logical_key(key) for key in _guard_versions}
            if len(guard_keys) != len(_guard_versions):
                raise InvalidLogicalKeyError("LOGICAL_KEY_NOT_ALLOWED")
            if guard_keys & set(validated_mutations):
                raise VersionConflictError("GUARD_KEY_MUST_NOT_BE_MUTATED")
            guards = self._normalize_expectations(guard_keys, _guard_versions)
        request_payload = {
            "operation_id": operation_id,
            "mutations": validated_mutations,
            "expected_versions": expectations,
        }
        if guards:
            request_payload["guard_versions"] = guards
        request_sha = _sha256_bytes(_canonical_bytes(request_payload))
        with self._exclusive_lock(project_dir):
            self._recover_unlocked(project_dir)
            replayed = self._existing_receipt(
                project_dir, operation_id, request_sha
            )
            if replayed is not None:
                return replayed
            old_pointer, current_manifest = self._load_manifest(
                project_dir, author_id, project_id
            )
            current_entries = copy.deepcopy(current_manifest["entries"])
            for key, expectation in {**expectations, **guards}.items():
                entry = current_entries.get(key)
                current_version = 0 if entry is None else entry.get("version")
                current_sha = None if entry is None else entry.get("payload_sha256")
                if current_version != expectation["version"]:
                    raise VersionConflictError("VERSION_CONFLICT")
                if (
                    expectation["sha256"] is not None
                    and current_sha != expectation["sha256"]
                ):
                    raise VersionConflictError("SHA_CONFLICT")
                if entry is not None:
                    self._read_entry(project_dir, key, entry)

            new_entries = copy.deepcopy(current_entries)
            committed_versions: dict[str, int] = {}
            committed_shas: dict[str, str] = {}
            for key in sorted(validated_mutations):
                old_entry = current_entries.get(key)
                new_version = 1 if old_entry is None else old_entry["version"] + 1
                payload = validated_mutations[key]
                payload_sha = _sha256_bytes(_canonical_bytes(payload))
                envelope = {
                    "schema_version": "author-workspace-state-blob-v1",
                    "logical_key": key,
                    "version": new_version,
                    "payload_sha256": payload_sha,
                    "payload": payload,
                }
                blob_bytes = _canonical_bytes(envelope)
                blob_sha = _sha256_bytes(blob_bytes)
                self._write_immutable(
                    project_dir / "blobs" / f"{blob_sha}.json", blob_bytes
                )
                new_entries[key] = {
                    "version": new_version,
                    "payload_sha256": payload_sha,
                    "blob_sha256": blob_sha,
                }
                committed_versions[key] = new_version
                committed_shas[key] = payload_sha

            generation_core = {
                "schema_version": "author-workspace-generation-v1",
                "author_id": author_id,
                "project_id": project_id,
                "parent_generation_id": (
                    None if old_pointer is None else old_pointer["generation_id"]
                ),
                "operation_id": operation_id,
                "request_sha256": request_sha,
                "entries": dict(sorted(new_entries.items())),
            }
            generation_id = f"g_{_sha256_bytes(_canonical_bytes(generation_core))}"
            manifest = {**generation_core, "generation_id": generation_id}
            manifest_bytes = _canonical_bytes(manifest)
            manifest_sha = _sha256_bytes(manifest_bytes)
            generation_dir = project_dir / "generations" / generation_id
            self._ensure_dir(generation_dir)
            self._write_immutable(
                generation_dir / "manifest.json", manifest_bytes
            )
            new_pointer = {
                "schema_version": "author-workspace-current-v1",
                "generation_id": generation_id,
                "manifest_sha256": manifest_sha,
            }
            receipt = {
                "schema_version": "author-workspace-commit-receipt-v1",
                "status": "COMMITTED",
                "operation_id": operation_id,
                "request_sha256": request_sha,
                "author_id": author_id,
                "project_id": project_id,
                "generation_id": generation_id,
                "versions": committed_versions,
                "payload_sha256": committed_shas,
            }
            journal = {
                "schema_version": "author-workspace-prepare-journal-v1",
                "phase": "PREPARED",
                "operation_id": operation_id,
                "request_sha256": request_sha,
                "old_pointer": old_pointer,
                "new_pointer": new_pointer,
                "receipt": receipt,
            }
            journal_path = self._prepare_journal_path(project_dir)
            self._ensure_dir(journal_path.parent)
            self._atomic_write(journal_path, _canonical_bytes(journal))
            self._maybe_fail("after_prepare")
            pointer_path = self._current_pointer_path(project_dir)
            self._ensure_dir(pointer_path.parent)
            self._atomic_write(pointer_path, _canonical_bytes(new_pointer))
            self._maybe_fail("after_pointer_swap")
            receipt_path = self._receipt_path(project_dir, operation_id)
            self._ensure_dir(receipt_path.parent)
            self._atomic_write(receipt_path, _canonical_bytes(receipt))
            self._maybe_fail("after_receipt")
            self._remove_file(journal_path)
            return {**receipt, "replayed": False}

    def commit_guarded(
        self,
        author_id: str,
        project_id: str,
        operation_id: str,
        mutations: Mapping[str, Any],
        expected_versions: Mapping[str, Any],
        guard_versions: Mapping[str, Any],
    ) -> dict[str, Any]:
        """原子提交 mutations，同时只校验 guard_versions，不改写 guard 键。"""
        return self.commit(
            author_id,
            project_id,
            operation_id,
            mutations,
            expected_versions,
            _guard_versions=guard_versions,
        )

    def store_immutable(
        self,
        author_id: str,
        project_id: str,
        kind: str,
        payload: bytes,
        metadata: Mapping[str, Any],
    ) -> dict[str, Any]:
        self._require_project(author_id, project_id)
        kind = _validate_immutable_kind(kind)
        if not isinstance(payload, (bytes, bytearray, memoryview)):
            raise WorkspaceError("IMMUTABLE_PAYLOAD_MUST_BE_BYTES")
        if not isinstance(metadata, Mapping):
            raise WorkspaceError("IMMUTABLE_METADATA_INVALID")
        content = bytes(payload)
        content_sha = _sha256_bytes(content)
        descriptor = {
            "schema_version": "author-workspace-immutable-metadata-v1",
            "kind": kind,
            "content_sha256": content_sha,
            "size": len(content),
            "metadata": copy.deepcopy(dict(metadata)),
        }
        descriptor_bytes = _canonical_bytes(descriptor)
        metadata_sha = _sha256_bytes(descriptor_bytes)
        kind_root = self._author_dir(author_id) / "immutable" / kind
        blob_path = kind_root / "blobs" / f"{content_sha}.blob"
        metadata_path = (
            kind_root
            / "metadata"
            / content_sha
            / f"{metadata_sha}.json"
        )
        self._write_immutable(blob_path, content)
        self._write_immutable(metadata_path, descriptor_bytes)
        return {
            "blob_id": f"i_{author_id[2:]}_{kind}_{content_sha}",
            "kind": kind,
            "content_sha256": content_sha,
            "size": len(content),
            "metadata_sha256": metadata_sha,
        }

    @staticmethod
    def _manifest_references_receipt(
        manifest_state: object,
        receipt: Mapping[str, Any],
    ) -> bool:
        if not isinstance(manifest_state, dict):
            return False
        payload = manifest_state.get("payload")
        if not isinstance(payload, dict) or set(payload) != {"uploads"}:
            return False
        uploads = payload["uploads"]
        if not isinstance(uploads, list):
            return False
        return any(
            isinstance(item, dict)
            and item.get("immutable_receipt") == dict(receipt)
            for item in uploads
        )

    def read_immutable(
        self,
        author_id: str,
        project_id: str,
        receipt: Mapping[str, Any],
    ) -> dict[str, Any]:
        """只读当前项目 manifest 正在引用的 raw_upload 完整回执。"""
        self._require_project(author_id, project_id)
        if not isinstance(receipt, Mapping) or set(receipt) != IMMUTABLE_RECEIPT_KEYS:
            raise WorkspaceError("IMMUTABLE_RECEIPT_INVALID")
        normalized = copy.deepcopy(dict(receipt))
        kind = normalized["kind"]
        content_sha = normalized["content_sha256"]
        metadata_sha = normalized["metadata_sha256"]
        size = normalized["size"]
        if kind != "raw_upload":
            raise WorkspaceError("IMMUTABLE_READ_KIND_NOT_ALLOWED")
        if (
            not isinstance(content_sha, str)
            or SHA256_RE.fullmatch(content_sha) is None
            or not isinstance(metadata_sha, str)
            or SHA256_RE.fullmatch(metadata_sha) is None
            or isinstance(size, bool)
            or not isinstance(size, int)
            or size < 0
        ):
            raise WorkspaceError("IMMUTABLE_RECEIPT_INVALID")
        expected_blob_id = f"i_{author_id[2:]}_{kind}_{content_sha}"
        if normalized["blob_id"] != expected_blob_id:
            raise AuthenticationError("IMMUTABLE_RECEIPT_AUTHOR_MISMATCH")

        manifest_before = self.read(author_id, project_id, "input_manifest")
        if not self._manifest_references_receipt(manifest_before, normalized):
            raise WorkspaceError("IMMUTABLE_RECEIPT_NOT_REFERENCED")

        kind_root = self._author_dir(author_id) / "immutable" / kind
        blob_path = kind_root / "blobs" / f"{content_sha}.blob"
        metadata_path = (
            kind_root
            / "metadata"
            / content_sha
            / f"{metadata_sha}.json"
        )
        try:
            raw_bytes = self._read_bytes(blob_path)
            descriptor_bytes = self._read_bytes(metadata_path)
        except FileNotFoundError as exc:
            raise IntegrityError("IMMUTABLE_OBJECT_MISSING") from exc
        if _sha256_bytes(raw_bytes) != content_sha or len(raw_bytes) != size:
            raise IntegrityError("IMMUTABLE_BLOB_INTEGRITY_MISMATCH")
        if _sha256_bytes(descriptor_bytes) != metadata_sha:
            raise IntegrityError("IMMUTABLE_METADATA_SHA_MISMATCH")
        try:
            descriptor = json.loads(descriptor_bytes)
        except json.JSONDecodeError as exc:
            raise IntegrityError("IMMUTABLE_METADATA_INVALID") from exc
        if (
            not isinstance(descriptor, dict)
            or set(descriptor)
            != {"schema_version", "kind", "content_sha256", "size", "metadata"}
            or descriptor.get("schema_version")
            != "author-workspace-immutable-metadata-v1"
            or descriptor.get("kind") != kind
            or descriptor.get("content_sha256") != content_sha
            or descriptor.get("size") != size
            or not isinstance(descriptor.get("metadata"), dict)
        ):
            raise IntegrityError("IMMUTABLE_METADATA_INVALID")

        manifest_after = self.read(author_id, project_id, "input_manifest")
        if manifest_after != manifest_before:
            raise WorkspaceError("IMMUTABLE_MANIFEST_WATERMARK_CHANGED")
        return {
            "receipt": normalized,
            "metadata": copy.deepcopy(descriptor["metadata"]),
            "raw_bytes": raw_bytes,
        }


class _AuthorWorkspaceBinding(NamedTuple):
    backend: _LocalFilesystemBackend
    author_id: str
    project_id: str
    binding_token: bytes


_AUTHOR_WORKSPACE_BINDINGS: weakref.WeakKeyDictionary[
    object,
    _AuthorWorkspaceBinding,
] = weakref.WeakKeyDictionary()


def _author_workspace_binding(
    workspace: "AuthorWorkspace",
) -> _AuthorWorkspaceBinding:
    try:
        binding = _AUTHOR_WORKSPACE_BINDINGS[workspace]
    except KeyError as exc:
        raise AuthenticationError("AUTHOR_WORKSPACE_BINDING_INVALID") from exc
    binding.backend._verify_handle_binding(
        binding.author_id,
        binding.project_id,
        binding.binding_token,
    )
    return binding


class AuthorWorkspace:
    """只绑定一个已认证作者和一个项目的能力句柄。"""

    __slots__ = ("__dict__", "__weakref__")

    def __init__(self, *args: object, **kwargs: object):
        del args, kwargs
        raise AuthenticationError("AUTHOR_WORKSPACE_ROUTER_REQUIRED")

    def __setattr__(self, name: str, value: object) -> None:
        if name in {"_backend", "author_id", "project_id"}:
            raise AuthenticationError("AUTHOR_WORKSPACE_BINDING_IMMUTABLE")
        object.__setattr__(self, name, value)

    def __delattr__(self, name: str) -> None:
        if name in {"_backend", "author_id", "project_id"}:
            raise AuthenticationError("AUTHOR_WORKSPACE_BINDING_IMMUTABLE")
        object.__delattr__(self, name)

    def __copy__(self) -> "AuthorWorkspace":
        raise AuthenticationError("AUTHOR_WORKSPACE_SERIALIZATION_FORBIDDEN")

    def __deepcopy__(self, memo: dict[int, object]) -> "AuthorWorkspace":
        del memo
        raise AuthenticationError("AUTHOR_WORKSPACE_SERIALIZATION_FORBIDDEN")

    def __reduce__(self) -> object:
        raise AuthenticationError("AUTHOR_WORKSPACE_SERIALIZATION_FORBIDDEN")

    def __reduce_ex__(self, protocol: int) -> object:
        del protocol
        raise AuthenticationError("AUTHOR_WORKSPACE_SERIALIZATION_FORBIDDEN")

    @property
    def author_id(self) -> str:
        return _author_workspace_binding(self).author_id

    @property
    def project_id(self) -> str:
        return _author_workspace_binding(self).project_id

    def read(self, logical_key: str) -> dict[str, Any] | None:
        binding = _author_workspace_binding(self)
        return binding.backend.read(
            binding.author_id,
            binding.project_id,
            logical_key,
        )

    def commit(
        self,
        operation_id: str,
        mutations: Mapping[str, Any],
        expected_versions: Mapping[str, Any],
    ) -> dict[str, Any]:
        binding = _author_workspace_binding(self)
        return binding.backend.commit(
            binding.author_id,
            binding.project_id,
            operation_id,
            mutations,
            expected_versions,
        )

    def commit_guarded(
        self,
        operation_id: str,
        mutations: Mapping[str, Any],
        expected_versions: Mapping[str, Any],
        guard_versions: Mapping[str, Any],
    ) -> dict[str, Any]:
        """提交业务状态，并在同一把锁内确认只读来源仍是调用方所见版本。"""
        binding = _author_workspace_binding(self)
        return binding.backend.commit_guarded(
            binding.author_id,
            binding.project_id,
            operation_id,
            mutations,
            expected_versions,
            guard_versions,
        )

    def store_immutable(
        self,
        kind: str,
        payload: bytes,
        metadata: Mapping[str, Any],
    ) -> dict[str, Any]:
        binding = _author_workspace_binding(self)
        return binding.backend.store_immutable(
            binding.author_id,
            binding.project_id,
            kind,
            payload,
            metadata,
        )

    def read_immutable(self, receipt: Mapping[str, Any]) -> dict[str, Any]:
        binding = _author_workspace_binding(self)
        return binding.backend.read_immutable(
            binding.author_id,
            binding.project_id,
            receipt,
        )

    def recover(self) -> dict[str, Any]:
        binding = _author_workspace_binding(self)
        return binding.backend.recover(
            binding.author_id,
            binding.project_id,
        )


class WorkspaceRouter:
    """用 authenticated_principal 绑定作者，再返回项目能力句柄。"""

    def __init__(self, runtime_root: str | os.PathLike[str]):
        root = Path(os.path.abspath(os.fspath(runtime_root)))
        # CLOUD_SWAP_POINT: 未来只在这里替换后端绑定；本票不建设云服务。
        self._backend = _LocalFilesystemBackend(root)

    def _set_failure_hook_for_testing(self, hook: object) -> None:
        self._backend._failure_hook = hook

    def create_project(
        self,
        authenticated_principal: str,
        display_name: str,
    ) -> AuthorWorkspace:
        author_id = _authenticated_author_id(authenticated_principal)
        return self._backend.create_project(
            author_id,
            _validate_display_name(display_name),
        )

    def open_project(
        self,
        authenticated_principal: str,
        project_id: str,
    ) -> AuthorWorkspace:
        author_id = _authenticated_author_id(authenticated_principal)
        return self._backend.open_project(author_id, project_id)

    def list_projects(
        self,
        authenticated_principal: str,
    ) -> list[dict[str, Any]]:
        author_id = _authenticated_author_id(authenticated_principal)
        return self._backend.list_projects(author_id)

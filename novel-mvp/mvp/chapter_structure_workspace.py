"""R01 storage kernel and closed stage-one entrypoints.

The underscored kernel is exercised with synthetic data in offline tests.
No test authorization provider is implemented or installed in product code.
"""

from __future__ import annotations

from copy import deepcopy
from threading import RLock

from .chapter_structure_access import require_bound_access
from .chapter_structure_contract import (
    CONTRACT_TYPES,
    SCHEMA,
    StructureError,
    _LOCAL,
    _require,
    business_items,
    canonical_bytes,
    decode_request,
    digest,
    new_id,
    resolve_local_ids,
    validate_capacity,
    validate_content,
    validate_shape,
    version_digest,
)
from .workspace import (
    AuthorWorkspace,
    IntegrityError,
    OperationConflictError,
    VersionConflictError,
    WorkspaceError,
    InjectedWorkspaceCrash,
    _structure_commit_footprint,
)

_KEY = "chapter_structures"
_REF_KEYS = (
    "project_id",
    "branch_id",
    "owner",
    "object_type",
    "id",
    "rev",
    "content_sha256",
)
# Only the dedicated namespace is declared. It never opens a ten-ledger snapshot.
STRUCTURE_CAPABILITY = {
    "owner": "CHAPTER_STRUCTURE",
    "object_type": "CHAPTER_STRUCTURE_VERSION",
}


def _write_error(code: str, state: str | None = None) -> dict:
    rule = next(
        r["then"]["properties"]
        for r in SCHEMA["$defs"]["StructureWriteResponse"]["allOf"][3:]
        if r["if"]["properties"]["error"]["properties"]["code"]["const"] == code
    )
    status = rule["status"]["const"]
    state = state or (
        "UNKNOWN" if code == "STORAGE_IO_ERROR" else rule["commit_state"]["enum"][0]
    )
    result = dict(
        contract="CHAPTER_STRUCTURE_WRITE_RESPONSE",
        version="chapter-structure-write-v1",
        status=status,
        commit_state=state,
        replayed=False,
        result=None,
        container_observation=None,
        error={"code": code, "retryable": False},
    )
    validate_shape("StructureWriteResponse", result)
    return result


def _success(result: dict, state: dict, replayed=False) -> dict:
    response = dict(
        contract="CHAPTER_STRUCTURE_WRITE_RESPONSE",
        version="chapter-structure-write-v1",
        status="OK",
        commit_state="COMMITTED",
        replayed=replayed,
        result=deepcopy(result),
        container_observation={"version": state["version"], "sha256": state["sha256"]},
        error=None,
    )
    validate_shape("StructureWriteResponse", response)
    return response


def _seal_read(response: dict) -> dict:
    receipt = response["receipt"]
    returned = (
        []
        if response["data"] is None
        else [
            {"structure_ref": x["structure_ref"], "retired_notice": x["retired_notice"]}
            for x in response["data"]["versions"]
        ]
    )
    basis = {
        k: response[k]
        for k in ("contract", "version", "action", "status", "reason_code")
    }
    basis.update(
        {
            k: receipt[k]
            for k in (
                "author_id",
                "project_id",
                "request_sha256",
                "access_basis_sha256",
                "source_manifest",
            )
        }
    )
    basis["returned_items"] = returned
    receipt["basis_sha256"] = digest(basis)
    for _ in range(8):
        size = len(canonical_bytes(response))
        if response["limits"]["response_bytes"] == size:
            return response
        response["limits"]["response_bytes"] = size
    raise StructureError("INTERNAL_ERROR")


def _read_shell(request: object, reason: str | None) -> dict:
    request_id = request.get("request_id") if type(request) is dict else None
    if not CONTRACT_TYPES["RequestId"].is_valid(request_id):
        request_id = None
    rules = SCHEMA["$defs"]["StructureReadResponse"]["allOf"]
    message = "已按指定版本完整读回结构候选。"
    if reason:
        message = next(
            r["then"]["properties"]["message"]["const"]
            for r in rules
            if r.get("if", {}).get("properties", {}).get("reason_code", {}).get("const")
            == reason
        )
    return {
        "contract": "CHAPTER_STRUCTURE_READ_RESPONSE",
        "version": "chapter-structure-read-v1",
        "request_id": request_id,
        "action": "READ_PINNED",
        "status": "ERROR"
        if reason in ("SOURCE_CORRUPTED", "INTERNAL_ERROR")
        else ("REJECTED" if reason else "OK"),
        "reason_code": reason,
        "message": message,
        "data": None,
        "receipt": dict(
            author_id=None,
            project_id=None,
            request_sha256=None,
            access_basis_sha256=None,
            storage_generation=None,
            source_manifest=[],
            basis_sha256="0" * 64,
        ),
        "limits": dict(
            policy_version="chapter-structure-read-limit-v1",
            returned_versions=0,
            business_items=0,
            response_bytes=0,
            truncated=False,
        ),
    }


def _validate_operation_history(store):
    """Rebuild object state from successful actions, without writing or repairing."""
    objects = {obj["id"]: obj for obj in store["objects"]}
    cursors = {}
    issued = {store["branch"]["branch_id"]}
    for index, op in enumerate(store["operations"]):
        result = op["result"]
        action = result["action"]
        if index == 0:
            _require(action == "REGISTER_BRANCH")
            _require(op["operation_id"] == store["branch"]["created_operation_id"])
            continue
        _require(action != "REGISTER_BRANCH")
        object_id = result["object_id"]
        _require(object_id in objects)
        obj = objects[object_id]
        cursor = cursors.get(object_id)
        old_selected = None if cursor is None else cursor["selected_ref"]
        if action == "CREATE_OBJECT":
            _require(cursor is None and object_id not in issued)
            cursor = dict(
                latest_rev=0,
                object_state_version=0,
                selected_ref=None,
                lifecycle_status="ACTIVE",
                retired_operation_id=None,
                known={array: set() for array in _LOCAL},
            )
            cursors[object_id] = cursor
        else:
            _require(cursor is not None and cursor["lifecycle_status"] == "ACTIVE")
        _require(result["previous_selected_ref"] == old_selected)
        expected_new = set()
        if action in ("CREATE_OBJECT", "SAVE_VERSION"):
            next_rev = cursor["latest_rev"] + 1
            _require(next_rev <= len(obj["versions"]))
            version = obj["versions"][next_rev - 1]
            _require(version["save_operation_id"] == op["operation_id"])
            _require(result["saved_ref"] == version["ref"])
            _require(result["selected_ref"] == version["ref"])
            if action == "SAVE_VERSION":
                _require(
                    version["structure_content"]
                    != obj["versions"][next_rev - 2]["structure_content"]
                )
            else:
                expected_new.add(("STRUCTURE_OBJECT", object_id))
            for array, (key, _prefix, kind, _typ) in _LOCAL.items():
                current = {item[key] for item in version["structure_content"][array]}
                expected_new.update(
                    (kind, item_id) for item_id in current - cursor["known"][array]
                )
                cursor["known"][array].update(current)
            cursor["latest_rev"] = next_rev
            cursor["selected_ref"] = version["ref"]
        elif action == "SELECT_VERSION":
            _require(result["selected_ref"] != old_selected)
            _require(
                any(
                    v["ref"] == result["selected_ref"]
                    for v in obj["versions"][: cursor["latest_rev"]]
                )
            )
            cursor["selected_ref"] = result["selected_ref"]
        elif action == "RETIRE_OBJECT":
            _require(result["selected_ref"] == old_selected)
            cursor["lifecycle_status"] = "RETIRED"
            cursor["retired_operation_id"] = op["operation_id"]
        rows = result["local_id_map"]
        placeholders = [row["placeholder"] for row in rows]
        _require(placeholders == sorted(set(placeholders)))
        _require(len({p.split(":")[1] for p in placeholders}) <= 1)
        actual_new = {(row["local_kind"], row["resolved_id"]) for row in rows}
        _require(len(actual_new) == len(rows) and actual_new == expected_new)
        _require(all(item_id not in issued for _, item_id in actual_new))
        issued.update(item_id for _, item_id in actual_new)
        cursor["object_state_version"] += 1
        for key in (
            "latest_rev",
            "object_state_version",
            "selected_ref",
            "lifecycle_status",
        ):
            _require(result[key] == cursor[key])
    _require(set(cursors) == set(objects))
    for object_id, cursor in cursors.items():
        for key in (
            "latest_rev",
            "object_state_version",
            "selected_ref",
            "lifecycle_status",
            "retired_operation_id",
        ):
            _require(objects[object_id][key] == cursor[key])


class _StructureKernel:
    """Trusted internal persistence component, not a model tool or permission issuer."""

    def __init__(self, workspace: AuthorWorkspace, capacity: dict):
        self.workspace = workspace
        self.capacity = validate_capacity(capacity)
        self._lock = RLock()
        # Process-local diagnostics of actual checks; not a permanent recovery DB.
        self._io_evidence: list[dict] = []

    def _state(self, view=None):
        if view is None:
            view = self.workspace.read_current_snapshot((_KEY,))
        state = view.read(_KEY)
        if state is not None:
            store = state["payload"]
            try:
                validate_shape("StructureStore", store)
                _require(state["sha256"] == digest(store))
                _require(
                    store["workspace_binding"]
                    == {
                        "author_id": self.workspace.author_id,
                        "project_id": self.workspace.project_id,
                    }
                )
                _require(state["version"] == len(store["operations"]))
                operations = {o["operation_id"]: o for o in store["operations"]}
                _require(len(operations) == len(store["operations"]))
                _require(
                    len({o["id"] for o in store["objects"]}) == len(store["objects"])
                )
                _require(store["branch"]["created_operation_id"] in operations)
                for index, operation in enumerate(store["operations"], 1):
                    result = operation["result"]
                    _require(result["operation_id"] == operation["operation_id"])
                    _require(result["committed_container_version"] == index)
                    _require(result["branch_ref"] == store["branch"]["branch_id"])
                for obj in store["objects"]:
                    _require(obj["branch_id"] == store["branch"]["branch_id"])
                    _require(obj["latest_rev"] == len(obj["versions"]))
                    refs = []
                    object_ops = [
                        o
                        for o in store["operations"]
                        if o["result"]["object_id"] == obj["id"]
                    ]
                    _require(len(object_ops) == obj["object_state_version"])
                    _require(object_ops[-1]["operation_id"] == obj["last_operation_id"])
                    _require(
                        (obj["retired_operation_id"] is not None)
                        == (obj["lifecycle_status"] == "RETIRED")
                    )
                    if obj["retired_operation_id"] is not None:
                        _require(
                            operations[obj["retired_operation_id"]]["result"]["action"]
                            == "RETIRE_OBJECT"
                        )
                    for rev, version in enumerate(obj["versions"], 1):
                        ref, content = version["ref"], version["structure_content"]
                        _require(
                            ref["project_id"] == self.workspace.project_id
                            and ref["branch_id"] == obj["branch_id"]
                        )
                        _require(ref["id"] == obj["id"] and ref["rev"] == rev)
                        _require(ref["content_sha256"] == version_digest(ref, content))
                        validate_content(content, ref)
                        op = operations[version["save_operation_id"]]
                        _require(op["result"]["saved_ref"] == ref)
                        refs.append(ref)
                    _require(obj["selected_ref"] in refs)
                _validate_operation_history(store)
            except (StructureError, KeyError, IndexError, TypeError) as exc:
                raise StructureError("STORAGE_CORRUPT") from exc
        return view, state

    def _request_hash(self, request, actor_ref, actor_kind):
        return digest(
            dict(
                author_id=self.workspace.author_id,
                project_id=self.workspace.project_id,
                actor_ref=actor_ref,
                actor_kind=actor_kind,
                request=request,
            )
        )

    def _replay(self, state, request, request_sha, actor_ref, actor_kind):
        if state is None:
            return None
        for op in state["payload"]["operations"]:
            if op["operation_id"] == request["operation_id"]:
                _require(
                    (op["request_sha256"], op["actor_ref"], op["actor_kind"])
                    == (request_sha, actor_ref, actor_kind),
                    "OPERATION_ID_CONFLICT",
                )
                return _success(op["result"], state, True)
        return None

    def _io_failure(self, request, request_sha, before):
        evidence = {
            "operation_id": request["operation_id"],
            "request_sha256": request_sha,
        }
        try:
            view, state = self._state()
            if state is not None:
                for op in state["payload"]["operations"]:
                    if (
                        op["operation_id"] == request["operation_id"]
                        and op["request_sha256"] == request_sha
                    ):
                        evidence.update(
                            commit_state="COMMITTED",
                            observed_operation=deepcopy(op),
                            storage_generation=view.generation_id,
                        )
                        self._io_evidence.append(evidence)
                        return _write_error("STORAGE_IO_ERROR", "COMMITTED")
            after = _structure_commit_footprint(self.workspace)
            if (
                before is not None
                and not before["prepared_journal_exists"]
                and before == after
            ):
                evidence.update(
                    commit_state="NOT_COMMITTED", before=before, after=after
                )
                self._io_evidence.append(evidence)
                return _write_error("STORAGE_IO_ERROR", "NOT_COMMITTED")
        except (OSError, WorkspaceError, StructureError):
            pass
        return _write_error("STORAGE_IO_ERROR", "UNKNOWN")

    def _write(self, raw, *, actor_ref: str, actor_kind: str, action_grant_ref: str):
        """Caller must already be authorized; offline tests do not certify that precondition."""
        try:
            request = decode_request(raw)
            validate_shape("StructureWriteRequest", request)
            validate_shape("ActionActorId", actor_ref)
            validate_shape("ProviderRecordId", action_grant_ref)
            _require(actor_kind in ("AUTHOR", "CONTROLLED_AGENT"))
            _require(
                actor_kind == "AUTHOR"
                or request["action"] in ("CREATE_OBJECT", "SAVE_VERSION"),
                "UNAUTHORIZED",
            )
            return self._write_checked(request, actor_ref, actor_kind, action_grant_ref)
        except StructureError as exc:
            return _write_error(exc.code)
        except OSError:
            return _write_error("STORAGE_IO_ERROR")
        except IntegrityError:
            return _write_error("STORAGE_CORRUPT")
        except WorkspaceError:
            return _write_error("STORAGE_CORRUPT")

    def _write_checked(self, request, actor_ref, actor_kind, grant_ref):
        with self._lock:
            _, state = self._state()
            request_sha = self._request_hash(request, actor_ref, actor_kind)
            replay = self._replay(state, request, request_sha, actor_ref, actor_kind)
            if replay is not None:
                return replay
            policy = self.capacity["owner"]
            _require(
                len(canonical_bytes(request)) <= policy["write_request_max_utf8_bytes"],
                "CAPACITY_EXCEEDED",
            )
            expected = (
                {"version": 0, "sha256": None}
                if state is None
                else {k: state[k] for k in ("version", "sha256")}
            )
            _require(request["expected_container"] == expected, "CONTAINER_CONFLICT")
            action, arg, operation_id = (
                request["action"],
                request["action_input"],
                request["operation_id"],
            )
            next_version = expected["version"] + 1
            if action == "REGISTER_BRANCH":
                _require(state is None, "BRANCH_ALREADY_REGISTERED")
                store = dict(
                    contract="CHAPTER_STRUCTURE_STORE",
                    version="chapter-structure-store-v1",
                    workspace_binding={
                        "author_id": self.workspace.author_id,
                        "project_id": self.workspace.project_id,
                    },
                    branch={
                        "branch_id": new_id("eb", set()),
                        "label": arg["branch_label"],
                        "created_operation_id": operation_id,
                    },
                    objects=[],
                    operations=[],
                )
            else:
                _require(state is not None, "STORE_NOT_INITIALIZED")
                store = deepcopy(state["payload"])
            branch = store["branch"]["branch_id"]
            result = dict(
                status="COMMITTED",
                operation_id=operation_id,
                action=action,
                effect="BRANCH_REGISTERED",
                branch_ref=branch,
                object_id=None,
                saved_ref=None,
                previous_selected_ref=None,
                selected_ref=None,
                latest_rev=None,
                object_state_version=None,
                lifecycle_status=None,
                committed_container_version=next_version,
                local_id_map=[],
            )
            occupied = {branch}
            for obj in store["objects"]:
                occupied.add(obj["id"])
                for version in obj["versions"]:
                    for array, (key, *_rest) in _LOCAL.items():
                        occupied.update(
                            x[key] for x in version["structure_content"][array]
                        )
            if action == "CREATE_OBJECT":
                _require(arg["branch_ref"] == branch, "REFERENCE_MISMATCH")
                _require(
                    len(store["objects"]) < policy["objects_max"], "CAPACITY_EXCEEDED"
                )
                content, mapping = resolve_local_ids(
                    arg["structure_content"],
                    arg["candidate_scope"],
                    [],
                    arg["new_object_ref"],
                    occupied,
                    self.capacity["max_new_id_mappings_per_operation"],
                )
                object_id = next(
                    x["resolved_id"]
                    for x in mapping
                    if x["local_kind"] == "STRUCTURE_OBJECT"
                )
                obj = dict(
                    id=object_id,
                    branch_id=branch,
                    latest_rev=0,
                    object_state_version=0,
                    selected_ref=None,
                    lifecycle_status="ACTIVE",
                    retired_operation_id=None,
                    last_operation_id=operation_id,
                    versions=[],
                )
                store["objects"].append(obj)
            elif action != "REGISTER_BRANCH":
                pin = arg["expected_latest_ref"]
                _require(
                    pin["project_id"] == self.workspace.project_id
                    and pin["branch_id"] == branch,
                    "REFERENCE_MISMATCH",
                )
                obj = next((o for o in store["objects"] if o["id"] == pin["id"]), None)
                _require(obj is not None, "OBJECT_NOT_FOUND")
                _require(
                    pin == obj["versions"][-1]["ref"]
                    and arg["expected_object_state_version"]
                    == obj["object_state_version"]
                    and arg["expected_selected_ref"] == obj["selected_ref"],
                    "OBJECT_STATE_CONFLICT",
                )
                _require(obj["lifecycle_status"] == "ACTIVE", "OBJECT_RETIRED")
                result["previous_selected_ref"] = deepcopy(obj["selected_ref"])
                if action == "SAVE_VERSION":
                    content, mapping = resolve_local_ids(
                        arg["structure_content"],
                        arg["candidate_scope"],
                        obj["versions"],
                        None,
                        occupied,
                        self.capacity["max_new_id_mappings_per_operation"],
                    )
                    _require(
                        content != obj["versions"][-1]["structure_content"],
                        "CONTENT_UNCHANGED",
                    )
            if action in ("CREATE_OBJECT", "SAVE_VERSION"):
                _require(
                    obj["latest_rev"] < policy["versions_per_object_max"],
                    "CAPACITY_EXCEEDED",
                )
                ref = dict(
                    project_id=self.workspace.project_id,
                    branch_id=branch,
                    owner="CHAPTER_STRUCTURE",
                    object_type="CHAPTER_STRUCTURE_VERSION",
                    id=obj["id"],
                    rev=obj["latest_rev"] + 1,
                )
                validate_content(content, ref)
                ref["content_sha256"] = version_digest(ref, content)
                version = dict(
                    ref=ref, structure_content=content, save_operation_id=operation_id
                )
                _require(
                    business_items(content) <= policy["business_items_per_version_max"],
                    "CAPACITY_EXCEEDED",
                )
                _require(
                    len(canonical_bytes(version))
                    <= policy["version_record_max_utf8_bytes"],
                    "CAPACITY_EXCEEDED",
                )
                obj["versions"].append(version)
                obj["latest_rev"] = ref["rev"]
                obj["selected_ref"] = ref
                result.update(
                    effect="CANDIDATE_SAVED",
                    saved_ref=deepcopy(ref),
                    local_id_map=mapping,
                )
            elif action == "SELECT_VERSION":
                _require(
                    any(v["ref"] == arg["selected_ref"] for v in obj["versions"]),
                    "REFERENCE_MISMATCH",
                )
                _require(
                    obj["selected_ref"] != arg["selected_ref"], "SELECTION_UNCHANGED"
                )
                obj["selected_ref"] = deepcopy(arg["selected_ref"])
                result["effect"] = "SELECTION_CHANGED"
            elif action == "RETIRE_OBJECT":
                obj["lifecycle_status"] = "RETIRED"
                obj["retired_operation_id"] = operation_id
                result["effect"] = "OBJECT_RETIRED"
            if action != "REGISTER_BRANCH":
                obj["object_state_version"] += 1
                obj["last_operation_id"] = operation_id
                result.update(
                    object_id=obj["id"],
                    selected_ref=deepcopy(obj["selected_ref"]),
                    latest_rev=obj["latest_rev"],
                    object_state_version=obj["object_state_version"],
                    lifecycle_status=obj["lifecycle_status"],
                )
            store["operations"].append(
                dict(
                    operation_id=operation_id,
                    request_sha256=request_sha,
                    actor_ref=actor_ref,
                    actor_kind=actor_kind,
                    action_grant_ref=grant_ref,
                    result=result,
                )
            )
            _require(
                len(store["operations"]) <= policy["committed_operations_max"],
                "CAPACITY_EXCEEDED",
            )
            _require(
                len(canonical_bytes(store)) <= policy["container_max_utf8_bytes"],
                "CAPACITY_EXCEEDED",
            )
            validate_shape("StructureStore", store)
            observation = {"version": next_version, "sha256": digest(store)}
            predicted = _success(result, observation)
            _require(
                len(canonical_bytes(predicted))
                <= policy["write_response_max_utf8_bytes"],
                "CAPACITY_EXCEEDED",
            )
            try:
                before = _structure_commit_footprint(self.workspace)
            except (OSError, WorkspaceError):
                before = None
            try:
                # No foreign source state is consumed in the offline persistence
                # kernel. None selects the existing source-free commit path;
                # the mutation itself still has exact version+SHA CAS.
                self.workspace.commit_guarded(
                    operation_id, {_KEY: store}, {_KEY: expected}, None
                )
            except VersionConflictError:
                _, current = self._state()
                replay = self._replay(
                    current, request, request_sha, actor_ref, actor_kind
                )
                return replay or _write_error("CONTAINER_CONFLICT")
            except OperationConflictError:
                _, current = self._state()
                replay = self._replay(
                    current, request, request_sha, actor_ref, actor_kind
                )
                return replay or _write_error("OPERATION_ID_CONFLICT")
            except (OSError, InjectedWorkspaceCrash):
                return self._io_failure(request, request_sha, before)
            try:
                _, committed = self._state()
                replay = self._replay(
                    committed, request, request_sha, actor_ref, actor_kind
                )
                _require(replay is not None, "COMMIT_READBACK_FAILED")
                replay["replayed"] = False
                return replay
            except (OSError, WorkspaceError, StructureError):
                return _write_error("COMMIT_READBACK_FAILED")

    def _read(self, raw, *, access_basis_sha256: str):
        """Only authorized internal callers; no authorization is manufactured here."""
        request = raw
        try:
            request = decode_request(raw)
            refs = request.get("structure_refs")
            _require(
                not isinstance(refs, list)
                or len(refs) <= self.capacity["read"]["max_input_refs"],
                "RESULT_TOO_LARGE",
            )
            try:
                validate_shape("StructureReadRequest", request)
                validate_shape("Sha256", access_basis_sha256)
            except StructureError as exc:
                raise StructureError("INVALID_SELECTOR") from exc
            seen = {}
            for ref in refs:
                key = tuple(ref[k] for k in _REF_KEYS[:-1])
                if key in seen:
                    _require(seen[key] != ref["content_sha256"], "INVALID_SELECTOR")
                    raise StructureError("INVALID_PIN_SET")
                seen[key] = ref["content_sha256"]
            try:
                view = self.workspace.read_current_snapshot((_KEY,))
                stored = view.read(_KEY)
                if stored is not None:
                    # Inspect only requested revisions for supported content
                    # protocol, from the same view used by all later checks.
                    for obj in stored["payload"]["objects"]:
                        for version in obj["versions"]:
                            ref = version["ref"]
                            if not any(
                                all(ref[k] == r[k] for k in _REF_KEYS[:-1])
                                for r in refs
                            ):
                                continue
                            body = version["structure_content"]
                            if (body.get("contract"), body.get("version")) != (
                                "CHAPTER_STRUCTURE_CONTENT",
                                "chapter-structure-content-v1",
                            ):
                                validate_shape("StructureRef", ref)
                                _require(
                                    version_digest(ref, body) == ref["content_sha256"],
                                    "SOURCE_CORRUPTED",
                                )
                                raise StructureError("SOURCE_VERSION_UNSUPPORTED")
                view, state = self._state(view)
            except StructureError as exc:
                if exc.code == "SOURCE_VERSION_UNSUPPORTED":
                    raise
                raise StructureError("SOURCE_CORRUPTED") from exc
            except (WorkspaceError, KeyError, TypeError, AttributeError) as exc:
                raise StructureError("SOURCE_CORRUPTED") from exc
            _require(state is not None, "ENTRY_NOT_FOUND")
            versions = []
            for ref in refs:
                store = state["payload"]
                _require(
                    ref["project_id"] == self.workspace.project_id
                    and ref["branch_id"] == store["branch"]["branch_id"],
                    "ENTRY_NOT_FOUND",
                )
                obj = next((o for o in store["objects"] if o["id"] == ref["id"]), None)
                _require(obj is not None, "ENTRY_NOT_FOUND")
                version = next(
                    (v for v in obj["versions"] if v["ref"]["rev"] == ref["rev"]), None
                )
                _require(version is not None, "REVISION_NOT_FOUND")
                _require(version["ref"] == ref, "SHA_MISMATCH")
                versions.append(
                    dict(
                        structure_ref=deepcopy(ref),
                        structure_content=deepcopy(version["structure_content"]),
                        retired_notice=obj["lifecycle_status"] == "RETIRED",
                    )
                )
            response = _read_shell(request, None)
            response["data"] = {"versions": versions}
            response["receipt"].update(
                author_id=self.workspace.author_id,
                project_id=self.workspace.project_id,
                request_sha256=digest(request),
                access_basis_sha256=access_basis_sha256,
                storage_generation=view.generation_id,
                source_manifest=[
                    dict(
                        source_kind="CHAPTER_STRUCTURE_VERSION",
                        structure_ref=deepcopy(ref),
                        binding_mode="RECORDED_PIN",
                    )
                    for ref in sorted(
                        refs, key=lambda r: tuple(r[k] for k in _REF_KEYS)
                    )
                ],
            )
            count = sum(business_items(v["structure_content"]) for v in versions)
            _require(
                count <= self.capacity["read"]["max_returned_business_items"],
                "RESULT_TOO_LARGE",
            )
            response["limits"].update(
                returned_versions=len(versions), business_items=count
            )
            response = _seal_read(response)
            _require(
                response["limits"]["response_bytes"]
                <= self.capacity["read"]["max_response_bytes"],
                "RESULT_TOO_LARGE",
            )
            validate_shape("StructureReadResponse", response)
            return response
        except StructureError as exc:
            code = (
                exc.code
                if exc.code in SCHEMA["$defs"]["ReadReason"]["enum"]
                else "INVALID_SELECTOR"
            )
            response = _seal_read(_read_shell(request, code))
            validate_shape("StructureReadResponse", response)
            return response
        except (OSError, WorkspaceError):
            return _seal_read(_read_shell(request, "INTERNAL_ERROR"))


def apply_structure_write(workspace, access_context, action_grant, request):
    """Public four-argument entry, closed until actual host binding is approved."""
    try:
        binding = require_bound_access(workspace, access_context, action_grant, request)
        binding.provider.authorize_action(
            workspace, access_context, action_grant, request
        )
        with binding.provider.with_current_authorization(
            workspace, access_context, action_grant, request
        ):
            return binding.kernel._write(
                request,
                actor_ref=binding.actor_ref,
                actor_kind=binding.actor_kind,
                action_grant_ref=binding.action_grant_ref,
            )
    except StructureError as exc:
        return _write_error(exc.code)


def read_structure_versions(workspace, access_context, action_grant, request):
    """No object probing, current fallback or partial success when unbound."""
    try:
        binding = require_bound_access(workspace, access_context, action_grant, request)
        binding.provider.authorize_action(
            workspace, access_context, action_grant, request
        )
        response = binding.kernel._read(
            request, access_basis_sha256=binding.access_basis_sha256
        )
        with binding.provider.with_current_authorization(
            workspace, access_context, action_grant, request
        ):
            return response
    except StructureError as exc:
        response = _seal_read(_read_shell(request, exc.code))
        validate_shape("StructureReadResponse", response)
        return response

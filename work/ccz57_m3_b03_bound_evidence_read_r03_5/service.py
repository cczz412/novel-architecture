"""Fixed B-03 facade: seven records, eight roles, no caller text range."""

from __future__ import annotations

import hashlib
import json
import threading
from copy import deepcopy
from pathlib import Path
from typing import Any, Callable

from b03_contracts import (
    ACTIVE_STATE,
    SLICE_RETENTION,
    admit_candidate_context,
    build_output_record,
    canonical_bytes,
    current_trusted_time_head,
    fail,
    parse_utc,
    record_ref,
    resolve_bound_candidate_input,
    sha256_value,
    validate_authorization_record,
    validate_consent_record,
    validate_lifecycle_record,
    validate_lifecycle_streams,
    validate_policy_record,
    validate_request_record,
    validate_slice_record,
    validate_trusted_time_record,
)
from b03_store import B03FixtureStore
from restricted_source_reader import (
    RestrictedSourceReader,
    SourceReadAuthorizationStateProjector,
)
from restricted_source_retention import RestrictedSourceRetentionController

_ROOT_LOCKS: dict[str, threading.RLock] = {}
_ROOT_LOCKS_GUARD = threading.Lock()


def _root_lock(root: Path) -> threading.RLock:
    key = str(root.resolve(strict=False))
    with _ROOT_LOCKS_GUARD:
        return _ROOT_LOCKS.setdefault(key, threading.RLock())


class B03Service:
    """Expose only admitted operations; plaintext storage stays private."""

    __slots__ = (
        "__store",
        "__load_context",
        "__load_policy",
        "__commit_capability",
        "__read_capability",
        "__validate_live",
        "__lock",
    )

    @staticmethod
    def __seal(value: Any, *, drift_code: str) -> Callable[[], Any]:
        sealed = canonical_bytes(value)
        seal_hash = hashlib.sha256(sealed).hexdigest()

        def load() -> Any:
            reopened = json.loads(sealed)
            if hashlib.sha256(canonical_bytes(reopened)).hexdigest() != seal_hash:
                fail(drift_code)
            return reopened

        return load

    def __init__(
        self,
        root: Path,
        *,
        upstream: dict[str, Any],
        policy: dict[str, Any],
        trusted_times: list[dict[str, Any]],
    ) -> None:
        context = admit_candidate_context(**upstream)
        validate_policy_record(policy)
        for trusted_time in trusted_times:
            validate_trusted_time_record(trusted_time)
        current_trusted_time_head(trusted_times)
        self.__load_context = self.__seal(
            context, drift_code="B03_ADMITTED_CONTEXT_DRIFT"
        )
        self.__load_policy = self.__seal(policy, drift_code="B03_ADMITTED_POLICY_DRIFT")

        def validate_request_writer(
            record: dict[str, Any], records: list[dict[str, Any]]
        ) -> None:
            validate_request_record(record, context=self.__load_context())

        def validate_consent_writer(
            record: dict[str, Any], records: list[dict[str, Any]]
        ) -> None:
            validate_consent_record(
                record,
                records=[*records, self.__load_policy()],
                context=self.__load_context(),
            )

        def validate_authorization_writer(
            record: dict[str, Any], records: list[dict[str, Any]]
        ) -> None:
            validate_authorization_record(
                record,
                all_records=[*records, self.__load_policy()],
                context=self.__load_context(),
            )

        def validate_lifecycle_writer(
            record: dict[str, Any], records: list[dict[str, Any]]
        ) -> None:
            validate_lifecycle_record(
                record, all_records=[*records, self.__load_policy()]
            )
            validate_lifecycle_streams([*records, record])

        record_validators = {
            "M3_SOURCE_READ_REQUEST": validate_request_writer,
            "M3_SOURCE_READ_CONSENT": validate_consent_writer,
            "M3_SOURCE_READ_CONSENT_LIFECYCLE_RECEIPT": validate_lifecycle_writer,
            "M3_SOURCE_READ_AUTHORIZATION": validate_authorization_writer,
            "M3_SOURCE_READ_AUTHORIZATION_LIFECYCLE_RECEIPT": validate_lifecycle_writer,
        }
        self.__validate_live = self.__validate_live_slice

        def plan_retention(
            slice_record: dict[str, Any],
            records: list[dict[str, Any]],
            trusted_time_records: list[dict[str, Any]],
            event: str,
        ) -> dict[str, Any]:
            return RestrictedSourceRetentionController.prepare(
                slice_record=slice_record,
                policy=self.__load_policy(),
                records=records,
                trusted_time_records=trusted_time_records,
                context=self.__load_context(),
                event=event,
            )

        self.__commit_capability = object()
        self.__read_capability = object()
        self.__store = B03FixtureStore(
            root,
            commit_capability=self.__commit_capability,
            read_capability=self.__read_capability,
            record_validators=record_validators,
            slice_validator=self.__validate_live,
            retention_planner=plan_retention,
        )
        self.__lock = _root_lock(self.__store.root)
        try:
            with self.__lock:
                self.__store.admit_trusted_times(
                    trusted_times,
                    chain_validator=current_trusted_time_head,
                    inactive_selector=self.__slice_is_inactive,
                )
        except BaseException:
            self.__store.close()
            raise

    @property
    def policy(self) -> dict[str, Any]:
        return self.__load_policy()

    @property
    def trusted_times(self) -> list[dict[str, Any]]:
        with self.__lock:
            return self.__store.trusted_times()

    def __records(self) -> list[dict[str, Any]]:
        return self.__store.records()

    @staticmethod
    def __record_from(
        records: list[dict[str, Any]], ref: dict[str, Any]
    ) -> dict[str, Any]:
        matches = [item for item in records if record_ref(item) == ref]
        if len(matches) != 1:
            fail("B03_REFERENCE_INTEGRITY_FAILED")
        return matches[0]

    def __record(self, ref: dict[str, Any]) -> dict[str, Any]:
        return self.__record_from(self.__records(), ref)

    def __append(self, record: dict[str, Any], *, expected_type: str) -> dict[str, Any]:
        return self.__store.append_record(
            record,
            expected_type=expected_type,
            commit_capability=self.__commit_capability,
        )

    def request(
        self, product_input: dict[str, Any], *, created_at: str
    ) -> dict[str, Any]:
        with self.__lock:
            context = self.__load_context()
            resolved = resolve_bound_candidate_input(product_input, context=context)
            record = build_output_record(
                record_type="M3_SOURCE_READ_REQUEST",
                created_at=created_at,
                payload={
                    "subject": resolved["subject"],
                    "evidence_binding": resolved["evidence_binding"],
                    "purpose": resolved["purpose"],
                    "candidate_schema_id": resolved["candidate_schema_id"],
                    "b02_context_hash": resolved["b02_context_hash"],
                },
            )
            validate_request_record(record, context=context)
            return self.__append(record, expected_type="M3_SOURCE_READ_REQUEST")

    def consent(
        self,
        request_ref: dict[str, Any],
        *,
        actor: str,
        created_at: str,
    ) -> dict[str, Any]:
        with self.__lock:
            records = self.__records()
            request = self.__record_from(records, request_ref)
            policy = self.__load_policy()
            record = build_output_record(
                record_type="M3_SOURCE_READ_CONSENT",
                created_at=created_at,
                payload={
                    "request_ref": request_ref,
                    "policy_ref": record_ref(policy),
                    "actor_identity": actor,
                    "authorization_mode": "POLICY_FIXTURE_ONLY",
                    "purpose": request["payload"]["purpose"],
                    "request_scope_hash": sha256_value(request["payload"]),
                    "issued_at": "2026-08-29T06:01:00Z",
                    "expires_at": "2026-08-29T06:10:00Z",
                    "consent_sequence": 0,
                },
            )
            validate_consent_record(
                record,
                records=[*records, policy],
                context=self.__load_context(),
            )
            return self.__append(record, expected_type="M3_SOURCE_READ_CONSENT")

    def authorize(
        self,
        request_ref: dict[str, Any],
        consent_ref: dict[str, Any],
        *,
        created_at: str,
    ) -> dict[str, Any]:
        with self.__lock:
            records = self.__records()
            request = self.__record_from(records, request_ref)
            policy = self.__load_policy()
            record = build_output_record(
                record_type="M3_SOURCE_READ_AUTHORIZATION",
                created_at=created_at,
                payload={
                    "request_ref": request_ref,
                    "policy_ref": record_ref(policy),
                    "source_read_consent_ref": consent_ref,
                    "authorization_mode": "POLICY_FIXTURE_ONLY",
                    "purpose": request["payload"]["purpose"],
                    "subject_binding_hash": sha256_value(request["payload"]["subject"]),
                    "evidence_binding_hash": request["payload"]["evidence_binding"][
                        "binding_hash"
                    ],
                    "evidence_sha256": request["payload"]["evidence_binding"][
                        "evidence_sha256"
                    ],
                    "source_revision_ref": deepcopy(
                        request["payload"]["subject"]["source_revision_ref"]
                    ),
                    "source_generation_ref": deepcopy(
                        request["payload"]["subject"]["source_generation_ref"]
                    ),
                    "b02_context_hash": request["payload"]["b02_context_hash"],
                    "issued_at": "2026-08-29T06:01:00Z",
                    "expires_at": "2026-08-29T06:10:00Z",
                    "authorization_sequence": 0,
                    "retention_class": SLICE_RETENTION,
                },
            )
            validate_authorization_record(
                record,
                all_records=[*records, policy],
                context=self.__load_context(),
            )
            return self.__append(record, expected_type="M3_SOURCE_READ_AUTHORIZATION")

    @staticmethod
    def __slice_links_parent(
        slice_record: dict[str, Any],
        parent_type: str,
        parent_ref: dict[str, Any],
    ) -> bool:
        payload = slice_record["payload"]
        if parent_type == "M3_SOURCE_READ_CONSENT":
            return payload["source_read_consent_ref"] == parent_ref
        return payload["authorization_ref"] == parent_ref

    def __project_slice(
        self,
        slice_record: dict[str, Any],
        records: list[dict[str, Any]],
        trusted_times: list[dict[str, Any]],
    ) -> dict[str, Any]:
        payload = slice_record["payload"]
        request = self.__record_from(records, payload["request_ref"])
        consent = self.__record_from(records, payload["source_read_consent_ref"])
        authorization = self.__record_from(records, payload["authorization_ref"])
        head = current_trusted_time_head(trusted_times)
        return SourceReadAuthorizationStateProjector.project(
            request=request,
            authorization=authorization,
            consent=consent,
            policy=self.__load_policy(),
            records=records,
            trusted_time_records=trusted_times,
            supplied_time_ref=record_ref(head),
            context=self.__load_context(),
        )

    def __slice_is_inactive(
        self,
        slice_record: dict[str, Any],
        records: list[dict[str, Any]],
        trusted_times: list[dict[str, Any]],
    ) -> bool:
        state = self.__project_slice(slice_record, records, trusted_times)
        return (
            state["projected_authorization_state"] != ACTIVE_STATE
            or state["projected_consent_state"] != ACTIVE_STATE
        )

    def lifecycle(
        self,
        parent_ref: dict[str, Any],
        *,
        event: str,
        effective_at: str,
        created_at: str,
        replacement_ref: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        with self.__lock:
            records = self.__records()
            parent = self.__record_from(records, parent_ref)
            mapping = {
                "M3_SOURCE_READ_CONSENT": "M3_SOURCE_READ_CONSENT_LIFECYCLE_RECEIPT",
                "M3_SOURCE_READ_AUTHORIZATION": "M3_SOURCE_READ_AUTHORIZATION_LIFECYCLE_RECEIPT",
            }
            record_type = mapping.get(parent["record_type"])
            if record_type is None:
                fail("B03_LIFECYCLE_INVALID")
            record = build_output_record(
                record_type=record_type,
                created_at=created_at,
                payload={
                    "parent_ref": parent_ref,
                    "lifecycle_sequence": 1,
                    "event": event,
                    "effective_at": effective_at,
                    "reason_code": "FIXTURE_TERMINAL_EVENT",
                    "replacement_ref": replacement_ref,
                },
            )
            policy = self.__load_policy()
            validate_lifecycle_record(record, all_records=[*records, policy])
            future_records = [*records, record]
            validate_lifecycle_streams(future_records)
            trusted_times = self.__store.trusted_times()
            head = current_trusted_time_head(trusted_times)
            if parse_utc(effective_at, "B03_LIFECYCLE_INVALID") > parse_utc(
                head["payload"]["trusted_evaluation_time"],
                "B03_TRUSTED_TIME_INVALID",
            ):
                fail("B03_LIFECYCLE_FUTURE_EFFECTIVE_AT")

            def should_retain(
                slice_record: dict[str, Any],
                current_records: list[dict[str, Any]],
                current_times: list[dict[str, Any]],
            ) -> bool:
                if not self.__slice_links_parent(
                    slice_record, parent["record_type"], parent_ref
                ):
                    return False
                state = self.__project_slice(
                    slice_record, current_records, current_times
                )
                return (
                    state["projected_authorization_state"] != ACTIVE_STATE
                    or state["projected_consent_state"] != ACTIVE_STATE
                )

            return self.__store.append_record_with_retentions(
                record,
                event="UNREADABLE",
                expected_type=record_type,
                commit_capability=self.__commit_capability,
                retention_selector=should_retain,
            )

    def __validate_live_slice(
        self,
        slice_record: dict[str, Any],
        records: list[dict[str, Any]],
        trusted_times: list[dict[str, Any]],
    ) -> None:
        policy = self.__load_policy()
        validate_slice_record(
            slice_record,
            all_records=[*records, policy],
            context=self.__load_context(),
        )
        state = self.__project_slice(slice_record, records, trusted_times)
        payload = slice_record["payload"]
        if (
            state["projected_authorization_state"] != ACTIVE_STATE
            or state["projected_consent_state"] != ACTIVE_STATE
        ):
            fail("B03_SOURCE_READ_NOT_ACTIVE")
        for key in (
            "authorization_lifecycle_refs",
            "consent_lifecycle_refs",
            "trusted_time_ref",
        ):
            if payload[key] != state[key]:
                fail("B03_SOURCE_READ_NOT_ACTIVE")

    def read(
        self,
        request_ref: dict[str, Any],
        consent_ref: dict[str, Any],
        authorization_ref: dict[str, Any],
    ) -> dict[str, Any]:
        with self.__lock:
            records = self.__records()
            trusted_times = self.__store.trusted_times()
            head = current_trusted_time_head(trusted_times)
            request = self.__record_from(records, request_ref)
            consent = self.__record_from(records, consent_ref)
            authorization = self.__record_from(records, authorization_ref)
            slice_record = RestrictedSourceReader.build_slice(
                request=request,
                consent=consent,
                authorization=authorization,
                policy=self.__load_policy(),
                records=records,
                trusted_time_records=trusted_times,
                supplied_time_ref=record_ref(head),
                context=self.__load_context(),
            )
            if self.__store.before_publish_hook is not None:
                self.__store.before_publish_hook()

            return self.__store.publish_slice(
                slice_record,
                commit_capability=self.__commit_capability,
            )

    def read_slice_content(self, slice_ref: dict[str, Any]) -> str:
        with self.__lock:
            try:
                return self.__store.read_slice_content(
                    slice_ref,
                    read_capability=self.__read_capability,
                )
            except Exception as error:
                if getattr(error, "code", None) == "B03_SOURCE_READ_NOT_ACTIVE":
                    self.__purge_one(slice_ref, event="UNREADABLE")
                raise

    def __purge_one(self, slice_ref: dict[str, Any], *, event: str) -> dict[str, Any]:
        return self.__store.commit_retention(
            slice_ref,
            event=event,
            commit_capability=self.__commit_capability,
        )

    def purge(
        self, slice_ref: dict[str, Any], *, event: str = "UNREADABLE"
    ) -> dict[str, Any]:
        with self.__lock:
            return self.__purge_one(slice_ref, event=event)

    def advance_trusted_time(self, record: dict[str, Any]) -> None:
        with self.__lock:
            validate_trusted_time_record(record)
            combined = [*self.__store.trusted_times(), record]
            current_trusted_time_head(combined)
            self.__store.admit_trusted_times(
                combined,
                chain_validator=current_trusted_time_head,
                inactive_selector=self.__slice_is_inactive,
            )

    def snapshot(self) -> dict[str, str]:
        with self.__lock:
            return self.__store.snapshot()

    def state_counts(self) -> dict[str, int]:
        with self.__lock:
            return self.__store.state_counts()

    def slice_core(self, slice_ref: dict[str, Any]) -> dict[str, Any] | None:
        with self.__lock:
            return deepcopy(self.__store.existing_slice_core(slice_ref))

    def plaintext_present(self, slice_ref: dict[str, Any]) -> bool:
        with self.__lock:
            return self.__store.plaintext_present(slice_ref)

    def tombstone(self, slice_ref: dict[str, Any]) -> dict[str, Any] | None:
        with self.__lock:
            return self.__store.tombstone(slice_ref)

    def storage_residue(self) -> list[str]:
        with self.__lock:
            return self.__store.storage_residue()

    @property
    def events(self) -> tuple[str, ...]:
        with self.__lock:
            return tuple(self.__store.events)

    def set_test_hook(self, name: str, hook: Any) -> None:
        if name not in {
            "before_publish",
            "before_retention_commit",
            "before_transaction_commit",
        }:
            fail("B03_TEST_HOOK_INVALID")
        attribute = {
            "before_publish": "before_publish_hook",
            "before_retention_commit": "before_retention_commit_hook",
            "before_transaction_commit": "before_transaction_commit_hook",
        }[name]
        setattr(self.__store, attribute, hook)

    def close(self) -> None:
        with self.__lock:
            self.__store.close()

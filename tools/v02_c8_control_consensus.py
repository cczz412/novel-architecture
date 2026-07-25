#!/usr/bin/env python3
"""V02/C8-C9：公开计票后解盲，并在正式靶零分歧时构造控制臂映射。

顺序是这件工具最重要的合同：

1. 第二票必须先命中源码内预写 SHA，生成第二票预封签；
2. 只读公开包清单与两张盲票，完成包身份、选项与独立性核验；
3. 在不知道 21 个正式靶和 6 个隐藏审计包身份时生成公开计票票；
4. 第二票预封签、公开计票及其独立封签实际落盘并回读通过后，才读取
   私有交叉表并解盲；
5. 隐藏审计 6 包须从 C7.7 冻结母集按原种子重算，并逐个核对源行；
6. 正式靶只要还有一条分歧，绝不生成 ``final_control_mapping``；
7. 隐藏审计包的分歧只让偏倚一致性读数变成 ``MISSING``，不改旧图，
   也不阻断正式靶零分歧时的控制臂冻结。

本工具不调用模型、不读取正文、不改正式金标，也不会改两张原票。
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[1]
V02_ROOT = ROOT / "experiments/extraction_redesign_v02_overnight_20260725"
C8_ROOT = V02_ROOT / "V02_C8_control_mapping_and_interpretability"
C9_ROOT = V02_ROOT / "V02_C9_engineering_gate_fix_20260725"
PREPARATION_DIR = C8_ROOT / "preparation"
C8_CONSENSUS_INPUT_DIR = C8_ROOT / "consensus"
DEFAULT_CONSENSUS_DIR = C9_ROOT / "consensus_rerun_r02"
DEFAULT_CONTROL_MAPPING_DIR = C9_ROOT / "control_mapping"
FIRST_VOTE = C8_CONSENSUS_INPUT_DIR / "votes/first_vote.json"
SECOND_VOTE = C8_CONSENSUS_INPUT_DIR / "votes/second_vote.json"
PREPARATION_MANIFEST = PREPARATION_DIR / "artifact_manifest.json"
PACKET_MANIFEST = PREPARATION_DIR / "blind_packet_manifest.json"
PRIVATE_CROSSWALK = PREPARATION_DIR / "packet_source_crosswalk_private.json"
PRIVATE_PREFREEZE = PREPARATION_DIR / "mechanical_prefreeze_private.json"
PRIVATE_LEDGER = PREPARATION_DIR / "route_ledger_private.json"
PRIVATE_QUEUE = PREPARATION_DIR / "blind_review_queue_private.json"
PRIVATE_AUDIT_PLAN = PREPARATION_DIR / "audit_sampling_plan_private.json"
TREATMENT_MAPPING = (
    V02_ROOT
    / "V02_C7_final_mapping_and_C5_rescore/mapping/final_treatment_mapping.json"
)
C77_DIR = V02_ROOT / "V02_C7_6_7_ai_consensus_workspace"
C77_PACKET_MANIFEST = C77_DIR / "c7_7_packet_manifest.json"

EXPECTED_PREPARATION_MANIFEST_SHA256 = (
    "5317e7667442e77d6203b3b23d74475967ec7fae3113889da39f320baab51362"
)
EXPECTED_PACKET_MANIFEST_SHA256 = (
    "12a155ebb1404cfcf06ff3fbc03133ed1778a155a8ba741318b882036d8c9235"
)
EXPECTED_TREATMENT_MAPPING_SHA256 = (
    "7ddfcb2b29ed7fc1340ebd323da8603f44a3bef7d6511bce474ecbbf78acea51"
)
EXPECTED_FIRST_VOTE_SHA256 = (
    "c247b12bbe7a4d0015d317220107ded64d944892ab749ea97c8d049d2fa26231"
)
EXPECTED_SECOND_VOTE_SHA256 = (
    "2b64f5ae08ce6a826c7258f0a385b093f895d02ed9093f6d2bde37623731a540"
)
EXPECTED_C77_PACKET_MANIFEST_SHA256 = (
    "c3a06c1917bfdcf52f10080867bbe858c8d2c3ac2b53f3e672597f8ee39529b5"
)
DECISION_RULE_SHA256 = (
    "2f2a01a8bf75dc7d960d5f1c75b385db8ffdbf7debb6ad20e69048bf5c693333"
)
AUDIT_SAMPLE_SEED = "V02-C8-FIXED-AUDIT-SAMPLE-v1"
AUDIT_SAMPLE_ALGORITHM = (
    "sort ascending by SHA256(seed + NUL + packet_id), "
    "tie-break packet_id; take first 6"
)
EXPECTED_AUDIT_SOURCE_ROW_IDS = (
    "C7-001",
    "C7-006",
    "C7-007",
    "C7-017",
    "C7-018",
    "C7-029",
)

CASE_ORDER = ("B02-U0039", "B03-U0041", "B01-U0033")
CASE_DENOMINATORS = {
    "B02-U0039": 8,
    "B03-U0041": 16,
    "B01-U0033": 25,
}
CONTROL_PARENT_EVENT_COUNTS = {
    "B02-U0039": 44,
    "B03-U0041": 10,
    "B01-U0033": 75,
}
NO_CORRESPONDENCE = "NO_CORRESPONDENCE"
TARGET_SOURCE_SET = "S1"
AUDIT_SOURCE_SET = "S2"


class C8ConsensusError(RuntimeError):
    """C8 计票、解盲或冻结不满足预写钢线。"""


_PUBLIC_PREUNBLIND_CAPABILITY = object()


class _VerifiedPublicPreunblindContext:
    """只由公开三件落盘回读闸签发的私有解盲通行凭据。"""

    __slots__ = (
        "_capability",
        "output_dir",
        "public_artifact_set_sha256",
        "public_file_shas",
    )

    def __init__(
        self,
        *,
        capability: object,
        output_dir: Path,
        public_artifact_set_sha256: str,
        public_file_shas: Mapping[str, str],
    ) -> None:
        if capability is not _PUBLIC_PREUNBLIND_CAPABILITY:
            raise C8ConsensusError("禁止自行构造公开落盘回读通行凭据")
        self._capability = capability
        self.output_dir = output_dir.resolve()
        self.public_artifact_set_sha256 = public_artifact_set_sha256
        self.public_file_shas = dict(public_file_shas)


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def canonical_bytes(value: Any) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def sha256_file(path: Path) -> str:
    if not path.is_file():
        raise C8ConsensusError(f"冻结输入不存在：{path}")
    return sha256_bytes(path.read_bytes())


def display_path(path: Path) -> str:
    resolved = path.resolve()
    try:
        return resolved.relative_to(ROOT).as_posix()
    except ValueError:
        return resolved.as_posix()


def canonical_sha(value: Any) -> str:
    return sha256_bytes(canonical_bytes(value))


def _assert_sha(label: str, path: Path, expected: str) -> str:
    observed = sha256_file(path)
    if observed != expected:
        raise C8ConsensusError(f"冻结输入 SHA 漂移：{label}")
    return observed


def _manifest_index(
    manifest: Mapping[str, Any],
) -> dict[str, Mapping[str, Any]]:
    rows = manifest.get("files")
    if not isinstance(rows, list):
        raise C8ConsensusError("C8 准备件清单缺 files")
    index: dict[str, Mapping[str, Any]] = {}
    for row in rows:
        if not isinstance(row, Mapping):
            raise C8ConsensusError("C8 准备件清单含非对象")
        path = row.get("path")
        digest = row.get("sha256")
        if (
            not isinstance(path, str)
            or path in index
            or not isinstance(digest, str)
            or len(digest) != 64
        ):
            raise C8ConsensusError("C8 准备件清单路径或 SHA 非法")
        index[path] = row
    return index


def _verify_manifest_member(
    index: Mapping[str, Mapping[str, Any]],
    relative: str,
) -> str:
    row = index.get(relative)
    if row is None:
        raise C8ConsensusError(f"C8 准备件未登记：{relative}")
    return _assert_sha(
        relative,
        PREPARATION_DIR / relative,
        str(row["sha256"]),
    )


def _public_packet_contract() -> tuple[
    Mapping[str, Any],
    dict[str, Mapping[str, Any]],
    list[str],
    dict[str, list[str]],
    dict[str, str],
]:
    _assert_sha(
        "preparation/artifact_manifest.json",
        PREPARATION_MANIFEST,
        EXPECTED_PREPARATION_MANIFEST_SHA256,
    )
    preparation_manifest = read_json(PREPARATION_MANIFEST)
    if (
        not isinstance(preparation_manifest, Mapping)
        or preparation_manifest.get("schema_version")
        != "v02-c8-preparation-artifact-manifest.v1"
    ):
        raise C8ConsensusError("C8 准备件清单身份漂移")
    manifest_index = _manifest_index(preparation_manifest)
    packet_manifest_sha = _verify_manifest_member(
        manifest_index,
        "blind_packet_manifest.json",
    )
    if packet_manifest_sha != EXPECTED_PACKET_MANIFEST_SHA256:
        raise C8ConsensusError("盲包清单 SHA 不等于预写值")

    packet_manifest = read_json(PACKET_MANIFEST)
    packet_rows = packet_manifest.get("packets")
    if (
        packet_manifest.get("schema_version")
        != "v02-c8-blind-packet-manifest.v1"
        or packet_manifest.get("packet_total") != 27
        or packet_manifest.get("decision_rule_sha256")
        != DECISION_RULE_SHA256
        or not isinstance(packet_rows, list)
        or len(packet_rows) != 27
    ):
        raise C8ConsensusError("27 个盲包清单身份、数量或判定规则漂移")

    packet_ids: list[str] = []
    allowed_by_packet: dict[str, list[str]] = {}
    packet_sha_by_id: dict[str, str] = {}
    for ordinal, row in enumerate(packet_rows, 1):
        if not isinstance(row, Mapping):
            raise C8ConsensusError("盲包清单含非对象")
        packet_id = row.get("packet_id")
        relative = row.get("packet_path")
        expected_id = f"C8-BLIND-{ordinal:03d}"
        if (
            packet_id != expected_id
            or not isinstance(relative, str)
            or relative != f"blind_packets/{expected_id}.json"
            or packet_id in allowed_by_packet
        ):
            raise C8ConsensusError("盲包身份、顺序或路径漂移")
        packet_sha = _verify_manifest_member(manifest_index, relative)
        if packet_sha != row.get("packet_sha256"):
            raise C8ConsensusError(f"{packet_id} 包 SHA 与包清单不一致")
        packet = read_json(PREPARATION_DIR / relative)
        choices = packet.get("choices")
        if (
            packet.get("packet_id") != packet_id
            or not isinstance(choices, list)
            or not choices
        ):
            raise C8ConsensusError(f"{packet_id} 票面身份或选项非法")
        choice_ids = [
            choice.get("choice_id")
            for choice in choices
            if isinstance(choice, Mapping)
        ]
        if (
            len(choice_ids) != len(choices)
            or any(not isinstance(value, str) for value in choice_ids)
            or len(choice_ids) != len(set(choice_ids))
            or choice_ids[-1] != NO_CORRESPONDENCE
            or not isinstance(packet.get("decision_rule"), str)
            or sha256_bytes(packet["decision_rule"].encode("utf-8"))
            != DECISION_RULE_SHA256
        ):
            raise C8ConsensusError(f"{packet_id} 选项合同或规则漂移")
        packet_ids.append(packet_id)
        allowed_by_packet[packet_id] = [str(value) for value in choice_ids]
        packet_sha_by_id[packet_id] = packet_sha

    return (
        preparation_manifest,
        manifest_index,
        packet_ids,
        allowed_by_packet,
        packet_sha_by_id,
    )


def _validate_vote(
    path: Path,
    *,
    packet_ids: Sequence[str],
    allowed_by_packet: Mapping[str, Sequence[str]],
    first_vote_sha: str | None,
) -> dict[str, Any]:
    document = read_json(path)
    base_fields = {
        "voter_id",
        "model_family",
        "packet_manifest_sha256",
        "decision_rule_sha256",
        "votes",
    }
    second_fields = base_fields | {
        "first_vote_sha256",
        "first_ballot_sha256_seen_only",
        "first_vote_content_read",
    }
    expected_fields = base_fields if first_vote_sha is None else second_fields
    if not isinstance(document, Mapping) or set(document) != expected_fields:
        raise C8ConsensusError(f"{path.name} 顶层字段不完整或夹带未知字段")

    voter_id = document.get("voter_id")
    model_family = document.get("model_family")
    votes = document.get("votes")
    if (
        not isinstance(voter_id, str)
        or not voter_id
        or not isinstance(model_family, str)
        or not model_family
        or document.get("packet_manifest_sha256")
        != EXPECTED_PACKET_MANIFEST_SHA256
        or document.get("decision_rule_sha256") != DECISION_RULE_SHA256
        or not isinstance(votes, list)
        or len(votes) != 27
    ):
        raise C8ConsensusError(f"{path.name} 身份、绑定 SHA 或票数非法")

    if first_vote_sha is not None:
        if (
            document.get("first_vote_sha256") != first_vote_sha
            or document.get("first_ballot_sha256_seen_only")
            != first_vote_sha
            or document.get("first_vote_content_read") is not False
        ):
            raise C8ConsensusError("第二票未只读绑定第一票 SHA，或已读取票面")

    canonical_votes: list[dict[str, Any]] = []
    for expected_packet_id, row in zip(packet_ids, votes, strict=True):
        if (
            not isinstance(row, Mapping)
            or set(row) != {"packet_id", "selected_choice_ids"}
            or row.get("packet_id") != expected_packet_id
        ):
            raise C8ConsensusError(f"{path.name} 包顺序或票行合同漂移")
        selected = row.get("selected_choice_ids")
        allowed = list(allowed_by_packet[expected_packet_id])
        if (
            not isinstance(selected, list)
            or not selected
            or any(not isinstance(value, str) for value in selected)
            or len(selected) != len(set(selected))
            or any(value not in allowed for value in selected)
            or (
                NO_CORRESPONDENCE in selected
                and selected != [NO_CORRESPONDENCE]
            )
            or selected
            != [value for value in allowed if value in set(selected)]
        ):
            raise C8ConsensusError(
                f"{path.name} {expected_packet_id} 选项非法或顺序漂移"
            )
        canonical_votes.append(
            {
                "packet_id": expected_packet_id,
                "selected_choice_ids": list(selected),
            }
        )

    return {
        "voter_id": voter_id,
        "model_family": model_family,
        "packet_manifest_sha256": document["packet_manifest_sha256"],
        "decision_rule_sha256": document["decision_rule_sha256"],
        "votes": canonical_votes,
        "vote_sha256": sha256_file(path),
    }


def _visible_tally(
    first: Mapping[str, Any],
    second: Mapping[str, Any],
) -> dict[str, Any]:
    if first["voter_id"] == second["voter_id"]:
        raise C8ConsensusError("两票 voter_id 相同，不构成独立票")
    if first["model_family"] == second["model_family"]:
        raise C8ConsensusError("两票 model_family 相同，不构成独立票")
    rows: list[dict[str, Any]] = []
    for first_row, second_row in zip(
        first["votes"], second["votes"], strict=True
    ):
        if first_row["packet_id"] != second_row["packet_id"]:
            raise C8ConsensusError("两票包顺序不一致")
        first_choices = list(first_row["selected_choice_ids"])
        second_choices = list(second_row["selected_choice_ids"])
        rows.append(
            {
                "packet_id": first_row["packet_id"],
                "agreement": first_choices == second_choices,
                "first_selected_choice_ids": first_choices,
                "second_selected_choice_ids": second_choices,
                "unanimous_selected_choice_ids": (
                    first_choices if first_choices == second_choices else None
                ),
            }
        )
    agreement_total = sum(row["agreement"] for row in rows)
    return {
        "schema_version": "v02-c8-visible-two-vote-tally.v1",
        "status": (
            "VISIBLE_TALLY_HAS_DISAGREEMENT"
            if agreement_total != 27
            else "VISIBLE_TALLY_ALL_AGREE"
        ),
        "packet_total": 27,
        "agreement_total": agreement_total,
        "disagreement_total": 27 - agreement_total,
        "role_labels_visible_during_tally": False,
        "private_crosswalk_opened_before_tally": False,
        "voters": [
            {
                "voter_id": first["voter_id"],
                "model_family": first["model_family"],
                "vote_sha256": first["vote_sha256"],
            },
            {
                "voter_id": second["voter_id"],
                "model_family": second["model_family"],
                "vote_sha256": second["vote_sha256"],
            },
        ],
        "rows": rows,
        "model_api_calls": 0,
        "network_requests": 0,
    }


def _build_public_preunblind_phase() -> tuple[
    dict[str, bytes],
    dict[str, Any],
]:
    """只读取公开件，构造必须先落盘的三份解盲前工件。"""

    (
        preparation_manifest,
        manifest_index,
        packet_ids,
        allowed_by_packet,
        _packet_shas,
    ) = _public_packet_contract()
    first_sha = _assert_sha(
        "first_vote.json",
        FIRST_VOTE,
        EXPECTED_FIRST_VOTE_SHA256,
    )
    second_sha = _assert_sha(
        "second_vote.json",
        SECOND_VOTE,
        EXPECTED_SECOND_VOTE_SHA256,
    )
    first = _validate_vote(
        FIRST_VOTE,
        packet_ids=packet_ids,
        allowed_by_packet=allowed_by_packet,
        first_vote_sha=None,
    )
    second = _validate_vote(
        SECOND_VOTE,
        packet_ids=packet_ids,
        allowed_by_packet=allowed_by_packet,
        first_vote_sha=first_sha,
    )
    if second["vote_sha256"] != second_sha:
        raise C8ConsensusError("第二票验证结果与预封签 SHA 不一致")

    second_vote_seal = {
        "schema_version": "v02-c9-second-vote-preunblind-seal.v1",
        "status": "SEALED_BEFORE_PRIVATE_UNBLIND",
        "second_vote_path": display_path(SECOND_VOTE),
        "expected_second_vote_sha256": EXPECTED_SECOND_VOTE_SHA256,
        "observed_second_vote_sha256": second_sha,
        "sha_match": True,
        "private_input_read_total_before_seal": 0,
        "model_api_calls": 0,
        "network_requests": 0,
    }
    second_vote_seal_raw = canonical_bytes(second_vote_seal)
    visible_tally = _visible_tally(first, second)
    visible_tally_raw = canonical_bytes(visible_tally)
    visible_tally_seal = {
        "schema_version": "v02-c9-visible-tally-preunblind-seal.v1",
        "status": "SEALED_BEFORE_PRIVATE_UNBLIND",
        "visible_tally_sha256": sha256_bytes(visible_tally_raw),
        "second_vote_preunblind_seal_sha256": sha256_bytes(
            second_vote_seal_raw
        ),
        "first_vote_sha256": first_sha,
        "second_vote_sha256": second_sha,
        "packet_total": 27,
        "private_input_read_total_before_seal": 0,
        "model_api_calls": 0,
        "network_requests": 0,
    }
    public_artifacts = {
        "second_vote_preunblind_seal.json": second_vote_seal_raw,
        "visible_tally.json": visible_tally_raw,
        "visible_tally_preunblind_seal.json": canonical_bytes(
            visible_tally_seal
        ),
    }
    context = {
        "preparation_manifest": preparation_manifest,
        "manifest_index": manifest_index,
        "packet_ids": packet_ids,
        "first": first,
        "second": second,
        "visible_tally": visible_tally,
        "public_artifacts": public_artifacts,
    }
    return public_artifacts, context


def _verify_public_preunblind_files(
    output_dir: Path,
    expected_artifacts: Mapping[str, bytes],
) -> _VerifiedPublicPreunblindContext:
    """回读三份已落盘公开件；任何漂移都禁止进入私有解盲阶段。"""

    required = {
        "second_vote_preunblind_seal.json",
        "visible_tally.json",
        "visible_tally_preunblind_seal.json",
    }
    if set(expected_artifacts) != required:
        raise C8ConsensusError("解盲前公开工件集合漂移")
    observed: dict[str, str] = {}
    for relative in sorted(required):
        path = output_dir / relative
        raw = path.read_bytes() if path.is_file() else None
        if raw != expected_artifacts[relative]:
            raise C8ConsensusError(f"解盲前公开工件未落盘或漂移：{relative}")
        observed[relative] = sha256_bytes(raw)

    second_seal = read_json(output_dir / "second_vote_preunblind_seal.json")
    visible_seal = read_json(
        output_dir / "visible_tally_preunblind_seal.json"
    )
    if (
        second_seal.get("status") != "SEALED_BEFORE_PRIVATE_UNBLIND"
        or second_seal.get("expected_second_vote_sha256")
        != EXPECTED_SECOND_VOTE_SHA256
        or second_seal.get("observed_second_vote_sha256")
        != EXPECTED_SECOND_VOTE_SHA256
        or sha256_file(SECOND_VOTE) != EXPECTED_SECOND_VOTE_SHA256
    ):
        raise C8ConsensusError("第二票解盲前预封签回读失败")
    if (
        visible_seal.get("status") != "SEALED_BEFORE_PRIVATE_UNBLIND"
        or visible_seal.get("visible_tally_sha256")
        != observed["visible_tally.json"]
        or visible_seal.get("second_vote_preunblind_seal_sha256")
        != observed["second_vote_preunblind_seal.json"]
        or visible_seal.get("first_vote_sha256")
        != EXPECTED_FIRST_VOTE_SHA256
        or visible_seal.get("second_vote_sha256")
        != EXPECTED_SECOND_VOTE_SHA256
    ):
        raise C8ConsensusError("公开计票独立封签回读失败")
    public_artifact_set_sha256 = canonical_sha(
        {
            relative: digest
            for relative, digest in sorted(observed.items())
        }
    )
    return _VerifiedPublicPreunblindContext(
        capability=_PUBLIC_PREUNBLIND_CAPABILITY,
        output_dir=output_dir,
        public_artifact_set_sha256=public_artifact_set_sha256,
        public_file_shas=observed,
    )


def _private_documents(
    manifest_index: Mapping[str, Mapping[str, Any]],
) -> dict[str, Mapping[str, Any]]:
    paths = {
        "crosswalk": "packet_source_crosswalk_private.json",
        "prefreeze": "mechanical_prefreeze_private.json",
        "ledger": "route_ledger_private.json",
        "queue": "blind_review_queue_private.json",
        "audit_plan": "audit_sampling_plan_private.json",
    }
    documents: dict[str, Mapping[str, Any]] = {}
    for label, relative in paths.items():
        _verify_manifest_member(manifest_index, relative)
        document = read_json(PREPARATION_DIR / relative)
        if not isinstance(document, Mapping):
            raise C8ConsensusError(f"{relative} 不是对象")
        documents[label] = document
    return documents


def _unblind_choices(
    selected: Sequence[str],
    crosswalk_row: Mapping[str, Any],
) -> list[str]:
    choice_rows = crosswalk_row.get("choice_crosswalk")
    if not isinstance(choice_rows, list):
        raise C8ConsensusError("私有交叉表缺 choice_crosswalk")
    real_by_visible: dict[str, str | None] = {}
    for row in choice_rows:
        if not isinstance(row, Mapping):
            raise C8ConsensusError("私有选项交叉表含非对象")
        visible = row.get("visible_choice_id")
        real = row.get("real_event_id")
        if (
            not isinstance(visible, str)
            or visible in real_by_visible
            or (real is not None and not isinstance(real, str))
        ):
            raise C8ConsensusError("私有选项交叉表身份非法")
        real_by_visible[visible] = real
    if any(value not in real_by_visible for value in selected):
        raise C8ConsensusError("票面选项无法由私有交叉表解盲")
    return [
        str(real_by_visible[value])
        for value in selected
        if real_by_visible[value] is not None
    ]


def _validated_audit_sampling_receipt(
    audit_plan: Mapping[str, Any],
    crosswalk_rows: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """按冻结母集、原种子与源行身份重算隐藏复判 6 包。"""

    _assert_sha(
        "c7_7_packet_manifest.json",
        C77_PACKET_MANIFEST,
        EXPECTED_C77_PACKET_MANIFEST_SHA256,
    )
    c77_manifest = read_json(C77_PACKET_MANIFEST)
    c77_rows = c77_manifest.get("packets")
    if (
        c77_manifest.get("schema_version")
        != "v02-c7-7-consensus-packet-manifest.v1"
        or c77_manifest.get("packet_total") != 26
        or not isinstance(c77_rows, list)
        or len(c77_rows) != 26
    ):
        raise C8ConsensusError("C7.7 隐藏复判母集身份或数量漂移")

    mother_rows: list[dict[str, str]] = []
    mother_ids: set[str] = set()
    for row in c77_rows:
        if not isinstance(row, Mapping):
            raise C8ConsensusError("C7.7 隐藏复判母集含非对象")
        packet_id = row.get("packet_id")
        relative = row.get("packet_path")
        expected_sha = row.get("packet_sha256")
        if (
            not isinstance(packet_id, str)
            or packet_id in mother_ids
            or not isinstance(relative, str)
            or not relative.startswith("packets/")
            or not isinstance(expected_sha, str)
            or len(expected_sha) != 64
        ):
            raise C8ConsensusError("C7.7 隐藏复判母集源行身份非法")
        path = (C77_DIR / relative).resolve()
        if C77_DIR.resolve() not in path.parents:
            raise C8ConsensusError("C7.7 隐藏复判母集路径越界")
        observed_sha = sha256_file(path)
        if observed_sha != expected_sha:
            raise C8ConsensusError(
                f"C7.7 隐藏复判母集包 SHA 漂移：{packet_id}"
            )
        mother_rows.append(
            {
                "packet_id": packet_id,
                "packet_sha256": observed_sha,
            }
        )
        mother_ids.add(packet_id)

    expected_ranked = sorted(
        (
            {
                **row,
                "selection_rank_sha256": sha256_bytes(
                    (
                        f"{AUDIT_SAMPLE_SEED}\0{row['packet_id']}"
                    ).encode("utf-8")
                ),
            }
            for row in mother_rows
        ),
        key=lambda row: (
            row["selection_rank_sha256"],
            row["packet_id"],
        ),
    )
    expected_selected = sorted(
        row["packet_id"] for row in expected_ranked[:6]
    )
    ranked_plan = audit_plan.get("ranked_mother_set")
    selected_plan = audit_plan.get("selected_source_packet_ids")
    if (
        audit_plan.get("schema_version")
        != "v02-c8-private-fixed-audit-sampling.v1"
        or audit_plan.get("status") != "FROZEN_BEFORE_VOTES"
        or audit_plan.get("algorithm") != AUDIT_SAMPLE_ALGORITHM
        or audit_plan.get("seed") != AUDIT_SAMPLE_SEED
        or audit_plan.get("mother_packet_total") != 26
        or audit_plan.get("mother_set_sha256") != canonical_sha(mother_rows)
        or audit_plan.get("sample_total") != 6
        or ranked_plan != expected_ranked
        or selected_plan != expected_selected
        or expected_selected != list(EXPECTED_AUDIT_SOURCE_ROW_IDS)
    ):
        raise C8ConsensusError("隐藏复判 6 包未按原种子从冻结母集完整重算")

    audit_crosswalk_rows = [
        row
        for row in crosswalk_rows
        if row.get("private_source_set") == AUDIT_SOURCE_SET
    ]
    audit_source_ids = [row.get("source_packet_id") for row in audit_crosswalk_rows]
    if (
        len(audit_crosswalk_rows) != 6
        or any(not isinstance(value, str) for value in audit_source_ids)
        or len(set(audit_source_ids)) != 6
        or set(audit_source_ids) != set(expected_selected)
        or any(row.get("source_row_id") is not None for row in audit_crosswalk_rows)
    ):
        raise C8ConsensusError("隐藏复判 6 包与私有交叉表源行不完整")

    treatment_sha = _assert_sha(
        "final_treatment_mapping.json",
        TREATMENT_MAPPING,
        EXPECTED_TREATMENT_MAPPING_SHA256,
    )
    treatment = read_json(TREATMENT_MAPPING)
    treatment_by_source: dict[str, Mapping[str, Any]] = {}
    for row in treatment.get("rows", []):
        if not isinstance(row, Mapping) or not isinstance(
            row.get("source_detail"), Mapping
        ):
            continue
        source_id = row["source_detail"].get("row_id")
        if isinstance(source_id, str):
            if source_id in treatment_by_source:
                raise C8ConsensusError("旧工作映射源行身份重复")
            treatment_by_source[source_id] = row
    for crosswalk_row in audit_crosswalk_rows:
        source_id = str(crosswalk_row["source_packet_id"])
        treatment_row = treatment_by_source.get(source_id)
        if (
            treatment_row is None
            or treatment_row.get("case_id") != crosswalk_row.get("case_id")
            or treatment_row.get("atom_id") != crosswalk_row.get("atom_id")
        ):
            raise C8ConsensusError(
                f"隐藏复判源行与旧工作映射身份不完整：{source_id}"
            )

    return {
        "schema_version": "v02-c9-audit-sampling-revalidation.v1",
        "status": "PASS_RECOMPUTED_FROM_FROZEN_MOTHER_SET",
        "seed": AUDIT_SAMPLE_SEED,
        "algorithm": AUDIT_SAMPLE_ALGORITHM,
        "mother_packet_total": 26,
        "mother_set_sha256": canonical_sha(mother_rows),
        "selected_source_row_total": 6,
        "selected_source_row_ids": expected_selected,
        "selected_source_rows_unique": True,
        "crosswalk_source_rows_complete": True,
        "treatment_mapping_source_rows_complete": True,
        "treatment_mapping_sha256": treatment_sha,
        "private_role_opened_after_public_tally_seal": True,
        "model_api_calls": 0,
        "network_requests": 0,
    }


def _validate_private_identity(
    private: Mapping[str, Mapping[str, Any]],
    packet_ids: Sequence[str],
) -> tuple[dict[str, Mapping[str, Any]], dict[str, Any]]:
    crosswalk = private["crosswalk"]
    rows = crosswalk.get("rows")
    if (
        crosswalk.get("packet_total") != 27
        or crosswalk.get("source_set_counts") != {"S1": 21, "S2": 6}
        or not isinstance(rows, list)
        or len(rows) != 27
    ):
        raise C8ConsensusError("私有包来源交叉表身份或 21+6 数量漂移")
    by_packet: dict[str, Mapping[str, Any]] = {}
    for expected_id, row in zip(packet_ids, rows, strict=True):
        if (
            not isinstance(row, Mapping)
            or row.get("blind_packet_id") != expected_id
            or expected_id in by_packet
            or row.get("private_source_set")
            not in {TARGET_SOURCE_SET, AUDIT_SOURCE_SET}
        ):
            raise C8ConsensusError("私有包来源交叉表顺序或身份漂移")
        by_packet[expected_id] = row

    prefreeze = private["prefreeze"]
    ledger = private["ledger"]
    queue = private["queue"]
    audit_plan = private["audit_plan"]
    if (
        prefreeze.get("row_total") != 28
        or len(prefreeze.get("rows", [])) != 28
        or ledger.get("row_total") != 49
        or len(ledger.get("rows", [])) != 49
        or queue.get("row_total") != 21
        or len(queue.get("rows", [])) != 21
        or audit_plan.get("sample_total") != 6
        or len(audit_plan.get("selected_source_packet_ids", [])) != 6
    ):
        raise C8ConsensusError("私有 28+21 路由或 6 包审计身份漂移")
    target_packets = {
        row["blind_packet_id"]
        for row in rows
        if row["private_source_set"] == TARGET_SOURCE_SET
    }
    if target_packets != {
        row["blind_packet_id"] for row in queue["rows"]
    }:
        raise C8ConsensusError("21 个正式靶与私有待判队列不一致")
    audit_sampling_receipt = _validated_audit_sampling_receipt(
        audit_plan,
        [row for row in rows if isinstance(row, Mapping)],
    )
    return by_packet, audit_sampling_receipt


def _unblinded_documents(
    visible_tally: Mapping[str, Any],
    crosswalk_by_packet: Mapping[str, Mapping[str, Any]],
) -> tuple[dict[str, Any], dict[str, Any]]:
    unblinded_rows: list[dict[str, Any]] = []
    target_disagreements: list[dict[str, Any]] = []
    for row in visible_tally["rows"]:
        packet_id = str(row["packet_id"])
        source = crosswalk_by_packet[packet_id]
        first_real = _unblind_choices(
            row["first_selected_choice_ids"],
            source,
        )
        second_real = _unblind_choices(
            row["second_selected_choice_ids"],
            source,
        )
        result = {
            "packet_id": packet_id,
            "private_source_set": source["private_source_set"],
            "case_id": source["case_id"],
            "atom_id": source["atom_id"],
            "source_row_id": source["source_row_id"],
            "source_packet_id": source["source_packet_id"],
            "agreement": row["agreement"],
            "first_selected_event_ids": first_real,
            "second_selected_event_ids": second_real,
            "unanimous_selected_event_ids": (
                first_real if row["agreement"] else None
            ),
        }
        unblinded_rows.append(result)
        if (
            source["private_source_set"] == TARGET_SOURCE_SET
            and not row["agreement"]
        ):
            target_disagreements.append(
                {
                    **result,
                    "status": "PENDING_CZ_TARGET_DISAGREEMENT",
                    "mapping_source_if_resolved": "CZ_MANUAL",
                }
            )

    target_rows = [
        row
        for row in unblinded_rows
        if row["private_source_set"] == TARGET_SOURCE_SET
    ]
    audit_rows = [
        row
        for row in unblinded_rows
        if row["private_source_set"] == AUDIT_SOURCE_SET
    ]
    unblinded = {
        "schema_version": "v02-c8-unblinded-two-vote-tally-private.v1",
        "status": "UNBLIND_COMPLETE_AFTER_VISIBLE_TALLY",
        "visible_tally_sha256": sha256_bytes(canonical_bytes(visible_tally)),
        "access_order": [
            "PUBLIC_PREPARATION_BOUND",
            "FIRST_VOTE_VALIDATED",
            "SECOND_VOTE_VALIDATED",
            "VISIBLE_TALLY_FROZEN",
            "PRIVATE_CROSSWALK_OPENED",
            "UNBLIND_COMPLETE",
        ],
        "target_packet_total": len(target_rows),
        "target_agreement_total": sum(row["agreement"] for row in target_rows),
        "target_disagreement_total": sum(
            not row["agreement"] for row in target_rows
        ),
        "audit_packet_total": len(audit_rows),
        "audit_agreement_total": sum(row["agreement"] for row in audit_rows),
        "audit_disagreement_total": sum(
            not row["agreement"] for row in audit_rows
        ),
        "rows": unblinded_rows,
        "model_api_calls": 0,
        "network_requests": 0,
    }
    queue = {
        "schema_version": "v02-c8-target-disagreement-queue.v1",
        "status": (
            "PENDING_CZ"
            if target_disagreements
            else "EMPTY_ALL_TARGETS_AGREE"
        ),
        "row_total": len(target_disagreements),
        "rows": target_disagreements,
        "mapping_freeze_allowed": not target_disagreements,
        "final_control_mapping_generated": False,
        "model_api_calls": 0,
        "network_requests": 0,
    }
    return unblinded, queue


def _audit_consistency(
    unblinded: Mapping[str, Any],
    sampling_validation: Mapping[str, Any],
) -> dict[str, Any]:
    treatment_sha = _assert_sha(
        "final_treatment_mapping.json",
        TREATMENT_MAPPING,
        EXPECTED_TREATMENT_MAPPING_SHA256,
    )
    treatment = read_json(TREATMENT_MAPPING)
    old_by_row_id = {
        row.get("source_detail", {}).get("row_id"): row
        for row in treatment.get("rows", [])
        if isinstance(row, Mapping)
        and isinstance(row.get("source_detail"), Mapping)
        and isinstance(row.get("source_detail", {}).get("row_id"), str)
    }
    rows: list[dict[str, Any]] = []
    disagreement_total = 0
    match_total = 0
    comparable_total = 0
    for row in unblinded["rows"]:
        if row["private_source_set"] != AUDIT_SOURCE_SET:
            continue
        source_packet_id = row["source_packet_id"]
        old = old_by_row_id.get(source_packet_id)
        if old is None:
            raise C8ConsensusError(
                f"隐藏审计包找不到旧映射：{source_packet_id}"
            )
        if not row["agreement"]:
            disagreement_total += 1
            rows.append(
                {
                    "packet_id": row["packet_id"],
                    "source_packet_id": source_packet_id,
                    "status": "MISSING_VOTER_DISAGREEMENT",
                    "old_mapping_changed": False,
                }
            )
            continue
        comparable_total += 1
        current = list(row["unanimous_selected_event_ids"])
        old_events = list(old["candidate_event_ids"])
        matches = current == old_events
        match_total += matches
        rows.append(
            {
                "packet_id": row["packet_id"],
                "source_packet_id": source_packet_id,
                "status": "COMPARABLE",
                "old_selected_event_ids": old_events,
                "blind_review_selected_event_ids": current,
                "matches_old_working_mapping": matches,
                "old_mapping_changed": False,
            }
        )
    if len(rows) != 6:
        raise C8ConsensusError("隐藏审计不是 6 包")
    return {
        "schema_version": "v02-c8-hidden-audit-consistency.v1",
        "status": (
            "MISSING_VOTER_DISAGREEMENT"
            if disagreement_total
            else "AVAILABLE_C9_REVALIDATED"
        ),
        "audit_packet_total": 6,
        "audit_voter_disagreement_total": disagreement_total,
        "comparable_total": comparable_total,
        "matches_old_working_mapping_total": (
            None if disagreement_total else match_total
        ),
        "consistency_rate": (
            None if disagreement_total else match_total / 6
        ),
        "treatment_mapping_path": display_path(TREATMENT_MAPPING),
        "treatment_mapping_sha256": treatment_sha,
        "treatment_mapping_read_only": True,
        "treatment_mapping_write_total": 0,
        "audit_disagreement_blocks_control_freeze": False,
        "old_c8_six_of_six_treated_as_observation_only": True,
        "c9_sampling_revalidation_status": sampling_validation["status"],
        "c9_sampling_revalidation_sha256": canonical_sha(
            sampling_validation
        ),
        "rows": rows,
        "model_api_calls": 0,
        "network_requests": 0,
    }


def _cardinality_metrics(
    rows: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    by_case: dict[str, dict[str, Any]] = {}
    event_to_atoms: dict[tuple[str, str], list[str]] = defaultdict(list)
    split_histogram: Counter[int] = Counter()
    mapped_atom_total = 0
    link_total = 0
    for row in rows:
        case_id = str(row["case_id"])
        event_ids = [str(value) for value in row["candidate_event_ids"]]
        degree = len(event_ids)
        if degree:
            mapped_atom_total += 1
            link_total += degree
            split_histogram[degree] += 1
            for event_id in event_ids:
                event_to_atoms[(case_id, event_id)].append(str(row["atom_id"]))
    merge_histogram = Counter(
        len(atom_ids) for atom_ids in event_to_atoms.values()
    )
    for case_id in CASE_ORDER:
        case_rows = [row for row in rows if row["case_id"] == case_id]
        case_event_keys = sorted(
            key for key in event_to_atoms if key[0] == case_id
        )
        case_event_loads = [
            {
                "event_id": event_id,
                "atom_ids": sorted(event_to_atoms[(case_id, event_id)]),
                "atom_count": len(event_to_atoms[(case_id, event_id)]),
            }
            for _, event_id in case_event_keys
        ]
        case_mapped = sum(bool(row["candidate_event_ids"]) for row in case_rows)
        case_split = Counter(
            len(row["candidate_event_ids"])
            for row in case_rows
            if row["candidate_event_ids"]
        )
        case_merge = Counter(row["atom_count"] for row in case_event_loads)
        denominator = CASE_DENOMINATORS[case_id]
        by_case[case_id] = {
            "produced_parent_event_total": CONTROL_PARENT_EVENT_COUNTS[case_id],
            "scoring_atom_total": denominator,
            "mapped_atom_total": case_mapped,
            "unmapped_atom_total": denominator - case_mapped,
            "coverage_rate": case_mapped / denominator,
            "mapped_parent_event_total": len(case_event_keys),
            "atom_split_degree_histogram": {
                str(key): value for key, value in sorted(case_split.items())
            },
            "mapped_event_degree_histogram": {
                str(key): value for key, value in sorted(case_merge.items())
            },
            "maximum_events_per_atom": max(case_split, default=0),
            "maximum_atoms_per_mapped_event": max(case_merge, default=0),
            "event_loads": case_event_loads,
        }
    return {
        "schema_version": "v02-c8-control-cardinality-metrics.v1",
        "arm": "control",
        "produced_parent_event_total": sum(CONTROL_PARENT_EVENT_COUNTS.values()),
        "produced_parent_event_total_by_case": CONTROL_PARENT_EVENT_COUNTS,
        "scoring_atom_total": 49,
        "mapped_atom_total": mapped_atom_total,
        "unmapped_atom_total": 49 - mapped_atom_total,
        "coverage_rate": mapped_atom_total / 49,
        "atom_to_event_link_total": link_total,
        "mapped_parent_event_total": len(event_to_atoms),
        "atom_split_degree_histogram": {
            str(key): value for key, value in sorted(split_histogram.items())
        },
        "one_event_atom_count": split_histogram[1],
        "multi_event_atom_count": sum(
            value for key, value in split_histogram.items() if key > 1
        ),
        "maximum_events_per_atom": max(split_histogram, default=0),
        "mapped_event_degree_histogram": {
            str(key): value for key, value in sorted(merge_histogram.items())
        },
        "one_to_one_mapped_event_count": merge_histogram[1],
        "many_to_one_mapped_event_count": sum(
            value for key, value in merge_histogram.items() if key > 1
        ),
        "maximum_atoms_per_mapped_event": max(merge_histogram, default=0),
        "by_case_breakdown": by_case,
        "event_loads": [
            {
                "case_id": case_id,
                "event_id": event_id,
                "atom_ids": sorted(atom_ids),
                "atom_count": len(atom_ids),
            }
            for (case_id, event_id), atom_ids in sorted(event_to_atoms.items())
        ],
    }


def _control_mapping_artifacts(
    private: Mapping[str, Mapping[str, Any]],
    unblinded: Mapping[str, Any],
) -> dict[str, bytes]:
    target_rows = [
        row
        for row in unblinded["rows"]
        if row["private_source_set"] == TARGET_SOURCE_SET
    ]
    if any(not row["agreement"] for row in target_rows):
        return {}
    prefreeze_rows = private["prefreeze"]["rows"]
    resolution_by_row: dict[str, dict[str, Any]] = {}
    for row in prefreeze_rows:
        resolution_by_row[str(row["row_id"])] = {
            "case_id": row["case_id"],
            "atom_id": row["atom_id"],
            "selected_event_ids": list(row["selected_event_ids"]),
            "mapping_source": row["mapping_source"],
            "source_detail": {
                "row_id": row["row_id"],
                "working_mapping_not_gold": True,
            },
        }
    for row in target_rows:
        row_id = str(row["source_row_id"])
        if row_id in resolution_by_row:
            raise C8ConsensusError(f"两票判词重复接管：{row_id}")
        resolution_by_row[row_id] = {
            "case_id": row["case_id"],
            "atom_id": row["atom_id"],
            "selected_event_ids": list(row["unanimous_selected_event_ids"]),
            "mapping_source": "AI_CONSENSUS",
            "source_detail": {
                "row_id": row_id,
                "blind_packet_id": row["packet_id"],
                "independent_vote_total": 2,
                "verdict_identity": "working_verdict_not_gold",
            },
        }
    if len(resolution_by_row) != 49:
        raise C8ConsensusError("控制臂 28+21 没有覆盖 49 原子")

    ledger_rows = private["ledger"]["rows"]
    mapping_rows: list[dict[str, Any]] = []
    source_counts: Counter[str] = Counter()
    for ordinal, ledger_row in enumerate(ledger_rows, 1):
        row_id = str(ledger_row["row_id"])
        resolution = resolution_by_row.get(row_id)
        if (
            resolution is None
            or resolution["case_id"] != ledger_row["case_id"]
            or resolution["atom_id"] != ledger_row["atom_id"]
        ):
            raise C8ConsensusError(f"控制臂正式顺序或原子身份漂移：{row_id}")
        event_ids = list(resolution["selected_event_ids"])
        source = str(resolution["mapping_source"])
        source_counts[source] += 1
        mapping_rows.append(
            {
                "ordinal": ordinal,
                "case_id": resolution["case_id"],
                "atom_id": resolution["atom_id"],
                "mapping_outcome": (
                    "MAPPED" if event_ids else NO_CORRESPONDENCE
                ),
                "selected_choice_ids": (
                    [f"MAP_TO::{event_id}" for event_id in event_ids]
                    if event_ids
                    else [NO_CORRESPONDENCE]
                ),
                "candidate_event_ids": event_ids,
                "split_degree": len(event_ids),
                "mapping_source": source,
                "source_detail": resolution["source_detail"],
                "verdict_identity": "working_mapping_not_gold",
            }
        )
    if source_counts["AI_CONSENSUS"] != 21 or sum(source_counts.values()) != 49:
        raise C8ConsensusError("控制臂 28 条机械路由＋21 条合议计数漂移")
    metrics = _cardinality_metrics(mapping_rows)
    mapping = {
        "schema_version": "v02-c8-final-control-mapping.v1",
        "status": "FROZEN_V02_WORKING_TRUTH",
        "arm": "control",
        "mapping_identity": "working_mapping_not_gold",
        "formal_gold_changed": False,
        "formal_gold_text_emitted": False,
        "case_order": list(CASE_ORDER),
        "scoring_atom_total": 49,
        "row_total": 49,
        "source_counts": dict(sorted(source_counts.items())),
        "rows": mapping_rows,
        "mapping_freeze_allowed": True,
        "c5_rescore_allowed": True,
        "model_api_calls": 0,
        "network_requests": 0,
    }
    artifacts = {
        "control_cardinality_metrics.json": canonical_bytes(metrics),
        "final_control_mapping.json": canonical_bytes(mapping),
        "mapping_freeze_receipt.json": canonical_bytes(
            {
                "schema_version": "v02-c8-control-mapping-freeze-receipt.v1",
                "status": "PASS_MAPPING_FROZEN",
                "mapping_row_total": 49,
                "target_agreement_total": 21,
                "target_disagreement_total": 0,
                "audit_disagreement_blocks_control_freeze": False,
                "mapping_freeze_allowed": True,
                "c5_rescore_allowed": True,
                "formal_gold_or_pointer_changed": False,
                "model_api_calls": 0,
                "network_requests": 0,
            }
        ),
    }
    preimage = {
        relative: sha256_bytes(raw)
        for relative, raw in sorted(artifacts.items())
    }
    artifacts["artifact_manifest.json"] = canonical_bytes(
        {
            "schema_version": "v02-c8-control-mapping-manifest.v1",
            "file_total_excluding_self": len(preimage),
            "files": [
                {"path": relative, "sha256": digest}
                for relative, digest in sorted(preimage.items())
            ],
            "artifact_set_sha256": sha256_bytes(canonical_bytes(preimage)),
            "mapping_freeze_allowed": True,
            "c5_rescore_allowed": True,
            "model_api_calls": 0,
            "network_requests": 0,
        }
    )
    return artifacts


def _build_private_unblind_phase(
    public_context: Mapping[str, Any],
    verified_public: _VerifiedPublicPreunblindContext,
) -> tuple[dict[str, bytes], dict[str, bytes]]:
    """在三份公开工件已实际落盘回读后，才允许调用本函数。"""

    preparation_manifest = public_context["preparation_manifest"]
    manifest_index = public_context["manifest_index"]
    packet_ids = public_context["packet_ids"]
    first = public_context["first"]
    second = public_context["second"]
    visible_tally = public_context["visible_tally"]
    public_artifacts = public_context["public_artifacts"]

    if (
        not isinstance(
            verified_public,
            _VerifiedPublicPreunblindContext,
        )
        or verified_public._capability is not _PUBLIC_PREUNBLIND_CAPABILITY
    ):
        raise C8ConsensusError("私有解盲缺公开三件落盘回读通行凭据")
    expected_public_shas = {
        relative: sha256_bytes(raw)
        for relative, raw in sorted(public_artifacts.items())
    }
    expected_public_set_sha = canonical_sha(expected_public_shas)
    if (
        verified_public.public_artifact_set_sha256
        != expected_public_set_sha
        or verified_public.public_file_shas != expected_public_shas
    ):
        raise C8ConsensusError("公开落盘回读通行凭据与当前公开工件不绑定")
    for relative, raw in sorted(public_artifacts.items()):
        path = verified_public.output_dir / relative
        if not path.is_file() or path.read_bytes() != raw:
            raise C8ConsensusError(
                f"公开工件在解盲前再次漂移：{relative}"
            )

    private = _private_documents(manifest_index)
    crosswalk_by_packet, audit_sampling_validation = (
        _validate_private_identity(private, packet_ids)
    )
    unblinded, disagreement_queue = _unblinded_documents(
        visible_tally,
        crosswalk_by_packet,
    )
    audit = _audit_consistency(unblinded, audit_sampling_validation)
    control_artifacts = _control_mapping_artifacts(private, unblinded)
    target_disagreement_total = disagreement_queue["row_total"]
    mapping_freeze_allowed = target_disagreement_total == 0
    if bool(control_artifacts) != mapping_freeze_allowed:
        raise C8ConsensusError("正式靶分歧状态与控制臂冻结产物不一致")

    block_or_pass = {
        "schema_version": "v02-c8-control-freeze-gate-receipt.v1",
        "status": (
            "PASS_CONTROL_MAPPING_GENERATED"
            if mapping_freeze_allowed
            else "BLOCKED_TARGET_DISAGREEMENT"
        ),
        "target_packet_total": 21,
        "target_agreement_total": unblinded["target_agreement_total"],
        "target_disagreement_total": target_disagreement_total,
        "audit_packet_total": 6,
        "audit_agreement_total": unblinded["audit_agreement_total"],
        "audit_disagreement_total": unblinded["audit_disagreement_total"],
        "audit_disagreement_blocks_control_freeze": False,
        "mapping_freeze_allowed": mapping_freeze_allowed,
        "final_control_mapping_generated": bool(control_artifacts),
        "c5_rescore_allowed": mapping_freeze_allowed,
        "formal_gold_or_pointer_changed": False,
        "model_api_calls": 0,
        "network_requests": 0,
    }
    source_receipt = {
        "schema_version": "v02-c8-consensus-source-receipt.v1",
        "status": "PASS_INPUTS_BOUND",
        "preparation_manifest_path": display_path(PREPARATION_MANIFEST),
        "preparation_manifest_sha256": sha256_file(PREPARATION_MANIFEST),
        "preparation_manifest_schema_version": preparation_manifest[
            "schema_version"
        ],
        "packet_manifest_path": display_path(PACKET_MANIFEST),
        "packet_manifest_sha256": sha256_file(PACKET_MANIFEST),
        "first_vote_path": display_path(FIRST_VOTE),
        "first_vote_sha256": first["vote_sha256"],
        "second_vote_path": display_path(SECOND_VOTE),
        "second_vote_sha256": second["vote_sha256"],
        "second_vote_preunblind_seal_sha256": sha256_bytes(
            public_artifacts["second_vote_preunblind_seal.json"]
        ),
        "visible_tally_preunblind_seal_sha256": sha256_bytes(
            public_artifacts["visible_tally_preunblind_seal.json"]
        ),
        "public_artifact_set_sha256": expected_public_set_sha,
        "public_seal_output_dir": display_path(verified_public.output_dir),
        "private_unblind_capability_verified": True,
        "first_vote_content_read_by_second_voter": False,
        "voter_ids_distinct": first["voter_id"] != second["voter_id"],
        "model_families_distinct": (
            first["model_family"] != second["model_family"]
        ),
        "private_crosswalk_opened_only_after_public_files_persisted": True,
        "model_api_calls": 0,
        "network_requests": 0,
    }
    consensus_artifacts = {
        **public_artifacts,
        "audit_bias_receipt.json": canonical_bytes(audit),
        "audit_sampling_validation_private.json": canonical_bytes(
            audit_sampling_validation
        ),
        "control_mapping_gate_receipt.json": canonical_bytes(block_or_pass),
        "source_receipt.json": canonical_bytes(source_receipt),
        "target_disagreement_queue_private.json": canonical_bytes(
            disagreement_queue
        ),
        "unblinded_tally_private.json": canonical_bytes(unblinded),
    }
    preimage = {
        relative: sha256_bytes(raw)
        for relative, raw in sorted(consensus_artifacts.items())
    }
    consensus_artifacts["artifact_manifest.json"] = canonical_bytes(
        {
            "schema_version": "v02-c9-consensus-artifact-manifest.v1",
            "file_total_excluding_self": len(preimage),
            "files": [
                {"path": relative, "sha256": digest}
                for relative, digest in sorted(preimage.items())
            ],
            "artifact_set_sha256": sha256_bytes(canonical_bytes(preimage)),
            "mapping_freeze_allowed": mapping_freeze_allowed,
            "final_control_mapping_generated": bool(control_artifacts),
            "model_api_calls": 0,
            "network_requests": 0,
        }
    )
    return consensus_artifacts, control_artifacts


def build_artifact_sets(
    consensus_dir: Path = DEFAULT_CONSENSUS_DIR,
) -> tuple[dict[str, bytes], dict[str, bytes]]:
    """只读重建；缺少已落盘公开三件时拒绝进入私有解盲。"""

    public_artifacts, public_context = _build_public_preunblind_phase()
    verified_public = _verify_public_preunblind_files(
        consensus_dir,
        public_artifacts,
    )
    return _build_private_unblind_phase(
        public_context,
        verified_public,
    )


def build_artifacts() -> dict[str, bytes]:
    """兼容测试与只读调用：返回共识目录工件。"""

    consensus_artifacts, _control_artifacts = build_artifact_sets()
    return consensus_artifacts


def _write_artifacts(output_dir: Path, artifacts: Mapping[str, bytes]) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    for relative, raw in sorted(artifacts.items()):
        path = output_dir / relative
        if path.is_file():
            if path.read_bytes() != raw:
                raise C8ConsensusError(f"已有工件漂移：{display_path(path)}")
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(raw)


def write_or_verify(
    consensus_dir: Path = DEFAULT_CONSENSUS_DIR,
    control_mapping_dir: Path = DEFAULT_CONTROL_MAPPING_DIR,
) -> dict[str, Any]:
    first_public, first_context = _build_public_preunblind_phase()
    second_public, second_context = _build_public_preunblind_phase()
    if first_public != second_public:
        raise C8ConsensusError("C9 解盲前公开工件连续两次构造不一致")

    # 三份公开件必须真的先落盘并回读，不能只在内存里说“已经冻结”。
    _write_artifacts(consensus_dir, first_public)
    verified_public = _verify_public_preunblind_files(
        consensus_dir,
        first_public,
    )

    first_consensus, first_control = _build_private_unblind_phase(
        first_context,
        verified_public,
    )
    second_consensus, second_control = _build_private_unblind_phase(
        second_context,
        verified_public,
    )
    if first_consensus != second_consensus or first_control != second_control:
        raise C8ConsensusError("C9 计票、解盲连续两次构造不一致")
    if first_control:
        raise C8ConsensusError("C9 工程闸重跑不得冻结最终映射")
    _write_artifacts(consensus_dir, first_consensus)
    expected_consensus = set(first_consensus)
    actual_consensus = {
        path.relative_to(consensus_dir).as_posix()
        for path in consensus_dir.rglob("*")
        if path.is_file()
    }
    if actual_consensus != expected_consensus:
        raise C8ConsensusError("C9 共识目录存在未登记文件")

    actual_control = (
        [
            path
            for path in control_mapping_dir.rglob("*")
            if path.is_file()
        ]
        if control_mapping_dir.exists()
        else []
    )
    if actual_control:
        raise C8ConsensusError("C9 工程闸重跑目录不得存在任何控制映射工件")

    gate = read_json(consensus_dir / "control_mapping_gate_receipt.json")
    audit = read_json(consensus_dir / "audit_bias_receipt.json")
    return {
        "status": gate["status"],
        "consensus_dir": display_path(consensus_dir),
        "consensus_manifest_sha256": sha256_file(
            consensus_dir / "artifact_manifest.json"
        ),
        "target_agreement_total": gate["target_agreement_total"],
        "target_disagreement_total": gate["target_disagreement_total"],
        "audit_agreement_total": gate["audit_agreement_total"],
        "audit_consistency_status": audit["status"],
        "audit_consistency_rate": audit["consistency_rate"],
        "second_vote_preunblind_seal_sha256": verified_public.public_file_shas[
            "second_vote_preunblind_seal.json"
        ],
        "visible_tally_preunblind_seal_sha256": verified_public.public_file_shas[
            "visible_tally_preunblind_seal.json"
        ],
        "mapping_freeze_executed": False,
        "final_control_mapping_generated": False,
        "mechanical_double_run_identical": True,
        "model_api_calls": 0,
        "network_requests": 0,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--consensus-dir",
        type=Path,
        default=DEFAULT_CONSENSUS_DIR,
    )
    parser.add_argument(
        "--control-mapping-dir",
        type=Path,
        default=DEFAULT_CONTROL_MAPPING_DIR,
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    print(
        json.dumps(
            write_or_verify(
                args.consensus_dir.resolve(),
                args.control_mapping_dir.resolve(),
            ),
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""V02/C7.7：机械验票、封签与全票一致合并。

本工具不读取正式金标，不调用模型。只有至少两份独立合格票齐套时，
才计算全票一致工作判词；任何分歧都保持映射冻结闸关闭。
"""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[1]
WORKSPACE = (
    ROOT
    / "experiments/extraction_redesign_v02_overnight_20260725"
    / "V02_C7_6_7_ai_consensus_workspace"
)
PACKET_MANIFEST = WORKSPACE / "c7_7_packet_manifest.json"
FORBIDDEN_VOTER_FRAGMENTS = (
    "deepseek-v4-flash",
    "v4 flash",
    "ling-3.0-flash",
)
NO_CORRESPONDENCE = "NO_CORRESPONDENCE"
NOTION_LEDGER_AUTHORITY = "notion_ledger_2026-07-25_14:50"
NOTION_LEDGER_PAGE_URL = (
    "https://app.notion.com/p/4a46597cd80242f385f15209ebe9170c"
)
NOTION_VOTE_PAGE_URL = (
    "https://app.notion.com/p/3a85cadc4d0f81769d91dfd38509624d"
)
REQUIRED_ISOLATION_EVIDENCE = (
    "commit_reveal_first_ballot_sealed",
    "notion_version_history_authorship",
    "seal_before_vote_timestamp_order",
)


class C7TallyError(RuntimeError):
    """C7.7 票据不满足独立合议合同。"""


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
        raise C7TallyError(f"文件不存在：{path}")
    return sha256_bytes(path.read_bytes())


def display_path(path: Path) -> str:
    resolved = path.resolve()
    try:
        return resolved.relative_to(ROOT).as_posix()
    except ValueError:
        return resolved.as_posix()


def _packet_contract() -> tuple[list[str], dict[str, list[str]], str]:
    manifest = read_json(PACKET_MANIFEST)
    rows = manifest.get("packets")
    if (
        manifest.get("packet_total") != 26
        or not isinstance(rows, list)
        or len(rows) != 26
    ):
        raise C7TallyError("C7.7 26 包清单漂移")
    packet_ids: list[str] = []
    allowed_by_packet: dict[str, list[str]] = {}
    for row in rows:
        packet_id = row.get("packet_id")
        choice_ids = row.get("choice_ids")
        if (
            not isinstance(packet_id, str)
            or packet_id in allowed_by_packet
            or not isinstance(choice_ids, list)
            or not choice_ids
            or choice_ids[-1] != NO_CORRESPONDENCE
            or any(not isinstance(value, str) for value in choice_ids)
        ):
            raise C7TallyError("C7.7 包 ID 或选项合同漂移")
        packet_ids.append(packet_id)
        allowed_by_packet[packet_id] = choice_ids
    return packet_ids, allowed_by_packet, sha256_file(PACKET_MANIFEST)


def _canonical_choice_order(
    selected: Sequence[str],
    allowed: Sequence[str],
) -> list[str]:
    selected_set = set(selected)
    return [choice_id for choice_id in allowed if choice_id in selected_set]


def _parse_datetime(value: Any, field: str) -> datetime:
    if not isinstance(value, str):
        raise C7TallyError(f"独立凭据 {field} 不是时间字符串")
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise C7TallyError(f"独立凭据 {field} 不是 ISO 时间") from exc
    if parsed.tzinfo is None:
        raise C7TallyError(f"独立凭据 {field} 缺少时区")
    return parsed


def _validate_independence_receipt(
    receipt: Any,
    *,
    manifest_sha: str,
    model_family: str,
) -> dict[str, Any]:
    required_fields = {
        "schema_version",
        "authority",
        "authority_page_url",
        "source_vote_page_url",
        "identity_self_declared",
        "first_ballot_canonical_sha256",
        "packet_manifest_sha256",
        "first_ballot_sealed_at",
        "second_ballot_submitted_at",
        "isolation_evidence",
        "child_page_total",
        "child_votes_match_parent_total",
        "notion_version_history_directly_verified_by_connector",
        "evidence_boundary",
    }
    if not isinstance(receipt, Mapping) or set(receipt) != required_fields:
        raise C7TallyError("第二票独立凭据字段不完整或夹带未知字段")
    if (
        receipt["schema_version"]
        != "v02-c7-7-independence-receipt.v1"
        or receipt["authority"] != NOTION_LEDGER_AUTHORITY
        or receipt["authority_page_url"] != NOTION_LEDGER_PAGE_URL
        or receipt["source_vote_page_url"] != NOTION_VOTE_PAGE_URL
        or receipt["identity_self_declared"] is not True
        or receipt["packet_manifest_sha256"] != manifest_sha
        or receipt["child_page_total"] != 26
        or receipt["child_votes_match_parent_total"] is not True
        or receipt[
            "notion_version_history_directly_verified_by_connector"
        ]
        is not False
        or receipt["evidence_boundary"]
        != (
            "accepted_by_notion_ledger;"
            "version_history_not_exposed_to_connector"
        )
        or tuple(receipt["isolation_evidence"])
        != REQUIRED_ISOLATION_EVIDENCE
        or model_family != "notion_platform_assistant"
    ):
        raise C7TallyError("第二票独立凭据不符合 14:50 账序裁定")
    first_sha = receipt["first_ballot_canonical_sha256"]
    if (
        not isinstance(first_sha, str)
        or len(first_sha) != 64
        or any(character not in "0123456789abcdef" for character in first_sha)
    ):
        raise C7TallyError("第二票未绑定合法的第一票 SHA")
    sealed_at = _parse_datetime(
        receipt["first_ballot_sealed_at"],
        "first_ballot_sealed_at",
    )
    submitted_at = _parse_datetime(
        receipt["second_ballot_submitted_at"],
        "second_ballot_submitted_at",
    )
    if submitted_at <= sealed_at:
        raise C7TallyError("第二票时间不晚于第一票封签时间")
    canonical_receipt = dict(receipt)
    return {
        "status": "PASS",
        "authority": receipt["authority"],
        "identity_self_declared": True,
        "first_ballot_canonical_sha256": first_sha,
        "packet_manifest_sha256": manifest_sha,
        "source_vote_page_url": receipt["source_vote_page_url"],
        "isolation_evidence": list(REQUIRED_ISOLATION_EVIDENCE),
        "first_ballot_sealed_at": sealed_at.isoformat(),
        "second_ballot_submitted_at": submitted_at.isoformat(),
        "evidence_boundary": receipt["evidence_boundary"],
        "receipt_sha256": sha256_bytes(canonical_bytes(canonical_receipt)),
    }


def validate_vote(path: Path) -> dict[str, Any]:
    packet_ids, allowed_by_packet, manifest_sha = _packet_contract()
    document = read_json(path)
    allowed_document_fields = {
        "voter_id",
        "model_family",
        "votes",
        "independence_receipt",
    }
    if (
        not {"voter_id", "model_family", "votes"}.issubset(document)
        or not set(document).issubset(allowed_document_fields)
    ):
        raise C7TallyError(f"{path.name} 顶层字段不是最小票据合同")
    voter_id = document.get("voter_id")
    model_family = document.get("model_family")
    votes = document.get("votes")
    if (
        not isinstance(voter_id, str)
        or not voter_id
        or not isinstance(model_family, str)
        or not model_family
        or not isinstance(votes, list)
        or len(votes) != 26
    ):
        raise C7TallyError(f"{path.name} 票据身份或票数非法")
    family_normalized = model_family.casefold()
    if any(
        fragment in family_normalized
        for fragment in FORBIDDEN_VOTER_FRAGMENTS
    ):
        raise C7TallyError(f"{path.name} 使用禁用投票模型：{model_family}")
    independence_receipt = None
    if "independence_receipt" in document:
        independence_receipt = _validate_independence_receipt(
            document["independence_receipt"],
            manifest_sha=manifest_sha,
            model_family=model_family,
        )

    canonical_votes: list[dict[str, Any]] = []
    seen: set[str] = set()
    for expected_packet_id, row in zip(packet_ids, votes, strict=True):
        if (
            not isinstance(row, Mapping)
            or set(row) != {"packet_id", "selected_choice_ids"}
        ):
            raise C7TallyError(f"{path.name} 票行夹带解释或未知字段")
        packet_id = row.get("packet_id")
        selected = row.get("selected_choice_ids")
        if packet_id != expected_packet_id or packet_id in seen:
            raise C7TallyError(f"{path.name} 包顺序、身份或唯一性漂移")
        seen.add(str(packet_id))
        allowed = allowed_by_packet[str(packet_id)]
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
        ):
            raise C7TallyError(f"{path.name}/{packet_id} 选择非法")
        canonical_votes.append(
            {
                "packet_id": packet_id,
                "selected_choice_ids": _canonical_choice_order(
                    selected,
                    allowed,
                ),
            }
        )

    canonical_document = {
        "voter_id": voter_id,
        "model_family": model_family,
        "votes": canonical_votes,
    }
    canonical_raw = canonical_bytes(canonical_document)
    return {
        "status": "PASS",
        "path": display_path(path),
        "source_file_sha256": sha256_file(path),
        "canonical_vote_sha256": sha256_bytes(canonical_raw),
        "packet_manifest_sha256": manifest_sha,
        "voter_id": voter_id,
        "model_family": model_family,
        "identity_self_declared": (
            independence_receipt is not None
            and independence_receipt["identity_self_declared"] is True
        ),
        "independence_receipt": independence_receipt,
        "vote_total": len(canonical_votes),
        "votes": canonical_votes,
    }


def tally_votes(vote_paths: Sequence[Path]) -> dict[str, Any]:
    receipts = [validate_vote(path) for path in vote_paths]
    voter_ids = [row["voter_id"] for row in receipts]
    model_families = [row["model_family"] for row in receipts]
    if len(voter_ids) != len(set(voter_ids)):
        raise C7TallyError("投票窗口身份重复，不构成独立票")
    if len(model_families) != len(set(model_families)):
        raise C7TallyError("投票模型家族重复，不构成独立票")
    if len(receipts) >= 2:
        sealed_first_ballots = [
            row for row in receipts if row["independence_receipt"] is None
        ]
        evidenced_later_ballots = [
            row for row in receipts if row["independence_receipt"] is not None
        ]
        if (
            len(sealed_first_ballots) != 1
            or len(evidenced_later_ballots) != len(receipts) - 1
        ):
            raise C7TallyError(
                "第二票不得只靠自报模型族，须带 14:50 独立凭据"
            )
        sealed_first_sha = sealed_first_ballots[0][
            "canonical_vote_sha256"
        ]
        for later_ballot in evidenced_later_ballots:
            if (
                later_ballot["independence_receipt"][
                    "first_ballot_canonical_sha256"
                ]
                != sealed_first_sha
            ):
                raise C7TallyError("第二票独立凭据未绑定本次第一票封签")

    packet_ids, _, manifest_sha = _packet_contract()
    unanimous: list[dict[str, Any]] = []
    disagreements: list[dict[str, Any]] = []
    if len(receipts) >= 2:
        for index, packet_id in enumerate(packet_ids):
            by_voter = {
                receipt["voter_id"]: receipt["votes"][index][
                    "selected_choice_ids"
                ]
                for receipt in receipts
            }
            unique = {
                tuple(selected) for selected in by_voter.values()
            }
            row = {
                "packet_id": packet_id,
                "votes_by_voter": by_voter,
            }
            if len(unique) == 1:
                row["selected_choice_ids"] = list(next(iter(unique)))
                row["verdict_identity"] = "working_verdict_not_gold"
                unanimous.append(row)
            else:
                disagreements.append(row)

    return {
        "schema_version": "v02-c7-7-ai-consensus-tally.v1",
        "status": (
            "WAITING_FOR_SECOND_INDEPENDENT_VOTE"
            if len(receipts) < 2
            else (
                "UNANIMOUS_COMPLETE"
                if not disagreements
                else "DISAGREEMENTS_REQUIRE_CZ"
            )
        ),
        "packet_manifest_sha256": manifest_sha,
        "independent_vote_total": len(receipts),
        "voter_ids": voter_ids,
        "model_families": model_families,
        "vote_receipts": [
            {
                key: value
                for key, value in receipt.items()
                if key != "votes"
            }
            for receipt in receipts
        ],
        "unanimous_working_verdict_total": len(unanimous),
        "disagreement_total": len(disagreements),
        "unanimous_working_verdicts": unanimous,
        "disagreements": disagreements,
        "mapping_freeze_allowed": (
            len(receipts) >= 2 and not disagreements
        ),
        "c5_rescore_allowed": False,
        "model_api_calls_by_this_tool": 0,
        "network_requests_by_this_tool": 0,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="机械验收并合并 C7.7 独立 AI 选项票"
    )
    parser.add_argument(
        "--vote",
        action="append",
        type=Path,
        required=True,
        help="可重复传入；至少两票齐套才计算全票一致",
    )
    parser.add_argument("--output", type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    result = tally_votes(args.vote)
    raw = canonical_bytes(result)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_bytes(raw)
    print(raw.decode("utf-8"), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""把已有的北塔夹具候选投影成门 1 页面；不抽取、不建库、不写回库。"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import uuid
from pathlib import Path
from typing import Any

MODULE_ROOT = Path(__file__).resolve().parent
REPOSITORY_ROOT = MODULE_ROOT.parents[1]
for candidate in (
    REPOSITORY_ROOT,
    REPOSITORY_ROOT / "work" / "ccz142_candidate_authority_r01",
    REPOSITORY_ROOT / "work" / "ccz142_current_candidate_read_proof_r01",
    REPOSITORY_ROOT / "work" / "ccz57_m3_b01_candidate_version_r03_5",
    REPOSITORY_ROOT / "work" / "ccz57_m3_b06_commit_core_r01",
    MODULE_ROOT,
):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

from marks_sidecar import (  # noqa: E402
    SIDECAR_NAME,
    MarksError,
    create_if_missing,
    empty_document,
    encode_document,
    read_marks,
)

DOCUMENT_IDENTITY = "DOOR1-AUTHOR-INTAKE-VIEW-R01"
GITHUB_ISSUE = 309
BASE_MAIN_SHA = "908fbbfef6fa3a6b1d92e9a3fc35b1c35570ef66"
PROJECT_SCOPE_ID = "fixture-project-001"
DATABASE_FILENAME = "b06-commit-core.sqlite3"
FIXTURE_TEXT_SHA256 = "9209f22416dfff31d931f9f8f02ce12f4b99ff735754afbb1a4abcaa4899910b"
FIXTURE_FILE_SHA256 = "e217cbdba708352584c26ef1404e99e24075da88d07b32624fecc7c436c3ffa4"
FIXTURE_PATH = "work/ccz142_human_card_vertical_wire_r01/synthetic_chapter.txt"
LEDGER_NAMES = (
    "章节账",
    "事实账",
    "人物账",
    "地点账",
    "物品账",
    "势力账",
    "体系账",
    "世界规则账",
    "长线账",
    "规划账",
)
LEDGER_NOTES = (
    "这章的身份与版本",
    "本次事实候选，保留原状态",
    "人物与随时间变化的状态",
    "地点身份与出现记录",
    "物品、持有关系与变化",
    "组织、阵营与关系",
    "等级、技能与克制",
    "世界里的硬规则",
    "还要发展的线与意向",
    "下一章已经选定的安排",
)
GAP_LABELS = {
    "GAP_NOT_RELEASED": "这刀只读北塔夹具第 1 章。",
    "GAP_FIXTURE_MISSING": "没有找到包内放行的夹具。",
    "GAP_FIXTURE_MISMATCH": "夹具指纹或责任段对不上，停止读取。",
    "GAP_DEPENDENCY_MISSING": "仓库切片少了兄弟包，不能读真实候选库。",
    "GAP_STORE_MISSING": "没有现成的候选库；页面生成器不会替你建库。",
    "GAP_SCOPE_MISMATCH": "读到的候选不是这份北塔夹具。",
    "GAP_POINTER_MISSING": "库里没有当前候选指针。",
    "GAP_POINTER_AMBIGUOUS": "库里有多个当前指针，本刀不替你猜。",
    "GAP_CANDIDATE_MISSING": "当前候选不存在或引用对不上。",
    "GAP_NO_HUMAN_ITEMS": "当前候选没有可展示条目。",
    "GAP_CANDIDATE_SHAPE": "候选字段形状不符，没有把坏数据装成正常结果。",
    "GAP_CURRENT_CHANGED": "生成前后候选变了，请重跑。",
    "GAP_OUTPUT_PATH": "输出只能是独立的 HTML，不能盖住仓库文件或候选库。",
    "GAP_OUTPUT_WRITE": "页面没有写成功；没有写回候选库。",
    "GAP_STORE_READ": "候选读取失败；没有另造数据补位。",
}
LOCATION_RE = re.compile(r"责任段 (\d+)，字节 (\d+)–(\d+)\Z")
SENTENCE_RE = re.compile(r".+?(?:[。！？!?]+[”’\"」』）)]*|\n+|$)", re.S)


class ViewGap(ValueError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def digest(value: Any) -> str:
    return hashlib.sha256(canonical(value).encode("utf-8")).hexdigest()


def load_fixture(book: str, chapter: int) -> dict[str, Any]:
    """先核书名和章号，再碰文件；不提供任意正文路径参数。"""
    if (
        book not in {"北塔夹具", "fixture-north-tower"}
        or type(chapter) is not int
        or chapter != 1
    ):
        raise ViewGap("GAP_NOT_RELEASED")
    allow_path = (
        REPOSITORY_ROOT / "work/ccz142_named_chapter_txt_card_r01/ALLOWLIST.json"
    )
    target = REPOSITORY_ROOT / FIXTURE_PATH
    try:
        release = json.loads(allow_path.read_text(encoding="utf-8"))
        entries = [
            entry
            for entry in release["entries"]
            if entry.get("book_id") == "fixture-north-tower"
        ]
        if len(entries) != 1:
            raise ViewGap("GAP_FIXTURE_MISMATCH")
        entry = entries[0]
        if (
            entry.get("book_title") != "北塔夹具"
            or entry.get("chapter_no") != 1
            or entry.get("rights") != "FIXTURE_RELEASED"
            or entry.get("source_txt_repo_path") != FIXTURE_PATH
            or entry.get("chapter_text_sha256") != FIXTURE_TEXT_SHA256
            or entry.get("source_file_sha256") != FIXTURE_FILE_SHA256
            or target.is_symlink()
            or target.resolve() != target.absolute()
        ):
            raise ViewGap("GAP_FIXTURE_MISMATCH")
        raw = target.read_bytes()
        if hashlib.sha256(raw).hexdigest() != FIXTURE_FILE_SHA256:
            raise ViewGap("GAP_FIXTURE_MISMATCH")
        text = raw.decode("utf-8").strip()
        if hashlib.sha256(text.encode("utf-8")).hexdigest() != FIXTURE_TEXT_SHA256:
            raise ViewGap("GAP_FIXTURE_MISMATCH")
    except (OSError, UnicodeError, KeyError, TypeError, json.JSONDecodeError) as exc:
        raise ViewGap("GAP_FIXTURE_MISSING") from exc
    try:
        from work.ccz57_m3_b01_candidate_version_r03_5.fixtures import (
            chapter_revision_ref,
            segment_inputs,
        )
    except (ModuleNotFoundError, ImportError) as exc:
        raise ViewGap("GAP_DEPENDENCY_MISSING") from exc
    segments = segment_inputs()
    if "".join(s["responsibility_text"] for s in segments) != text:
        raise ViewGap("GAP_FIXTURE_MISMATCH")
    text_bytes = text.encode("utf-8")
    for segment in segments:
        if text_bytes[segment["start_byte"] : segment["end_byte"]] != segment[
            "responsibility_text"
        ].encode("utf-8"):
            raise ViewGap("GAP_FIXTURE_MISMATCH")
    return {
        "book_id": "fixture-north-tower",
        "book_title": "北塔夹具",
        "chapter_no": 1,
        "text": text,
        "text_sha256": FIXTURE_TEXT_SHA256,
        "segments": segments,
        "revision": chapter_revision_ref(),
    }


def split_sentences(text: str) -> list[dict[str, Any]]:
    """按句末标点／换行切；保留字符与顺序，用 UTF-8 字节作坐标。"""
    pieces: list[dict[str, Any]] = []
    for match in SENTENCE_RE.finditer(text):
        part = match.group()
        start = len(text[: match.start()].encode("utf-8"))
        end = len(text[: match.end()].encode("utf-8"))
        pieces.append(
            {
                "id": "s_" + digest([text, start, end])[:20],
                "number": len(pieces) + 1,
                "text": part,
                "start_byte": start,
                "end_byte": end,
                "candidate_ids": [],
                "possibly_missing": True,
            }
        )
    if "".join(s["text"] for s in pieces) != text:
        raise ViewGap("GAP_FIXTURE_MISMATCH")
    return pieces


def bind_source(
    item: dict[str, Any], fixture: dict[str, Any], sentences: list[dict[str, Any]]
) -> list[str]:
    """只核位置和逐字证据；缺位置时，即便文字相同也不搜索补关系。"""
    location = item.get("source_location")
    evidence = item.get("evidence")
    if not isinstance(location, str) or not isinstance(evidence, str) or not evidence:
        return []
    parsed: list[dict[str, int]] = []
    for token in location.split("；"):
        match = LOCATION_RE.fullmatch(token)
        if match is None:
            return []
        seg, start, end = map(int, match.groups())
        parsed.append({"seg": seg, "start_byte": start, "end_byte": end})
    locations = item.get("match_locations")
    if locations is not None:
        if not isinstance(locations, list) or not locations or locations != parsed:
            return []
        if any(
            not isinstance(loc, dict) or any(type(v) is not int for v in loc.values())
            for loc in locations
        ):
            return []
    segments = {segment["seg"]: segment for segment in fixture["segments"]}
    bound: set[str] = set()
    for loc in parsed:
        segment = segments.get(loc["seg"])
        if segment is None:
            return []
        raw = segment["responsibility_text"].encode("utf-8")
        start, end = loc["start_byte"], loc["end_byte"]
        if not (0 <= start < end <= len(raw)) or raw[start:end] != evidence.encode(
            "utf-8"
        ):
            return []
        absolute_start = segment["start_byte"] + start
        absolute_end = segment["start_byte"] + end
        hits = [
            s["id"]
            for s in sentences
            if s["start_byte"] < absolute_end and absolute_start < s["end_byte"]
        ]
        if not hits:
            return []
        bound.update(hits)
    return [s["id"] for s in sentences if s["id"] in bound]


def route_ledger(item: dict[str, Any]) -> str:
    """这版只认现成的状态；不靠句子里的名词猜人物、地点或物品身份。"""
    return "长线账" if item.get("status") in {"计划", "承诺"} else "事实账"


def validate_proof(proof: dict[str, Any], fixture: dict[str, Any]) -> None:
    if not isinstance(proof, dict) or proof.get("status") != "READ_OK":
        gaps = proof.get("gaps") if isinstance(proof, dict) else None
        code = (
            gaps[0]
            if isinstance(gaps, list) and gaps and isinstance(gaps[0], str)
            else "GAP_STORE_READ"
        )
        raise ViewGap(code if re.fullmatch(r"GAP_[A-Z_]+", code) else "GAP_STORE_READ")
    identity, scope = proof.get("identity"), proof.get("result_scope")
    if not isinstance(identity, dict) or not isinstance(scope, dict):
        raise ViewGap("GAP_SCOPE_MISMATCH")
    if (
        identity.get("pointer_namespace") != "FIXTURE_ONLY"
        or identity.get("candidate_access") != "POLICY_FIXTURE_READ_ONLY"
        or identity.get("product_adopted") is not False
        or scope.get("project_scope_id") != PROJECT_SCOPE_ID
        or scope.get("revision_text_sha256") != fixture["text_sha256"]
        or scope.get("revision_no") != fixture["revision"]["revision_no"]
        or scope.get("chapter_id") not in {fixture["revision"]["chapter_id"], "1"}
        or scope.get("book_title") not in {"未提供", "北塔夹具"}
        or scope.get("responsibility_segment") != 1
        or not isinstance(proof.get("pointer_key"), str)
        or not proof["pointer_key"]
    ):
        raise ViewGap("GAP_SCOPE_MISMATCH")


def project_view(proof: dict[str, Any], fixture: dict[str, Any]) -> dict[str, Any]:
    """投影只读回执；调用方能单测画面，不必另外造一个候选 writer。"""
    validate_proof(proof, fixture)
    card = proof.get("human_card")
    raw_items = card.get("items") if isinstance(card, dict) else None
    if not isinstance(raw_items, list) or not raw_items:
        raise ViewGap("GAP_NO_HUMAN_ITEMS")
    sentences = split_sentences(fixture["text"])
    items: list[dict[str, Any]] = []
    seen: set[str] = set()
    for index, raw in enumerate(raw_items):
        if not isinstance(raw, dict) or any(
            not isinstance(raw.get(k), str) or not raw[k]
            for k in ("fact", "status", "evidence")
        ):
            raise ViewGap("GAP_CANDIDATE_SHAPE")
        stable = raw.get("stable_item_id")
        stable_ok = isinstance(stable, str) and re.fullmatch(
            r"lin_[A-Za-z0-9_-]+", stable
        )
        candidate_id = (
            stable
            if stable_ok
            else "c_" + digest([proof["pointer_key"], index, raw])[:24]
        )
        if candidate_id in seen:
            raise ViewGap("GAP_CANDIDATE_SHAPE")
        seen.add(candidate_id)
        source_ids = bind_source(raw, fixture, sentences)
        item = {
            "id": candidate_id,
            "number": index + 1,
            "fact": raw["fact"],
            "status": raw["status"],
            "evidence": raw["evidence"],
            "kind": raw.get("kind") if isinstance(raw.get("kind"), str) else "未提供",
            "speaker": raw.get("speaker")
            if isinstance(raw.get("speaker"), str)
            else None,
            "source_location": raw.get("source_location")
            if isinstance(raw.get("source_location"), str)
            else "未提供",
            "stable_item_id": stable if stable_ok else "未提供（仅本页定位）",
            "source_ids": source_ids,
            "source_matched": bool(source_ids),
            "source_message": "位置与证据一致" if source_ids else "来源没对上",
            "ledger": route_ledger(raw),
        }
        items.append(item)
        for sentence in sentences:
            if sentence["id"] in source_ids:
                sentence["candidate_ids"].append(candidate_id)
                sentence["possibly_missing"] = False
    ledgers = [
        {"name": name, "note": note, "entries": []}
        for name, note in zip(LEDGER_NAMES, LEDGER_NOTES)
    ]
    by_name = {book["name"]: book for book in ledgers}
    by_name["章节账"]["entries"].append(
        {
            "id": "chapter_identity",
            "candidate_id": None,
            "primary_key": "北塔夹具 · 第 1 章",
            "tags": {
                "修订": str(fixture["revision"]["revision_no"]),
                "身份": "FIXTURE_ONLY",
            },
            "tag_groups": ["只读"],
        }
    )
    for item in items:
        tags = {"状态": item["status"], "类型": item["kind"]}
        if item["speaker"]:
            tags["说话人"] = item["speaker"]
        by_name[item["ledger"]]["entries"].append(
            {
                "id": "ledger_" + item["id"],
                "candidate_id": item["id"],
                "primary_key": item["fact"],
                "tags": tags,
                "tag_groups": ["只读"],
            }
        )
    view_id = digest(
        {
            "chapter_text_sha256": fixture["text_sha256"],
            "scope": proof["result_scope"],
            "pointer_key": proof["pointer_key"],
            "items": items,
        }
    )
    return {
        "document_identity": DOCUMENT_IDENTITY,
        "view_id": view_id,
        "identity": "北塔夹具 第 1 章 · FIXTURE_ONLY · 不是产品权威",
        "chapter_text_sha256": fixture["text_sha256"],
        "sentences": sentences,
        "candidates": items,
        "ledgers": ledgers,
        "authority_wrote": False,
        "product_adopted": False,
        "pointer_key": proof["pointer_key"],
        "revision_no": fixture["revision"]["revision_no"],
        "missing_count": sum(s["possibly_missing"] for s in sentences),
    }


def read_current_fixture(store_root: Path) -> dict[str, Any]:
    """唯一读路就是原来的 prove_current_read；缺依赖则停，没有替代库。"""
    if not (store_root / DATABASE_FILENAME).is_file():
        raise ViewGap("GAP_STORE_MISSING")
    try:
        from current_read_proof import prove_current_read
    except (ImportError, ModuleNotFoundError) as exc:
        raise ViewGap("GAP_DEPENDENCY_MISSING") from exc
    try:
        return prove_current_read(
            store_root=store_root, project_scope_id=PROJECT_SCOPE_ID
        )
    except (OSError, ValueError, RuntimeError) as exc:
        raise ViewGap("GAP_STORE_READ") from exc


def _output_guard(out: Path, store_root: Path) -> Path:
    target = out.expanduser().absolute()
    resolved = target.resolve()
    if (
        target.is_symlink()
        or target.suffix.lower() != ".html"
        or target.name in {"", ".", ".."}
        or resolved.is_relative_to(store_root.resolve())
        or resolved.is_relative_to(REPOSITORY_ROOT / "work")
        or resolved == REPOSITORY_ROOT
        or not target.parent.is_dir()
    ):
        raise ViewGap("GAP_OUTPUT_PATH")
    if target.exists():
        if not target.is_file() or target.stat().st_nlink != 1:
            raise ViewGap("GAP_OUTPUT_PATH")
        with target.open("rb") as handle:
            head = handle.read(2048)
        if b'name="door1-document"' not in head:
            raise ViewGap("GAP_OUTPUT_PATH")
    return target


def build_view(
    *, book: str, chapter: int, store_root: Path, out: Path
) -> dict[str, Any]:
    fixture = load_fixture(book, chapter)
    try:
        target = _output_guard(Path(out), Path(store_root))
    except OSError as exc:
        raise ViewGap("GAP_OUTPUT_PATH") from exc
    proof = read_current_fixture(Path(store_root))
    model = project_view(proof, fixture)
    # 只重读同一路；两次不同就停，不把变动中的候选装成当前快照。
    again = project_view(read_current_fixture(Path(store_root)), fixture)
    if again["view_id"] != model["view_id"]:
        raise ViewGap("GAP_CURRENT_CHANGED")
    sentence_ids = {s["id"] for s in model["sentences"]}
    candidate_ids = {item["id"] for item in model["candidates"]}
    marks_path = target.with_name(SIDECAR_NAME)
    marks = read_marks(marks_path, model["view_id"], sentence_ids, candidate_ids)
    from view_render import render_page

    page = render_page(
        model, marks, output_name=target.name, document_token=uuid.uuid4().hex
    )
    temporary = target.with_name(".door1-view." + uuid.uuid4().hex + ".tmp")
    descriptor: int | None = None
    created_marks_identity: tuple[int, int] | None = None
    empty_marks_bytes = encode_document(empty_document(model["view_id"]))
    published = False
    try:
        descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
            descriptor = None
            handle.write(page)
            handle.flush()
            os.fsync(handle.fileno())
        # 不覆盖已有边车；坏边车也留给人核对。
        if marks["status"] == "MISSING":
            if create_if_missing(marks_path, empty_document(model["view_id"])):
                info = marks_path.stat()
                created_marks_identity = (info.st_dev, info.st_ino)
        _output_guard(target, Path(store_root))
        os.replace(temporary, target)
        published = True
    except (OSError, MarksError) as exc:
        raise ViewGap("GAP_OUTPUT_WRITE") from exc
    finally:
        if descriptor is not None:
            os.close(descriptor)
        temporary.unlink(missing_ok=True)
        # 页面没发布时只收走本次新建、仍为空的边车，不碰原有标记或其他进程的新写入。
        if not published and created_marks_identity is not None:
            try:
                info = marks_path.stat()
                if (
                    not marks_path.is_symlink()
                    and (info.st_dev, info.st_ino) == created_marks_identity
                    and marks_path.read_bytes() == empty_marks_bytes
                ):
                    marks_path.unlink()
            except OSError:
                pass
    return {
        "document_identity": DOCUMENT_IDENTITY,
        "status": "BUILT",
        "gaps": [],
        "html_written": True,
        "authority_wrote": False,
        "product_adopted": False,
        "pointer_namespace": "FIXTURE_ONLY",
        "candidate_count": len(model["candidates"]),
        "source_sentence_count": len(model["sentences"]),
        "possibly_missing_count": model["missing_count"],
        "marks_status": marks["status"],
        "marks_gap": marks["gap"],
        "output_filename": target.name,
        "browser_permission_required": True,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="从现成的北塔夹具候选库生成门 1 单文件页面。不会建库。"
    )
    parser.add_argument("--book", required=True, help="只接受北塔夹具或它的放行编号。")
    parser.add_argument(
        "--chapter", type=int, required=True, help="这一刀只接受第 1 章。"
    )
    parser.add_argument(
        "--store",
        type=Path,
        required=True,
        help="现成的 CandidateAuthorityStore 目录。",
    )
    parser.add_argument(
        "--out",
        type=Path,
        required=True,
        help="输出 HTML；父目录须已存在，不放进 work/ 或库目录。",
    )
    args = parser.parse_args(argv)
    try:
        result = build_view(
            book=args.book, chapter=args.chapter, store_root=args.store, out=args.out
        )
        code = 0
    except ViewGap as exc:
        result = {
            "document_identity": DOCUMENT_IDENTITY,
            "status": "GAP",
            "gaps": [exc.code],
            "message": GAP_LABELS.get(exc.code, "读取缺口，请核对现有读路。"),
            "html_written": False,
            "authority_wrote": False,
            "product_adopted": False,
        }
        code = 2
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return code


if __name__ == "__main__":
    raise SystemExit(main())

"""Read local candidate material and project it into disposable workspaces."""

from __future__ import annotations

import collections
import copy
import csv
import hashlib
import json
import math
import re
import sys
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence


SOURCE_MAP_VERSION = "ccz158-seven-book-source-map-v1"


class LocalCandidateAdapterError(ValueError):
    """Local candidate material or its disposable projection is invalid."""


def _fail(code: str) -> None:
    raise LocalCandidateAdapterError(code)


def _canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _resolved_child(root: Path, relative: str) -> Path:
    root = root.resolve()
    candidate = (root / relative).resolve()
    try:
        candidate.relative_to(root)
    except ValueError:
        _fail("SOURCE_PATH_ESCAPES_ROOT")
    return candidate


def _is_within(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
    except ValueError:
        return False
    return True


def ensure_disposable_output(
    output_root: Path,
    *,
    repository_root: Path,
    protected_roots: Sequence[Path],
) -> Path:
    resolved = output_root.resolve()
    if _is_within(resolved, repository_root):
        _fail("OUTPUT_INSIDE_GIT_REPOSITORY")
    for protected in protected_roots:
        if _is_within(resolved, protected) or _is_within(protected, resolved):
            _fail("OUTPUT_OVERLAPS_PROTECTED_MATERIAL")
    if resolved.exists() and any(resolved.iterdir()):
        _fail("OUTPUT_DIRECTORY_NOT_EMPTY")
    resolved.mkdir(parents=True, exist_ok=True)
    return resolved


@dataclass(frozen=True)
class BookSource:
    book: str
    placement_dir: str
    chapter_dir: str
    row_ref_prefix: str | None


@dataclass(frozen=True)
class CandidateChapter:
    book: str
    chapter: int
    source_file: str
    text: str
    text_sha256: str


@dataclass(frozen=True)
class CandidateFact:
    book: str
    public_ref: str
    chapter: int
    fact_text: str
    body: str
    source_file: str
    source_row: int
    source_position: str
    placement_status: str
    row_sha256: str


@dataclass(frozen=True)
class RankedCandidate:
    public_ref: str
    score: float
    matched_term_count: int

    def as_dict(self) -> dict[str, Any]:
        return {
            "public_ref": self.public_ref,
            "score": round(self.score, 12),
            "matched_term_count": self.matched_term_count,
            "selection_method": "CHAR_2_3_GRAM_BM25_LIKE",
        }


@dataclass(frozen=True)
class CandidateCorpus:
    sources: tuple[BookSource, ...]
    chapters: tuple[CandidateChapter, ...]
    facts: tuple[CandidateFact, ...]
    source_map_sha256: str
    placement_file_sha256: Mapping[str, str]

    @property
    def books(self) -> tuple[str, ...]:
        return tuple(sorted({row.book for row in self.sources}))

    def facts_for_book(self, book: str) -> tuple[CandidateFact, ...]:
        return tuple(row for row in self.facts if row.book == book)

    def chapter_count(self) -> int:
        return len(self.chapters)

    def fact_count(self) -> int:
        return len(self.facts)


@dataclass(frozen=True)
class CandidateProjection:
    workspaces: Mapping[str, Any]
    public_to_internal: Mapping[tuple[str, str], str]
    internal_to_public: Mapping[str, tuple[str, str]]
    facts_by_public: Mapping[tuple[str, str], CandidateFact]
    sidecar: tuple[dict[str, Any], ...]


def load_source_map(path: Path) -> tuple[tuple[BookSource, ...], str]:
    if not path.is_file():
        _fail("SOURCE_MAP_MISSING")
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise LocalCandidateAdapterError("SOURCE_MAP_INVALID_JSON") from exc
    if not isinstance(document, dict) or set(document) != {
        "schema_version",
        "sources",
    }:
        _fail("SOURCE_MAP_FIELDS_INVALID")
    if document["schema_version"] != SOURCE_MAP_VERSION:
        _fail("SOURCE_MAP_VERSION_INVALID")
    if not isinstance(document["sources"], list) or not document["sources"]:
        _fail("SOURCE_MAP_SOURCES_INVALID")

    sources: list[BookSource] = []
    seen_placement_dirs: set[str] = set()
    for row in document["sources"]:
        if not isinstance(row, dict) or set(row) != {
            "book",
            "placement_dir",
            "chapter_dir",
            "row_ref_prefix",
        }:
            _fail("SOURCE_MAP_ROW_FIELDS_INVALID")
        for field in ("book", "placement_dir", "chapter_dir"):
            if not isinstance(row[field], str) or not row[field].strip():
                _fail(f"SOURCE_MAP_ROW_FIELD_INVALID:{field}")
        prefix = row["row_ref_prefix"]
        if prefix is not None and (
            not isinstance(prefix, str) or not prefix.strip()
        ):
            _fail("SOURCE_MAP_ROW_REF_PREFIX_INVALID")
        if row["placement_dir"] in seen_placement_dirs:
            _fail("SOURCE_MAP_PLACEMENT_DIR_DUPLICATE")
        seen_placement_dirs.add(row["placement_dir"])
        sources.append(
            BookSource(
                book=row["book"],
                placement_dir=row["placement_dir"],
                chapter_dir=row["chapter_dir"],
                row_ref_prefix=prefix,
            )
        )
    return tuple(sources), _sha256_file(path)


def _first(row: Mapping[str, str | None], names: Iterable[str]) -> str:
    for name in names:
        value = row.get(name)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def _chapter_number(value: str) -> int:
    match = re.search(r"\d+", value)
    if match is None or int(match.group()) < 1:
        _fail("CANDIDATE_CHAPTER_NUMBER_INVALID")
    return int(match.group())


def _public_ref(source: BookSource, raw_ref: str) -> str:
    if not raw_ref:
        _fail("CANDIDATE_FACT_REF_MISSING")
    if source.row_ref_prefix is None:
        return raw_ref
    if not raw_ref.isdigit():
        _fail("CANDIDATE_ROW_NUMBER_INVALID")
    return f"{source.row_ref_prefix}{int(raw_ref):03d}"


def _load_facts(
    placement_root: Path,
    sources: Sequence[BookSource],
) -> tuple[tuple[CandidateFact, ...], dict[str, str]]:
    facts: list[CandidateFact] = []
    file_shas: dict[str, str] = {}
    seen: set[tuple[str, str]] = set()
    for source in sources:
        csv_path = _resolved_child(
            placement_root,
            f"{source.placement_dir}/01_落位表.csv",
        )
        if not csv_path.is_file():
            _fail("PLACEMENT_FILE_MISSING")
        relative = csv_path.relative_to(placement_root.resolve()).as_posix()
        file_shas[relative] = _sha256_file(csv_path)
        with csv_path.open(encoding="utf-8-sig", newline="") as handle:
            for source_row, row in enumerate(csv.DictReader(handle), start=2):
                if not row:
                    continue
                row_book = _first(row, ("book", "书名"))
                if row_book and row_book != source.book:
                    _fail("PLACEMENT_BOOK_SCOPE_MISMATCH")
                raw_ref = _first(row, ("evidence_id", "fact_id", "行号"))
                public_ref = _public_ref(source, raw_ref)
                identity = (source.book, public_ref)
                if identity in seen:
                    _fail("CANDIDATE_FACT_REF_DUPLICATE_WITHIN_BOOK")
                seen.add(identity)
                chapter_value = _first(row, ("chapter", "章号", "章号＋位置"))
                fact_text = _first(row, ("fact_sentence", "事实句"))
                if not fact_text:
                    _fail("CANDIDATE_FACT_TEXT_MISSING")
                body = " ".join(str(value or "") for value in row.values())
                facts.append(
                    CandidateFact(
                        book=source.book,
                        public_ref=public_ref,
                        chapter=_chapter_number(chapter_value),
                        fact_text=fact_text,
                        body=body,
                        source_file=relative,
                        source_row=source_row,
                        source_position=_first(
                            row,
                            ("source_position", "原文位置", "章号＋位置"),
                        ),
                        placement_status=_first(
                            row,
                            ("placement_status", "落位状态"),
                        ),
                        row_sha256=_sha256_text(_canonical_json(row)),
                    )
                )
    return tuple(facts), file_shas


def _chapter_file_number(path: Path) -> int:
    match = re.match(r"^(?:ch_)?0*(\d+)", path.stem)
    if match is None or int(match.group(1)) < 1:
        _fail("CHAPTER_FILE_NAME_INVALID")
    return int(match.group(1))


def _load_chapters(
    chapter_root: Path,
    sources: Sequence[BookSource],
) -> tuple[CandidateChapter, ...]:
    chapters: list[CandidateChapter] = []
    seen_source: set[tuple[str, str]] = set()
    seen_chapter: set[tuple[str, int]] = set()
    for source in sources:
        source_identity = (source.book, source.chapter_dir)
        if source_identity in seen_source:
            continue
        seen_source.add(source_identity)
        directory = _resolved_child(chapter_root, source.chapter_dir)
        if not directory.is_dir():
            _fail("CHAPTER_DIRECTORY_MISSING")
        files = sorted(path for path in directory.rglob("*.txt") if path.is_file())
        if not files:
            _fail("CHAPTER_DIRECTORY_EMPTY")
        for path in files:
            number = _chapter_file_number(path)
            identity = (source.book, number)
            if identity in seen_chapter:
                _fail("CHAPTER_NUMBER_DUPLICATE_WITHIN_BOOK")
            seen_chapter.add(identity)
            text = path.read_text(encoding="utf-8")
            chapters.append(
                CandidateChapter(
                    book=source.book,
                    chapter=number,
                    source_file=path.relative_to(chapter_root.resolve()).as_posix(),
                    text=text,
                    text_sha256=_sha256_text(text),
                )
            )
    return tuple(chapters)


def load_candidate_corpus(
    *,
    placement_root: Path,
    chapter_root: Path,
    source_map_path: Path,
) -> CandidateCorpus:
    placement_root = placement_root.resolve()
    chapter_root = chapter_root.resolve()
    if not placement_root.is_dir():
        _fail("PLACEMENT_ROOT_MISSING")
    if not chapter_root.is_dir():
        _fail("CHAPTER_ROOT_MISSING")
    sources, source_map_sha = load_source_map(source_map_path)
    facts, file_shas = _load_facts(placement_root, sources)
    chapters = _load_chapters(chapter_root, sources)
    chapter_keys = {(row.book, row.chapter) for row in chapters}
    missing = sorted(
        {(row.book, row.chapter) for row in facts if (row.book, row.chapter) not in chapter_keys}
    )
    if missing:
        _fail(f"FACT_CHAPTER_SOURCE_MISSING:{missing[0][0]}:{missing[0][1]}")
    return CandidateCorpus(
        sources=tuple(sources),
        chapters=tuple(chapters),
        facts=tuple(facts),
        source_map_sha256=source_map_sha,
        placement_file_sha256=dict(sorted(file_shas.items())),
    )


def _tokens(value: str) -> list[str]:
    normalized = unicodedata.normalize("NFKC", value).casefold()
    compact = "".join(
        char
        for char in normalized
        if "\u4e00" <= char <= "\u9fff" or char.isalnum()
    )
    result: list[str] = []
    for size in (2, 3):
        result.extend(
            compact[index : index + size]
            for index in range(max(0, len(compact) - size + 1))
        )
    result.extend(re.findall(r"[a-z0-9_]+", normalized))
    return result


class SparseRanker:
    """The frozen R01 character 2/3-gram BM25-like diagnostic selector."""

    def __init__(self, facts: Sequence[CandidateFact]):
        if not facts:
            _fail("RANKER_CORPUS_EMPTY")
        self._facts = tuple(facts)
        self._frequencies: list[collections.Counter[str]] = []
        self._document_frequency: collections.Counter[str] = collections.Counter()
        self._lengths: list[int] = []
        for fact in self._facts:
            frequency = collections.Counter(_tokens(fact.body))
            self._frequencies.append(frequency)
            self._lengths.append(sum(frequency.values()))
            self._document_frequency.update(frequency.keys())
        self._average_length = sum(self._lengths) / len(self._lengths)
        if self._average_length <= 0:
            _fail("RANKER_CORPUS_HAS_NO_TERMS")

    def rank(
        self,
        question: str,
        *,
        allowed_chapters: set[int] | None = None,
    ) -> tuple[RankedCandidate, ...]:
        query_frequency = collections.Counter(_tokens(question))
        scored: list[tuple[float, str, int]] = []
        document_count = len(self._facts)
        for fact, frequency, length in zip(
            self._facts,
            self._frequencies,
            self._lengths,
            strict=True,
        ):
            if allowed_chapters is not None and fact.chapter not in allowed_chapters:
                continue
            score = 0.0
            matched = 0
            for term, query_count in query_frequency.items():
                observed = frequency.get(term, 0)
                if not observed:
                    continue
                matched += 1
                inverse_frequency = math.log(
                    1
                    + (document_count - self._document_frequency[term] + 0.5)
                    / (self._document_frequency[term] + 0.5)
                )
                score += (
                    min(query_count, 2)
                    * inverse_frequency
                    * (observed * 2.2)
                    / (
                        observed
                        + 1.2
                        * (0.25 + 0.75 * length / self._average_length)
                    )
                )
            if score > 0:
                scored.append((score, fact.public_ref, matched))
        scored.sort(key=lambda row: (-row[0], row[1]))
        return tuple(
            RankedCandidate(public_ref=ref, score=score, matched_term_count=matched)
            for score, ref, matched in scored
        )


def rankers_by_book(corpus: CandidateCorpus) -> dict[str, SparseRanker]:
    return {book: SparseRanker(corpus.facts_for_book(book)) for book in corpus.books}


def build_disposable_projection(
    corpus: CandidateCorpus,
    *,
    output_root: Path,
    repository_root: Path,
    protected_roots: Sequence[Path],
) -> CandidateProjection:
    output_root = ensure_disposable_output(
        output_root,
        repository_root=repository_root,
        protected_roots=protected_roots,
    )
    product_root = repository_root.resolve() / "novel-mvp"
    sys.path.insert(0, str(product_root))
    try:
        from mvp import ledger_directory_workspace
        from mvp.workspace import WorkspaceRouter
    finally:
        sys.path.pop(0)

    chapter_ids = {
        (row.book, row.chapter): f"c{index:06d}"
        for index, row in enumerate(
            sorted(corpus.chapters, key=lambda item: (item.book, item.chapter)),
            start=1,
        )
    }
    chapter_documents: dict[tuple[str, int], dict[str, Any]] = {}
    for row in corpus.chapters:
        chapter_id = chapter_ids[(row.book, row.chapter)]
        chapter_documents[(row.book, row.chapter)] = {
            "contract": "C1_CHAPTER_DOC",
            "version": "v1",
            "id": chapter_id,
            "title": f"第{row.chapter}章",
            "kind": "draft",
            "text": row.text,
            "added_at": "1970-01-01 00:00:00",
            "chapter_revision_ref": {
                "chapter_id": chapter_id,
                "revision_no": 1,
                "revision_text_sha256": row.text_sha256,
            },
        }

    ordered_facts = sorted(
        corpus.facts,
        key=lambda row: (row.book, row.chapter, row.public_ref, row.source_file, row.source_row),
    )
    public_to_internal: dict[tuple[str, str], str] = {}
    internal_to_public: dict[str, tuple[str, str]] = {}
    facts_by_public: dict[tuple[str, str], CandidateFact] = {}
    fact_documents: dict[str, list[dict[str, Any]]] = collections.defaultdict(list)
    sidecar: list[dict[str, Any]] = []
    for index, row in enumerate(ordered_facts, start=1):
        internal_id = f"f{index:06d}"
        identity = (row.book, row.public_ref)
        public_to_internal[identity] = internal_id
        internal_to_public[internal_id] = identity
        facts_by_public[identity] = row
        chapter = chapter_documents[(row.book, row.chapter)]
        fact_documents[row.book].append(
            {
                "contract": "C4_FACT_QUERY",
                "version": "v1",
                "id": internal_id,
                "chapter_id": chapter["id"],
                "text": row.fact_text,
                "quote": "",
                "status": "extracted",
                "source": "CCZ158_LOCAL_CANDIDATE_PROJECTION",
                "note": "",
                "added_at": "1970-01-01 00:00:00",
                "chapter_revision_ref": copy.deepcopy(
                    chapter["chapter_revision_ref"]
                ),
                "anchor_ref": None,
                "anchor_state": "LEGACY_UNVERIFIED",
                "recheck": None,
            }
        )
        sidecar.append(
            {
                "book": row.book,
                "public_ref": row.public_ref,
                "internal_fact_id": internal_id,
                "chapter": row.chapter,
                "internal_chapter_id": chapter["id"],
                "source_file": row.source_file,
                "source_row": row.source_row,
                "source_position": row.source_position,
                "placement_status": row.placement_status,
                "row_sha256": row.row_sha256,
            }
        )

    router = WorkspaceRouter(output_root / "ephemeral_author_workspace")
    workspaces: dict[str, Any] = {}
    for book in corpus.books:
        principal = f"auth:ccz158-eval:{_sha256_text(book)[:16]}"
        workspace = router.create_project(principal, book)
        suffix = _sha256_text(book)[:12]
        ledger_directory_workspace.initialize_directory(
            workspace,
            f"op-directory-{suffix}",
        )
        chapters = [
            copy.deepcopy(chapter_documents[(row.book, row.chapter)])
            for row in sorted(
                (item for item in corpus.chapters if item.book == book),
                key=lambda item: item.chapter,
            )
        ]
        workspace.commit(
            f"op-content-{suffix}",
            {
                "chapters": chapters,
                "chapter_index": [
                    copy.deepcopy(chapter["chapter_revision_ref"])
                    for chapter in chapters
                ],
                "facts": copy.deepcopy(fact_documents[book]),
            },
            {"chapters": 0, "chapter_index": 0, "facts": 0},
        )
        workspaces[book] = workspace

    return CandidateProjection(
        workspaces=workspaces,
        public_to_internal=public_to_internal,
        internal_to_public=internal_to_public,
        facts_by_public=facts_by_public,
        sidecar=tuple(sidecar),
    )


__all__ = [
    "BookSource",
    "CandidateCorpus",
    "CandidateFact",
    "CandidateProjection",
    "LocalCandidateAdapterError",
    "RankedCandidate",
    "SOURCE_MAP_VERSION",
    "SparseRanker",
    "build_disposable_projection",
    "ensure_disposable_output",
    "load_candidate_corpus",
    "load_source_map",
    "rankers_by_book",
]

"""Parse retrieval prompts separately from hidden evaluation answers."""

from __future__ import annotations

import hashlib
import json
import re
import statistics
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence


FACT_REF_RE = re.compile(r"(?:LQ-\d+|MK-[A-Z0-9-]+|GK-[AB]-R\d+|E-\d+-\d+)")
QA_HEADING_RE = re.compile(r"(?=^## QA-\d{3}\s*$)", re.MULTILINE)


class QuestionSetError(ValueError):
    """The local candidate question set does not match the evaluation adapter."""


@dataclass(frozen=True)
class RetrievalPrompt:
    """Only the fields a candidate selector is allowed to see."""

    question_id: str
    book: str
    book_class: str
    chapter_scope_text: str
    scope_chapters: tuple[int, ...]
    question: str
    return_budget: int

    def as_dict(self) -> dict[str, Any]:
        return {
            "question_id": self.question_id,
            "book": self.book,
            "book_class": self.book_class,
            "chapter_scope_text": self.chapter_scope_text,
            "scope_chapters": list(self.scope_chapters),
            "question": self.question,
            "return_budget": self.return_budget,
        }


@dataclass(frozen=True)
class EvaluationAnswer:
    """Hidden answer material loaded only after retrieval output is sealed."""

    question_id: str
    required_fact_refs: tuple[str, ...]
    reference_fact_refs: tuple[str, ...]
    unsupported_non_fact_requirements: tuple[str, ...]
    semantic_assertions_unscored: tuple[str, ...]

    def as_dict(self) -> dict[str, Any]:
        return {
            "question_id": self.question_id,
            "required_fact_refs": list(self.required_fact_refs),
            "reference_fact_refs": list(self.reference_fact_refs),
            "unsupported_non_fact_requirements": list(
                self.unsupported_non_fact_requirements
            ),
            "semantic_assertions_unscored": list(
                self.semantic_assertions_unscored
            ),
        }


def canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def sha256_json(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _fail(code: str) -> None:
    raise QuestionSetError(code)


def _blocks(path: Path, expected_count: int) -> list[str]:
    if not path.is_file():
        _fail("QA_FILE_MISSING")
    text = path.read_text(encoding="utf-8")
    blocks = QA_HEADING_RE.split(text)[1:]
    if len(blocks) != expected_count:
        _fail(f"QA_COUNT_MISMATCH:{len(blocks)}:{expected_count}")
    ids = []
    for block in blocks:
        match = re.search(r"^## (QA-\d{3})\s*$", block, re.MULTILINE)
        if match is None:
            _fail("QA_HEADING_INVALID")
        ids.append(match.group(1))
    if len(ids) != len(set(ids)):
        _fail("QA_ID_DUPLICATE")
    return blocks


def _field(block: str, number: int, label: str) -> str:
    pattern = re.compile(
        rf"^{number}\. \*\*{re.escape(label)}\*\*：(.*?)(?=^\d+\. \*\*|\Z)",
        re.MULTILINE | re.DOTALL,
    )
    match = pattern.search(block)
    if match is None:
        _fail(f"QA_FIELD_MISSING:{number}:{label}")
    return match.group(1).strip()


def _chapter_numbers(value: str) -> tuple[int, ...]:
    result: set[int] = set()
    for start, end in re.findall(r"(\d+)\s*[–—-]\s*(\d+)", value):
        lower, upper = int(start), int(end)
        if lower > upper:
            _fail("QA_CHAPTER_RANGE_INVALID")
        result.update(range(lower, upper + 1))
    result.update(int(number) for number in re.findall(r"\d+", value))
    if not result:
        _fail("QA_CHAPTER_SCOPE_EMPTY")
    return tuple(sorted(result))


def _return_budget(value: str) -> int:
    numbers = [int(item) for item in re.findall(r"\d+", value.split("；", 1)[0])]
    if not numbers or max(numbers) < 1:
        _fail("QA_RETURN_BUDGET_INVALID")
    return max(numbers)


def _question_id(block: str) -> str:
    match = re.search(r"^## (QA-\d{3})\s*$", block, re.MULTILINE)
    if match is None:
        _fail("QA_HEADING_INVALID")
    return match.group(1)


def load_retrieval_prompts(
    path: Path,
    *,
    expected_count: int = 50,
) -> tuple[RetrievalPrompt, ...]:
    """Read no answer-list or error-list fields."""

    prompts: list[RetrievalPrompt] = []
    for block in _blocks(path, expected_count):
        scope = _field(block, 2, "书名｜新书或旧书｜章节范围")
        parts = [part.strip() for part in scope.split("｜")]
        if len(parts) != 3 or any(not part for part in parts):
            _fail("QA_SCOPE_FIELD_INVALID")
        prompts.append(
            RetrievalPrompt(
                question_id=_question_id(block),
                book=parts[0],
                book_class=parts[1],
                chapter_scope_text=parts[2],
                scope_chapters=_chapter_numbers(parts[2]),
                question=_field(block, 4, "问题").splitlines()[0].strip(),
                return_budget=_return_budget(_field(block, 9, "合理返回量")),
            )
        )
    return tuple(prompts)


def _bold_list_keys(section: str) -> tuple[str, ...]:
    values = tuple(
        match.strip()
        for match in re.findall(r"^- \*\*([^*]+)\*\*", section, re.MULTILINE)
        if match.strip()
    )
    fact_refs = [value for value in values if FACT_REF_RE.fullmatch(value)]
    if len(fact_refs) != len(set(fact_refs)):
        _fail("QA_EVALUATION_FACT_REF_DUPLICATE")
    return values


def _bullet_lines(section: str) -> tuple[str, ...]:
    return tuple(
        line[2:].strip()
        for line in section.splitlines()
        if line.startswith("- ") and line[2:].strip()
    )


def load_evaluation_answers(
    path: Path,
    *,
    expected_count: int = 50,
) -> tuple[EvaluationAnswer, ...]:
    """Load hidden answers. Call only after candidate and C9 output are sealed."""

    answers: list[EvaluationAnswer] = []
    for block in _blocks(path, expected_count):
        required_items = _bold_list_keys(_field(block, 6, "必取清单"))
        reference_items = _bold_list_keys(_field(block, 7, "参考清单"))
        answers.append(
            EvaluationAnswer(
                question_id=_question_id(block),
                required_fact_refs=tuple(
                    item for item in required_items if FACT_REF_RE.fullmatch(item)
                ),
                reference_fact_refs=tuple(
                    item for item in reference_items if FACT_REF_RE.fullmatch(item)
                ),
                unsupported_non_fact_requirements=tuple(
                    item for item in required_items if not FACT_REF_RE.fullmatch(item)
                ),
                semantic_assertions_unscored=_bullet_lines(
                    _field(block, 8, "多余／错误清单")
                ),
            )
        )
    return tuple(answers)


def _aligned(
    prompts: Sequence[RetrievalPrompt],
    answers: Sequence[EvaluationAnswer],
) -> None:
    prompt_ids = [row.question_id for row in prompts]
    answer_ids = [row.question_id for row in answers]
    if prompt_ids != answer_ids:
        _fail("QA_PROMPT_ANSWER_ALIGNMENT_MISMATCH")


def score_question(
    prompt: RetrievalPrompt,
    answer: EvaluationAnswer,
    returned_refs: Sequence[str],
) -> dict[str, Any]:
    if prompt.question_id != answer.question_id:
        _fail("QA_SCORE_ID_MISMATCH")
    if any(not isinstance(ref, str) or not ref for ref in returned_refs):
        _fail("QA_RETURNED_REF_INVALID")

    required = set(answer.required_fact_refs)
    reference = set(answer.reference_fact_refs)
    returned = list(returned_refs)
    returned_unique = set(returned)
    required_hits = required & returned_unique
    reference_hits = reference & returned_unique
    relevant_hits = (required | reference) & returned_unique
    missing = required - returned_unique
    duplicate_count = len(returned) - len(returned_unique)
    relevant_hit_count = len(relevant_hits)
    noise_count = len(returned) - relevant_hit_count
    required_count = len(required)
    reference_count = len(reference)
    returned_count = len(returned)
    budget_ok = returned_count <= prompt.return_budget
    required_complete = not missing and duplicate_count == 0
    full = required_complete and budget_ok

    return {
        "question_id": prompt.question_id,
        "book": prompt.book,
        "return_budget": prompt.return_budget,
        "returned_count": returned_count,
        "returned_refs": returned,
        "required_count": required_count,
        "required_hit_count": len(required_hits),
        "required_hit_refs": sorted(required_hits),
        "required_missing_refs": sorted(missing),
        "required_recall": (
            len(required_hits) / required_count if required_count else 1.0
        ),
        "reference_count": reference_count,
        "reference_hit_count": len(reference_hits),
        "reference_hit_refs": sorted(reference_hits),
        "reference_recall": (
            len(reference_hits) / reference_count if reference_count else None
        ),
        "required_precision_r01_comparable": (
            len(required_hits) / returned_count if returned_count else 0.0
        ),
        "relevant_precision": (
            relevant_hit_count / returned_count if returned_count else 0.0
        ),
        "noise_count": noise_count,
        "noise_refs": [
            ref for ref in returned if ref not in required and ref not in reference
        ],
        "duplicate_count": duplicate_count,
        "budget_ok": budget_ok,
        "required_complete": required_complete,
        "full_question_pass": full,
        "unsupported_non_fact_requirements": list(
            answer.unsupported_non_fact_requirements
        ),
        "semantic_assertions_unscored": list(
            answer.semantic_assertions_unscored
        ),
    }


def summarize_scores(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    if not rows:
        _fail("QA_SCORE_ROWS_EMPTY")
    required_hits = sum(int(row["required_hit_count"]) for row in rows)
    required_count = sum(int(row["required_count"]) for row in rows)
    reference_hits = sum(int(row["reference_hit_count"]) for row in rows)
    reference_count = sum(int(row["reference_count"]) for row in rows)
    returned_count = sum(int(row["returned_count"]) for row in rows)
    relevant_hits = required_hits + reference_hits
    return {
        "question_count": len(rows),
        "required_complete_count": sum(
            bool(row["required_complete"]) for row in rows
        ),
        "full_question_count": sum(bool(row["full_question_pass"]) for row in rows),
        "micro_required_recall": round(required_hits / required_count, 6),
        "macro_required_recall": round(
            statistics.mean(float(row["required_recall"]) for row in rows), 6
        ),
        "reference_recall": (
            round(reference_hits / reference_count, 6)
            if reference_count
            else None
        ),
        "required_precision_r01_comparable": round(
            required_hits / returned_count if returned_count else 0.0, 6
        ),
        "relevant_precision": round(
            relevant_hits / returned_count if returned_count else 0.0, 6
        ),
        "noise_count": sum(int(row["noise_count"]) for row in rows),
        "average_returned": round(returned_count / len(rows), 6),
        "budget_ok_count": sum(bool(row["budget_ok"]) for row in rows),
        "required_fact_ref_count": required_count,
        "reference_fact_ref_count": reference_count,
        "unsupported_non_fact_requirement_count": sum(
            len(row["unsupported_non_fact_requirements"]) for row in rows
        ),
    }


def score_run(
    prompts: Sequence[RetrievalPrompt],
    answers: Sequence[EvaluationAnswer],
    returned_by_question: Mapping[str, Sequence[str]],
) -> dict[str, Any]:
    _aligned(prompts, answers)
    expected_ids = {prompt.question_id for prompt in prompts}
    if set(returned_by_question) != expected_ids:
        _fail("QA_RETURN_SET_MISMATCH")
    rows = [
        score_question(prompt, answer, returned_by_question[prompt.question_id])
        for prompt, answer in zip(prompts, answers, strict=True)
    ]
    result = {
        "per_question": rows,
        "summary": summarize_scores(rows),
    }
    result["score_sha256"] = sha256_json(result)
    return result


__all__ = [
    "EvaluationAnswer",
    "FACT_REF_RE",
    "QuestionSetError",
    "RetrievalPrompt",
    "canonical_json",
    "load_evaluation_answers",
    "load_retrieval_prompts",
    "score_question",
    "score_run",
    "sha256_file",
    "sha256_json",
    "summarize_scores",
]

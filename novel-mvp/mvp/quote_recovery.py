"""Exact source-LF recovery and the explicitly named provider-key adapter."""
from __future__ import annotations

import copy

RULE = "SOURCE_LF_ONLY_V1"


def locate_source_lf(quote: str, text: str) -> tuple[int, int, list[dict]]:
    """Find one full-chapter span; non-LF source characters never change."""
    if not isinstance(quote, str) or not quote or quote != quote.strip():
        raise ValueError("RECOVERY_QUOTE_INVALID")
    matches = {}
    for start, char in enumerate(text):
        if char == "\n" or char != quote[0]:
            continue
        pending = [(start, 0, ())]
        seen = set()
        while pending:
            i, j, changes = pending.pop()
            if (i, j) in seen:
                continue
            seen.add((i, j))
            if j == len(quote):
                if i > start and text[i - 1] != "\n":
                    matches[(start, i)] = changes
                continue
            if i == len(text):
                continue
            if text[i] == "\n":
                if quote[j] == "\n":
                    pending.append((i + 1, j + 1, changes))
                elif quote[j] == " ":
                    pending.append((i + 1, j + 1,
                                    changes + ((i, j, "SPACE_TO_SOURCE_LF"),)))
                pending.append((i + 1, j, changes + ((i, j, "RESTORE_SOURCE_LF"),)))
            elif text[i] == quote[j]:
                pending.append((i + 1, j + 1, changes))
        if len(matches) > 1:
            raise ValueError("RECOVERY_AMBIGUOUS_SOURCE")
    if not matches:
        raise ValueError("RECOVERY_NO_EXACT_NON_LF_MATCH")
    (start, end), changes = next(iter(matches.items()))
    if not changes:
        raise ValueError("RECOVERY_NOT_NEEDED")
    return start, end, [
        {"original_offset": i, "returned_offset": j, "reason": reason}
        for i, j, reason in changes
    ]


def adapt_provider_item(item: object) -> tuple[dict, dict | None]:
    """Only the exact text： alias is recognized, with an immutable source copy."""
    if not isinstance(item, dict):
        raise ValueError("PROVIDER_ITEM_NOT_OBJECT")
    if set(item) == {"text", "quote"}:
        return copy.deepcopy(item), None
    if set(item) != {"text：", "quote"}:
        raise ValueError("PROVIDER_ADAPTATION_KEYS_INVALID")
    adapted = {"text": item["text："], "quote": item["quote"]}
    evidence = {"rule": "TEXT_FULLWIDTH_COLON_KEY_V1",
                "original_item": copy.deepcopy(item), "from_key": "text：", "to_key": "text"}
    return adapted, evidence


def validate_adaptation(value: object, quote: str, fact_text: str | None = None) -> None:
    if value is None:
        return
    if not isinstance(value, dict) or set(value) != {"rule", "original_item", "from_key", "to_key"}:
        raise ValueError("PROVIDER_ADAPTATION_INVALID")
    adapted, expected = adapt_provider_item(value["original_item"])
    if expected is None or value != expected:
        raise ValueError("PROVIDER_ADAPTATION_REPLAY_MISMATCH")
    text = adapted["text"]
    if (not isinstance(text, str) or not text or text != text.strip()
            or adapted["quote"] != quote
            or (fact_text is not None and fact_text != text)):
        raise ValueError("PROVIDER_ADAPTATION_VALUE_MISMATCH")

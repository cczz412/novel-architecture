from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Mapping, Sequence


GRAPH_SCHEMA = "r2-event-graph.v1"
TRIGGER_SCHEMA = "r2-event-trigger.v1"
QUERY_MAP_SCHEMA = "r2-query-map.v1"
PLANNER_SOURCE_SCHEMA = "r2-planner-visible-source.v1"


class A8EventGraphError(ValueError):
    """A8 事件图旁车拒收错误。"""


def canonical_bytes(value: Any) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        + "\n"
    ).encode("utf-8")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_contract(path: Path, *, expected_sha256: str) -> dict[str, Any]:
    if sha256_file(path) != expected_sha256:
        raise A8EventGraphError("A8_EVENT_GRAPH_CONTRACT_SHA_MISMATCH")
    value = json.loads(path.read_text(encoding="utf-8"))
    required = {
        "schema_version",
        "contract_status",
        "frozen_at",
        "candidate_status",
        "graph_schema_version",
        "trigger_schema_version",
        "query_map_schema_version",
        "construction_policy",
        "input_contract",
        "forbidden_field_names_or_prefixes",
        "node_kinds",
        "edge_relations",
        "state_axes",
        "event_specs",
        "mechanical_extraction",
        "query_compilation",
        "model_api_calls_allowed",
        "network_calls_allowed",
    }
    if set(value) != required:
        raise A8EventGraphError("A8_EVENT_GRAPH_CONTRACT_FIELDS_INVALID")
    if value["contract_status"] != "FROZEN_BEFORE_IMPLEMENTATION":
        raise A8EventGraphError("A8_EVENT_GRAPH_CONTRACT_NOT_FROZEN")
    if value["model_api_calls_allowed"] != 0 or value["network_calls_allowed"] != 0:
        raise A8EventGraphError("A8_EVENT_GRAPH_CONTRACT_NONZERO_CALLS")
    return value


def _stable_id(prefix: str, *parts: object) -> str:
    payload = "\x1f".join(str(part) for part in parts).encode("utf-8")
    return f"{prefix}-{sha256_bytes(payload)[:20]}"


def _trim_bounds(text: str, start: int, end: int) -> tuple[int, int]:
    while start < end and text[start].isspace():
        start += 1
    while end > start and text[end - 1].isspace():
        end -= 1
    return start, end


def _span(
    *,
    planner_source: Mapping[str, Any],
    paragraph_id: str,
    sentence_id: str,
    start: int,
    end: int,
) -> dict[str, Any]:
    source_text = planner_source["source_text"]
    start, end = _trim_bounds(source_text, start, end)
    if start >= end:
        raise A8EventGraphError("A8_EMPTY_SOURCE_SPAN")
    surface = source_text[start:end]
    return {
        "source_id": planner_source["source_id"],
        "source_body_sha256": planner_source["source_body_sha256"],
        "paragraph_id": paragraph_id,
        "sentence_id": sentence_id,
        "char_start": start,
        "char_end_exclusive": end,
        "surface_text": surface,
        "surface_sha256": sha256_bytes(surface.encode("utf-8")),
    }


def _reject_forbidden_keys(value: Any, forbidden: Sequence[str]) -> None:
    lowered = tuple(item.lower() for item in forbidden)
    if isinstance(value, Mapping):
        for key, child in value.items():
            normalized = str(key).lower()
            if any(normalized == item or normalized.startswith(item) for item in lowered):
                raise A8EventGraphError(f"A8_FORBIDDEN_FIELD:{key}")
            _reject_forbidden_keys(child, forbidden)
    elif isinstance(value, list):
        for child in value:
            _reject_forbidden_keys(child, forbidden)


def _verify_planner_source(
    planner_source: Mapping[str, Any], contract: Mapping[str, Any]
) -> None:
    allowed = set(contract["input_contract"]["allowed_planner_source_fields"])
    if set(planner_source) != allowed:
        raise A8EventGraphError("A8_PLANNER_SOURCE_FIELDS_INVALID")
    if planner_source["schema_version"] != PLANNER_SOURCE_SCHEMA:
        raise A8EventGraphError("A8_PLANNER_SOURCE_SCHEMA_INVALID")
    source_text = planner_source["source_text"]
    if sha256_bytes(source_text.encode("utf-8")) != planner_source["source_body_sha256"]:
        raise A8EventGraphError("A8_SOURCE_BODY_SHA_MISMATCH")
    payload = dict(planner_source)
    actual = payload.pop("projection_payload_sha256")
    if sha256_bytes(canonical_bytes(payload)) != actual:
        raise A8EventGraphError("A8_PLANNER_SOURCE_PAYLOAD_SHA_MISMATCH")
    _reject_forbidden_keys(
        planner_source,
        contract["forbidden_field_names_or_prefixes"],
    )


_CLAUSE_SEPARATORS = "，,；;：:。！？!?“”\""
_LEADING_DISCOURSE = (
    "不过",
    "然而",
    "可是",
    "但是",
    "因此",
    "所以",
    "于是",
    "而且",
    "并且",
    "这时",
    "此时",
    "现在",
    "但",
    "而",
)


def _actor_bounds(
    sentence_text: str,
    *,
    sentence_start: int,
    marker_local_start: int,
) -> tuple[int, int] | None:
    left = sentence_text[:marker_local_start]
    boundary = max((left.rfind(char) for char in _CLAUSE_SEPARATORS), default=-1)
    local_start = boundary + 1
    candidate = left[local_start:]
    stripped_left = len(candidate) - len(candidate.lstrip())
    candidate = candidate.lstrip()
    local_start += stripped_left
    changed = True
    while changed:
        changed = False
        for token in _LEADING_DISCOURSE:
            if candidate.startswith(token):
                candidate = candidate[len(token) :].lstrip()
                local_start = marker_local_start - len(candidate)
                changed = True
                break
    candidate = candidate.rstrip()
    if not candidate:
        return None
    if len(candidate) > 12:
        candidate = candidate[-12:]
    local_end = marker_local_start
    local_start = local_end - len(candidate)
    if local_start < 0 or local_start >= local_end:
        return None
    return sentence_start + local_start, sentence_start + local_end


def _assertion_mode(event_type: str, marker: str) -> str:
    if marker in {"听说", "据说"}:
        return "HEARSAY"
    if marker in {"猜测", "可能", "似乎", "怀疑"}:
        return "GUESSED"
    if marker in {"认为", "相信", "误以为"}:
        return "BELIEVED"
    if marker in {"告诉", "承认", "坦白", "答应", "保证", "约定"}:
        return "SPOKEN"
    if event_type == "BELIEF_OR_HEARSAY":
        return "UNCERTAIN"
    return "NARRATED"


def _polarity(sentence_text: str, marker_local_start: int) -> str:
    local = sentence_text[max(0, marker_local_start - 2) : marker_local_start]
    if any(token in local for token in ("不", "没", "未", "无")):
        return "NEGATED"
    return "UNSPECIFIED"


def _add_unique(rows: dict[str, dict[str, Any]], row: dict[str, Any]) -> None:
    existing = rows.setdefault(row["node_id"], row)
    if existing != row:
        raise A8EventGraphError(f"A8_NODE_ID_COLLISION:{row['node_id']}")


def _ordinary_event_rows(
    *,
    sentence: Mapping[str, Any],
    planner_source: Mapping[str, Any],
    spec: Mapping[str, Any],
    marker: str,
    marker_local_start: int,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]] | None:
    sentence_start = int(sentence["char_start"])
    sentence_end = int(sentence["char_end_exclusive"])
    actor_bounds = _actor_bounds(
        sentence["original_text"],
        sentence_start=sentence_start,
        marker_local_start=marker_local_start,
    )
    marker_start = sentence_start + marker_local_start
    marker_end = marker_start + len(marker)
    if actor_bounds is None or marker_end >= sentence_end:
        return None
    actor_span = _span(
        planner_source=planner_source,
        paragraph_id=sentence["paragraph_id"],
        sentence_id=sentence["sentence_id"],
        start=actor_bounds[0],
        end=actor_bounds[1],
    )
    predicate_span = _span(
        planner_source=planner_source,
        paragraph_id=sentence["paragraph_id"],
        sentence_id=sentence["sentence_id"],
        start=marker_start,
        end=marker_end,
    )
    content_span = _span(
        planner_source=planner_source,
        paragraph_id=sentence["paragraph_id"],
        sentence_id=sentence["sentence_id"],
        start=marker_start,
        end=sentence_end,
    )
    query_span = _span(
        planner_source=planner_source,
        paragraph_id=sentence["paragraph_id"],
        sentence_id=sentence["sentence_id"],
        start=sentence_start,
        end=sentence_end,
    )
    mention_id = _stable_id(
        "MN",
        planner_source["source_id"],
        actor_span["char_start"],
        actor_span["char_end_exclusive"],
    )
    event_id = _stable_id(
        "EV",
        planner_source["source_id"],
        spec["event_type"],
        predicate_span["char_start"],
        predicate_span["char_end_exclusive"],
    )
    proposition_id = _stable_id(
        "PR",
        planner_source["source_id"],
        spec["event_type"],
        content_span["char_start"],
        content_span["char_end_exclusive"],
    )
    nodes = [
        {
            "node_id": mention_id,
            "kind": "MENTION",
            "mention_type": "EXPLICIT_SURFACE_CANDIDATE",
            "evidence_spans": [actor_span],
            "rule_ids": ["MENTION_BEFORE_PREDICATE_SAME_CLAUSE_V1"],
            "status": "CANDIDATE_NOT_ANSWER",
        },
        {
            "node_id": event_id,
            "kind": "EVENT",
            "event_type": spec["event_type"],
            "predicate_span": predicate_span,
            "query_span": query_span,
            "polarity": _polarity(sentence["original_text"], marker_local_start),
            "assertion_mode": _assertion_mode(spec["event_type"], marker),
            "resolution_status": (
                "OPEN"
                if spec["event_type"] == "UNRESOLVED_OR_RISK"
                else "UNSPECIFIED"
            ),
            "rule_ids": [f"EVENT_MARKER_EXPLICIT_V1:{marker}"],
            "status": "CANDIDATE_NOT_ANSWER",
        },
        {
            "node_id": proposition_id,
            "kind": "PROPOSITION",
            "proposition_type": f"{spec['event_type']}_CONTENT_CANDIDATE",
            "evidence_spans": [content_span],
            "polarity": _polarity(sentence["original_text"], marker_local_start),
            "assertion_mode": _assertion_mode(spec["event_type"], marker),
            "resolution_status": (
                "OPEN"
                if spec["event_type"] == "UNRESOLVED_OR_RISK"
                else "UNSPECIFIED"
            ),
            "rule_ids": [f"CONTENT_AFTER_PREDICATE_V1:{marker}"],
            "status": "CANDIDATE_NOT_ANSWER",
        },
    ]
    edges = []
    for relation, from_id in (
        (spec["actor_edge"], mention_id),
        ("CONTENT_OF", proposition_id),
    ):
        edge_id = _stable_id(
            "ED",
            planner_source["source_id"],
            relation,
            from_id,
            event_id,
        )
        edges.append(
            {
                "edge_id": edge_id,
                "from_node_id": from_id,
                "to_node_id": event_id,
                "relation": relation,
                "directed": True,
                "inverse_not_implied": True,
                "evidence_spans": [query_span],
                "rule_id": f"EDGE_{relation}_SAME_SENTENCE_V1",
                "status": "CANDIDATE_NOT_ANSWER",
            }
        )
    return nodes, edges


def _causal_rows(
    *,
    sentence: Mapping[str, Any],
    planner_source: Mapping[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    text = sentence["original_text"]
    sentence_start = int(sentence["char_start"])
    pairs: list[tuple[int, int, int, int, str]] = []
    because = text.find("因为")
    so = text.find("所以", because + 2) if because >= 0 else -1
    if because >= 0 and so > because + 2:
        pairs.append((because + 2, so, so + 2, len(text), "因为...所以"))
    for connector in ("因此", "导致", "于是", "结果"):
        start = text.find(connector)
        if start > 0 and start + len(connector) < len(text):
            pairs.append((0, start, start + len(connector), len(text), connector))
    nodes_by_id: dict[str, dict[str, Any]] = {}
    edges: list[dict[str, Any]] = []
    for cause_start, cause_end, result_start, result_end, connector in pairs:
        try:
            cause_span = _span(
                planner_source=planner_source,
                paragraph_id=sentence["paragraph_id"],
                sentence_id=sentence["sentence_id"],
                start=sentence_start + cause_start,
                end=sentence_start + cause_end,
            )
            result_span = _span(
                planner_source=planner_source,
                paragraph_id=sentence["paragraph_id"],
                sentence_id=sentence["sentence_id"],
                start=sentence_start + result_start,
                end=sentence_start + result_end,
            )
        except A8EventGraphError:
            continue
        query_span = _span(
            planner_source=planner_source,
            paragraph_id=sentence["paragraph_id"],
            sentence_id=sentence["sentence_id"],
            start=sentence_start,
            end=int(sentence["char_end_exclusive"]),
        )
        cause_id = _stable_id(
            "PR",
            planner_source["source_id"],
            "CAUSE",
            cause_span["char_start"],
            cause_span["char_end_exclusive"],
        )
        result_id = _stable_id(
            "PR",
            planner_source["source_id"],
            "RESULT",
            result_span["char_start"],
            result_span["char_end_exclusive"],
        )
        for node_id, proposition_type, span in (
            (cause_id, "CAUSE_CANDIDATE", cause_span),
            (result_id, "RESULT_CANDIDATE", result_span),
        ):
            _add_unique(
                nodes_by_id,
                {
                    "node_id": node_id,
                    "kind": "PROPOSITION",
                    "proposition_type": proposition_type,
                    "evidence_spans": [span],
                    "polarity": "UNSPECIFIED",
                    "assertion_mode": "NARRATED",
                    "resolution_status": "UNSPECIFIED",
                    "rule_ids": [f"EXPLICIT_CAUSAL_CLAUSE_V1:{connector}"],
                    "status": "CANDIDATE_NOT_ANSWER",
                },
            )
        edge_id = _stable_id(
            "ED",
            planner_source["source_id"],
            "CAUSES",
            cause_id,
            result_id,
        )
        edges.append(
            {
                "edge_id": edge_id,
                "from_node_id": cause_id,
                "to_node_id": result_id,
                "relation": "CAUSES",
                "event_type": "CAUSE_RESULT",
                "directed": True,
                "inverse_not_implied": True,
                "evidence_spans": [query_span],
                "rule_id": f"EDGE_CAUSES_EXPLICIT_SAME_SENTENCE_V1:{connector}",
                "status": "CANDIDATE_NOT_ANSWER",
            }
        )
    return list(nodes_by_id.values()), edges


def build_event_graph(
    planner_source: Mapping[str, Any], contract: Mapping[str, Any]
) -> dict[str, Any]:
    _verify_planner_source(planner_source, contract)
    nodes_by_id: dict[str, dict[str, Any]] = {}
    edges_by_id: dict[str, dict[str, Any]] = {}
    ordinary_specs = [
        row for row in contract["event_specs"] if row["event_type"] != "CAUSE_RESULT"
    ]
    for sentence in planner_source["sentences"]:
        sentence_text = sentence["original_text"]
        for spec in ordinary_specs:
            for marker in spec["markers"]:
                start = 0
                while True:
                    marker_start = sentence_text.find(marker, start)
                    if marker_start < 0:
                        break
                    rows = _ordinary_event_rows(
                        sentence=sentence,
                        planner_source=planner_source,
                        spec=spec,
                        marker=marker,
                        marker_local_start=marker_start,
                    )
                    if rows is not None:
                        nodes, edges = rows
                        for node in nodes:
                            _add_unique(nodes_by_id, node)
                        for edge in edges:
                            existing = edges_by_id.setdefault(edge["edge_id"], edge)
                            if existing != edge:
                                raise A8EventGraphError(
                                    f"A8_EDGE_ID_COLLISION:{edge['edge_id']}"
                                )
                    start = marker_start + len(marker)
        cause_nodes, cause_edges = _causal_rows(
            sentence=sentence,
            planner_source=planner_source,
        )
        for node in cause_nodes:
            _add_unique(nodes_by_id, node)
        for edge in cause_edges:
            existing = edges_by_id.setdefault(edge["edge_id"], edge)
            if existing != edge:
                raise A8EventGraphError(f"A8_EDGE_ID_COLLISION:{edge['edge_id']}")
    graph: dict[str, Any] = {
        "schema_version": GRAPH_SCHEMA,
        "source_id": planner_source["source_id"],
        "source_body_sha256": planner_source["source_body_sha256"],
        "planner_visible_source_sha256": planner_source[
            "projection_payload_sha256"
        ],
        "semantic_truth_verified_by_program": False,
        "completeness_claim": "NOT_SELF_CERTIFIED",
        "cardinality_policy": "UNKNOWN_OPEN_WORLD",
        "construction_policy": contract["construction_policy"],
        "nodes": sorted(nodes_by_id.values(), key=lambda row: row["node_id"]),
        "edges": sorted(edges_by_id.values(), key=lambda row: row["edge_id"]),
    }
    graph["graph_payload_sha256"] = sha256_bytes(canonical_bytes(graph))
    validate_event_graph(graph, planner_source=planner_source, contract=contract)
    return graph


def _verify_span(
    span: Mapping[str, Any],
    *,
    planner_source: Mapping[str, Any],
) -> None:
    allowed = {
        "source_id",
        "source_body_sha256",
        "paragraph_id",
        "sentence_id",
        "char_start",
        "char_end_exclusive",
        "surface_text",
        "surface_sha256",
    }
    if set(span) != allowed:
        raise A8EventGraphError("A8_EVIDENCE_SPAN_FIELDS_INVALID")
    if span["source_id"] != planner_source["source_id"]:
        raise A8EventGraphError("A8_EVIDENCE_SPAN_SOURCE_MISMATCH")
    if span["source_body_sha256"] != planner_source["source_body_sha256"]:
        raise A8EventGraphError("A8_EVIDENCE_SPAN_BODY_SHA_MISMATCH")
    start = int(span["char_start"])
    end = int(span["char_end_exclusive"])
    if start < 0 or end <= start or end > len(planner_source["source_text"]):
        raise A8EventGraphError("A8_EVIDENCE_SPAN_BOUNDS_INVALID")
    surface = planner_source["source_text"][start:end]
    if surface != span["surface_text"]:
        raise A8EventGraphError("A8_EVIDENCE_SPAN_REBUILD_MISMATCH")
    if sha256_bytes(surface.encode("utf-8")) != span["surface_sha256"]:
        raise A8EventGraphError("A8_EVIDENCE_SPAN_SHA_MISMATCH")
    sentence_rows = {
        row["sentence_id"]: row for row in planner_source["sentences"]
    }
    sentence = sentence_rows.get(span["sentence_id"])
    if sentence is None or sentence["paragraph_id"] != span["paragraph_id"]:
        raise A8EventGraphError("A8_EVIDENCE_SENTENCE_PARAGRAPH_MISMATCH")
    if start < sentence["char_start"] or end > sentence["char_end_exclusive"]:
        raise A8EventGraphError("A8_EVIDENCE_OUTSIDE_SENTENCE")


def validate_event_graph(
    graph: Mapping[str, Any],
    *,
    planner_source: Mapping[str, Any],
    contract: Mapping[str, Any],
) -> None:
    _verify_planner_source(planner_source, contract)
    allowed_top = {
        "schema_version",
        "source_id",
        "source_body_sha256",
        "planner_visible_source_sha256",
        "semantic_truth_verified_by_program",
        "completeness_claim",
        "cardinality_policy",
        "construction_policy",
        "nodes",
        "edges",
        "graph_payload_sha256",
    }
    if set(graph) != allowed_top or graph["schema_version"] != GRAPH_SCHEMA:
        raise A8EventGraphError("A8_GRAPH_FIELDS_OR_SCHEMA_INVALID")
    _reject_forbidden_keys(graph, contract["forbidden_field_names_or_prefixes"])
    payload = dict(graph)
    actual_payload_sha = payload.pop("graph_payload_sha256")
    if sha256_bytes(canonical_bytes(payload)) != actual_payload_sha:
        raise A8EventGraphError("A8_GRAPH_PAYLOAD_SHA_MISMATCH")
    if graph["source_id"] != planner_source["source_id"]:
        raise A8EventGraphError("A8_GRAPH_SOURCE_MISMATCH")
    if graph["source_body_sha256"] != planner_source["source_body_sha256"]:
        raise A8EventGraphError("A8_GRAPH_SOURCE_SHA_MISMATCH")
    if graph["semantic_truth_verified_by_program"] is not False:
        raise A8EventGraphError("A8_GRAPH_SEMANTIC_TRUTH_SELF_CLAIM")
    if graph["construction_policy"] != contract["construction_policy"]:
        raise A8EventGraphError("A8_GRAPH_CONSTRUCTION_POLICY_DRIFT")
    node_ids: set[str] = set()
    node_sentence: dict[str, tuple[str, str]] = {}
    for node in graph["nodes"]:
        node_kind = node.get("kind")
        expected_node_fields = {
            "MENTION": {
                "node_id",
                "kind",
                "mention_type",
                "evidence_spans",
                "rule_ids",
                "status",
            },
            "EVENT": {
                "node_id",
                "kind",
                "event_type",
                "predicate_span",
                "query_span",
                "polarity",
                "assertion_mode",
                "resolution_status",
                "rule_ids",
                "status",
            },
            "PROPOSITION": {
                "node_id",
                "kind",
                "proposition_type",
                "evidence_spans",
                "polarity",
                "assertion_mode",
                "resolution_status",
                "rule_ids",
                "status",
            },
        }.get(node_kind)
        if expected_node_fields is None or set(node) != expected_node_fields:
            raise A8EventGraphError("A8_GRAPH_NODE_FIELDS_INVALID")
        node_id = node.get("node_id")
        if not node_id or node_id in node_ids:
            raise A8EventGraphError("A8_GRAPH_NODE_ID_INVALID")
        node_ids.add(node_id)
        spans: list[Mapping[str, Any]] = []
        if node_kind == "EVENT":
            if node["polarity"] not in contract["state_axes"]["polarity"]:
                raise A8EventGraphError("A8_GRAPH_POLARITY_INVALID")
            if (
                node["assertion_mode"]
                not in contract["state_axes"]["assertion_mode"]
            ):
                raise A8EventGraphError("A8_GRAPH_ASSERTION_MODE_INVALID")
            if (
                node["resolution_status"]
                not in contract["state_axes"]["resolution_status"]
            ):
                raise A8EventGraphError("A8_GRAPH_RESOLUTION_STATUS_INVALID")
            spans.extend([node["predicate_span"], node["query_span"]])
        else:
            spans.extend(node["evidence_spans"])
            if node_kind == "PROPOSITION":
                if node["polarity"] not in contract["state_axes"]["polarity"]:
                    raise A8EventGraphError("A8_GRAPH_POLARITY_INVALID")
                if (
                    node["assertion_mode"]
                    not in contract["state_axes"]["assertion_mode"]
                ):
                    raise A8EventGraphError("A8_GRAPH_ASSERTION_MODE_INVALID")
                if (
                    node["resolution_status"]
                    not in contract["state_axes"]["resolution_status"]
                ):
                    raise A8EventGraphError(
                        "A8_GRAPH_RESOLUTION_STATUS_INVALID"
                    )
        for span in spans:
            _verify_span(span, planner_source=planner_source)
        first = spans[0]
        node_sentence[node_id] = (first["paragraph_id"], first["sentence_id"])
    edge_ids: set[str] = set()
    for edge in graph["edges"]:
        expected_edge_fields = {
            "edge_id",
            "from_node_id",
            "to_node_id",
            "relation",
            "directed",
            "inverse_not_implied",
            "evidence_spans",
            "rule_id",
            "status",
        }
        if edge.get("relation") == "CAUSES":
            expected_edge_fields = {*expected_edge_fields, "event_type"}
        if set(edge) != expected_edge_fields:
            raise A8EventGraphError("A8_GRAPH_EDGE_FIELDS_INVALID")
        edge_id = edge.get("edge_id")
        if not edge_id or edge_id in edge_ids:
            raise A8EventGraphError("A8_GRAPH_EDGE_ID_INVALID")
        edge_ids.add(edge_id)
        if edge["relation"] not in contract["edge_relations"]:
            raise A8EventGraphError("A8_GRAPH_EDGE_RELATION_INVALID")
        if edge["from_node_id"] not in node_ids or edge["to_node_id"] not in node_ids:
            raise A8EventGraphError("A8_GRAPH_EDGE_ENDPOINT_MISSING")
        if edge["directed"] is not True or edge["inverse_not_implied"] is not True:
            raise A8EventGraphError("A8_GRAPH_EDGE_DIRECTION_INVALID")
        for span in edge["evidence_spans"]:
            _verify_span(span, planner_source=planner_source)
        left = node_sentence[edge["from_node_id"]]
        right = node_sentence[edge["to_node_id"]]
        if left != right:
            raise A8EventGraphError("A8_GRAPH_CROSS_SENTENCE_EDGE_FORBIDDEN")


def compile_event_queries(
    *,
    question: Mapping[str, str],
    graph: Mapping[str, Any],
    contract: Mapping[str, Any],
) -> dict[str, Any]:
    matching_specs = [
        spec
        for spec in contract["event_specs"]
        if any(trigger in question["question_text"] for trigger in spec["question_triggers"])
    ]
    intents = [row["event_type"] for row in matching_specs]
    spec_by_type = {row["event_type"]: row for row in matching_specs}
    edges_by_target: dict[str, list[Mapping[str, Any]]] = {}
    for edge in graph["edges"]:
        edges_by_target.setdefault(edge["to_node_id"], []).append(edge)
    candidates: list[dict[str, Any]] = []
    rejected: list[dict[str, str]] = []
    for node in graph["nodes"]:
        if node["kind"] != "EVENT" or node["event_type"] not in spec_by_type:
            continue
        direct_edges = edges_by_target.get(node["node_id"], [])
        relations = {row["relation"] for row in direct_edges}
        required = set(spec_by_type[node["event_type"]]["required_relations"])
        if not required.issubset(relations):
            rejected.append(
                {
                    "node_id": node["node_id"],
                    "reason": "REQUIRED_RELATION_SIGNATURE_MISSING",
                }
            )
            continue
        candidates.append(
            {
                "query_text": node["query_span"]["surface_text"],
                "origin_kind": "EVENT_GRAPH_EXACT_RELATION_SPAN",
                "source_span": node["query_span"],
                "origin_node_ids": sorted(
                    {node["node_id"], *[row["from_node_id"] for row in direct_edges]}
                ),
                "origin_edge_ids": sorted(row["edge_id"] for row in direct_edges),
                "relation_signature": sorted(relations),
                "status": "CANDIDATE_NOT_ANSWER",
            }
        )
    if "CAUSE_RESULT" in spec_by_type:
        for edge in graph["edges"]:
            if edge["relation"] != "CAUSES":
                continue
            candidates.append(
                {
                    "query_text": edge["evidence_spans"][0]["surface_text"],
                    "origin_kind": "EVENT_GRAPH_EXACT_RELATION_SPAN",
                    "source_span": edge["evidence_spans"][0],
                    "origin_node_ids": sorted(
                        [edge["from_node_id"], edge["to_node_id"]]
                    ),
                    "origin_edge_ids": [edge["edge_id"]],
                    "relation_signature": ["CAUSES"],
                    "status": "CANDIDATE_NOT_ANSWER",
                }
            )
    candidates.sort(
        key=lambda row: (
            row["source_span"]["paragraph_id"],
            row["source_span"]["char_start"],
            row["source_span"]["char_end_exclusive"],
            row["relation_signature"],
            row["origin_node_ids"],
        )
    )
    deduped: list[dict[str, Any]] = []
    seen_text: set[str] = set()
    for row in candidates:
        if row["query_text"] in seen_text:
            continue
        seen_text.add(row["query_text"])
        deduped.append(row)
    for index, row in enumerate(deduped, start=1):
        row["query_id"] = f"EGQ-{index:04d}"
    trigger: dict[str, Any] = {
        "schema_version": TRIGGER_SCHEMA,
        "route_id": "A8",
        "case_id": graph["source_id"],
        "question_id": question["question_id"],
        "question_text_sha256": sha256_bytes(
            question["question_text"].encode("utf-8")
        ),
        "event_graph_sha256": graph["graph_payload_sha256"],
        "intent_ids": intents,
        "traversal_policy": "DIRECT_EDGES_ONLY_NO_TRANSITIVE_CLOSURE",
        "triggered_node_ids": sorted(
            {item for row in deduped for item in row["origin_node_ids"]}
        ),
        "triggered_edge_ids": sorted(
            {item for row in deduped for item in row["origin_edge_ids"]}
        ),
        "rejected_candidates": sorted(
            rejected, key=lambda row: (row["node_id"], row["reason"])
        ),
        "query_candidates": deduped,
    }
    trigger["trigger_payload_sha256"] = sha256_bytes(canonical_bytes(trigger))
    return trigger


def build_a8_query_map(
    *,
    case_id: str,
    question_id: str,
    a5_queries: Sequence[str],
    trigger: Mapping[str, Any],
) -> dict[str, Any]:
    queries = [
        {
            "query_id": f"QRY-{index:03d}",
            "query_text": query_text,
            "origin_kind": "A5_FROZEN_PREFIX",
        }
        for index, query_text in enumerate(a5_queries, start=1)
    ]
    a5_texts = set(a5_queries)
    event_queries = [
        row for row in trigger["query_candidates"] if row["query_text"] not in a5_texts
    ]
    queries.extend(event_queries)
    result = {
        "schema_version": QUERY_MAP_SCHEMA,
        "route_id": "A8",
        "case_id": case_id,
        "question_id": question_id,
        "a5_prefix_count": len(a5_queries),
        "event_query_count": len(event_queries),
        "queries": queries,
    }
    if [row["query_text"] for row in queries[: len(a5_queries)]] != list(a5_queries):
        raise A8EventGraphError("A8_A5_QUERY_PREFIX_DRIFT")
    if not event_queries and [row["query_text"] for row in queries] != list(a5_queries):
        raise A8EventGraphError("A8_ZERO_TRIGGER_NOT_A5_EXACT")
    return result

from __future__ import annotations

import re
import shlex
from dataclasses import dataclass

from .model import (
    Connection,
    Diagram,
    Lane,
    Node,
    Shape,
    canonical_symbol_id,
    normalize_identifier,
)

_CONNECTION_WITH_PIPE_LABEL = re.compile(
    r"(?P<src>[A-Za-z_][A-Za-z0-9_-]*)\s*-->\s*\|(?P<label>[^|]+)\|\s*(?P<tgt>[A-Za-z_][A-Za-z0-9_-]*)"
)
_CONNECTION_WITH_OPTIONAL_SUFFIX_LABEL = re.compile(
    r"(?P<src>[A-Za-z_][A-Za-z0-9_-]*)\s*-->\s*(?P<tgt>[A-Za-z_][A-Za-z0-9_-]*)(?:\s*:\s*(?P<label>.+))?"
)


class DiagramSyntaxError(ValueError):
    def __init__(
        self, message: str, line_no: int | None = None, line_text: str | None = None
    ) -> None:
        self.message = message
        self.line_no = line_no
        self.line_text = line_text
        super().__init__(self.__str__())

    def __str__(self) -> str:
        if self.line_no is None:
            return self.message
        excerpt = self.line_text.strip() if self.line_text else ""
        if excerpt:
            return f"Line {self.line_no}: {self.message} -> {excerpt}"
        return f"Line {self.line_no}: {self.message}"


@dataclass(slots=True, frozen=True)
class _ParsedNode:
    node_id: str
    lane_ref: str
    shape: Shape
    text: str


def parse_diagram(source: str) -> Diagram:
    title = ""
    lanes: list[Lane] = []
    nodes: list[Node] = []
    connections: list[Connection] = []

    # phases: 0 = lane declarations, 1 = nodes, 2 = connections
    phase = 0

    lane_id_lookup: dict[str, str] = {}
    lane_ref_lookup: dict[str, str] = {}
    node_lookup: dict[str, Node] = {}

    for line_no, raw_line in enumerate(source.splitlines(), start=1):
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith("%%") or line.startswith("#"):
            continue

        lowered = line.lower()
        if lowered in {"swimlanediagram", "swimlane", "swimlane_flow"}:
            continue

        keyword = lowered.split(maxsplit=1)[0]

        if keyword == "title":
            title = _parse_title(line, line_no, raw_line)
            continue

        if keyword == "lane":
            if phase > 0:
                raise DiagramSyntaxError(
                    "Lane declarations must come before node and connection declarations.",
                    line_no,
                    raw_line,
                )
            lane_id, lane_title = _parse_lane(
                line, line_no, raw_line, lane_index=len(lanes)
            )
            if lane_id in lane_id_lookup:
                raise DiagramSyntaxError(
                    f"Duplicate lane id '{lane_id}'.", line_no, raw_line
                )
            lane = Lane(id=lane_id, title=lane_title, index=len(lanes))
            lanes.append(lane)
            lane_id_lookup[lane.id] = lane.id
            lane_ref_lookup[lane.id] = lane.id
            lane_ref_lookup[lane.title.casefold()] = lane.id
            normalized_title = normalize_identifier(lane.title)
            if normalized_title:
                lane_ref_lookup[normalized_title] = lane.id
            continue

        if keyword == "node":
            if not lanes:
                raise DiagramSyntaxError(
                    "Define at least one lane before nodes.", line_no, raw_line
                )
            if phase == 2:
                raise DiagramSyntaxError(
                    "Node declarations must come before connection declarations.",
                    line_no,
                    raw_line,
                )
            phase = 1
            parsed_node = _parse_node(line, line_no, raw_line)
            lane_id = _resolve_lane_ref(parsed_node.lane_ref, lane_ref_lookup)
            if lane_id is None:
                raise DiagramSyntaxError(
                    f"Unknown lane reference '{parsed_node.lane_ref}' for node '{parsed_node.node_id}'.",
                    line_no,
                    raw_line,
                )
            if parsed_node.node_id in node_lookup:
                raise DiagramSyntaxError(
                    f"Duplicate node id '{parsed_node.node_id}'.", line_no, raw_line
                )

            node = Node(
                id=parsed_node.node_id,
                lane_id=lane_id,
                shape=parsed_node.shape,
                text=parsed_node.text,
                order=len(nodes),
            )
            nodes.append(node)
            node_lookup[node.id] = node
            continue

        if keyword == "connect" or "-->" in line:
            if not nodes:
                raise DiagramSyntaxError(
                    "Define nodes before connection declarations.",
                    line_no,
                    raw_line,
                )
            phase = 2
            connection = _parse_connection(line, line_no, raw_line)
            if connection.source not in node_lookup:
                raise DiagramSyntaxError(
                    f"Connection source node '{connection.source}' does not exist.",
                    line_no,
                    raw_line,
                )
            if connection.target not in node_lookup:
                raise DiagramSyntaxError(
                    f"Connection target node '{connection.target}' does not exist.",
                    line_no,
                    raw_line,
                )
            connections.append(connection)
            continue

        raise DiagramSyntaxError(
            "Unknown statement. Use: title, lane, node, connect, or Mermaid-style 'A --> B'.",
            line_no,
            raw_line,
        )

    if not lanes:
        raise DiagramSyntaxError("Diagram must declare at least one lane.")
    if not nodes:
        raise DiagramSyntaxError("Diagram must declare at least one node.")

    return Diagram(title=title, lanes=lanes, nodes=nodes, connections=connections)


def _split_tokens(line: str, line_no: int, raw_line: str) -> list[str]:
    try:
        return shlex.split(line, comments=False, posix=True)
    except ValueError as exc:
        raise DiagramSyntaxError(
            f"Cannot parse line: {exc}", line_no, raw_line
        ) from exc


def _strip_matching_quotes(value: str) -> str:
    text = value.strip()
    if len(text) >= 2 and text[0] == text[-1] and text[0] in {'"', "'"}:
        return text[1:-1].strip()
    return text


def _parse_title(line: str, line_no: int, raw_line: str) -> str:
    text = line[len("title") :].strip()
    if text.startswith(":"):
        text = text[1:].strip()
    text = _strip_matching_quotes(text)
    if not text:
        raise DiagramSyntaxError("Title cannot be empty.", line_no, raw_line)
    return text


def _parse_lane(
    line: str, line_no: int, raw_line: str, lane_index: int
) -> tuple[str, str]:
    tokens = _split_tokens(line, line_no, raw_line)
    if len(tokens) < 2:
        raise DiagramSyntaxError("Lane statement is incomplete.", line_no, raw_line)

    if len(tokens) == 2:
        candidate = tokens[1]
        if _is_symbol(candidate):
            lane_id = canonical_symbol_id(candidate, kind="Lane id")
            lane_title = candidate
        else:
            lane_id = f"lane_{lane_index + 1}"
            lane_title = candidate
        return lane_id, lane_title

    lane_id = canonical_symbol_id(tokens[1], kind="Lane id")
    lane_title = " ".join(tokens[2:]).strip()
    if not lane_title:
        lane_title = tokens[1]
    return lane_id, lane_title


def _parse_node(line: str, line_no: int, raw_line: str) -> _ParsedNode:
    tokens = _split_tokens(line, line_no, raw_line)
    if len(tokens) < 5:
        raise DiagramSyntaxError(
            "Node syntax must be: node <id> in <lane> [shape] <text>.",
            line_no,
            raw_line,
        )
    if tokens[2].lower() != "in":
        raise DiagramSyntaxError(
            "Expected keyword 'in' in node declaration.", line_no, raw_line
        )

    node_id = canonical_symbol_id(tokens[1], kind="Node id")
    lane_ref = tokens[3]
    remainder = tokens[4:]

    shape = Shape.PROCESS
    first_token = remainder[0]
    if _looks_like_shape_token(first_token):
        parsed_shape = Shape.try_parse(first_token)
        if parsed_shape is None:
            raise DiagramSyntaxError(
                f"Unknown shape '{first_token}'. Allowed: process, decision, subprocess, start/end, document, data.",
                line_no,
                raw_line,
            )
        shape = parsed_shape
        remainder = remainder[1:]

    if not remainder:
        raise DiagramSyntaxError("Node text cannot be empty.", line_no, raw_line)

    text = " ".join(remainder).strip()
    if not text:
        raise DiagramSyntaxError("Node text cannot be empty.", line_no, raw_line)

    return _ParsedNode(node_id=node_id, lane_ref=lane_ref, shape=shape, text=text)


def _parse_connection(line: str, line_no: int, raw_line: str) -> Connection:
    connection_line = line.strip()
    if connection_line.lower().startswith("connect "):
        connection_line = connection_line.split(maxsplit=1)[1].strip()

    match = _CONNECTION_WITH_PIPE_LABEL.fullmatch(connection_line)
    if match:
        source = canonical_symbol_id(match.group("src"), kind="Node id")
        target = canonical_symbol_id(match.group("tgt"), kind="Node id")
        label = match.group("label").strip()
        return Connection(source=source, target=target, label=label or None)

    match = _CONNECTION_WITH_OPTIONAL_SUFFIX_LABEL.fullmatch(connection_line)
    if match:
        source = canonical_symbol_id(match.group("src"), kind="Node id")
        target = canonical_symbol_id(match.group("tgt"), kind="Node id")
        label_raw = match.group("label")
        label = label_raw.strip() if label_raw else None
        return Connection(source=source, target=target, label=label or None)

    raise DiagramSyntaxError(
        "Invalid connection syntax. Use 'connect A --> B', 'A -->|label| B', or 'A --> B : label'.",
        line_no,
        raw_line,
    )


def _resolve_lane_ref(lane_ref: str, lane_ref_lookup: dict[str, str]) -> str | None:
    exact_key = lane_ref.casefold()
    if exact_key in lane_ref_lookup:
        return lane_ref_lookup[exact_key]

    normalized = normalize_identifier(lane_ref)
    if normalized and normalized in lane_ref_lookup:
        return lane_ref_lookup[normalized]

    return None


def _looks_like_shape_token(token: str) -> bool:
    stripped = token.strip()
    if stripped.startswith("[") and stripped.endswith("]"):
        return True
    return Shape.try_parse(stripped) is not None


def _is_symbol(value: str) -> bool:
    return bool(re.fullmatch(r"[A-Za-z_][A-Za-z0-9_-]*", value.strip()))

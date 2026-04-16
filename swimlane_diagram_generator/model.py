from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
import re

_SYMBOL_ID_PATTERN = re.compile(r"[A-Za-z_][A-Za-z0-9_-]*")


def canonical_symbol_id(raw: str, *, kind: str) -> str:
    candidate = raw.strip()
    if not _SYMBOL_ID_PATTERN.fullmatch(candidate):
        raise ValueError(
            f"{kind} '{raw}' is invalid. Use letters, numbers, '_' or '-' and do not start with a number."
        )
    return candidate.lower()


def normalize_identifier(raw: str) -> str:
    value = raw.strip().lower()
    value = value.replace("-", "_").replace("/", "_")
    value = re.sub(r"\s+", "_", value)
    value = re.sub(r"[^a-z0-9_]", "", value)
    value = re.sub(r"_+", "_", value).strip("_")
    return value


def _normalize_shape_token(token: str) -> str:
    cleaned = token.strip()
    if cleaned.startswith("[") and cleaned.endswith("]"):
        cleaned = cleaned[1:-1]
    return normalize_identifier(cleaned)


class Shape(StrEnum):
    PROCESS = "process"
    DECISION = "decision"
    SUBPROCESS = "subprocess"
    START_END = "start_end"
    DOCUMENT = "document"
    DATA = "data"

    @classmethod
    def try_parse(cls, token: str) -> Shape | None:
        normalized = _normalize_shape_token(token)
        return _SHAPE_ALIASES.get(normalized)

    @classmethod
    def parse(cls, token: str) -> Shape:
        parsed = cls.try_parse(token)
        if parsed is None:
            raise ValueError(f"Unknown shape '{token}'.")
        return parsed


_SHAPE_ALIASES: dict[str, Shape] = {
    "process": Shape.PROCESS,
    "decision": Shape.DECISION,
    "subprocess": Shape.SUBPROCESS,
    "sub_process": Shape.SUBPROCESS,
    "predefined_process": Shape.SUBPROCESS,
    "start_end": Shape.START_END,
    "startend": Shape.START_END,
    "start": Shape.START_END,
    "end": Shape.START_END,
    "terminal": Shape.START_END,
    "document": Shape.DOCUMENT,
    "data": Shape.DATA,
    "input_output": Shape.DATA,
    "io": Shape.DATA,
}


@dataclass(slots=True, frozen=True)
class Lane:
    id: str
    title: str
    index: int


@dataclass(slots=True, frozen=True)
class Node:
    id: str
    lane_id: str
    shape: Shape
    text: str
    order: int


@dataclass(slots=True, frozen=True)
class Connection:
    source: str
    target: str
    label: str | None = None


@dataclass(slots=True)
class Diagram:
    title: str
    lanes: list[Lane]
    nodes: list[Node]
    connections: list[Connection]

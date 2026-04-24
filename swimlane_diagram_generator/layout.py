# swimlane_diagram_generator/layout.py
from __future__ import annotations

from dataclasses import dataclass

from .model import Shape


@dataclass(slots=True, frozen=True)
class NodeBox:
    node_id: str
    lane_index: int
    shape: Shape
    text: str
    x: float
    y: float
    width: float
    height: float


@dataclass(slots=True, frozen=True)
class LabelBox:
    connection_index: int
    x: float
    y: float
    width: float
    height: float
    text_lines: tuple[str, ...]
    segment_index: int


@dataclass(slots=True, frozen=True)
class LabelStem:
    connection_index: int
    start: tuple[float, float]
    end: tuple[float, float]


@dataclass(slots=True)
class RenderGlobalConfig:
    min_line_gap: float = 12.0


GLOBAL_RENDER_CONFIG = RenderGlobalConfig()


def set_global_min_line_gap(min_line_gap: float) -> None:
    GLOBAL_RENDER_CONFIG.min_line_gap = max(4.0, float(min_line_gap))


def get_global_min_line_gap() -> float:
    return GLOBAL_RENDER_CONFIG.min_line_gap


def snap_to_grid(value: float, grid_size: float) -> float:
    if grid_size <= 0.0:
        return value
    return round(value / grid_size) * grid_size


def _expand_even_grid_units(width_units: int, height_units: int) -> tuple[int, int]:
    if width_units % 2:
        width_units += 1
    if height_units % 2:
        height_units += 1
    return width_units, height_units


def _shape_grid_size(shape: Shape) -> tuple[int, int]:
    if shape is Shape.DECISION:
        return 4, 4
    if shape is Shape.DOCUMENT:
        return 4, 4
    return 4, 4

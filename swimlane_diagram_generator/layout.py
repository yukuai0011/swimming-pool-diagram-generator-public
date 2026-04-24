# swimlane_diagram_generator/layout.py
from __future__ import annotations

from dataclasses import dataclass

from .model import Diagram, Shape


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


@dataclass(slots=True, frozen=True)
class RouteHint:
    cross_slot: int = 0
    same_slot: int = 0
    start_offset: float = 0.0
    end_offset: float = 0.0
    cross_y_offset: float = 0.0


@dataclass(slots=True, frozen=True)
class LineJump:
    line_index: int
    x: float
    y: float
    orientation: str


@dataclass(slots=True, frozen=True)
class ConnectionLayout:
    connection_index: int
    points: tuple[tuple[float, float], ...]
    label_box: LabelBox | None = None
    stem: LabelStem | None = None


@dataclass(slots=True, frozen=True)
class ResolvedLayout:
    grid_size: float
    chart_x: float
    chart_y: float
    chart_width: float
    chart_height: float
    title_height: float
    lane_header_height: float
    lane_body_y: float
    body_height: float
    lane_width: float
    boxes: dict[str, NodeBox]
    connections: tuple[ConnectionLayout, ...]
    line_jumps: tuple[LineJump, ...]


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


def iter_layout_coordinates(layout: ResolvedLayout):
    """Yield all coordinate values from a resolved layout for testing."""
    yield layout.chart_x
    yield layout.chart_y
    yield layout.chart_width
    yield layout.chart_height
    yield layout.title_height
    yield layout.lane_header_height
    yield layout.lane_body_y
    yield layout.body_height
    yield layout.lane_width
    for box in layout.boxes.values():
        yield box.x
        yield box.y
        yield box.width
        yield box.height
    for connection in layout.connections:
        for x, y in connection.points:
            yield x
            yield y
        if connection.label_box is not None:
            yield connection.label_box.x
            yield connection.label_box.y
            yield connection.label_box.width
            yield connection.label_box.height
        if connection.stem is not None:
            yield connection.stem.start[0]
            yield connection.stem.start[1]
            yield connection.stem.end[0]
            yield connection.stem.end[1]


def build_layout(diagram: Diagram) -> ResolvedLayout:
    """Build a resolved layout from a diagram.

    This is a placeholder that will be implemented in subsequent subtasks.
    """
    raise NotImplementedError("build_layout() will be implemented in Task 2b")

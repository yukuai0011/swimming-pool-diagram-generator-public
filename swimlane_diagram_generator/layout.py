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

    This implementation wraps the existing renderer_svg layout logic.
    Future refactoring will move the internal functions into this module.
    """
    # Import here to avoid circular dependency during transition
    from .renderer_svg import (
        _assign_vertical_slots,
        _build_boxes,
        _build_connection_paths,
        _compute_lane_width,
        _compute_line_jumps,
        _compute_node_dimensions,
        _grid_size,
        _lane_borders_x,
        _resolve_layout_tuning,
        _snap_to_grid,
    )

    if not diagram.lanes:
        raise ValueError("Cannot render diagram without lanes.")
    if not diagram.nodes:
        raise ValueError("Cannot render diagram without nodes.")

    lane_count = len(diagram.lanes)
    lane_index_by_id = {lane.id: lane.index for lane in diagram.lanes}
    slot_by_node, slot_count = _assign_vertical_slots(diagram, lane_index_by_id)
    node_dimensions = _compute_node_dimensions(diagram, lane_index_by_id, slot_by_node)
    grid_size = _grid_size()

    # Use full-grid snapping (half=False) for the new layout
    chart_x = snap_to_grid(max(24.0, grid_size * 2.0), grid_size)
    chart_y = snap_to_grid(max(24.0, grid_size * 2.0), grid_size)
    lane_width = _compute_lane_width(
        diagram,
        lane_index_by_id,
        node_dimensions=node_dimensions,
    )
    title_height = snap_to_grid(48.0 if diagram.title else 36.0, grid_size)
    lane_header_height = snap_to_grid(48.0, grid_size)

    first_row_offset = snap_to_grid(max(60.0, grid_size * 4.0), grid_size)
    max_node_height = max((size[1] for size in node_dimensions.values()), default=74.0)
    row_gap = snap_to_grid(
        max(108.0, max_node_height + grid_size * 2.0),
        grid_size,
    )
    body_height = max(
        320.0,
        first_row_offset + max(slot_count - 1, 0) * row_gap + max_node_height + 60.0,
    )
    body_height = snap_to_grid(body_height, grid_size)

    lane_body_y = snap_to_grid(chart_y + title_height + lane_header_height, grid_size)
    lane_width, incident_step, cross_y_step = _resolve_layout_tuning(
        diagram,
        lane_index_by_id,
        slot_by_node,
        lane_width,
        lane_body_y,
        first_row_offset,
        row_gap,
        node_dimensions=node_dimensions,
    )

    chart_width = snap_to_grid(lane_count * lane_width, grid_size)
    chart_height = snap_to_grid(
        title_height + lane_header_height + body_height,
        grid_size,
    )

    boxes = _build_boxes(
        diagram,
        lane_index_by_id,
        slot_by_node,
        lane_width,
        chart_x,
        lane_body_y,
        first_row_offset,
        row_gap,
        node_dimensions=node_dimensions,
    )
    lane_borders_x = _lane_borders_x(chart_x, lane_width, lane_count)
    connection_paths = _build_connection_paths(
        diagram,
        boxes,
        lane_index_by_id,
        incident_step=incident_step,
        cross_y_step=cross_y_step,
        lane_borders_x=lane_borders_x,
    )

    line_jumps = _compute_line_jumps(connection_paths)

    # Convert to ConnectionLayout tuples
    connections = tuple(
        ConnectionLayout(connection_index=index, points=tuple(path))
        for index, path in enumerate(connection_paths)
    )

    return ResolvedLayout(
        grid_size=grid_size,
        chart_x=chart_x,
        chart_y=chart_y,
        chart_width=chart_width,
        chart_height=chart_height,
        title_height=title_height,
        lane_header_height=lane_header_height,
        lane_body_y=lane_body_y,
        body_height=body_height,
        lane_width=lane_width,
        boxes=boxes,
        connections=connections,
        line_jumps=tuple(line_jumps),
    )

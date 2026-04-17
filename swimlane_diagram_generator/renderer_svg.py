from __future__ import annotations

import textwrap
from collections import defaultdict
from dataclasses import dataclass
from html import escape

from .model import Diagram, Node, Shape


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
class _Segment:
    line_index: int
    segment_index: int
    x1: float
    y1: float
    x2: float
    y2: float
    orientation: str


@dataclass(slots=True)
class RenderGlobalConfig:
    min_line_gap: float = 12.0


GLOBAL_RENDER_CONFIG = RenderGlobalConfig()


def set_global_min_line_gap(min_line_gap: float) -> None:
    GLOBAL_RENDER_CONFIG.min_line_gap = max(4.0, float(min_line_gap))


def get_global_min_line_gap() -> float:
    return GLOBAL_RENDER_CONFIG.min_line_gap


def _grid_size() -> float:
    return get_global_min_line_gap()


def _grid_half_step() -> float:
    return _grid_size() / 2.0


def _snap_to_grid(value: float, *, half: bool = False) -> float:
    step = _grid_half_step() if half else _grid_size()
    if step <= 0.0:
        return value
    return round(value / step) * step


def _snap_path_to_grid(
    path: list[tuple[float, float]],
    *,
    half: bool = True,
) -> list[tuple[float, float]]:
    return [(_snap_to_grid(x, half=half), _snap_to_grid(y, half=half)) for x, y in path]


def render_svg(diagram: Diagram) -> str:
    if not diagram.lanes:
        raise ValueError("Cannot render diagram without lanes.")
    if not diagram.nodes:
        raise ValueError("Cannot render diagram without nodes.")

    lane_count = len(diagram.lanes)
    lane_index_by_id = {lane.id: lane.index for lane in diagram.lanes}
    slot_by_node, slot_count = _assign_vertical_slots(diagram, lane_index_by_id)
    node_dimensions = _compute_node_dimensions(diagram, lane_index_by_id, slot_by_node)
    grid_size = _grid_size()

    chart_x = _snap_to_grid(max(18.0, grid_size * 1.5), half=True)
    chart_y = _snap_to_grid(max(18.0, grid_size * 1.5), half=True)
    lane_width = _compute_lane_width(
        diagram,
        lane_index_by_id,
        node_dimensions=node_dimensions,
    )
    title_height = _snap_to_grid(48.0 if diagram.title else 36.0, half=True)
    lane_header_height = _snap_to_grid(40.0, half=True)

    first_row_offset = _snap_to_grid(max(54.0, grid_size * 2.0), half=True)
    max_node_height = max((size[1] for size in node_dimensions.values()), default=74.0)
    row_gap = _snap_to_grid(
        max(104.0, max_node_height + max(24.0, get_global_min_line_gap() * 1.2)),
        half=True,
    )
    body_height = max(
        320.0,
        first_row_offset + max(slot_count - 1, 0) * row_gap + max_node_height + 52.0,
    )
    body_height = _snap_to_grid(body_height, half=True)

    lane_body_y = _snap_to_grid(chart_y + title_height + lane_header_height, half=True)
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

    chart_width = _snap_to_grid(lane_count * lane_width)
    chart_height = _snap_to_grid(
        title_height + lane_header_height + body_height, half=True
    )
    svg_width = chart_x * 2 + chart_width
    svg_height = chart_y * 2 + chart_height

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

    parts: list[str] = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{_fmt(svg_width)}" height="{_fmt(svg_height)}" '
        f'viewBox="0 0 {_fmt(svg_width)} {_fmt(svg_height)}">',
        "  <defs>",
        '    <marker id="arrowhead" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="8" markerHeight="8" orient="auto-start-reverse">',
        '      <path d="M 0 0 L 10 5 L 0 10 z" fill="#111827" />',
        "    </marker>",
        "  </defs>",
        f'  <rect x="{_fmt(chart_x)}" y="{_fmt(chart_y)}" width="{_fmt(chart_width)}" height="{_fmt(chart_height)}" fill="#ffffff" stroke="#111827" stroke-width="1.3" />',
    ]

    # Title band
    parts.append(
        f'  <rect x="{_fmt(chart_x)}" y="{_fmt(chart_y)}" width="{_fmt(chart_width)}" height="{_fmt(title_height)}" fill="#ffffff" stroke="#111827" stroke-width="1.0" />'
    )
    if diagram.title:
        parts.append(
            f'  <text x="{_fmt(chart_x + chart_width / 2)}" y="{_fmt(chart_y + title_height / 2 + 6)}" text-anchor="middle" '
            f'font-size="22" font-family="Segoe UI, Microsoft YaHei, Arial, sans-serif" fill="#111827">{escape(diagram.title)}</text>'
        )

    # Lane headers and lane body backgrounds
    for lane in diagram.lanes:
        lane_x = chart_x + lane.index * lane_width
        header_y = chart_y + title_height
        parts.append(
            f'  <rect x="{_fmt(lane_x)}" y="{_fmt(header_y)}" width="{_fmt(lane_width)}" height="{_fmt(lane_header_height)}" fill="#f3f4f6" stroke="#111827" stroke-width="1.0" />'
        )
        parts.append(
            f'  <text x="{_fmt(lane_x + lane_width / 2)}" y="{_fmt(header_y + lane_header_height / 2 + 5)}" text-anchor="middle" '
            f'font-size="14" font-family="Segoe UI, Microsoft YaHei, Arial, sans-serif" fill="#111827">{escape(lane.title)}</text>'
        )
        parts.append(
            f'  <rect x="{_fmt(lane_x)}" y="{_fmt(lane_body_y)}" width="{_fmt(lane_width)}" height="{_fmt(body_height)}" fill="#f8f8f8" stroke="#111827" stroke-width="1.0" />'
        )

    # Connection lines first.
    for path_points in connection_paths:
        points_attr = " ".join(f"{_fmt(x)},{_fmt(y)}" for x, y in path_points)
        parts.append(
            f'  <polyline points="{points_attr}" fill="none" stroke="#111827" stroke-width="1.8" marker-end="url(#arrowhead)" />'
        )

    # Draw line jumps (bridge bumps) where lines cross.
    for jump in line_jumps:
        parts.extend(_draw_jump_svg(jump))

    # Draw labels over lines and bumps.
    for connection, path_points in zip(diagram.connections, connection_paths):
        if not connection.label:
            continue
        parts.extend(_draw_connection_label_svg(path_points, connection.label))

    # Nodes on top of everything.
    for node in diagram.nodes:
        parts.extend(_draw_node(boxes[node.id]))

    parts.append("</svg>")
    return "\n".join(parts)


def _draw_node(box: NodeBox) -> list[str]:
    x = box.x - box.width / 2
    y = box.y - box.height / 2
    stroke = 'fill="#ffffff" stroke="#111827" stroke-width="1.5"'

    fragments: list[str] = []
    if box.shape is Shape.PROCESS:
        fragments.append(
            f'  <rect x="{_fmt(x)}" y="{_fmt(y)}" width="{_fmt(box.width)}" height="{_fmt(box.height)}" rx="4" ry="4" {stroke} />'
        )
    elif box.shape is Shape.START_END:
        radius = box.height / 2
        fragments.append(
            f'  <rect x="{_fmt(x)}" y="{_fmt(y)}" width="{_fmt(box.width)}" height="{_fmt(box.height)}" rx="{_fmt(radius)}" ry="{_fmt(radius)}" {stroke} />'
        )
    elif box.shape is Shape.DECISION:
        points = [
            (box.x, y),
            (x + box.width, box.y),
            (box.x, y + box.height),
            (x, box.y),
        ]
        point_text = " ".join(f"{_fmt(px)},{_fmt(py)}" for px, py in points)
        fragments.append(f'  <polygon points="{point_text}" {stroke} />')
    elif box.shape is Shape.SUBPROCESS:
        fragments.append(
            f'  <rect x="{_fmt(x)}" y="{_fmt(y)}" width="{_fmt(box.width)}" height="{_fmt(box.height)}" rx="4" ry="4" {stroke} />'
        )
        inset = min(12.0, box.width * 0.12)
        fragments.append(
            f'  <line x1="{_fmt(x + inset)}" y1="{_fmt(y)}" x2="{_fmt(x + inset)}" y2="{_fmt(y + box.height)}" stroke="#111827" stroke-width="1.2" />'
        )
        fragments.append(
            f'  <line x1="{_fmt(x + box.width - inset)}" y1="{_fmt(y)}" x2="{_fmt(x + box.width - inset)}" y2="{_fmt(y + box.height)}" stroke="#111827" stroke-width="1.2" />'
        )
    elif box.shape is Shape.DOCUMENT:
        wave = min(16.0, box.height * 0.22)
        path = (
            f"M {_fmt(x)} {_fmt(y)} "
            f"H {_fmt(x + box.width)} "
            f"V {_fmt(y + box.height - wave)} "
            f"Q {_fmt(x + box.width * 0.75)} {_fmt(y + box.height + wave * 0.35)} {_fmt(x + box.width * 0.5)} {_fmt(y + box.height - wave * 0.25)} "
            f"Q {_fmt(x + box.width * 0.25)} {_fmt(y + box.height - wave * 0.85)} {_fmt(x)} {_fmt(y + box.height - wave * 0.35)} "
            "Z"
        )
        fragments.append(f'  <path d="{path}" {stroke} />')
    elif box.shape is Shape.DATA:
        skew = min(20.0, box.width * 0.15)
        points = [
            (x + skew, y),
            (x + box.width, y),
            (x + box.width - skew, y + box.height),
            (x, y + box.height),
        ]
        point_text = " ".join(f"{_fmt(px)},{_fmt(py)}" for px, py in points)
        fragments.append(f'  <polygon points="{point_text}" {stroke} />')

    lines = _wrap_text(box.text, _text_capacity(box))
    text_center_y = box.y
    if box.shape is Shape.DOCUMENT:
        text_center_y -= box.height * 0.12
    line_height = 15.0
    text_y = _snap_to_grid(
        text_center_y - ((len(lines) - 1) * line_height) / 2 + 5,
        half=True,
    )
    fragments.append(
        f'  <text x="{_fmt(box.x)}" y="{_fmt(text_y)}" text-anchor="middle" '
        f'font-size="13" font-family="Segoe UI, Microsoft YaHei, Arial, sans-serif" fill="#111827">'
    )
    for index, line in enumerate(lines):
        dy = "0" if index == 0 else _fmt(line_height)
        fragments.append(
            f'    <tspan x="{_fmt(box.x)}" dy="{dy}">{escape(line)}</tspan>'
        )
    fragments.append("  </text>")
    return fragments


def _shape_size(shape: Shape) -> tuple[float, float]:
    if shape is Shape.DECISION:
        return 122.0, 78.0
    if shape is Shape.SUBPROCESS:
        return 154.0, 68.0
    if shape is Shape.START_END:
        return 124.0, 50.0
    if shape is Shape.DOCUMENT:
        return 152.0, 74.0
    if shape is Shape.DATA:
        return 146.0, 68.0
    return 144.0, 66.0


def _compute_lane_width(
    diagram: Diagram,
    lane_index_by_id: dict[str, int],
    *,
    node_dimensions: dict[str, tuple[float, float]] | None = None,
) -> float:
    grid_size = _grid_size()
    base_width = max(210.0, grid_size * 8.0)
    if node_dimensions is None:
        shape_need = (
            max((_shape_size(node.shape)[0] for node in diagram.nodes), default=144.0)
            + 42.0
        )
    else:
        shape_need = (
            max((node_dimensions[node.id][0] for node in diagram.nodes), default=144.0)
            + 42.0
        )
    title_need = max(
        (_estimate_text_width(lane.title, 14) + 32.0 for lane in diagram.lanes),
        default=base_width,
    )
    boundary_pressure = _compute_boundary_pressure(diagram, lane_index_by_id)
    pressure_need = 200.0 + min(140.0, boundary_pressure * 8.0)
    return _snap_to_grid(max(base_width, shape_need, title_need, pressure_need))


def _resolve_lane_width_for_clarity(
    diagram: Diagram,
    lane_index_by_id: dict[str, int],
    slot_by_node: dict[str, int],
    initial_lane_width: float,
    lane_body_y: float,
    first_row_offset: float,
    row_gap: float,
    node_dimensions: dict[str, tuple[float, float]] | None = None,
) -> float:
    lane_width, _, _ = _resolve_layout_tuning(
        diagram,
        lane_index_by_id,
        slot_by_node,
        initial_lane_width,
        lane_body_y,
        first_row_offset,
        row_gap,
        node_dimensions=node_dimensions,
    )
    return lane_width


def _resolve_layout_tuning(
    diagram: Diagram,
    lane_index_by_id: dict[str, int],
    slot_by_node: dict[str, int],
    initial_lane_width: float,
    lane_body_y: float,
    first_row_offset: float,
    row_gap: float,
    *,
    node_dimensions: dict[str, tuple[float, float]] | None = None,
) -> tuple[float, float, float]:
    min_line_gap = get_global_min_line_gap()
    base_incident_step = _snap_to_grid(max(10.0, min_line_gap), half=True)
    base_cross_y_step = _snap_to_grid(max(5.0, min_line_gap * 0.75), half=True)
    target_dense_pairs = 0
    best_result = (initial_lane_width, base_incident_step, base_cross_y_step)
    best_dense_pairs = float("inf")

    width_candidates = sorted({
        _snap_to_grid(initial_lane_width),
        _snap_to_grid(initial_lane_width + max(12.0, min_line_gap * 0.8)),
        _snap_to_grid(initial_lane_width + max(24.0, min_line_gap * 1.6)),
    })
    incident_factors = [1.0, 1.2, 1.4, 1.6, 1.8]
    cross_factors = [1.0, 1.2, 1.4]

    for lane_width in width_candidates:
        for incident_factor in incident_factors:
            incident_step = _snap_to_grid(
                base_incident_step * incident_factor, half=True
            )
            for cross_factor in cross_factors:
                cross_y_step = _snap_to_grid(
                    base_cross_y_step * cross_factor, half=True
                )
                boxes = _build_boxes(
                    diagram,
                    lane_index_by_id,
                    slot_by_node,
                    lane_width,
                    chart_x=18.0,
                    lane_body_y=lane_body_y,
                    first_row_offset=first_row_offset,
                    row_gap=row_gap,
                    node_dimensions=node_dimensions,
                )
                connection_paths = _build_connection_paths(
                    diagram,
                    boxes,
                    lane_index_by_id,
                    incident_step=incident_step,
                    cross_y_step=cross_y_step,
                )
                dense_pairs = _count_close_parallel_segments(
                    connection_paths, min_line_gap=min_line_gap
                )

                if dense_pairs < best_dense_pairs:
                    best_dense_pairs = dense_pairs
                    best_result = (lane_width, incident_step, cross_y_step)

                if dense_pairs <= target_dense_pairs:
                    return lane_width, incident_step, cross_y_step

    return best_result


def _build_boxes(
    diagram: Diagram,
    lane_index_by_id: dict[str, int],
    slot_by_node: dict[str, int],
    lane_width: float,
    chart_x: float,
    lane_body_y: float,
    first_row_offset: float,
    row_gap: float,
    *,
    node_dimensions: dict[str, tuple[float, float]] | None = None,
) -> dict[str, NodeBox]:
    boxes: dict[str, NodeBox] = {}
    for node in diagram.nodes:
        lane_index = lane_index_by_id[node.lane_id]
        if node_dimensions is None:
            node_width, node_height = _shape_size(node.shape)
        else:
            node_width, node_height = node_dimensions[node.id]
        node_width = _snap_to_grid(node_width)
        node_height = _snap_to_grid(node_height)
        slot = slot_by_node[node.id]
        x = _snap_to_grid(chart_x + lane_index * lane_width + lane_width / 2, half=True)
        y = _snap_to_grid(lane_body_y + first_row_offset + slot * row_gap, half=True)
        boxes[node.id] = NodeBox(
            node_id=node.id,
            lane_index=lane_index,
            shape=node.shape,
            text=node.text,
            x=x,
            y=y,
            width=node_width,
            height=node_height,
        )
    return boxes


def _build_connection_paths(
    diagram: Diagram,
    boxes: dict[str, NodeBox],
    lane_index_by_id: dict[str, int],
    *,
    incident_step: float = 10.0,
    cross_y_step: float = 6.0,
    lane_borders_x: list[float] | None = None,
) -> list[list[tuple[float, float]]]:
    min_line_gap = get_global_min_line_gap()
    route_hints = _build_route_hints(
        diagram,
        lane_index_by_id,
        incident_step=incident_step,
        cross_y_step=cross_y_step,
    )
    connection_paths: list[list[tuple[float, float]]] = []
    for index, connection in enumerate(diagram.connections):
        source = boxes[connection.source]
        target = boxes[connection.target]
        connection_paths.append(_route_connection(source, target, route_hints[index]))

    connection_paths = _separate_overlapping_vertical_channels(
        connection_paths, min_line_gap=min_line_gap
    )
    connection_paths = _separate_overlapping_horizontal_channels(
        connection_paths, min_line_gap=min_line_gap
    )
    connection_paths = _separate_overlapping_vertical_channels(
        connection_paths, min_line_gap=min_line_gap
    )
    if lane_borders_x:
        connection_paths = _nudge_paths_off_lane_borders(
            connection_paths, lane_borders_x
        )
        connection_paths = _separate_overlapping_vertical_channels(
            connection_paths,
            min_line_gap=min_line_gap,
        )
        connection_paths = _separate_overlapping_horizontal_channels(
            connection_paths,
            min_line_gap=min_line_gap,
        )
        connection_paths = _separate_overlapping_vertical_channels(
            connection_paths,
            min_line_gap=min_line_gap,
        )
    return [_normalize_path(path) for path in connection_paths]


def _lane_borders_x(chart_x: float, lane_width: float, lane_count: int) -> list[float]:
    return [
        _snap_to_grid(chart_x + index * lane_width, half=True)
        for index in range(lane_count + 1)
    ]


def _nudge_paths_off_lane_borders(
    connection_paths: list[list[tuple[float, float]]],
    lane_borders_x: list[float],
) -> list[list[tuple[float, float]]]:
    if not lane_borders_x:
        return connection_paths

    border_to_shift = _build_border_shift_lookup(lane_borders_x)
    adjusted_paths: list[list[tuple[float, float]]] = []
    for path in connection_paths:
        adjusted_paths.append(_nudge_single_path_off_borders(path, border_to_shift))
    return adjusted_paths


def _build_border_shift_lookup(lane_borders_x: list[float]) -> dict[float, float]:
    if not lane_borders_x:
        return {}

    min_border = min(lane_borders_x)
    max_border = max(lane_borders_x)
    half = _grid_half_step()
    lookup: dict[float, float] = {}

    for index, border in enumerate(lane_borders_x):
        if abs(border - min_border) < 1e-6:
            lookup[border] = half
            continue
        if abs(border - max_border) < 1e-6:
            lookup[border] = -half
            continue
        lookup[border] = half if index % 2 == 0 else -half

    return lookup


def _nudge_single_path_off_borders(
    path: list[tuple[float, float]],
    border_to_shift: dict[float, float],
) -> list[tuple[float, float]]:
    if not path or not border_to_shift:
        return path

    x_values = sorted({point[0] for point in path})
    remap: dict[float, float] = {}
    for x_value in x_values:
        border_key = _match_border_key(x_value, border_to_shift)
        if border_key is None:
            continue
        remap[x_value] = _snap_to_grid(x_value + border_to_shift[border_key], half=True)

    if not remap:
        return path

    adjusted = [(remap.get(x, x), y) for x, y in path]
    return _snap_path_to_grid(adjusted, half=True)


def _match_border_key(
    x_value: float, border_to_shift: dict[float, float]
) -> float | None:
    for border in border_to_shift:
        if abs(x_value - border) < 1e-6:
            return border
    return None


def _normalize_path(path: list[tuple[float, float]]) -> list[tuple[float, float]]:
    if not path:
        return path

    deduped = [path[0]]
    for point in path[1:]:
        if _points_equal(point, deduped[-1]):
            continue
        deduped.append(point)

    normalized: list[tuple[float, float]] = [deduped[0]]
    for point in deduped[1:]:
        if len(normalized) >= 2 and _is_axis_collinear(
            normalized[-2], normalized[-1], point
        ):
            normalized[-1] = point
        else:
            normalized.append(point)

    return normalized


def _points_equal(first: tuple[float, float], second: tuple[float, float]) -> bool:
    return abs(first[0] - second[0]) < 1e-6 and abs(first[1] - second[1]) < 1e-6


def _is_axis_collinear(
    first: tuple[float, float],
    second: tuple[float, float],
    third: tuple[float, float],
) -> bool:
    same_x = abs(first[0] - second[0]) < 1e-6 and abs(second[0] - third[0]) < 1e-6
    same_y = abs(first[1] - second[1]) < 1e-6 and abs(second[1] - third[1]) < 1e-6
    return same_x or same_y


def _count_close_parallel_segments(
    connection_paths: list[list[tuple[float, float]]],
    *,
    min_line_gap: float | None = None,
) -> int:
    effective_gap = (
        min_line_gap if min_line_gap is not None else get_global_min_line_gap()
    )
    segments: list[_Segment] = []
    for line_index, path_points in enumerate(connection_paths):
        segments.extend(_build_segments(path_points, line_index))

    dense_pairs = 0
    for index, first in enumerate(segments):
        for second in segments[index + 1 :]:
            if first.line_index == second.line_index:
                continue
            if _are_segments_close_parallel(first, second, min_line_gap=effective_gap):
                dense_pairs += 1
    return dense_pairs


def _are_segments_close_parallel(
    first: _Segment,
    second: _Segment,
    *,
    min_line_gap: float,
) -> bool:
    if first.orientation != second.orientation:
        return False

    if first.orientation == "horizontal":
        if abs(first.y1 - second.y1) >= min_line_gap:
            return False
        overlap = _range_overlap(first.x1, first.x2, second.x1, second.x2)
        return overlap >= min_line_gap

    if abs(first.x1 - second.x1) >= min_line_gap:
        return False
    overlap = _range_overlap(first.y1, first.y2, second.y1, second.y2)
    return overlap >= min_line_gap


def _estimate_text_width(text: str, font_size: float) -> float:
    unit = font_size / 14.0
    width = 0.0
    for ch in text:
        width += 7.0 * unit if ord(ch) < 128 else 11.5 * unit
    return width


def _compute_boundary_pressure(
    diagram: Diagram, lane_index_by_id: dict[str, int]
) -> int:
    if len(diagram.lanes) <= 1:
        return 0

    node_lane = {node.id: lane_index_by_id[node.lane_id] for node in diagram.nodes}
    boundary_counts = [0 for _ in range(len(diagram.lanes) - 1)]

    for connection in diagram.connections:
        source_lane = node_lane[connection.source]
        target_lane = node_lane[connection.target]
        if source_lane == target_lane:
            continue

        start_boundary = min(source_lane, target_lane)
        end_boundary = max(source_lane, target_lane)
        for boundary_index in range(start_boundary, end_boundary):
            boundary_counts[boundary_index] += 1

    return max(boundary_counts, default=0)


def _build_route_hints(
    diagram: Diagram,
    lane_index_by_id: dict[str, int],
    *,
    incident_step: float = 10.0,
    cross_y_step: float = 6.0,
) -> list[RouteHint]:
    incident_by_node: dict[str, list[tuple[int, str]]] = defaultdict(list)

    for index, connection in enumerate(diagram.connections):
        incident_by_node[connection.source].append((index, "source"))
        incident_by_node[connection.target].append((index, "target"))

    start_offsets, end_offsets = _distribute_incident_offsets(
        incident_by_node, incident_step
    )

    node_lane = {node.id: lane_index_by_id[node.lane_id] for node in diagram.nodes}
    cross_lane_counter: dict[tuple[int, int], int] = defaultdict(int)

    hints: list[RouteHint] = []
    for index, connection in enumerate(diagram.connections):
        source_lane = node_lane[connection.source]
        target_lane = node_lane[connection.target]
        same_slot, cross_slot, cross_y_offset = _next_route_slots(
            source_lane,
            target_lane,
            cross_lane_counter,
            cross_y_step,
        )

        hints.append(
            RouteHint(
                cross_slot=cross_slot,
                same_slot=same_slot,
                start_offset=start_offsets.get(index, 0.0),
                end_offset=end_offsets.get(index, 0.0),
                cross_y_offset=cross_y_offset,
            )
        )

    return hints


def _distribute_incident_offsets(
    incident_by_node: dict[str, list[tuple[int, str]]],
    incident_step: float,
) -> tuple[dict[int, float], dict[int, float]]:
    start_offsets: dict[int, float] = {}
    end_offsets: dict[int, float] = {}
    for entries in incident_by_node.values():
        ordered_entries = sorted(
            entries, key=lambda item: (item[0], 0 if item[1] == "source" else 1)
        )
        offsets = _centered_offsets(len(ordered_entries), incident_step)
        for (connection_index, role), offset in zip(ordered_entries, offsets):
            if role == "source":
                start_offsets[connection_index] = offset
            else:
                end_offsets[connection_index] = offset
    return start_offsets, end_offsets


def _next_route_slots(
    source_lane: int,
    target_lane: int,
    cross_lane_counter: dict[tuple[int, int], int],
    cross_y_step: float,
) -> tuple[int, int, float]:
    if source_lane == target_lane:
        # Same-lane links default to a straight vertical channel.
        return 0, 0, 0.0

    route_key = (source_lane, target_lane)
    cross_slot = cross_lane_counter[route_key]
    cross_lane_counter[route_key] += 1
    cross_y_offset = _stagger_value(cross_slot, step=cross_y_step)
    return 0, cross_slot, cross_y_offset


def _centered_offsets(count: int, step: float) -> list[float]:
    if count <= 1:
        return [0.0] * count
    middle = (count - 1) / 2
    return [(index - middle) * step for index in range(count)]


def _stagger_value(slot: int, step: float) -> float:
    if slot <= 0:
        return 0.0
    magnitude = (slot + 1) // 2
    sign = 1.0 if slot % 2 == 1 else -1.0
    return sign * magnitude * step


def _route_connection(
    source: NodeBox,
    target: NodeBox,
    hint: RouteHint,
) -> list[tuple[float, float]]:
    source_offset = _clamp_node_offset(source.height, hint.start_offset)
    target_offset = _clamp_node_offset(target.height, hint.end_offset)

    if source.lane_index == target.lane_index:
        is_downward = target.y >= source.y
        if is_downward:
            start = (source.x, source.y + source.height / 2)
            end = (target.x, target.y - target.height / 2)
        else:
            start = (source.x, source.y - source.height / 2)
            end = (target.x, target.y + target.height / 2)

        if abs(start[0] - end[0]) < 1e-6:
            return _snap_path_to_grid([start, end], half=True)

        channel_x = (start[0] + end[0]) / 2
        if abs(channel_x - start[0]) < 1e-6 and abs(channel_x - end[0]) < 1e-6:
            return _snap_path_to_grid([start, end], half=True)

        return _snap_path_to_grid(
            [start, (channel_x, start[1]), (channel_x, end[1]), end],
            half=True,
        )

    direction = 1.0 if target.lane_index > source.lane_index else -1.0
    cross_y_offset = _clamp_node_offset(
        min(source.height, target.height), hint.cross_y_offset
    )
    start = (
        source.x + direction * source.width / 2,
        source.y + source_offset + cross_y_offset,
    )
    end = (
        target.x - direction * target.width / 2,
        target.y + target_offset + cross_y_offset,
    )

    mid_x = (
        (start[0] + end[0]) / 2
        + direction * 8.0
        + _stagger_value(hint.cross_slot, step=14.0)
    )
    if direction > 0:
        mid_x = min(max(mid_x, start[0] + 16.0), end[0] - 16.0)
    else:
        mid_x = max(min(mid_x, start[0] - 16.0), end[0] + 16.0)

    return _snap_path_to_grid(
        [start, (mid_x, start[1]), (mid_x, end[1]), end],
        half=True,
    )


def _clamp_node_offset(node_height: float, offset: float) -> float:
    limit = max(8.0, node_height / 2 - 6.0)
    return max(-limit, min(limit, offset))


def _separate_overlapping_vertical_channels(
    connection_paths: list[list[tuple[float, float]]],
    *,
    min_line_gap: float,
) -> list[list[tuple[float, float]]]:
    adjusted_paths: list[list[tuple[float, float]]] = [
        list(path) for path in connection_paths
    ]
    occupied_channels: list[tuple[float, float, float]] = []

    for index, path in enumerate(adjusted_paths):
        base_path = list(path)
        attempt = 0
        candidate = base_path

        if not _is_shiftable_vertical_path(candidate):
            adjusted_paths[index] = candidate
            occupied_channels.append(_extract_vertical_channel(candidate))
            continue

        while _path_channel_overlaps(
            candidate, occupied_channels, min_line_gap=min_line_gap
        ):
            attempt += 1
            candidate = _shift_path_middle_channel(
                base_path, _stagger_value(attempt, min_line_gap)
            )
            if attempt > 10:
                break

        adjusted_paths[index] = candidate
        occupied_channels.append(_extract_vertical_channel(candidate))

    return adjusted_paths


def _separate_overlapping_horizontal_channels(
    connection_paths: list[list[tuple[float, float]]],
    *,
    min_line_gap: float,
) -> list[list[tuple[float, float]]]:
    adjusted_paths: list[list[tuple[float, float]]] = [
        list(path) for path in connection_paths
    ]
    occupied_channels: list[tuple[float, float, float]] = []

    for index, path in enumerate(adjusted_paths):
        base_path = list(path)
        attempt = 0
        candidate = base_path

        if not _is_shiftable_horizontal_path(candidate):
            adjusted_paths[index] = candidate
            occupied_channels.extend(_extract_horizontal_channels(candidate))
            continue

        while _path_horizontal_overlaps(
            candidate, occupied_channels, min_line_gap=min_line_gap
        ):
            attempt += 1
            shift = _stagger_value(attempt, _grid_half_step())
            max_shift = min_line_gap * 2.0
            shift = max(-max_shift, min(max_shift, shift))
            candidate = _shift_path_vertically(base_path, shift)
            if attempt > 10:
                break

        adjusted_paths[index] = candidate
        occupied_channels.extend(_extract_horizontal_channels(candidate))

    return adjusted_paths


def _path_channel_overlaps(
    path: list[tuple[float, float]],
    occupied_channels: list[tuple[float, float, float]],
    *,
    min_line_gap: float,
) -> bool:
    x, y1, y2 = _extract_vertical_channel(path)
    for occupied_x, occupied_y1, occupied_y2 in occupied_channels:
        if abs(x - occupied_x) >= min_line_gap:
            continue
        if _range_overlap(y1, y2, occupied_y1, occupied_y2) >= min_line_gap:
            return True
    return False


def _path_horizontal_overlaps(
    path: list[tuple[float, float]],
    occupied_channels: list[tuple[float, float, float]],
    *,
    min_line_gap: float,
) -> bool:
    channels = _extract_horizontal_channels(path)
    for y, x1, x2 in channels:
        for occupied_y, occupied_x1, occupied_x2 in occupied_channels:
            if abs(y - occupied_y) >= min_line_gap:
                continue
            if _range_overlap(x1, x2, occupied_x1, occupied_x2) >= min_line_gap:
                return True
    return False


def _is_shiftable_vertical_path(path: list[tuple[float, float]]) -> bool:
    if len(path) < 4:
        return False
    return abs(path[0][0] - path[-1][0]) >= 1.0


def _is_shiftable_horizontal_path(path: list[tuple[float, float]]) -> bool:
    if len(path) < 4:
        return False
    return abs(path[0][0] - path[-1][0]) >= 1.0


def _extract_horizontal_channels(
    path: list[tuple[float, float]],
) -> list[tuple[float, float, float]]:
    channels: list[tuple[float, float, float]] = []
    for index in range(len(path) - 1):
        x1, y1 = path[index]
        x2, y2 = path[index + 1]
        if abs(y1 - y2) < 1e-6 and abs(x1 - x2) >= 1e-6:
            channels.append((y1, min(x1, x2), max(x1, x2)))
    return channels


def _extract_vertical_channel(
    path: list[tuple[float, float]],
) -> tuple[float, float, float]:
    if len(path) < 4:
        x1, y1 = path[0]
        x2, y2 = path[-1]
        x = (x1 + x2) / 2
        return x, min(y1, y2), max(y1, y2)

    x, y1 = path[1]
    _, y2 = path[2]
    return x, min(y1, y2), max(y1, y2)


def _shift_path_middle_channel(
    path: list[tuple[float, float]], delta_x: float
) -> list[tuple[float, float]]:
    if len(path) < 4:
        return list(path)

    shifted = list(path)
    x1, y1 = shifted[1]
    x2, y2 = shifted[2]
    shifted[1] = (x1 + delta_x, y1)
    shifted[2] = (x2 + delta_x, y2)
    return _snap_path_to_grid(shifted, half=True)


def _shift_path_vertically(
    path: list[tuple[float, float]], delta_y: float
) -> list[tuple[float, float]]:
    return _snap_path_to_grid([(x, y + delta_y) for x, y in path], half=True)


def _range_overlap(a1: float, a2: float, b1: float, b2: float) -> float:
    low = max(min(a1, a2), min(b1, b2))
    high = min(max(a1, a2), max(b1, b2))
    return max(0.0, high - low)


def _compute_line_jumps(
    connection_paths: list[list[tuple[float, float]]],
) -> list[LineJump]:
    segments_by_line: list[list[_Segment]] = [
        _build_segments(path_points, line_index)
        for line_index, path_points in enumerate(connection_paths)
    ]

    raw_jumps: list[LineJump] = []
    for earlier_line, later_line in _iter_line_pairs(len(segments_by_line)):
        raw_jumps.extend(
            _collect_pair_jumps(
                segments_by_line[earlier_line],
                segments_by_line[later_line],
                later_line,
            )
        )

    unique_jumps = _dedupe_jumps(raw_jumps)
    unique_jumps.sort(key=lambda item: (item.line_index, item.x, item.y))
    return unique_jumps


def _iter_line_pairs(line_count: int):
    for earlier_line in range(line_count):
        for later_line in range(earlier_line + 1, line_count):
            yield earlier_line, later_line


def _collect_pair_jumps(
    earlier_segments: list[_Segment],
    later_segments: list[_Segment],
    later_line: int,
) -> list[LineJump]:
    jumps: list[LineJump] = []
    for earlier_segment in earlier_segments:
        for later_segment in later_segments:
            intersection = _orthogonal_intersection(earlier_segment, later_segment)
            if intersection is None:
                continue
            x, y = intersection
            jumps.append(
                LineJump(
                    line_index=later_line,
                    x=x,
                    y=y,
                    orientation=later_segment.orientation,
                )
            )
    return jumps


def _dedupe_jumps(jumps: list[LineJump]) -> list[LineJump]:
    unique: list[LineJump] = []
    seen: set[tuple[int, float, float, str]] = set()
    for jump in jumps:
        key = (jump.line_index, round(jump.x, 1), round(jump.y, 1), jump.orientation)
        if key in seen:
            continue
        seen.add(key)
        unique.append(jump)
    return unique


def _build_segments(
    path_points: list[tuple[float, float]], line_index: int
) -> list[_Segment]:
    segments: list[_Segment] = []
    for segment_index in range(len(path_points) - 1):
        x1, y1 = path_points[segment_index]
        x2, y2 = path_points[segment_index + 1]

        if abs(x1 - x2) < 1e-6 and abs(y1 - y2) >= 1e-6:
            orientation = "vertical"
        elif abs(y1 - y2) < 1e-6 and abs(x1 - x2) >= 1e-6:
            orientation = "horizontal"
        else:
            continue

        segments.append(
            _Segment(
                line_index=line_index,
                segment_index=segment_index,
                x1=x1,
                y1=y1,
                x2=x2,
                y2=y2,
                orientation=orientation,
            )
        )
    return segments


def _orthogonal_intersection(
    segment_a: _Segment, segment_b: _Segment
) -> tuple[float, float] | None:
    if segment_a.orientation == segment_b.orientation:
        return None

    horizontal = segment_a if segment_a.orientation == "horizontal" else segment_b
    vertical = segment_b if horizontal is segment_a else segment_a

    x = vertical.x1
    y = horizontal.y1

    if not _between_open(x, horizontal.x1, horizontal.x2, epsilon=1.0):
        return None
    if not _between_open(y, vertical.y1, vertical.y2, epsilon=1.0):
        return None
    return x, y


def _between_open(value: float, start: float, end: float, epsilon: float) -> bool:
    low = min(start, end) + epsilon
    high = max(start, end) - epsilon
    return low < value < high


def _draw_jump_svg(jump: LineJump) -> list[str]:
    radius = 5.2
    fragments = [
        f'  <circle cx="{_fmt(jump.x)}" cy="{_fmt(jump.y)}" r="{_fmt(radius)}" fill="#ffffff" stroke="#ffffff" stroke-width="2.4" />'
    ]
    if jump.orientation == "horizontal":
        path = (
            f"M {_fmt(jump.x - radius)} {_fmt(jump.y)} "
            f"Q {_fmt(jump.x)} {_fmt(jump.y - radius * 1.25)} {_fmt(jump.x + radius)} {_fmt(jump.y)}"
        )
    else:
        path = (
            f"M {_fmt(jump.x)} {_fmt(jump.y - radius)} "
            f"Q {_fmt(jump.x + radius * 1.25)} {_fmt(jump.y)} {_fmt(jump.x)} {_fmt(jump.y + radius)}"
        )
    fragments.append(
        f'  <path class="line-jump" d="{path}" fill="none" stroke="#111827" stroke-width="1.8" stroke-linecap="round" />'
    )
    return fragments


def _draw_connection_label_svg(
    path_points: list[tuple[float, float]], label_text: str
) -> list[str]:
    label_x, label_y, orientation = _label_anchor(path_points)

    if orientation == "vertical":
        lines = _vertical_label_lines(label_text)
        line_height = 12.0
        label_height = max(28.0, len(lines) * line_height + 10.0)
        longest = max((len(line) for line in lines), default=1)
        label_width = max(20.0, min(120.0, longest * 7.2 + 10.0))
        text_start_y = label_y - ((len(lines) - 1) * line_height) / 2

        fragments = [
            f'  <rect x="{_fmt(label_x - label_width / 2)}" y="{_fmt(label_y - label_height / 2)}" width="{_fmt(label_width)}" height="{_fmt(label_height)}" fill="#ffffff" fill-opacity="0.92" rx="3" />',
            f'  <text class="vertical-label" x="{_fmt(label_x)}" y="{_fmt(text_start_y)}" text-anchor="middle" dominant-baseline="middle" font-size="12" font-family="Segoe UI, Microsoft YaHei, Arial, sans-serif" fill="#111827">',
        ]
        for index, line in enumerate(lines):
            dy = "0" if index == 0 else _fmt(line_height)
            fragments.append(
                f'    <tspan x="{_fmt(label_x)}" dy="{dy}">{escape(line)}</tspan>'
            )
        fragments.append("  </text>")
        return fragments

    label_width = max(34.0, len(label_text) * 7.2 + 12.0)
    return [
        f'  <rect x="{_fmt(label_x - label_width / 2)}" y="{_fmt(label_y - 10)}" width="{_fmt(label_width)}" height="20" fill="#ffffff" fill-opacity="0.92" rx="3" />',
        f'  <text x="{_fmt(label_x)}" y="{_fmt(label_y)}" text-anchor="middle" dominant-baseline="middle" font-size="12" font-family="Segoe UI, Microsoft YaHei, Arial, sans-serif" fill="#111827">{escape(label_text)}</text>',
    ]


def _vertical_label_lines(label_text: str) -> list[str]:
    text = label_text.replace("\n", " ").strip()
    if not text:
        return ["?"]

    has_cjk = any("\u4e00" <= char <= "\u9fff" for char in text)
    if has_cjk:
        lines = [char for char in text if char != " "]
        return lines or [text]

    words = [word for word in text.split(" ") if word]
    if len(words) >= 2:
        return words

    token = words[0] if words else text
    chunk_size = 3
    return [
        token[index : index + chunk_size] for index in range(0, len(token), chunk_size)
    ]


def _text_capacity(box: NodeBox) -> int:
    return _text_capacity_for_dimensions(box.shape, box.width)


def _text_capacity_for_dimensions(shape: Shape, width: float) -> int:
    width_factor, _ = _shape_text_box_factors(shape)
    width *= width_factor
    width = max(48.0, width - 20.0)
    return max(4, int(width / 7.2))


def _wrap_text(text: str, max_chars: int) -> list[str]:
    wrapped_lines: list[str] = []
    for chunk in text.splitlines() or [text]:
        lines = textwrap.wrap(
            chunk,
            width=max_chars,
            break_long_words=True,
            break_on_hyphens=False,
            replace_whitespace=False,
        )
        wrapped_lines.extend(lines or [chunk])
    return wrapped_lines if wrapped_lines else [text]


def _compute_node_dimensions(
    diagram: Diagram,
    lane_index_by_id: dict[str, int],
    slot_by_node: dict[str, int],
) -> dict[str, tuple[float, float]]:
    grid_size = _grid_size()
    side_counts = _compute_node_side_connection_counts(
        diagram,
        lane_index_by_id,
        slot_by_node,
    )
    dimensions: dict[str, tuple[float, float]] = {}

    for node in diagram.nodes:
        counts = side_counts[node.id]
        total_connections = (
            counts["left"] + counts["right"] + counts["top"] + counts["bottom"]
        )

        width_units, height_units = _shape_grid_size(node.shape)
        width_units, height_units = _expand_units_for_connection_capacity(
            width_units,
            height_units,
            total_connections,
        )

        width_units = max(
            width_units,
            max(1, counts["top"] - 1),
            max(1, counts["bottom"] - 1),
        )
        height_units = max(
            height_units,
            max(1, counts["left"] - 1),
            max(1, counts["right"] - 1),
        )

        width_units, height_units = _fit_text_in_grid_units(
            node.text,
            node.shape,
            width_units,
            height_units,
            grid_size,
        )

        dimensions[node.id] = (
            _snap_to_grid(width_units * grid_size),
            _snap_to_grid(height_units * grid_size),
        )

    return dimensions


def _shape_grid_size(shape: Shape) -> tuple[int, int]:
    if shape is Shape.DECISION:
        return 4, 4
    if shape is Shape.DOCUMENT:
        return 4, 4
    return 4, 3


def _shape_text_box_factors(shape: Shape) -> tuple[float, float]:
    if shape is Shape.DECISION:
        return 0.62, 0.62
    if shape is Shape.START_END:
        return 0.76, 0.72
    if shape is Shape.DATA:
        return 0.8, 0.78
    if shape is Shape.DOCUMENT:
        return 0.74, 0.58
    return 0.86, 0.82


def _node_connection_capacity(width_units: int, height_units: int) -> int:
    return max(4, 2 * (width_units + height_units) - 4)


def _expand_units_for_connection_capacity(
    width_units: int,
    height_units: int,
    total_connections: int,
) -> tuple[int, int]:
    while _node_connection_capacity(width_units, height_units) < total_connections:
        if height_units <= width_units:
            height_units += 1
        else:
            width_units += 1
    return width_units, height_units


def _fit_text_in_grid_units(
    text: str,
    shape: Shape,
    width_units: int,
    height_units: int,
    grid_size: float,
) -> tuple[int, int]:
    text_width_factor, text_height_factor = _shape_text_box_factors(shape)
    text_width_raw = _estimate_text_width(text, 13) + 8.0

    for _ in range(20):
        width = width_units * grid_size
        height = height_units * grid_size

        text_box_width = max(24.0, width * text_width_factor - grid_size * 0.5)
        max_chars = max(4, int(text_box_width / 7.2))
        wrapped_lines = _wrap_text(text, max_chars)
        required_text_height = len(wrapped_lines) * 15.0 + 10.0
        available_text_height = max(14.0, height * text_height_factor - grid_size * 0.2)

        if required_text_height > available_text_height:
            height_units += 1
            continue

        if text_width_raw > text_box_width * 1.25 and width_units < 16:
            width_units += 1
            continue

        break

    return width_units, height_units


def _compute_node_side_connection_counts(
    diagram: Diagram,
    lane_index_by_id: dict[str, int],
    slot_by_node: dict[str, int],
) -> dict[str, dict[str, int]]:
    counts: dict[str, dict[str, int]] = {
        node.id: {"left": 0, "right": 0, "top": 0, "bottom": 0}
        for node in diagram.nodes
    }
    node_lane = {node.id: lane_index_by_id[node.lane_id] for node in diagram.nodes}

    for connection in diagram.connections:
        source_lane = node_lane[connection.source]
        target_lane = node_lane[connection.target]
        source_slot = slot_by_node[connection.source]
        target_slot = slot_by_node[connection.target]

        if source_lane == target_lane:
            if target_slot >= source_slot:
                counts[connection.source]["bottom"] += 1
                counts[connection.target]["top"] += 1
            else:
                counts[connection.source]["top"] += 1
                counts[connection.target]["bottom"] += 1
            continue

        if target_lane > source_lane:
            counts[connection.source]["right"] += 1
            counts[connection.target]["left"] += 1
        else:
            counts[connection.source]["left"] += 1
            counts[connection.target]["right"] += 1

    return counts


def _assign_vertical_slots(
    diagram: Diagram,
    lane_index_by_id: dict[str, int],
) -> tuple[dict[str, int], int]:
    outgoing, incoming = _build_graph(diagram)
    base_level = _compute_base_levels(diagram, outgoing, incoming)
    slot_by_node = _place_nodes(diagram, lane_index_by_id, base_level, incoming)
    slot_count = max(slot_by_node.values()) + 1 if slot_by_node else 0
    return slot_by_node, slot_count


def _build_graph(diagram: Diagram) -> tuple[dict[str, list[str]], dict[str, list[str]]]:
    outgoing: dict[str, list[str]] = {node.id: [] for node in diagram.nodes}
    incoming: dict[str, list[str]] = {node.id: [] for node in diagram.nodes}
    for connection in diagram.connections:
        outgoing[connection.source].append(connection.target)
        incoming[connection.target].append(connection.source)
    return outgoing, incoming


def _compute_base_levels(
    diagram: Diagram,
    outgoing: dict[str, list[str]],
    incoming: dict[str, list[str]],
) -> dict[str, int]:
    base_level = {node.id: 0 for node in diagram.nodes}
    topological_order = _topological_order(diagram.nodes, outgoing, incoming)
    if topological_order is None:
        return _compute_feedback_aware_levels(diagram, incoming)

    for node_id in topological_order:
        for next_node_id in outgoing[node_id]:
            base_level[next_node_id] = max(
                base_level[next_node_id], base_level[node_id] + 1
            )
    return base_level


def _compute_feedback_aware_levels(
    diagram: Diagram,
    incoming: dict[str, list[str]],
) -> dict[str, int]:
    # For cyclic flows, treat edges from later-declared nodes as feedback edges,
    # so they don't force a strictly sequential vertical layout.
    base_level = {node.id: 0 for node in diagram.nodes}
    order_lookup = {node.id: node.order for node in diagram.nodes}
    nodes_by_order = sorted(diagram.nodes, key=lambda node: node.order)

    for node in nodes_by_order:
        for predecessor in incoming[node.id]:
            if order_lookup[predecessor] < node.order:
                base_level[node.id] = max(
                    base_level[node.id], base_level[predecessor] + 1
                )

    return base_level


def _place_nodes(
    diagram: Diagram,
    lane_index_by_id: dict[str, int],
    base_level: dict[str, int],
    incoming: dict[str, list[str]],
) -> dict[str, int]:
    occupied_slots: set[tuple[int, int]] = set()
    slot_by_node: dict[str, int] = {}

    for node in sorted(
        diagram.nodes, key=lambda item: (base_level[item.id], item.order)
    ):
        lane_index = lane_index_by_id[node.lane_id]
        slot = base_level[node.id]
        for predecessor in incoming[node.id]:
            if predecessor in slot_by_node:
                slot = max(slot, slot_by_node[predecessor] + 1)
        while (lane_index, slot) in occupied_slots:
            slot += 1
        slot_by_node[node.id] = slot
        occupied_slots.add((lane_index, slot))

    return slot_by_node


def _topological_order(
    nodes: list[Node],
    outgoing: dict[str, list[str]],
    incoming: dict[str, list[str]],
) -> list[str] | None:
    indegree = {node.id: len(incoming[node.id]) for node in nodes}
    order_lookup = {node.id: node.order for node in nodes}
    ready = sorted(
        (node.id for node in nodes if indegree[node.id] == 0),
        key=lambda node_id: order_lookup[node_id],
    )
    result: list[str] = []

    while ready:
        node_id = ready.pop(0)
        result.append(node_id)
        for next_node_id in outgoing[node_id]:
            indegree[next_node_id] -= 1
            if indegree[next_node_id] == 0:
                ready.append(next_node_id)
                ready.sort(key=lambda item: order_lookup[item])

    if len(result) != len(nodes):
        return None
    return result


def _label_anchor(path_points: list[tuple[float, float]]) -> tuple[float, float, str]:
    if len(path_points) >= 4:
        start = path_points[1]
        end = path_points[2]
    else:
        start = path_points[0]
        end = path_points[-1]

    x = (start[0] + end[0]) / 2
    y = (start[1] + end[1]) / 2
    orientation = (
        "vertical" if abs(end[0] - start[0]) < abs(end[1] - start[1]) else "horizontal"
    )
    if orientation == "horizontal":
        y -= 4.0
    return x, y, orientation


def _fmt(value: float) -> str:
    return f"{value:.1f}"

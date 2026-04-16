from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from html import escape
import textwrap

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


def render_svg(diagram: Diagram) -> str:
    if not diagram.lanes:
        raise ValueError("Cannot render diagram without lanes.")
    if not diagram.nodes:
        raise ValueError("Cannot render diagram without nodes.")

    lane_count = len(diagram.lanes)
    lane_index_by_id = {lane.id: lane.index for lane in diagram.lanes}
    slot_by_node, slot_count = _assign_vertical_slots(diagram, lane_index_by_id)

    chart_x = 18.0
    chart_y = 18.0
    lane_width = _compute_lane_width(diagram, lane_index_by_id)
    title_height = 48.0 if diagram.title else 36.0
    lane_header_height = 40.0

    first_row_offset = 54.0
    row_gap = 104.0
    body_height = max(320.0, first_row_offset + max(slot_count - 1, 0) * row_gap + 92.0)

    chart_width = lane_count * lane_width
    chart_height = title_height + lane_header_height + body_height
    svg_width = chart_x * 2 + chart_width
    svg_height = chart_y * 2 + chart_height

    lane_body_y = chart_y + title_height + lane_header_height

    boxes: dict[str, NodeBox] = {}
    for node in diagram.nodes:
        lane_index = lane_index_by_id[node.lane_id]
        node_width, node_height = _shape_size(node.shape)
        slot = slot_by_node[node.id]
        x = chart_x + lane_index * lane_width + lane_width / 2
        y = lane_body_y + first_row_offset + slot * row_gap
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

    route_hints = _build_route_hints(diagram, lane_index_by_id)
    connection_paths: list[list[tuple[float, float]]] = []
    for index, connection in enumerate(diagram.connections):
        source = boxes[connection.source]
        target = boxes[connection.target]
        path = _route_connection(source, target, route_hints[index], lane_width)
        connection_paths.append(path)

    connection_paths = _separate_overlapping_vertical_channels(connection_paths)

    line_jumps = _compute_line_jumps(connection_paths)

    parts: list[str] = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{_fmt(svg_width)}" height="{_fmt(svg_height)}" '
        f'viewBox="0 0 {_fmt(svg_width)} {_fmt(svg_height)}">',
        "  <defs>",
        "    <marker id=\"arrowhead\" viewBox=\"0 0 10 10\" refX=\"9\" refY=\"5\" markerWidth=\"8\" markerHeight=\"8\" orient=\"auto-start-reverse\">",
        "      <path d=\"M 0 0 L 10 5 L 0 10 z\" fill=\"#111827\" />",
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
        label_x, label_y = _label_anchor(path_points)
        label_text = connection.label
        label_width = max(34.0, len(label_text) * 7.2 + 12.0)
        parts.append(
            f'  <rect x="{_fmt(label_x - label_width / 2)}" y="{_fmt(label_y - 15)}" width="{_fmt(label_width)}" height="20" fill="#ffffff" fill-opacity="0.92" rx="3" />'
        )
        parts.append(
            f'  <text x="{_fmt(label_x)}" y="{_fmt(label_y)}" text-anchor="middle" '
            f'font-size="12" font-family="Segoe UI, Microsoft YaHei, Arial, sans-serif" fill="#111827">{escape(label_text)}</text>'
        )

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
    line_height = 15.0
    text_y = box.y - ((len(lines) - 1) * line_height) / 2 + 5
    fragments.append(
        f'  <text x="{_fmt(box.x)}" y="{_fmt(text_y)}" text-anchor="middle" '
        f'font-size="13" font-family="Segoe UI, Microsoft YaHei, Arial, sans-serif" fill="#111827">'
    )
    for index, line in enumerate(lines):
        dy = "0" if index == 0 else _fmt(line_height)
        fragments.append(f'    <tspan x="{_fmt(box.x)}" dy="{dy}">{escape(line)}</tspan>')
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


def _compute_lane_width(diagram: Diagram, lane_index_by_id: dict[str, int]) -> float:
    base_width = 210.0
    shape_need = max((_shape_size(node.shape)[0] for node in diagram.nodes), default=144.0) + 42.0
    title_need = max((_estimate_text_width(lane.title, 14) + 32.0 for lane in diagram.lanes), default=base_width)
    boundary_pressure = _compute_boundary_pressure(diagram, lane_index_by_id)
    pressure_need = 200.0 + min(140.0, boundary_pressure * 8.0)
    return max(base_width, shape_need, title_need, pressure_need)


def _estimate_text_width(text: str, font_size: float) -> float:
    unit = font_size / 14.0
    width = 0.0
    for ch in text:
        width += 7.0 * unit if ord(ch) < 128 else 11.5 * unit
    return width


def _compute_boundary_pressure(diagram: Diagram, lane_index_by_id: dict[str, int]) -> int:
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


def _build_route_hints(diagram: Diagram, lane_index_by_id: dict[str, int]) -> list[RouteHint]:
    incident_by_node: dict[str, list[tuple[int, str]]] = defaultdict(list)

    for index, connection in enumerate(diagram.connections):
        incident_by_node[connection.source].append((index, "source"))
        incident_by_node[connection.target].append((index, "target"))

    start_offsets: dict[int, float] = {}
    end_offsets: dict[int, float] = {}

    for entries in incident_by_node.values():
        ordered_entries = sorted(entries, key=lambda item: (item[0], 0 if item[1] == "source" else 1))
        offsets = _centered_offsets(len(ordered_entries), 10.0)
        for (connection_index, role), offset in zip(ordered_entries, offsets):
            if role == "source":
                start_offsets[connection_index] = offset
            else:
                end_offsets[connection_index] = offset

    node_lane = {node.id: lane_index_by_id[node.lane_id] for node in diagram.nodes}
    same_lane_counter: dict[int, int] = defaultdict(int)
    cross_lane_counter: dict[tuple[int, int], int] = defaultdict(int)

    hints: list[RouteHint] = []
    for index, connection in enumerate(diagram.connections):
        source_lane = node_lane[connection.source]
        target_lane = node_lane[connection.target]

        if source_lane == target_lane:
            same_slot = same_lane_counter[source_lane]
            same_lane_counter[source_lane] += 1
            cross_slot = 0
        else:
            route_key = (source_lane, target_lane)
            cross_slot = cross_lane_counter[route_key]
            cross_lane_counter[route_key] += 1
            same_slot = 0

        hints.append(
            RouteHint(
                cross_slot=cross_slot,
                same_slot=same_slot,
                start_offset=start_offsets.get(index, 0.0),
                end_offset=end_offsets.get(index, 0.0),
            )
        )

    return hints


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
    lane_width: float,
) -> list[tuple[float, float]]:
    if source.lane_index == target.lane_index:
        is_downward = target.y >= source.y
        if is_downward:
            start = (source.x + hint.start_offset, source.y + source.height / 2)
            end = (target.x + hint.end_offset, target.y - target.height / 2)
        else:
            start = (source.x + hint.start_offset, source.y - source.height / 2)
            end = (target.x + hint.end_offset, target.y + target.height / 2)

        detour = _stagger_value(hint.same_slot + 1, step=14.0)
        max_detour = max(12.0, lane_width / 2 - max(source.width, target.width) / 2 - 14.0)
        detour = max(-max_detour, min(max_detour, detour))
        detour_x = (source.x + target.x) / 2 + detour
        return [start, (detour_x, start[1]), (detour_x, end[1]), end]

    direction = 1.0 if target.lane_index > source.lane_index else -1.0
    start = (
        source.x + direction * source.width / 2,
        source.y + hint.start_offset,
    )
    end = (
        target.x - direction * target.width / 2,
        target.y + hint.end_offset,
    )

    mid_x = (start[0] + end[0]) / 2 + direction * 8.0 + _stagger_value(hint.cross_slot, step=14.0)
    if direction > 0:
        mid_x = min(max(mid_x, start[0] + 16.0), end[0] - 16.0)
    else:
        mid_x = max(min(mid_x, start[0] - 16.0), end[0] + 16.0)

    return [start, (mid_x, start[1]), (mid_x, end[1]), end]


def _separate_overlapping_vertical_channels(
    connection_paths: list[list[tuple[float, float]]],
) -> list[list[tuple[float, float]]]:
    adjusted_paths: list[list[tuple[float, float]]] = [list(path) for path in connection_paths]
    occupied_channels: list[tuple[float, float, float]] = []

    for index, path in enumerate(adjusted_paths):
        base_path = list(path)
        attempt = 0
        candidate = base_path

        while _path_channel_overlaps(candidate, occupied_channels):
            attempt += 1
            candidate = _shift_path_middle_channel(base_path, _stagger_value(attempt, 8.0))
            if attempt > 10:
                break

        adjusted_paths[index] = candidate
        occupied_channels.append(_extract_vertical_channel(candidate))

    return adjusted_paths


def _path_channel_overlaps(path: list[tuple[float, float]], occupied_channels: list[tuple[float, float, float]]) -> bool:
    x, y1, y2 = _extract_vertical_channel(path)
    for occupied_x, occupied_y1, occupied_y2 in occupied_channels:
        if abs(x - occupied_x) >= 1.0:
            continue
        if _range_overlap(y1, y2, occupied_y1, occupied_y2) >= 8.0:
            return True
    return False


def _extract_vertical_channel(path: list[tuple[float, float]]) -> tuple[float, float, float]:
    x, y1 = path[1]
    _, y2 = path[2]
    return x, min(y1, y2), max(y1, y2)


def _shift_path_middle_channel(path: list[tuple[float, float]], delta_x: float) -> list[tuple[float, float]]:
    shifted = list(path)
    x1, y1 = shifted[1]
    x2, y2 = shifted[2]
    shifted[1] = (x1 + delta_x, y1)
    shifted[2] = (x2 + delta_x, y2)
    return shifted


def _range_overlap(a1: float, a2: float, b1: float, b2: float) -> float:
    low = max(min(a1, a2), min(b1, b2))
    high = min(max(a1, a2), max(b1, b2))
    return max(0.0, high - low)


def _compute_line_jumps(connection_paths: list[list[tuple[float, float]]]) -> list[LineJump]:
    segments_by_line: list[list[_Segment]] = [
        _build_segments(path_points, line_index) for line_index, path_points in enumerate(connection_paths)
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


def _build_segments(path_points: list[tuple[float, float]], line_index: int) -> list[_Segment]:
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


def _orthogonal_intersection(segment_a: _Segment, segment_b: _Segment) -> tuple[float, float] | None:
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


def _text_capacity(box: NodeBox) -> int:
    width = box.width
    if box.shape is Shape.DECISION:
        width *= 0.62
    elif box.shape is Shape.START_END:
        width *= 0.78
    elif box.shape is Shape.DATA:
        width *= 0.82
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
    return wrapped_lines[:4] if wrapped_lines else [text]


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
            base_level[next_node_id] = max(base_level[next_node_id], base_level[node_id] + 1)
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
                base_level[node.id] = max(base_level[node.id], base_level[predecessor] + 1)

    return base_level


def _place_nodes(
    diagram: Diagram,
    lane_index_by_id: dict[str, int],
    base_level: dict[str, int],
    incoming: dict[str, list[str]],
) -> dict[str, int]:
    occupied_slots: set[tuple[int, int]] = set()
    slot_by_node: dict[str, int] = {}

    for node in sorted(diagram.nodes, key=lambda item: (base_level[item.id], item.order)):
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
    ready = sorted((node.id for node in nodes if indegree[node.id] == 0), key=lambda node_id: order_lookup[node_id])
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


def _label_anchor(path_points: list[tuple[float, float]]) -> tuple[float, float]:
    if len(path_points) >= 4:
        x = (path_points[1][0] + path_points[2][0]) / 2
        y = (path_points[1][1] + path_points[2][1]) / 2 - 4.0
        return x, y
    start = path_points[0]
    end = path_points[-1]
    return (start[0] + end[0]) / 2, (start[1] + end[1]) / 2 - 4.0


def _fmt(value: float) -> str:
    return f"{value:.1f}"

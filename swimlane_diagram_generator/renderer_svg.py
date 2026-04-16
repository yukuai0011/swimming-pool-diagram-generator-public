from __future__ import annotations

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
    lane_width = 210.0
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

    # Connections first, then nodes on top.
    for connection_index, connection in enumerate(diagram.connections):
        source = boxes[connection.source]
        target = boxes[connection.target]
        path_points = _route_connection(source, target, track_index=connection_index)
        points_attr = " ".join(f"{_fmt(x)},{_fmt(y)}" for x, y in path_points)
        parts.append(
            f'  <polyline points="{points_attr}" fill="none" stroke="#111827" stroke-width="1.8" marker-end="url(#arrowhead)" />'
        )

        if connection.label:
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


def _route_connection(source: NodeBox, target: NodeBox, track_index: int = 0) -> list[tuple[float, float]]:
    if source.lane_index == target.lane_index:
        is_downward = target.y >= source.y
        if is_downward:
            start = (source.x, source.y + source.height / 2)
            end = (target.x, target.y - target.height / 2)
        else:
            start = (source.x, source.y - source.height / 2)
            end = (target.x, target.y + target.height / 2)
        mid_y = (start[1] + end[1]) / 2
        return [start, (start[0], mid_y), (end[0], mid_y), end]

    direction = 1 if target.lane_index > source.lane_index else -1
    start = (source.x + direction * source.width / 2, source.y)
    end = (target.x - direction * target.width / 2, target.y)
    elbow_x = start[0] + direction * (24.0 + (track_index % 4) * 10.0)
    return [start, (elbow_x, start[1]), (elbow_x, end[1]), end]


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
    ready = sorted((node.id for node in nodes if indegree[node.id] == 0), key=order_lookup.get)
    result: list[str] = []

    while ready:
        node_id = ready.pop(0)
        result.append(node_id)
        for next_node_id in outgoing[node_id]:
            indegree[next_node_id] -= 1
            if indegree[next_node_id] == 0:
                ready.append(next_node_id)
                ready.sort(key=order_lookup.get)

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

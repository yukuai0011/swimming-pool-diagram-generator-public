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


def _boxes_overlap(
    box1_x: float, box1_y: float, box1_w: float, box1_h: float,
    box2_x: float, box2_y: float, box2_w: float, box2_h: float,
    margin: float = 0.0,
) -> bool:
    """Check if two axis-aligned boxes overlap with optional margin."""
    return (
        box1_x - box1_w / 2 - margin < box2_x + box2_w / 2 + margin
        and box1_x + box1_w / 2 + margin > box2_x - box2_w / 2 - margin
        and box1_y - box1_h / 2 - margin < box2_y + box2_h / 2 + margin
        and box1_y + box1_h / 2 + margin > box2_y - box2_h / 2 - margin
    )


def _point_near_segment(
    px: float, py: float,
    seg_start: tuple[float, float], seg_end: tuple[float, float],
    threshold: float,
) -> bool:
    """Check if a point is within threshold distance of a line segment."""
    x1, y1 = seg_start
    x2, y2 = seg_end
    dx = x2 - x1
    dy = y2 - y1
    length_sq = dx * dx + dy * dy
    if length_sq < 1e-6:
        return (px - x1) ** 2 + (py - y1) ** 2 < threshold ** 2
    t = max(0.0, min(1.0, ((px - x1) * dx + (py - y1) * dy) / length_sq))
    closest_x = x1 + t * dx
    closest_y = y1 + t * dy
    return (px - closest_x) ** 2 + (py - closest_y) ** 2 < threshold ** 2


def _box_intersects_segment(
    box_x: float, box_y: float, box_w: float, box_h: float,
    seg_start: tuple[float, float], seg_end: tuple[float, float],
    margin: float = 0.0,
) -> bool:
    """Check if a box intersects a line segment with margin."""
    half_w = box_w / 2 + margin
    half_h = box_h / 2 + margin
    x1, y1 = seg_start
    x2, y2 = seg_end
    dx = x2 - x1
    dy = y2 - y1
    if abs(dx) < 1e-6 and abs(dy) < 1e-6:
        return _boxes_overlap(box_x, box_y, box_w, box_h, x1, y1, 0.0, 0.0, margin)
    p = -dx
    q = box_x - half_w - x1
    if abs(p) > 1e-6:
        t1 = q / p if p < 0 else float("-inf")
        t2 = q / p if p > 0 else float("inf")
    else:
        t1 = float("-inf") if q < 0 else float("inf")
        t2 = t1
    p = dx
    q = x1 + half_w - box_x
    if abs(p) > 1e-6:
        t3 = q / p if p < 0 else float("-inf")
        t4 = q / p if p > 0 else float("inf")
    else:
        t3 = float("-inf") if q < 0 else float("inf")
        t4 = t3
    t_min = max(0.0, max(t1, t3))
    t_max = min(1.0, min(t2, t4))
    if t_min > t_max:
        return False
    p = -dy
    q = box_y - half_h - y1
    if abs(p) > 1e-6:
        t5 = q / p if p < 0 else float("-inf")
        t6 = q / p if p > 0 else float("inf")
    else:
        t5 = float("-inf") if q < 0 else float("inf")
        t6 = t5
    p = dy
    q = y1 + half_h - box_y
    if abs(p) > 1e-6:
        t7 = q / p if p < 0 else float("-inf")
        t8 = q / p if p > 0 else float("inf")
    else:
        t7 = float("-inf") if q < 0 else float("inf")
        t8 = t7
    t_min_y = max(t_min, max(t5, t7))
    t_max_y = min(t_max, min(t6, t8))
    return t_min_y <= t_max_y


def _diagonal_stem_intersects_box(
    stem_start: tuple[float, float], stem_end: tuple[float, float],
    box_x: float, box_y: float, box_w: float, box_h: float,
    margin: float = 0.0,
) -> bool:
    """Check if a diagonal stem intersects a box."""
    return _box_intersects_segment(box_x, box_y, box_w, box_h, stem_start, stem_end, margin)


def _compute_label_dimensions(
    label_text: str, grid_size: float, is_vertical: bool,
) -> tuple[float, float, tuple[str, ...]]:
    """Compute label box dimensions based on text and orientation."""
    text = label_text.replace("\n", " ").strip()
    if not text:
        text = "?"
    has_cjk = any("一" <= char <= "鿿" for char in text)
    if is_vertical:
        if has_cjk:
            lines = tuple(char for char in text if char != " ")
        else:
            words = [word for word in text.split(" ") if word]
            if len(words) >= 2:
                lines = tuple(words)
            else:
                token = words[0] if words else text
                lines = tuple(
                    token[index:index + 3] for index in range(0, len(token), 3)
                )
        line_height = grid_size
        height = max(2 * grid_size, len(lines) * line_height + grid_size)
        longest = max((len(line) for line in lines), default=1)
        width = max(2 * grid_size, min(10 * grid_size, longest * grid_size * 0.6 + grid_size))
    else:
        lines = (text,)
        width = max(3 * grid_size, len(text) * grid_size * 0.6 + grid_size)
        height = 2 * grid_size
    width = snap_to_grid(width, grid_size)
    height = snap_to_grid(height, grid_size)
    return width, height, lines


def _find_label_placement(
    connection_index: int,
    points: tuple[tuple[float, float], ...],
    label_text: str,
    grid_size: float,
    boxes: dict[str, NodeBox],
    existing_labels: list[LabelBox],
    existing_stems: list[LabelStem],
    chart_bounds: tuple[float, float, float, float],
) -> tuple[LabelBox, LabelStem] | None:
    """Find a non-overlapping placement for a label with diagonal stem."""
    if not points or not label_text:
        return None
    chart_x, chart_y, chart_w, chart_h = chart_bounds
    margin = grid_size
    stem_margin = grid_size / 2
    candidate_segments = list(range(len(points) - 1))
    for seg_idx in candidate_segments:
        seg_start = points[seg_idx]
        seg_end = points[seg_idx + 1]
        dx = seg_end[0] - seg_start[0]
        dy = seg_end[1] - seg_start[1]
        is_vertical = abs(dx) < abs(dy)
        mid_x = (seg_start[0] + seg_end[0]) / 2
        mid_y = (seg_start[1] + seg_end[1]) / 2
        label_w, label_h, text_lines = _compute_label_dimensions(label_text, grid_size, is_vertical)
        offsets = [
            (grid_size * 2, 0.0),
            (-grid_size * 2, 0.0),
            (0.0, grid_size * 2),
            (0.0, -grid_size * 2),
            (grid_size * 2, grid_size * 2),
            (-grid_size * 2, grid_size * 2),
            (grid_size * 2, -grid_size * 2),
            (-grid_size * 2, -grid_size * 2),
            (grid_size * 4, 0.0),
            (-grid_size * 4, 0.0),
            (0.0, grid_size * 4),
            (0.0, -grid_size * 4),
            (grid_size * 6, 0.0),
            (-grid_size * 6, 0.0),
            (0.0, grid_size * 6),
            (0.0, -grid_size * 6),
            (grid_size * 8, 0.0),
            (-grid_size * 8, 0.0),
            (0.0, grid_size * 8),
            (0.0, -grid_size * 8),
        ]
        for off_x, off_y in offsets:
            label_x = snap_to_grid(mid_x + off_x, grid_size)
            label_y = snap_to_grid(mid_y + off_y, grid_size)
            if label_x - label_w / 2 < chart_x or label_x + label_w / 2 > chart_x + chart_w:
                continue
            if label_y - label_h / 2 < chart_y or label_y + label_h / 2 > chart_y + chart_h:
                continue
            overlaps_node = False
            for node_box in boxes.values():
                if _boxes_overlap(label_x, label_y, label_w, label_h,
                                  node_box.x, node_box.y, node_box.width, node_box.height, margin):
                    overlaps_node = True
                    break
            if overlaps_node:
                continue
            overlaps_line = False
            for other_conn_idx, other_points in enumerate(points for _ in [points]):
                if other_conn_idx == connection_index:
                    continue
            for pt_idx, pt in enumerate(points):
                if pt_idx == seg_idx or pt_idx == seg_idx + 1:
                    continue
                if _point_near_segment(pt[0], pt[1], seg_start, seg_end, margin):
                    overlaps_line = True
                    break
            if overlaps_line:
                continue
            overlaps_label = False
            for existing in existing_labels:
                if _boxes_overlap(label_x, label_y, label_w, label_h,
                                  existing.x, existing.y, existing.width, existing.height, margin):
                    overlaps_label = True
                    break
            if overlaps_label:
                continue
            anchor_x = snap_to_grid(mid_x, grid_size)
            anchor_y = snap_to_grid(mid_y, grid_size)
            stem_dx = label_x - anchor_x
            stem_dy = label_y - anchor_y
            if abs(stem_dx) < grid_size and abs(stem_dy) < grid_size:
                if abs(dx) > abs(dy):
                    stem_dx = grid_size * 2 if label_x >= anchor_x else -grid_size * 2
                else:
                    stem_dy = grid_size * 2 if label_y >= anchor_y else -grid_size * 2
            stem_end_x = snap_to_grid(anchor_x + stem_dx * 0.3, grid_size)
            stem_end_y = snap_to_grid(anchor_y + stem_dy * 0.3, grid_size)
            stem_start = (anchor_x, anchor_y)
            stem_end = (stem_end_x, stem_end_y)
            stem_intersects_node = False
            for node_box in boxes.values():
                if _diagonal_stem_intersects_box(stem_start, stem_end,
                                                  node_box.x, node_box.y, node_box.width, node_box.height, stem_margin):
                    stem_intersects_node = True
                    break
            if stem_intersects_node:
                continue
            stem_intersects_label = False
            for existing in existing_labels:
                if _diagonal_stem_intersects_box(stem_start, stem_end,
                                                  existing.x, existing.y, existing.width, existing.height, stem_margin):
                    stem_intersects_label = True
                    break
            if stem_intersects_label:
                continue
            label_box = LabelBox(
                connection_index=connection_index,
                x=label_x,
                y=label_y,
                width=label_w,
                height=label_h,
                text_lines=text_lines,
                segment_index=seg_idx,
            )
            stem = LabelStem(
                connection_index=connection_index,
                start=stem_start,
                end=stem_end,
            )
            return label_box, stem
    return None


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

    # Compute label boxes with collision avoidance
    chart_bounds = (chart_x, chart_y, chart_width, chart_height)
    placed_labels: list[LabelBox] = []
    placed_stems: list[LabelStem] = []
    connection_layouts: list[ConnectionLayout] = []

    for index, (connection, path) in enumerate(zip(diagram.connections, connection_paths)):
        label_box: LabelBox | None = None
        stem: LabelStem | None = None

        if connection.label:
            result = _find_label_placement(
                connection_index=index,
                points=tuple(path),
                label_text=connection.label,
                grid_size=grid_size,
                boxes=boxes,
                existing_labels=placed_labels,
                existing_stems=placed_stems,
                chart_bounds=chart_bounds,
            )
            if result is not None:
                label_box, stem = result
                placed_labels.append(label_box)
                if stem:
                    placed_stems.append(stem)

        connection_layouts.append(
            ConnectionLayout(
                connection_index=index,
                points=tuple(path),
                label_box=label_box,
                stem=stem,
            )
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
        connections=tuple(connection_layouts),
        line_jumps=tuple(line_jumps),
    )

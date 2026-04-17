from __future__ import annotations

from functools import lru_cache
from io import BytesIO
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from .model import Diagram, Shape
from .renderer_svg import (
    LineJump,
    NodeBox,
    _assign_vertical_slots,
    _build_boxes,
    _build_connection_paths,
    _compute_lane_width,
    _compute_line_jumps,
    _compute_node_dimensions,
    _label_anchor,
    _lane_borders_x,
    _resolve_layout_tuning,
    _snap_to_grid,
    _text_capacity,
    _wrap_text,
    get_global_min_line_gap,
)

LINE_COLOR = "#111827"
WHITE = "#ffffff"
LANE_HEADER = "#f3f4f6"
LANE_BODY = "#f8f8f8"
FontLike = ImageFont.FreeTypeFont | ImageFont.ImageFont


def render_png_bytes(diagram: Diagram) -> bytes:
    if not diagram.lanes:
        raise ValueError("Cannot render diagram without lanes.")
    if not diagram.nodes:
        raise ValueError("Cannot render diagram without nodes.")

    lane_count = len(diagram.lanes)
    lane_index_by_id = {lane.id: lane.index for lane in diagram.lanes}
    slot_by_node, slot_count = _assign_vertical_slots(diagram, lane_index_by_id)
    node_dimensions = _compute_node_dimensions(diagram, lane_index_by_id, slot_by_node)
    grid_size = get_global_min_line_gap()

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
    min_line_gap = get_global_min_line_gap()
    row_gap = _snap_to_grid(
        max(104.0, max_node_height + max(24.0, min_line_gap * 1.2)),
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
    image_width = round(chart_x * 2 + chart_width)
    image_height = round(chart_y * 2 + chart_height)

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

    jumps = _compute_line_jumps(connection_paths)

    image = Image.new("RGB", (image_width, image_height), WHITE)
    draw = ImageDraw.Draw(image)

    _draw_rect(
        draw,
        chart_x,
        chart_y,
        chart_width,
        chart_height,
        fill=WHITE,
        outline=LINE_COLOR,
        stroke_width=2,
    )

    # Title band
    _draw_rect(
        draw,
        chart_x,
        chart_y,
        chart_width,
        title_height,
        fill=WHITE,
        outline=LINE_COLOR,
        stroke_width=2,
    )
    if diagram.title:
        _draw_centered_text(
            draw,
            chart_x + chart_width / 2,
            chart_y + title_height / 2,
            diagram.title,
            _load_font(22),
            LINE_COLOR,
        )

    # Lane headers and bodies
    for lane in diagram.lanes:
        lane_x = chart_x + lane.index * lane_width
        header_y = chart_y + title_height
        _draw_rect(
            draw,
            lane_x,
            header_y,
            lane_width,
            lane_header_height,
            fill=LANE_HEADER,
            outline=LINE_COLOR,
            stroke_width=1,
        )
        _draw_centered_text(
            draw,
            lane_x + lane_width / 2,
            header_y + lane_header_height / 2,
            lane.title,
            _load_font(14),
            LINE_COLOR,
        )
        _draw_rect(
            draw,
            lane_x,
            lane_body_y,
            lane_width,
            body_height,
            fill=LANE_BODY,
            outline=LINE_COLOR,
            stroke_width=1,
        )

    # Connection lines
    for path_points in connection_paths:
        draw.line(path_points, fill=LINE_COLOR, width=3)
        _draw_arrowhead(draw, path_points[-2], path_points[-1], size=9.0)

    # Bridge bumps on crossings
    for jump in jumps:
        _draw_jump_png(draw, jump)

    # Connection labels
    for connection, path_points in zip(diagram.connections, connection_paths):
        if not connection.label:
            continue
        _draw_label(draw, path_points, connection.label)

    # Nodes
    for node in diagram.nodes:
        _draw_node_png(draw, boxes[node.id])

    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def render_png(diagram: Diagram, output_path: str | Path) -> None:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(render_png_bytes(diagram))


def _draw_rect(
    draw: ImageDraw.ImageDraw,
    x: float,
    y: float,
    rect_width: float,
    rect_height: float,
    *,
    fill: str,
    outline: str,
    stroke_width: int = 1,
) -> None:
    draw.rectangle(
        [x, y, x + rect_width, y + rect_height],
        fill=fill,
        outline=outline,
        width=stroke_width,
    )


def _draw_centered_text(
    draw: ImageDraw.ImageDraw,
    center_x: float,
    center_y: float,
    text: str,
    font: FontLike,
    color: str,
) -> None:
    bbox = draw.textbbox((0, 0), text, font=font)
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]
    draw.text(
        (center_x - text_width / 2, center_y - text_height / 2),
        text,
        font=font,
        fill=color,
    )


def _draw_node_png(draw: ImageDraw.ImageDraw, box: NodeBox) -> None:
    left = box.x - box.width / 2
    top = box.y - box.height / 2
    right = left + box.width
    bottom = top + box.height

    if box.shape is Shape.PROCESS:
        draw.rounded_rectangle(
            [left, top, right, bottom],
            radius=4,
            fill=WHITE,
            outline=LINE_COLOR,
            width=2,
        )
    elif box.shape is Shape.START_END:
        draw.rounded_rectangle(
            [left, top, right, bottom],
            radius=box.height / 2,
            fill=WHITE,
            outline=LINE_COLOR,
            width=2,
        )
    elif box.shape is Shape.DECISION:
        points = [
            (box.x, top),
            (right, box.y),
            (box.x, bottom),
            (left, box.y),
        ]
        draw.polygon(points, fill=WHITE, outline=LINE_COLOR)
    elif box.shape is Shape.SUBPROCESS:
        draw.rounded_rectangle(
            [left, top, right, bottom],
            radius=4,
            fill=WHITE,
            outline=LINE_COLOR,
            width=2,
        )
        inset = min(12.0, box.width * 0.12)
        draw.line(
            [(left + inset, top), (left + inset, bottom)], fill=LINE_COLOR, width=2
        )
        draw.line(
            [(right - inset, top), (right - inset, bottom)], fill=LINE_COLOR, width=2
        )
    elif box.shape is Shape.DOCUMENT:
        wave = min(14.0, box.height * 0.2)
        points = [
            (left, top),
            (right, top),
            (right, bottom - wave),
            (left + box.width * 0.76, bottom + wave * 0.25),
            (left + box.width * 0.52, bottom - wave * 0.2),
            (left + box.width * 0.26, bottom - wave * 0.75),
            (left, bottom - wave * 0.35),
        ]
        draw.polygon(points, fill=WHITE, outline=LINE_COLOR)
    elif box.shape is Shape.DATA:
        skew = min(20.0, box.width * 0.15)
        points = [
            (left + skew, top),
            (right, top),
            (right - skew, bottom),
            (left, bottom),
        ]
        draw.polygon(points, fill=WHITE, outline=LINE_COLOR)

    _draw_node_text(draw, box)


def _draw_node_text(draw: ImageDraw.ImageDraw, box: NodeBox) -> None:
    lines = _wrap_text(box.text, _text_capacity(box))
    line_height = 15.0
    text_center_y = box.y
    if box.shape is Shape.DOCUMENT:
        text_center_y -= box.height * 0.12

    start_y = text_center_y - (len(lines) - 1) * line_height / 2
    font = _load_font(13)

    for index, line in enumerate(lines):
        _draw_centered_text(
            draw,
            box.x,
            start_y + index * line_height,
            line,
            font,
            LINE_COLOR,
        )


def _draw_label(
    draw: ImageDraw.ImageDraw, path_points: list[tuple[float, float]], label_text: str
) -> None:
    label_x, label_y, orientation = _label_anchor(path_points)
    font = _load_font(12)

    if orientation == "vertical":
        _draw_vertical_label(draw, label_x, label_y, label_text, font)
        return

    bbox = draw.textbbox((0, 0), label_text, font=font)
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]
    pad_x = 6.0
    pad_y = 4.0

    left = label_x - text_width / 2 - pad_x
    top = label_y - text_height / 2 - pad_y
    right = label_x + text_width / 2 + pad_x
    bottom = label_y + text_height / 2 + pad_y

    draw.rounded_rectangle([left, top, right, bottom], radius=3, fill=WHITE)
    _draw_centered_text(draw, label_x, label_y, label_text, font, LINE_COLOR)


def _draw_vertical_label(
    draw: ImageDraw.ImageDraw,
    center_x: float,
    center_y: float,
    label_text: str,
    font: FontLike,
) -> None:
    chars = list(label_text) if label_text else ["?"]
    char_sizes: list[tuple[float, float]] = []
    for char in chars:
        sample = char if char.strip() else "A"
        bbox = draw.textbbox((0, 0), sample, font=font)
        char_sizes.append((bbox[2] - bbox[0], bbox[3] - bbox[1]))

    max_char_width = max((size[0] for size in char_sizes), default=8.0)
    line_height = max((size[1] for size in char_sizes), default=12.0)
    spacing = 1.0
    text_height = len(chars) * line_height + max(0, len(chars) - 1) * spacing
    pad_x = 4.0
    pad_y = 4.0

    left = center_x - max_char_width / 2 - pad_x
    top = center_y - text_height / 2 - pad_y
    right = center_x + max_char_width / 2 + pad_x
    bottom = center_y + text_height / 2 + pad_y

    draw.rounded_rectangle([left, top, right, bottom], radius=3, fill=WHITE)

    current_y = top + pad_y + line_height / 2
    for char in chars:
        if char.strip():
            _draw_centered_text(draw, center_x, current_y, char, font, LINE_COLOR)
        current_y += line_height + spacing


def _draw_jump_png(draw: ImageDraw.ImageDraw, jump: LineJump) -> None:
    radius = 5.2
    draw.ellipse(
        [jump.x - radius, jump.y - radius, jump.x + radius, jump.y + radius],
        fill=WHITE,
        outline=WHITE,
    )

    if jump.orientation == "horizontal":
        points = _quadratic_points(
            (jump.x - radius, jump.y),
            (jump.x, jump.y - radius * 1.25),
            (jump.x + radius, jump.y),
        )
    else:
        points = _quadratic_points(
            (jump.x, jump.y - radius),
            (jump.x + radius * 1.25, jump.y),
            (jump.x, jump.y + radius),
        )

    draw.line(points, fill=LINE_COLOR, width=3)


def _quadratic_points(
    start: tuple[float, float],
    control: tuple[float, float],
    end: tuple[float, float],
    *,
    steps: int = 12,
) -> list[tuple[float, float]]:
    points: list[tuple[float, float]] = []
    for index in range(steps + 1):
        t = index / steps
        x = (1 - t) ** 2 * start[0] + 2 * (1 - t) * t * control[0] + t**2 * end[0]
        y = (1 - t) ** 2 * start[1] + 2 * (1 - t) * t * control[1] + t**2 * end[1]
        points.append((x, y))
    return points


def _draw_arrowhead(
    draw: ImageDraw.ImageDraw,
    second_last: tuple[float, float],
    last: tuple[float, float],
    *,
    size: float,
) -> None:
    x1, y1 = second_last
    x2, y2 = last
    dx = x2 - x1
    dy = y2 - y1
    length = max((dx * dx + dy * dy) ** 0.5, 1e-6)
    ux = dx / length
    uy = dy / length

    base_x = x2 - ux * size
    base_y = y2 - uy * size

    # perpendicular
    px = -uy
    py = ux

    left = (base_x + px * (size * 0.45), base_y + py * (size * 0.45))
    right = (base_x - px * (size * 0.45), base_y - py * (size * 0.45))
    draw.polygon([last, left, right], fill=LINE_COLOR)


@lru_cache(maxsize=16)
def _load_font(size: int) -> FontLike:
    candidates = [
        "C:/Windows/Fonts/msyh.ttc",
        "C:/Windows/Fonts/segoeui.ttf",
        "C:/Windows/Fonts/arial.ttf",
    ]

    for candidate in candidates:
        try:
            return ImageFont.truetype(candidate, size=size)
        except OSError:
            continue

    return ImageFont.load_default()

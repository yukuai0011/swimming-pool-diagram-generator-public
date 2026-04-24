# Grid-only label layout Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Refactor the diagram layout so all geometry uses full-grid coordinates only, connection labels reserve real layout space, and both SVG and PNG render the same non-overlapping label boxes with diagonal stems.

**Architecture:** Introduce a shared `layout.py` module that owns grid snapping, line-gap configuration, node sizing, path routing, label placement, occupancy checks, and growth retries. Keep `renderer_svg.py` and `renderer_png.py` as thin drawing backends that consume a single solved `ResolvedLayout` instead of computing labels independently.

**Tech Stack:** Python 3.11, unittest, uv, Pillow, SVG string rendering

---

## File structure

- Create: `swimlane_diagram_generator/layout.py` — shared full-grid geometry solver, solved-layout dataclasses, line-gap configuration, occupancy helpers, and label/stem placement.
- Modify: `swimlane_diagram_generator/renderer_svg.py` — keep SVG-only drawing; consume `ResolvedLayout` and re-export line-gap configuration for the CLI and package API.
- Modify: `swimlane_diagram_generator/renderer_png.py` — keep PNG-only drawing; consume `ResolvedLayout` instead of `_label_anchor(...)`.
- Modify: `swimlane_diagram_generator/__init__.py` — keep public exports stable after moving shared configuration helpers.
- Modify: `swimlane_diagram_generator/cli.py` — keep `--min-line-gap` wired through the shared layout configuration.
- Create: `tests/test_layout.py` — grid-only invariants, occupancy checks, stem ownership checks, growth-loop coverage, and layout solver tests.
- Modify: `tests/test_renderer_svg.py` — replace half-grid assertions with full-grid assertions and verify solved label/stem rendering behavior.
- Modify: `tests/test_renderer_png.py` — add overlap-sample smoke coverage for the shared layout path.

### Task 1: Add shared full-grid primitives and move line-gap configuration

**Files:**
- Create: `swimlane_diagram_generator/layout.py`
- Modify: `swimlane_diagram_generator/renderer_svg.py:1-89`
- Modify: `swimlane_diagram_generator/__init__.py:1-21`
- Modify: `swimlane_diagram_generator/cli.py:1-109`
- Create: `tests/test_layout.py`
- Modify: `tests/test_renderer_svg.py:1-18`

- [ ] **Step 1: Write the failing primitive and config tests**

```python
# tests/test_layout.py
import unittest

from swimlane_diagram_generator.layout import (
    _expand_even_grid_units,
    _shape_grid_size,
    get_global_min_line_gap,
    set_global_min_line_gap,
    snap_to_grid,
)
from swimlane_diagram_generator.model import Shape


class LayoutPrimitiveTests(unittest.TestCase):
    def test_snap_to_grid_uses_full_step_only(self) -> None:
        self.assertEqual(snap_to_grid(17.9, 12.0), 12.0)
        self.assertEqual(snap_to_grid(18.0, 12.0), 24.0)
        self.assertEqual(snap_to_grid(30.0, 12.0), 24.0)

    def test_shape_grid_size_uses_even_unit_counts(self) -> None:
        self.assertEqual(_shape_grid_size(Shape.PROCESS), (4, 4))
        self.assertEqual(_shape_grid_size(Shape.START_END), (4, 4))
        self.assertEqual(_shape_grid_size(Shape.DECISION), (4, 4))
        self.assertEqual(_shape_grid_size(Shape.DOCUMENT), (4, 4))

    def test_expand_even_grid_units_preserves_even_counts(self) -> None:
        self.assertEqual(_expand_even_grid_units(4, 4), (4, 4))
        self.assertEqual(_expand_even_grid_units(5, 4), (6, 4))
        self.assertEqual(_expand_even_grid_units(4, 5), (4, 6))
        self.assertEqual(_expand_even_grid_units(5, 5), (6, 6))

    def test_line_gap_configuration_moves_to_layout_module(self) -> None:
        original_gap = get_global_min_line_gap()
        try:
            set_global_min_line_gap(18.0)
            self.assertEqual(get_global_min_line_gap(), 18.0)
        finally:
            set_global_min_line_gap(original_gap)
```

- [ ] **Step 2: Run the new tests to verify they fail**

Run: `uv run python -m unittest tests.test_layout.LayoutPrimitiveTests -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'swimlane_diagram_generator.layout'`

- [ ] **Step 3: Add the shared primitive module and move line-gap configuration into it**

```python
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
```

```python
# swimlane_diagram_generator/renderer_svg.py
from .layout import get_global_min_line_gap, set_global_min_line_gap
```

```python
# swimlane_diagram_generator/__init__.py
from .layout import get_global_min_line_gap, set_global_min_line_gap
from .renderer_svg import render_svg
```

```python
# swimlane_diagram_generator/cli.py
from .renderer_svg import render_svg
from .layout import set_global_min_line_gap
```

- [ ] **Step 4: Re-run the primitive tests**

Run: `uv run python -m unittest tests.test_layout.LayoutPrimitiveTests -v`
Expected: PASS for all 4 tests.

- [ ] **Step 5: Commit the primitive scaffolding**

```bash
git add swimlane_diagram_generator/layout.py swimlane_diagram_generator/renderer_svg.py swimlane_diagram_generator/__init__.py swimlane_diagram_generator/cli.py tests/test_layout.py tests/test_renderer_svg.py
git commit -m "refactor: add shared full-grid layout primitives"
```

### Task 2: Move node and connector geometry into a shared full-grid solver

**Files:**
- Modify: `swimlane_diagram_generator/layout.py`
- Modify: `swimlane_diagram_generator/renderer_svg.py:1-224, 437-1537`
- Modify: `swimlane_diagram_generator/renderer_png.py:1-202`
- Modify: `tests/test_layout.py`
- Modify: `tests/test_renderer_svg.py:1-389`

- [ ] **Step 1: Write the failing shared-layout tests**

```python
# tests/test_layout.py
from swimlane_diagram_generator.layout import build_layout, iter_layout_coordinates
from swimlane_diagram_generator.parser import parse_diagram

GRID_ONLY_DSL = """swimlaneDiagram
 title Grid Only

 lane a \"A\"
 lane b \"B\"

 node start in a [start/end] \"Start\"
 node collect in a process \"Collect\"
 node approve in b decision \"Approve\"

 connect start --> collect
 connect collect --> approve : route
"""


class ResolvedLayoutTests(unittest.TestCase):
    def test_build_layout_quantizes_all_coordinates_to_full_grid(self) -> None:
        diagram = parse_diagram(GRID_ONLY_DSL)
        layout = build_layout(diagram)
        grid_size = layout.grid_size

        for value in iter_layout_coordinates(layout):
            snapped = round(value / grid_size) * grid_size
            self.assertAlmostEqual(snapped, value, places=5)

    def test_node_dimensions_keep_even_grid_units(self) -> None:
        diagram = parse_diagram(GRID_ONLY_DSL)
        layout = build_layout(diagram)

        for box in layout.boxes.values():
            self.assertEqual((box.width / layout.grid_size) % 2, 0)
            self.assertEqual((box.height / layout.grid_size) % 2, 0)
```

```python
# tests/test_renderer_svg.py
from swimlane_diagram_generator.layout import build_layout

    def test_connections_snap_to_full_grid(self) -> None:
        diagram = parse_diagram(STRAIGHT_DSL)
        layout = build_layout(diagram)

        for connection_layout in layout.connections:
            for x, y in connection_layout.points:
                self.assertAlmostEqual(
                    round(x / layout.grid_size) * layout.grid_size,
                    x,
                    places=5,
                )
                self.assertAlmostEqual(
                    round(y / layout.grid_size) * layout.grid_size,
                    y,
                    places=5,
                )
```

- [ ] **Step 2: Run the shared-layout tests to verify they fail**

Run: `uv run python -m unittest tests.test_layout.ResolvedLayoutTests tests.test_renderer_svg.SvgRendererTests.test_connections_snap_to_full_grid -v`
Expected: FAIL with `ImportError` or `AttributeError` because `build_layout(...)` and `iter_layout_coordinates(...)` do not exist yet.

- [ ] **Step 3: Implement `ResolvedLayout` and move full-grid node/path solving into `layout.py`**

```python
# swimlane_diagram_generator/layout.py
from collections import defaultdict
from dataclasses import dataclass

from .model import Diagram, Node, Shape


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


def iter_layout_coordinates(layout: ResolvedLayout):
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
    lane_index_by_id = {lane.id: lane.index for lane in diagram.lanes}
    slot_by_node, slot_count = _assign_vertical_slots(diagram, lane_index_by_id)
    node_dimensions = _compute_node_dimensions(diagram, lane_index_by_id, slot_by_node)
    grid_size = get_global_min_line_gap()

    chart_x = snap_to_grid(max(24.0, grid_size * 2.0), grid_size)
    chart_y = snap_to_grid(max(24.0, grid_size * 2.0), grid_size)
    title_height = snap_to_grid(48.0 if diagram.title else 36.0, grid_size)
    lane_header_height = snap_to_grid(48.0, grid_size)
    first_row_offset = snap_to_grid(max(60.0, grid_size * 4.0), grid_size)
    row_gap = snap_to_grid(
        max(108.0, max(size[1] for size in node_dimensions.values()) + grid_size * 2.0),
        grid_size,
    )

    lane_width = _compute_lane_width(diagram, lane_index_by_id, node_dimensions=node_dimensions)
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
    base_paths = _build_connection_paths(
        diagram,
        boxes,
        lane_index_by_id,
        incident_step=incident_step,
        cross_y_step=cross_y_step,
        lane_borders_x=_lane_borders_x(chart_x, lane_width, len(diagram.lanes)),
    )
    connections = tuple(
        ConnectionLayout(connection_index=index, points=tuple(path))
        for index, path in enumerate(base_paths)
    )
    line_jumps = tuple(_compute_line_jumps(base_paths))

    chart_width = snap_to_grid(len(diagram.lanes) * lane_width, grid_size)
    chart_height = snap_to_grid(
        title_height
        + lane_header_height
        + max(
            320.0,
            first_row_offset
            + max(slot_count - 1, 0) * row_gap
            + max(size[1] for size in node_dimensions.values())
            + 60.0,
        ),
        grid_size,
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
        body_height=chart_height - title_height - lane_header_height,
        lane_width=lane_width,
        boxes=boxes,
        connections=connections,
        line_jumps=line_jumps,
    )
```

- [ ] **Step 4: Update both renderers to consume `build_layout(...)`**

```python
# swimlane_diagram_generator/renderer_svg.py
from .layout import LineJump, NodeBox, ResolvedLayout, build_layout, get_global_min_line_gap, set_global_min_line_gap


def render_svg(diagram: Diagram) -> str:
    layout = build_layout(diagram)
    parts: list[str] = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{_fmt(layout.chart_x * 2 + layout.chart_width)}" '
        f'height="{_fmt(layout.chart_y * 2 + layout.chart_height)}" '
        f'viewBox="0 0 {_fmt(layout.chart_x * 2 + layout.chart_width)} {_fmt(layout.chart_y * 2 + layout.chart_height)}">',
        "  <defs>",
        '    <marker id="arrowhead" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="8" markerHeight="8" orient="auto-start-reverse">',
        '      <path d="M 0 0 L 10 5 L 0 10 z" fill="#111827" />',
        "    </marker>",
        "  </defs>",
    ]

    for connection_layout in layout.connections:
        points_attr = " ".join(
            f"{_fmt(x)},{_fmt(y)}" for x, y in connection_layout.points
        )
        parts.append(
            f'  <polyline points="{points_attr}" fill="none" stroke="#111827" stroke-width="1.8" marker-end="url(#arrowhead)" />'
        )
```

```python
# swimlane_diagram_generator/renderer_png.py
from .layout import build_layout, get_global_min_line_gap


def render_png_bytes(diagram: Diagram) -> bytes:
    layout = build_layout(diagram)
    image_width = round(layout.chart_x * 2 + layout.chart_width)
    image_height = round(layout.chart_y * 2 + layout.chart_height)
    image = Image.new("RGB", (image_width, image_height), WHITE)
    draw = ImageDraw.Draw(image)

    for connection_layout in layout.connections:
        draw.line(connection_layout.points, fill=LINE_COLOR, width=3)
        _draw_arrowhead(draw, connection_layout.points[-2], connection_layout.points[-1], size=9.0)
```

- [ ] **Step 5: Re-run the targeted tests**

Run: `uv run python -m unittest tests.test_layout.ResolvedLayoutTests tests.test_renderer_svg.SvgRendererTests.test_connections_snap_to_full_grid -v`
Expected: PASS, and the old half-grid-only assertion is gone.

- [ ] **Step 6: Commit the shared full-grid layout migration**

```bash
git add swimlane_diagram_generator/layout.py swimlane_diagram_generator/renderer_svg.py swimlane_diagram_generator/renderer_png.py tests/test_layout.py tests/test_renderer_svg.py
git commit -m "refactor: share full-grid node and path layout"
```

### Task 3: Add solved label boxes, diagonal stems, and collision checks

**Files:**
- Modify: `swimlane_diagram_generator/layout.py`
- Modify: `swimlane_diagram_generator/renderer_svg.py:1151-1537`
- Modify: `swimlane_diagram_generator/renderer_png.py:340-399`
- Modify: `tests/test_layout.py`
- Modify: `tests/test_renderer_svg.py`
- Modify: `tests/test_renderer_png.py`

- [ ] **Step 1: Write the failing label/stem tests**

```python
# tests/test_layout.py
LABEL_DSL = """swimlaneDiagram
 title Label Occupancy

 lane left \"Left\"
 lane center \"Center\"
 lane right \"Right\"

 node a in left process \"A\"
 node b in center process \"B\"
 node c in right process \"C\"
 node d in left process \"D\"
 node e in center process \"E\"
 node f in right process \"F\"

 connect a --> c : Alpha Label
 connect d --> f : Beta Label
 connect b --> e
"""


def _pairwise(items):
    for index, first in enumerate(items):
        for second in items[index + 1 :]:
            yield first, second


class LabelPlacementTests(unittest.TestCase):
    def test_labels_do_not_overlap_nodes_paths_or_other_labels(self) -> None:
        diagram = parse_diagram(LABEL_DSL)
        layout = build_layout(diagram)
        labels = [connection.label_box for connection in layout.connections if connection.label_box]

        self.assertGreaterEqual(len(labels), 2)
        for label in labels:
            for node_box in layout.boxes.values():
                self.assertFalse(boxes_overlap(label, node_box))
            for connection in layout.connections:
                self.assertFalse(label_box_overlaps_path(label, connection.points))
        for first, second in _pairwise(labels):
            self.assertFalse(boxes_overlap(first, second))

    def test_stems_are_diagonal_and_touch_only_the_owner(self) -> None:
        diagram = parse_diagram(LABEL_DSL)
        layout = build_layout(diagram)
        stems = [connection.stem for connection in layout.connections if connection.stem]

        for connection in layout.connections:
            if connection.stem is None:
                continue
            self.assertNotEqual(connection.stem.start[0], connection.stem.end[0])
            self.assertNotEqual(connection.stem.start[1], connection.stem.end[1])
            self.assertFalse(
                stem_intersects_foreign_paths(
                    connection.stem,
                    connection.connection_index,
                    layout.connections,
                )
            )
            self.assertFalse(
                stem_intersects_foreign_boxes(
                    connection.stem,
                    connection.connection_index,
                    layout.connections,
                    tuple(layout.boxes.values()),
                )
            )
        for first, second in _pairwise(stems):
            self.assertFalse(stems_intersect(first, second))

    def test_label_can_move_to_a_non_midpoint_segment_when_needed(self) -> None:
        diagram = parse_diagram(LABEL_DSL)
        layout = build_layout(diagram)
        placed = [connection.label_box for connection in layout.connections if connection.label_box]

        self.assertTrue(any(label.segment_index != 1 for label in placed))
        self.assertTrue(all(label.segment_index >= 0 for label in placed))
```

```python
# tests/test_renderer_svg.py
    def test_render_svg_contains_solved_label_box_and_stem(self) -> None:
        diagram = parse_diagram(RENDER_DSL)
        svg = render_svg(diagram)

        self.assertIn('class="connection-label"', svg)
        self.assertIn('class="label-stem"', svg)
```

```python
# tests/test_renderer_png.py
from pathlib import Path

OVERLAP_DSL = Path("examples/overlap_test.swim").read_text(encoding="utf-8")

    def test_render_png_bytes_handles_overlap_sample(self) -> None:
        diagram = parse_diagram(OVERLAP_DSL)
        png_bytes = render_png_bytes(diagram)

        self.assertGreater(len(png_bytes), 100)
        self.assertEqual(png_bytes[:8], b"\x89PNG\r\n\x1a\n")
```

- [ ] **Step 2: Run the new label/stem tests to verify they fail**

Run: `uv run python -m unittest tests.test_layout.LabelPlacementTests tests.test_renderer_svg.SvgRendererTests.test_render_svg_contains_solved_label_box_and_stem tests.test_renderer_png.PngRendererTests.test_render_png_bytes_handles_overlap_sample -v`
Expected: FAIL because labels are still drawn from midpoint overlays and no stem geometry exists in `ResolvedLayout`.

- [ ] **Step 3: Implement label boxes, diagonal stems, and occupancy helpers in `layout.py`**

```python
# swimlane_diagram_generator/layout.py
from dataclasses import replace


def boxes_overlap(first: LabelBox | NodeBox, second: LabelBox | NodeBox) -> bool:
    first_left = first.x - first.width / 2
    first_top = first.y - first.height / 2
    first_right = first.x + first.width / 2
    first_bottom = first.y + first.height / 2
    second_left = second.x - second.width / 2
    second_top = second.y - second.height / 2
    second_right = second.x + second.width / 2
    second_bottom = second.y + second.height / 2
    return not (
        first_right <= second_left
        or second_right <= first_left
        or first_bottom <= second_top
        or second_bottom <= first_top
    )


def label_box_overlaps_path(
    label_box: LabelBox,
    points: tuple[tuple[float, float], ...],
) -> bool:
    left = label_box.x - label_box.width / 2
    top = label_box.y - label_box.height / 2
    right = label_box.x + label_box.width / 2
    bottom = label_box.y + label_box.height / 2
    for start, end in zip(points, points[1:]):
        if _segment_intersects_rect(start, end, left, top, right, bottom):
            return True
    return False


def stem_intersects_foreign_paths(
    stem: LabelStem,
    owner_connection_index: int,
    connections: tuple[ConnectionLayout, ...],
) -> bool:
    for connection in connections:
        if connection.connection_index == owner_connection_index:
            continue
        for start, end in zip(connection.points, connection.points[1:]):
            if _segments_intersect(stem.start, stem.end, start, end):
                return True
    return False


def stem_intersects_foreign_boxes(
    stem: LabelStem,
    owner_connection_index: int,
    connections: tuple[ConnectionLayout, ...],
    node_boxes: tuple[NodeBox, ...],
) -> bool:
    for node_box in node_boxes:
        if _segment_intersects_rect(
            stem.start,
            stem.end,
            node_box.x - node_box.width / 2,
            node_box.y - node_box.height / 2,
            node_box.x + node_box.width / 2,
            node_box.y + node_box.height / 2,
        ):
            return True
    for connection in connections:
        if connection.connection_index == owner_connection_index:
            continue
        if connection.label_box is None:
            continue
        if _segment_intersects_rect(
            stem.start,
            stem.end,
            connection.label_box.x - connection.label_box.width / 2,
            connection.label_box.y - connection.label_box.height / 2,
            connection.label_box.x + connection.label_box.width / 2,
            connection.label_box.y + connection.label_box.height / 2,
        ):
            return True
    return False


def stems_intersect(first: LabelStem, second: LabelStem) -> bool:
    return _segments_intersect(first.start, first.end, second.start, second.end)


def _choose_label_placement(
    connection_index: int,
    label_text: str,
    points: tuple[tuple[float, float], ...],
    occupied_boxes: list[NodeBox | LabelBox],
    connections: tuple[ConnectionLayout, ...],
    grid_size: float,
) -> tuple[LabelBox, LabelStem] | None:
    for segment_index, (start, end) in enumerate(zip(points, points[1:])):
        for label_box, stem in _candidate_label_boxes(
            connection_index,
            label_text,
            segment_index,
            start,
            end,
            grid_size,
        ):
            if any(boxes_overlap(label_box, occupied_box) for occupied_box in occupied_boxes):
                continue
            if label_box_overlaps_path(label_box, points):
                continue
            if stem_intersects_foreign_paths(stem, connection_index, connections):
                continue
            if stem_intersects_foreign_boxes(
                stem,
                connection_index,
                connections,
                tuple(box for box in occupied_boxes if isinstance(box, NodeBox)),
            ):
                continue
            if any(
                existing.stem is not None and stems_intersect(stem, existing.stem)
                for existing in connections
            ):
                continue
            return label_box, stem
    return None


def _candidate_label_boxes(
    connection_index: int,
    label_text: str,
    segment_index: int,
    start: tuple[float, float],
    end: tuple[float, float],
    grid_size: float,
) -> list[tuple[LabelBox, LabelStem]]:
    label_width = snap_to_grid(max(48.0, len(label_text) * 8.0 + grid_size), grid_size)
    label_height = snap_to_grid(24.0 + grid_size, grid_size)
    mid_x = snap_to_grid((start[0] + end[0]) / 2, grid_size)
    mid_y = snap_to_grid((start[1] + end[1]) / 2, grid_size)
    offsets = [
        (grid_size * 2, -grid_size * 2),
        (grid_size * 2, grid_size * 2),
        (-grid_size * 2, -grid_size * 2),
        (-grid_size * 2, grid_size * 2),
    ]
    candidates: list[tuple[LabelBox, LabelStem]] = []
    for dx, dy in offsets:
        label_box = LabelBox(
            connection_index=connection_index,
            x=mid_x + dx,
            y=mid_y + dy,
            width=label_width,
            height=label_height,
            text_lines=(label_text,),
            segment_index=segment_index,
        )
        stem = LabelStem(
            connection_index=connection_index,
            start=(mid_x, mid_y),
            end=(label_box.x, label_box.y),
        )
        candidates.append((label_box, stem))
    return candidates


def _segment_intersects_rect(
    start: tuple[float, float],
    end: tuple[float, float],
    left: float,
    top: float,
    right: float,
    bottom: float,
) -> bool:
    if left <= start[0] <= right and top <= start[1] <= bottom:
        return True
    if left <= end[0] <= right and top <= end[1] <= bottom:
        return True
    edges = [
        ((left, top), (right, top)),
        ((right, top), (right, bottom)),
        ((right, bottom), (left, bottom)),
        ((left, bottom), (left, top)),
    ]
    return any(
        _segments_intersect(start, end, edge_start, edge_end)
        for edge_start, edge_end in edges
    )


def _segments_intersect(
    first_start: tuple[float, float],
    first_end: tuple[float, float],
    second_start: tuple[float, float],
    second_end: tuple[float, float],
) -> bool:
    def _orientation(a, b, c) -> float:
        return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])

    o1 = _orientation(first_start, first_end, second_start)
    o2 = _orientation(first_start, first_end, second_end)
    o3 = _orientation(second_start, second_end, first_start)
    o4 = _orientation(second_start, second_end, first_end)
    return ((o1 >= 0.0) != (o2 >= 0.0)) and ((o3 >= 0.0) != (o4 >= 0.0))


def _solve_connection_labels(
    diagram: Diagram,
    boxes: dict[str, NodeBox],
    connections: tuple[ConnectionLayout, ...],
    grid_size: float,
) -> tuple[ConnectionLayout, ...] | None:
    occupied_boxes: list[NodeBox | LabelBox] = list(boxes.values())
    resolved: list[ConnectionLayout] = []

    for connection_layout, connection in zip(connections, diagram.connections):
        if not connection.label:
            resolved.append(connection_layout)
            continue

        placement = _choose_label_placement(
            connection_layout.connection_index,
            connection.label,
            connection_layout.points,
            occupied_boxes,
            tuple(resolved) + tuple(connections[len(resolved) + 1 :]),
            grid_size,
        )
        if placement is None:
            return None

        label_box, stem = placement
        occupied_boxes.append(label_box)
        resolved.append(replace(connection_layout, label_box=label_box, stem=stem))

    return tuple(resolved)

# inside build_layout(...), replace the old `connections = tuple(...)` line with:
# base_connections = tuple(ConnectionLayout(connection_index=index, points=tuple(path)) for index, path in enumerate(base_paths))
# solved_connections = _solve_connection_labels(diagram, boxes, base_connections, grid_size)
# if solved_connections is None:
#     raise ValueError("Unable to place labels without overlap on the configured grid.")
# connections = solved_connections
```

- [ ] **Step 4: Update both renderers to draw solved labels and stems instead of midpoint anchors**

```python
# swimlane_diagram_generator/renderer_svg.py
from .layout import LabelBox, LabelStem


def _draw_connection_label_svg(label_box: LabelBox, label_text: str) -> list[str]:
    left = label_box.x - label_box.width / 2
    top = label_box.y - label_box.height / 2
    return [
        f'  <rect class="connection-label" x="{_fmt(left)}" y="{_fmt(top)}" width="{_fmt(label_box.width)}" height="{_fmt(label_box.height)}" fill="#ffffff" fill-opacity="0.92" rx="3" />',
        f'  <text x="{_fmt(label_box.x)}" y="{_fmt(label_box.y)}" text-anchor="middle" dominant-baseline="middle" font-size="12" font-family="Segoe UI, Microsoft YaHei, Arial, sans-serif" fill="#111827">{escape(label_text)}</text>',
    ]


def _draw_label_stem_svg(stem: LabelStem) -> str:
    return (
        f'  <line class="label-stem" x1="{_fmt(stem.start[0])}" y1="{_fmt(stem.start[1])}" '
        f'x2="{_fmt(stem.end[0])}" y2="{_fmt(stem.end[1])}" stroke="#111827" stroke-width="1.4" />'
    )

# in render_svg(...), replace the old label loop with:
# for connection, connection_layout in zip(diagram.connections, layout.connections):
#     if connection_layout.stem is not None:
#         parts.append(_draw_label_stem_svg(connection_layout.stem))
#     if connection.label and connection_layout.label_box is not None:
#         parts.extend(_draw_connection_label_svg(connection_layout.label_box, connection.label))
```

```python
# swimlane_diagram_generator/renderer_png.py
from .layout import LabelBox, LabelStem


def _draw_label(draw: ImageDraw.ImageDraw, label_box: LabelBox, label_text: str) -> None:
    left = label_box.x - label_box.width / 2
    top = label_box.y - label_box.height / 2
    right = label_box.x + label_box.width / 2
    bottom = label_box.y + label_box.height / 2
    draw.rounded_rectangle([left, top, right, bottom], radius=3, fill=WHITE)
    _draw_centered_text(
        draw,
        label_box.x,
        label_box.y,
        label_text,
        _load_font(12),
        LINE_COLOR,
    )


def _draw_label_stem(draw: ImageDraw.ImageDraw, stem: LabelStem) -> None:
    draw.line([stem.start, stem.end], fill=LINE_COLOR, width=2)

# in render_png_bytes(...), replace the old `_draw_label(draw, path_points, connection.label)` call with:
# for connection, connection_layout in zip(diagram.connections, layout.connections):
#     if connection_layout.stem is not None:
#         _draw_label_stem(draw, connection_layout.stem)
#     if connection.label and connection_layout.label_box is not None:
#         _draw_label(draw, connection_layout.label_box, connection.label)
```

- [ ] **Step 5: Re-run the targeted label/stem tests**

Run: `uv run python -m unittest tests.test_layout.LabelPlacementTests tests.test_renderer_svg.SvgRendererTests.test_render_svg_contains_solved_label_box_and_stem tests.test_renderer_png.PngRendererTests.test_render_png_bytes_handles_overlap_sample -v`
Expected: PASS, with labels and stems coming from `ResolvedLayout` in both renderers.

- [ ] **Step 6: Commit the solved-label implementation**

```bash
git add swimlane_diagram_generator/layout.py swimlane_diagram_generator/renderer_svg.py swimlane_diagram_generator/renderer_png.py tests/test_layout.py tests/test_renderer_svg.py tests/test_renderer_png.py
git commit -m "feat: add solved label boxes and diagonal stems"
```

### Task 4: Add growth retries and verify the overlap example end-to-end

**Files:**
- Modify: `swimlane_diagram_generator/layout.py`
- Modify: `tests/test_layout.py`
- Modify: `tests/test_renderer_svg.py`
- Modify: `tests/test_renderer_png.py`
- Generate: `output/overlap_test.svg`
- Generate: `output/overlap_test.png`

- [ ] **Step 1: Write the failing growth-loop test against the overlap example**

```python
# tests/test_layout.py
from pathlib import Path

OVERLAP_DSL = Path("examples/overlap_test.swim").read_text(encoding="utf-8")


class LayoutGrowthTests(unittest.TestCase):
    def test_overlap_example_expands_until_labels_fit(self) -> None:
        diagram = parse_diagram(OVERLAP_DSL)
        layout = build_layout(diagram)
        labels = [connection.label_box for connection in layout.connections if connection.label_box]

        self.assertGreaterEqual(len(labels), 1)
        for label in labels:
            for connection in layout.connections:
                self.assertFalse(label_box_overlaps_path(label, connection.points))
        for connection in layout.connections:
            if connection.stem is None:
                continue
            self.assertFalse(
                stem_intersects_foreign_paths(
                    connection.stem,
                    connection.connection_index,
                    layout.connections,
                )
            )
            self.assertFalse(
                stem_intersects_foreign_boxes(
                    connection.stem,
                    connection.connection_index,
                    layout.connections,
                    tuple(layout.boxes.values()),
                )
            )
```

- [ ] **Step 2: Run the growth-loop test to verify it fails**

Run: `uv run python -m unittest tests.test_layout.LayoutGrowthTests -v`
Expected: FAIL because the current solver raises `ValueError` instead of retrying with larger lane or row spacing when label placement is blocked.

- [ ] **Step 3: Add growth candidates and retry label placement until it succeeds or raises**

```python
# swimlane_diagram_generator/layout.py

def _layout_growth_candidates(
    diagram: Diagram,
    lane_index_by_id: dict[str, int],
    slot_by_node: dict[str, int],
    node_dimensions: dict[str, tuple[float, float]],
    grid_size: float,
):
    base_lane_width = _compute_lane_width(
        diagram,
        lane_index_by_id,
        node_dimensions=node_dimensions,
    )
    base_row_gap = snap_to_grid(
        max(108.0, max(size[1] for size in node_dimensions.values()) + grid_size * 2.0),
        grid_size,
    )
    for lane_units in range(0, 8, 2):
        for row_units in range(0, 8, 2):
            lane_width = snap_to_grid(base_lane_width + lane_units * grid_size, grid_size)
            row_gap = snap_to_grid(base_row_gap + row_units * grid_size, grid_size)
            incident_step = snap_to_grid(grid_size + lane_units * grid_size, grid_size)
            cross_y_step = snap_to_grid(grid_size, grid_size)
            yield lane_width, row_gap, incident_step, cross_y_step


def _finalize_layout(
    diagram: Diagram,
    grid_size: float,
    chart_x: float,
    chart_y: float,
    title_height: float,
    lane_header_height: float,
    lane_body_y: float,
    lane_width: float,
    slot_count: int,
    first_row_offset: float,
    row_gap: float,
    node_dimensions: dict[str, tuple[float, float]],
    boxes: dict[str, NodeBox],
    connections: tuple[ConnectionLayout, ...],
    line_jumps: tuple[LineJump, ...],
) -> ResolvedLayout:
    chart_width = snap_to_grid(len(diagram.lanes) * lane_width, grid_size)
    chart_height = snap_to_grid(
        title_height
        + lane_header_height
        + max(
            320.0,
            first_row_offset
            + max(slot_count - 1, 0) * row_gap
            + max(size[1] for size in node_dimensions.values())
            + 60.0,
        ),
        grid_size,
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
        body_height=chart_height - title_height - lane_header_height,
        lane_width=lane_width,
        boxes=boxes,
        connections=connections,
        line_jumps=line_jumps,
    )


def build_layout(diagram: Diagram) -> ResolvedLayout:
    lane_index_by_id = {lane.id: lane.index for lane in diagram.lanes}
    slot_by_node, slot_count = _assign_vertical_slots(diagram, lane_index_by_id)
    node_dimensions = _compute_node_dimensions(diagram, lane_index_by_id, slot_by_node)
    grid_size = get_global_min_line_gap()
    chart_x = snap_to_grid(max(24.0, grid_size * 2.0), grid_size)
    chart_y = snap_to_grid(max(24.0, grid_size * 2.0), grid_size)
    title_height = snap_to_grid(48.0 if diagram.title else 36.0, grid_size)
    lane_header_height = snap_to_grid(48.0, grid_size)
    first_row_offset = snap_to_grid(max(60.0, grid_size * 4.0), grid_size)
    lane_body_y = snap_to_grid(chart_y + title_height + lane_header_height, grid_size)

    for lane_width, row_gap, incident_step, cross_y_step in _layout_growth_candidates(
        diagram,
        lane_index_by_id,
        slot_by_node,
        node_dimensions,
        grid_size,
    ):
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
        base_paths = _build_connection_paths(
            diagram,
            boxes,
            lane_index_by_id,
            incident_step=incident_step,
            cross_y_step=cross_y_step,
            lane_borders_x=_lane_borders_x(chart_x, lane_width, len(diagram.lanes)),
        )
        base_connections = tuple(
            ConnectionLayout(connection_index=index, points=tuple(path))
            for index, path in enumerate(base_paths)
        )
        solved_connections = _solve_connection_labels(
            diagram,
            boxes,
            base_connections,
            grid_size,
        )
        if solved_connections is None:
            continue
        return _finalize_layout(
            diagram,
            grid_size,
            chart_x,
            chart_y,
            title_height,
            lane_header_height,
            lane_body_y,
            lane_width,
            slot_count,
            first_row_offset,
            row_gap,
            node_dimensions,
            boxes,
            solved_connections,
            tuple(_compute_line_jumps(base_paths)),
        )

    raise ValueError("Unable to place labels without overlap on the configured grid.")
```

- [ ] **Step 4: Run the full automated test suite**

Run: `uv run python -m unittest discover -s tests -v`
Expected: PASS for `tests/test_layout.py`, `tests/test_renderer_svg.py`, and `tests/test_renderer_png.py`.

- [ ] **Step 5: Commit the growth-loop verification changes**

```bash
git add swimlane_diagram_generator/layout.py tests/test_layout.py tests/test_renderer_svg.py tests/test_renderer_png.py
git commit -m "feat: grow layout until label placement is clear"
```

- [ ] **Step 6: Generate the overlap example outputs with `uv`**

Run: `uv run swimlane-gen examples/overlap_test.swim -o output/overlap_test.svg`
Expected: `output/overlap_test.svg` exists and shows label boxes off the routed lines.

Run: `uv run swimlane-gen examples/overlap_test.swim -o output/overlap_test.png`
Expected: `output/overlap_test.png` exists and matches the same solved layout.

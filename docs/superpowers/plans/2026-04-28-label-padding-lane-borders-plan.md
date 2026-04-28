# Label padding & dotted lane separators Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Enforce label padding against all connector segments (anchor-only exception) and render internal lane separators as dotted vertical lines in both SVG and PNG.

**Architecture:** Keep label placement grid-based, but treat the padded label region as the single clearance rule against all segments. Render lane backgrounds as full-width bands and draw dotted vertical separators between lanes, leaving the outer border solid.

**Tech Stack:** Python 3.11, unittest, PIL (Pillow), SVG string rendering.

---

## File structure & responsibilities

- **Modify:** `swimlane_diagram_generator/renderer_svg.py`
  - Label padding collision checks (include own segments with anchor exception)
  - SVG lane background rendering and dotted internal separators
- **Modify:** `swimlane_diagram_generator/renderer_png.py`
  - PNG lane background rendering and dotted internal separators
- **Modify:** `tests/test_renderer_svg.py`
  - Regression test for padding vs all segments (anchor-only exception)
  - SVG dotted separators test

---

### Task 1: Add failing SVG tests for padding and dotted separators

**Files:**
- Modify: `tests/test_renderer_svg.py` (near label-placement tests and helpers)

- [ ] **Step 1: Add helper functions for segment/rect overlap with anchor exception**

Add below existing helper functions in `tests/test_renderer_svg.py`:

```python
def _segment_overlap_length(
    segment,
    rect: tuple[float, float, float, float],
) -> float:
    left, top, right, bottom = rect
    if segment.orientation == "horizontal":
        if not (top <= segment.y1 <= bottom):
            return 0.0
        low = max(min(segment.x1, segment.x2), left)
        high = min(max(segment.x1, segment.x2), right)
        return max(0.0, high - low)

    if not (left <= segment.x1 <= right):
        return 0.0
    low = max(min(segment.y1, segment.y2), top)
    high = min(max(segment.y1, segment.y2), bottom)
    return max(0.0, high - low)


def _anchor_on_segment(anchor_x: float, anchor_y: float, segment) -> bool:
    if segment.orientation == "horizontal":
        if abs(anchor_y - segment.y1) > 1e-6:
            return False
        return min(segment.x1, segment.x2) - 1e-6 <= anchor_x <= max(segment.x1, segment.x2) + 1e-6

    if abs(anchor_x - segment.x1) > 1e-6:
        return False
    return min(segment.y1, segment.y2) - 1e-6 <= anchor_y <= max(segment.y1, segment.y2) + 1e-6
```

- [ ] **Step 2: Add failing test for padding vs all segments (anchor-only exception)**

Add this test near other label-placement tests:

```python
def test_label_padding_avoids_all_lines_except_anchor(self) -> None:
    diagram = parse_diagram(OVERLAP_STRESS_DSL)
    lane_index_by_id = {lane.id: lane.index for lane in diagram.lanes}
    slot_by_node, _ = _assign_vertical_slots(diagram, lane_index_by_id)
    node_dimensions = _compute_node_dimensions(diagram, lane_index_by_id, slot_by_node)
    lane_body_y = 18.0 + 48.0 + 40.0
    lane_width = _compute_lane_width(
        diagram,
        lane_index_by_id,
        node_dimensions=node_dimensions,
    )
    lane_width, incident_step, cross_y_step = _resolve_layout_tuning(
        diagram,
        lane_index_by_id,
        slot_by_node,
        lane_width,
        lane_body_y,
        54.0,
        104.0,
        node_dimensions=node_dimensions,
    )
    boxes = _build_boxes(
        diagram,
        lane_index_by_id,
        slot_by_node,
        lane_width,
        18.0,
        lane_body_y,
        54.0,
        104.0,
        node_dimensions=node_dimensions,
    )
    paths = _build_connection_paths(
        diagram,
        boxes,
        lane_index_by_id,
        incident_step=incident_step,
        cross_y_step=cross_y_step,
    )
    placements = _compute_label_placements(diagram, paths, boxes)

    padding = get_global_min_line_gap()
    for placement in placements.values():
        rect = _placement_occupied_rect(placement, padding)
        collisions = []
        for line_index, path in enumerate(paths):
            for segment in _build_segments(path, line_index):
                overlap = _segment_overlap_length(segment, rect)
                if overlap <= 0.0:
                    continue
                if line_index == placement.connection_index and _anchor_on_segment(
                    placement.anchor_x, placement.anchor_y, segment
                ) and overlap <= 1e-6:
                    continue
                collisions.append(
                    (line_index, (segment.x1, segment.y1, segment.x2, segment.y2))
                )
        self.assertFalse(
            collisions,
            f"label '{placement.text}' padding overlaps connector segments: {collisions}",
        )
```

- [ ] **Step 3: Add failing test for dotted internal separators in SVG**

Add this test near other SVG rendering tests:

```python
def test_internal_lane_separators_are_dotted(self) -> None:
    diagram = parse_diagram(RENDER_DSL)
    svg = render_svg(diagram)

    self.assertIn('class="lane-separator"', svg)
    self.assertIn('stroke-dasharray', svg)

    # The outer border should remain solid (no dash array on the first chart rect)
    outer_rect = svg.split('\n')[3]
    self.assertNotIn('stroke-dasharray', outer_rect)
```

- [ ] **Step 4: Run the SVG tests to confirm failure (RED)**

Run: `uv run python -m unittest tests/test_renderer_svg.py -v`
Expected: FAIL
- `test_label_padding_avoids_all_lines_except_anchor` fails due to overlap
- `test_internal_lane_separators_are_dotted` fails due to missing dotted separators

- [ ] **Step 5: Commit tests**

```bash
git add tests/test_renderer_svg.py
git commit -m "test: add label padding and lane separator regressions"
```

---

### Task 2: Enforce padding against all segments with anchor exception (SVG)

**Files:**
- Modify: `swimlane_diagram_generator/renderer_svg.py` (label overlap helpers)

- [ ] **Step 1: Add anchor-on-segment helper**

Add near `_segment_rect_overlap`:

```python
def _anchor_on_segment(anchor_x: float, anchor_y: float, segment: _Segment) -> bool:
    if segment.orientation == "horizontal":
        if abs(anchor_y - segment.y1) > 1e-6:
            return False
        return min(segment.x1, segment.x2) - 1e-6 <= anchor_x <= max(segment.x1, segment.x2) + 1e-6

    if abs(anchor_x - segment.x1) > 1e-6:
        return False
    return min(segment.y1, segment.y2) - 1e-6 <= anchor_y <= max(segment.y1, segment.y2) + 1e-6
```

- [ ] **Step 2: Update overlap scoring to include own segments with anchor exception**

Replace `_foreign_line_overlap_score` body with:

```python
def _foreign_line_overlap_score(
    candidate: LabelPlacement,
    segments_by_connection: list[list[_Segment]],
    padding: float,
) -> float:
    occupied = _label_occupied_bounds(candidate, padding)
    total_overlap = 0.0
    for segments in segments_by_connection:
        for segment in segments:
            overlap = _segment_rect_overlap(segment, occupied)
            if overlap <= 0.0:
                continue
            if segment.line_index == candidate.connection_index and _anchor_on_segment(
                candidate.anchor_x,
                candidate.anchor_y,
                segment,
            ) and overlap <= 1e-6:
                continue
            total_overlap += overlap
    return total_overlap
```

- [ ] **Step 3: Run SVG tests (GREEN)**

Run: `uv run python -m unittest tests/test_renderer_svg.py -v`
Expected: PASS for padding + dotted separator tests

- [ ] **Step 4: Commit**

```bash
git add swimlane_diagram_generator/renderer_svg.py
git commit -m "fix: enforce label padding against all segments"
```

---

### Task 3: Dotted internal lane separators in SVG

**Files:**
- Modify: `swimlane_diagram_generator/renderer_svg.py` (rendering section)

- [ ] **Step 1: Render header/body bands without internal solid borders**

Replace per-lane header/body rectangles with full-width bands and add a solid horizontal line at the header/body boundary:

```python
# Header band across full width (no stroke)
parts.append(
    f'  <rect x="{_fmt(chart_x)}" y="{_fmt(chart_y + title_height)}" width="{_fmt(chart_width)}" height="{_fmt(lane_header_height)}" fill="#f3f4f6" stroke="none" />'
)
# Body band across full width (no stroke)
parts.append(
    f'  <rect x="{_fmt(chart_x)}" y="{_fmt(lane_body_y)}" width="{_fmt(chart_width)}" height="{_fmt(body_height)}" fill="#f8f8f8" stroke="none" />'
)
# Solid line between header and body
parts.append(
    f'  <line x1="{_fmt(chart_x)}" y1="{_fmt(lane_body_y)}" x2="{_fmt(chart_x + chart_width)}" y2="{_fmt(lane_body_y)}" stroke="#111827" stroke-width="1.0" />'
)
```

Keep lane title text rendering as-is (per lane).

- [ ] **Step 2: Draw dotted internal separators**

Add after header/body bands:

```python
separator_dash = _fmt(max(3.0, grid_size * 0.6))
separator_gap = _fmt(max(3.0, grid_size * 0.4))
for index in range(1, lane_count):
    x = chart_x + index * lane_width
    parts.append(
        f'  <line class="lane-separator" x1="{_fmt(x)}" y1="{_fmt(chart_y + title_height)}" '
        f'x2="{_fmt(x)}" y2="{_fmt(lane_body_y + body_height)}" '
        f'stroke="#111827" stroke-width="1.0" stroke-dasharray="{separator_dash},{separator_gap}" />'
    )
```

- [ ] **Step 3: Run SVG tests (GREEN)**

Run: `uv run python -m unittest tests/test_renderer_svg.py -v`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add swimlane_diagram_generator/renderer_svg.py
git commit -m "feat: dotted internal lane separators in svg"
```

---

### Task 4: Dotted internal lane separators in PNG

**Files:**
- Modify: `swimlane_diagram_generator/renderer_png.py`

- [ ] **Step 1: Add dotted line helper**

Add near other helpers:

```python
def _draw_dotted_vertical_line(
    draw: ImageDraw.ImageDraw,
    x: float,
    y1: float,
    y2: float,
    *,
    dash: float,
    gap: float,
    color: str,
    width: int,
) -> None:
    current = min(y1, y2)
    end = max(y1, y2)
    while current < end:
        segment_end = min(current + dash, end)
        draw.line([(x, current), (x, segment_end)], fill=color, width=width)
        current = segment_end + gap
```

- [ ] **Step 2: Replace per-lane header/body outlines with full-width bands**

In `render_png_bytes` after drawing the title band:

```python
# Header band across full width
_draw_rect(
    draw,
    chart_x,
    chart_y + title_height,
    chart_width,
    lane_header_height,
    fill=LANE_HEADER,
    outline=None,
    stroke_width=0,
)
# Body band across full width
_draw_rect(
    draw,
    chart_x,
    lane_body_y,
    chart_width,
    body_height,
    fill=LANE_BODY,
    outline=None,
    stroke_width=0,
)
# Solid line between header and body
_draw_line(draw, chart_x, lane_body_y, chart_x + chart_width, lane_body_y, LINE_COLOR, 1)
```

Also update `_draw_rect` to accept `outline: str | None` and skip outline when `None`.

Add helper for horizontal line if needed:

```python
def _draw_line(draw: ImageDraw.ImageDraw, x1: float, y1: float, x2: float, y2: float, color: str, width: int) -> None:
    draw.line([(x1, y1), (x2, y2)], fill=color, width=width)
```

- [ ] **Step 3: Draw dotted separators**

After lane titles:

```python
separator_dash = max(3.0, grid_size * 0.6)
separator_gap = max(3.0, grid_size * 0.4)
for index in range(1, lane_count):
    x = chart_x + index * lane_width
    _draw_dotted_vertical_line(
        draw,
        x,
        chart_y + title_height,
        lane_body_y + body_height,
        dash=separator_dash,
        gap=separator_gap,
        color=LINE_COLOR,
        width=1,
    )
```

- [ ] **Step 4: Run PNG test**

Run: `uv run python -m unittest tests/test_renderer_png.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add swimlane_diagram_generator/renderer_png.py
git commit -m "feat: dotted internal lane separators in png"
```

---

### Task 5: Full verification

**Files:**
- Verify: `tests/test_renderer_svg.py`, `tests/test_renderer_png.py`, `tests/test_parser.py`

- [ ] **Step 1: Run full test suite**

Run: `uv run python -m unittest discover -s tests -v`
Expected: PASS

- [ ] **Step 2: Regenerate overlap sample**

Run:
- `uv run swimlane-gen examples/overlap_test.swim -o output/overlap_test.svg`
- `uv run swimlane-gen examples/overlap_test.swim -o output/overlap_test.png`

Expected: outputs updated; Vertical Flow leader no longer overlaps its own line; dotted internal separators visible.

- [ ] **Step 3: Commit verification artifacts (optional)**

Only if you normally commit generated outputs; otherwise skip.

---

## Self-review checklist
- [ ] Spec coverage: padding vs all segments (anchor exception), dotted separators in SVG/PNG
- [ ] No placeholders or missing code
- [ ] Test-first steps included (RED → GREEN)
- [ ] Command outputs defined

---

## Execution handoff
Plan complete and saved to `docs/superpowers/plans/2026-04-28-label-padding-lane-borders-plan.md`.

Two execution options:
1) **Subagent-Driven (recommended)** — dispatch a fresh subagent per task, review between tasks
2) **Inline Execution** — execute tasks in this session using executing-plans, batch execution with checkpoints

Which approach would you like?
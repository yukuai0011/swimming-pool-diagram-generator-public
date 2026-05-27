# Connection Detour Routing Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** After computing an orthogonal connection path, detect if any segment passes through a non-terminal node's bounding box, and if so, inject detour waypoints to route around the node's edge.

**Architecture:** Post-routing detour injection in `_build_connection_paths()`. `_route_connection()` computes the initial orthogonal path, then a new detour pass checks each segment against all node boxes and inserts bends to route around any crossed nodes. Detour logic lives in three new helpers and one modified existing function.

**Tech Stack:** Pure Python, no new dependencies.

---

## File Structure

- Modify: `swimlane_diagram_generator/renderer_svg.py` — add detour helpers, update `_build_connection_paths()` to call detour pass
- Modify: `swimlane_diagram_generator/renderer_png.py` — apply same detour changes (shares path computation with SVG renderer)
- Modify: `tests/test_renderer_svg.py` — add test for detour routing

---

### Task 1: Add detour detection and injection helpers to renderer_svg.py

**Files:**
- Modify: `swimlane_diagram_generator/renderer_svg.py`

- [ ] **Step 1: Add `_node_box_bounds()` usage clarification and `_path_crosses_node()` helper**

Add below the existing helpers section (around line 1664 where `_node_box_bounds` already exists). The helper `_path_crosses_node()` checks whether a path's bounding box intersects a node's bounding box:

```python
def _path_crosses_node(
    path: list[tuple[float, float]],
    node_id: str,
    boxes: dict[str, NodeBox],
    min_line_gap: float,
) -> bool:
    """Return True if any segment of path crosses through the node's bounding box.

    A crossing is detected when a horizontal segment's y falls within the node's
    y-range AND its x-span overlaps the node's x-range, or similarly for a
    vertical segment crossing the node's x-range.
    """
    if len(path) < 2:
        return False

    left, top, right, bottom = _node_box_bounds(boxes[node_id])
    # Shrink the exclusion zone slightly so paths that merely touch the edge
    # (without entering) are not flagged.
    exclusion = min_line_gap * 0.5
    inner_left = left + exclusion
    inner_top = top + exclusion
    inner_right = right - exclusion
    inner_bottom = bottom - exclusion

    for i in range(len(path) - 1):
        x1, y1 = path[i]
        x2, y2 = path[i + 1]

        if abs(y1 - y2) < 1e-6:  # horizontal segment
            y = y1
            x_min, x_max = min(x1, x2), max(x1, x2)
            if inner_top <= y <= inner_bottom:
                if _range_overlap(x_min, x_max, inner_left, inner_right) >= 1e-6:
                    return True

        elif abs(x1 - x2) < 1e-6:  # vertical segment
            x = x1
            y_min, y_max = min(y1, y2), max(y1, y2)
            if inner_left <= x <= inner_right:
                if _range_overlap(y_min, y_max, inner_top, inner_bottom) >= 1e-6:
                    return True

    return False
```

- [ ] **Step 2: Add `_inject_detour()` helper**

```python
def _inject_detour(
    path: list[tuple[float, float]],
    crossed_node_id: str,
    boxes: dict[str, NodeBox],
    min_line_gap: float,
) -> list[tuple[float, float]]:
    """Return a new path with detour waypoints around the crossed node.

    For a horizontal segment entering the node's bounding box, route above or
    below the node. For a vertical segment, route left or right.
    Preference: above > below for horizontal; right > left for vertical.
    """
    box = boxes[crossed_node_id]
    left, top, right, bottom = _node_box_bounds(box)
    clearance = min_line_gap

    # Find the segment index where crossing occurs
    crossing_index = -1
    for i in range(len(path) - 1):
        x1, y1 = path[i]
        x2, y2 = path[i + 1]
        if abs(y1 - y2) < 1e-6:  # horizontal
            if top - clearance <= y1 <= bottom + clearance:
                x_min, x_max = min(x1, x2), max(x1, x2)
                if x_min <= right and x_max >= left:
                    crossing_index = i
                    break
        elif abs(x1 - x2) < 1e-6:  # vertical
            if left - clearance <= x1 <= right + clearance:
                y_min, y_max = min(y1, y2), max(y1, y2)
                if y_min <= bottom and y_max >= top:
                    crossing_index = i
                    break

    if crossing_index < 0:
        return path

    # Determine detour direction
    seg_x1, seg_y1 = path[crossing_index]
    seg_x2, seg_y2 = path[crossing_index + 1]

    if abs(seg_y1 - seg_y2) < 1e-6:  # horizontal segment — route above/below
        mid_x = (seg_x1 + seg_x2) / 2.0
        node_center_x = box.x
        # Check which side has more clearance from adjacent nodes
        dist_above = seg_y1 - top
        dist_below = bottom - seg_y1
        if dist_above >= dist_below:
            # Route above
            detour_y = top - clearance
            new_path = list(path)
            # Insert waypoints above
            insert_idx = crossing_index + 1
            new_path.insert(insert_idx, (mid_x, detour_y))
            new_path.insert(insert_idx + 1, (mid_x, top - clearance))
            return _snap_path_to_grid(new_path, half=True)
        else:
            # Route below
            detour_y = bottom + clearance
            new_path = list(path)
            insert_idx = crossing_index + 1
            new_path.insert(insert_idx, (mid_x, detour_y))
            new_path.insert(insert_idx + 1, (mid_x, bottom + clearance))
            return _snap_path_to_grid(new_path, half=True)
    else:  # vertical segment — route left/right
        mid_y = (seg_y1 + seg_y2) / 2.0
        dist_right = left - seg_x1
        dist_left = seg_x1 - right
        if dist_right >= dist_left:
            # Route right
            detour_x = left - clearance
            new_path = list(path)
            insert_idx = crossing_index + 1
            new_path.insert(insert_idx, (detour_x, mid_y))
            new_path.insert(insert_idx + 1, (left - clearance, mid_y))
            return _snap_path_to_grid(new_path, half=True)
        else:
            # Route left
            detour_x = right + clearance
            new_path = list(path)
            insert_idx = crossing_index + 1
            new_path.insert(insert_idx, (detour_x, mid_y))
            new_path.insert(insert_idx + 1, (right + clearance, mid_y))
            return _snap_path_to_grid(new_path, half=True)
```

- [ ] **Step 3: Add `_path_has_crossed_nodes()` top-level check**

```python
def _path_has_crossed_nodes(
    path: list[tuple[float, float]],
    boxes: dict[str, NodeBox],
    source_id: str,
    target_id: str,
    min_line_gap: float,
) -> list[str]:
    """Return list of node IDs whose bounding boxes are crossed by the path."""
    crossed = []
    for node_id, box in boxes.items():
        if node_id in (source_id, target_id):
            continue
        if _path_crosses_node(path, node_id, boxes, min_line_gap):
            crossed.append(node_id)
    return crossed
```

- [ ] **Step 4: Run tests to verify no breakage**

Run: `uv run python -m unittest discover -s tests -v 2>&1 | head -60`
Expected: All existing tests PASS

- [ ] **Step 5: Commit**

```bash
git add swimlane_diagram_generator/renderer_svg.py
git commit -m "feat: add path crossing detection helpers for detour routing"
```

---

### Task 2: Wire detour pass into `_build_connection_paths()`

**Files:**
- Modify: `swimlane_diagram_generator/renderer_svg.py:514-571`

- [ ] **Step 1: After initial path computation, inject detour pass in `_build_connection_paths()`**

In `_build_connection_paths()`, after the loop that builds `connection_paths` (around line 541, after the `connection_paths.append(...)` call) and before the `_separate_overlapping_channels` calls, add:

```python
    # Inject detour waypoints for any path that crosses intermediate nodes
    for idx, connection in enumerate(diagram.connections):
        source_id = connection.source
        target_id = connection.target
        path = connection_paths[idx]
        crossed = _path_has_crossed_nodes(
            path, boxes, source_id, target_id, min_line_gap
        )
        for node_id in crossed:
            path = _inject_detour(path, node_id, boxes, min_line_gap)
        connection_paths[idx] = path
```

Place this right before line 543 (`connection_paths = _separate_overlapping_channels(...)`).

- [ ] **Step 2: Run stress_test to verify rendering**

Run: `uv run swimlane-gen examples/stress_test.swim -o output/stress_test.svg && uv run swimlane-gen examples/stress_test.swim -o output/stress_test.png`
Expected: SVG and PNG generated without error

- [ ] **Step 3: Run full test suite**

Run: `uv run python -m unittest discover -s tests -v`
Expected: All tests PASS

- [ ] **Step 4: Commit**

```bash
git add swimlane_diagram_generator/renderer_svg.py
git commit -m "feat: inject detour waypoints when connection paths cross intermediate nodes"
```

---

### Task 3: Apply same detour changes to PNG renderer

**Files:**
- Modify: `swimlane_diagram_generator/renderer_png.py`

- [ ] **Step 1: Read renderer_png.py to find path computation location**

```bash
uv run python -c "from swimlane_diagram_generator.renderer_png import *; import inspect; [print(f'{name}: {inspect.getsourcelines(func)[1]+1}') for name,func in inspect.getmembers(__import__('swimlane_diagram_generator.renderer_png',fromlist=['_']))" 2>/dev/null | grep -E "build_connection|_route" | head -10
```

- [ ] **Step 2: Apply same detour pass to renderer_png.py**

Read `renderer_png.py` around the `_build_connection_paths` call and apply the identical detour injection block.

- [ ] **Step 3: Run tests**

Run: `uv run python -m unittest discover -s tests -v`
Expected: All tests PASS

- [ ] **Step 4: Commit**

```bash
git add swimlane_diagram_generator/renderer_png.py
git commit -m "feat: apply detour routing to PNG renderer"
```

---

### Task 4: Add regression test for detour routing

**Files:**
- Modify: `tests/test_renderer_svg.py`

- [ ] **Step 1: Add a DSL and test case for detour routing around decision nodes**

Add to `test_renderer_svg.py`:

```python
DETOUR_DECISION_DSL = """swimlaneDiagram
title Detour Routing Test

lane l1 "Lane 1"
lane l2 "Lane 2"
lane l3 "Lane 3"

node start in l1 [start/end] "Start"
node dec in l2 decision "Decision"
node mid in l2 process "Mid"
node end in l3 [start/end] "End"

connect start --> mid
connect mid --> dec
connect dec -->|pass| end
connect dec -->|fail| mid : loop
"""


def _path_segment_count(path: list[tuple[float, float]]) -> int:
    return len(path) - 1


class DetourRoutingTests(unittest.TestCase):
    def test_paths_do_not_intersect_intermediate_node_boxes(self) -> None:
        """Connections that cross a non-terminal node's bounding box get detour bends."""
        diagram = parse_diagram(DETOUR_DECISION_DSL)
        lane_index_by_id = {lane.id: lane.index for lane in diagram.lanes}
        slot_by_node, _ = _assign_vertical_slots(diagram, lane_index_by_id)
        node_dimensions = _compute_node_dimensions(
            diagram, lane_index_by_id, slot_by_node
        )
        lane_body_y = 18.0 + 48.0 + 40.0
        lane_width = _compute_lane_width(
            diagram, lane_index_by_id, node_dimensions=node_dimensions
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

        min_gap = get_global_min_line_gap()
        # For each connection path, check it doesn't intersect non-terminal node boxes
        for conn_idx, connection in enumerate(diagram.connections):
            path = paths[conn_idx]
            source_id = connection.source
            target_id = connection.target
            for node_id, box in boxes.items():
                if node_id in (source_id, target_id):
                    continue
                left, top, right, bottom = _node_box_bounds(box)
                # Shrink exclusion slightly so paths near but not through aren't flagged
                excl = min_gap * 0.5
                inner_l, inner_t = left + excl, top + excl
                inner_r, inner_b = right - excl, bottom - excl
                for i in range(len(path) - 1):
                    x1, y1 = path[i]
                    x2, y2 = path[i + 1]
                    if abs(y1 - y2) < 1e-6:  # horizontal
                        if inner_t <= y1 <= inner_b:
                            x_min, x_max = min(x1, x2), max(x1, x2)
                            self.assertFalse(
                                max(x_min, inner_l) < min(x_max, inner_r),
                                f"Connection {conn_idx} horizontal segment crosses "
                                f"node {node_id} at y={y1}",
                            )
                    elif abs(x1 - x2) < 1e-6:  # vertical
                        if inner_l <= x1 <= inner_r:
                            y_min, y_max = min(y1, y2), max(y1, y2)
                            self.assertFalse(
                                max(y_min, inner_t) < min(y_max, inner_b),
                                f"Connection {conn_idx} vertical segment crosses "
                                f"node {node_id} at x={x1}",
                            )
```

- [ ] **Step 2: Run the new test**

Run: `uv run python -m unittest tests/test_renderer_svg.py DetourRoutingTests.test_paths_do_not_intersect_intermediate_node_boxes -v`
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add tests/test_renderer_svg.py
git commit -m "test: add detour routing regression test"
```

---

### Task 5: Visual verification with stress_test

- [ ] **Step 1: Regenerate stress_test output**

Run: `uv run swimlane-gen examples/stress_test.swim -o output/stress_test.svg && uv run swimlane-gen examples/stress_test.swim -o output/stress_test.png`

- [ ] **Step 2: Use MiniMax MCP to inspect the rerouted PNG**

```bash
uv run python -c "
from swimlane_diagram_generator.parser import parse_diagram
from swimlane_diagram_generator.renderer_svg import render_svg
diagram = parse_diagram(open('examples/stress_test.swim').read())
svg = render_svg(diagram)
open('output/stress_test.svg', 'w').write(svg)
print('SVG regenerated')
"
```

- [ ] **Step 3: Commit final output**

```bash
git add output/stress_test.svg output/stress_test.png
git commit -m "feat: regenerate stress test diagrams after detour routing fix"
```

---

## Self-Review Checklist

- [ ] `_path_crosses_node()` correctly identifies horizontal/vertical segment crossings using the same range-overlap logic as line jumps
- [ ] `_inject_detour()` inserts 2 waypoints (4 total path points for the detour segment) and snaps to grid
- [ ] Detour pass is called once per connection, before `_separate_overlapping_channels` so the separation logic can still operate on the refined paths
- [ ] PNG renderer gets identical changes since it shares the same path structure
- [ ] Test DSL and assertions actually trigger a crossing scenario (the `dec` decision node sits between `mid` and `end`)
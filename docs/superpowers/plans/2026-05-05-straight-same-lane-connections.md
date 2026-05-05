# Straight Same-Lane Connections Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove unnecessary bends for same-lane vertical connections with labels, making lines straight while labels snap to the vertical segment.

**Architecture:** Modify `_route_connection` in renderer_svg.py to always return a 2-point straight path for vertically aligned same-lane connections, regardless of whether there's a label. The existing label placement logic will handle positioning labels on the vertical segment.

**Tech Stack:** Python, SVG rendering, unittest

---

## File Structure

**Modify:**
- `swimlane_diagram_generator/renderer_svg.py` - Remove the bent path logic for same-lane vertical connections with labels

**Test:**
- `tests/test_renderer_svg.py` - Add test for same-lane vertical connection with label being straight

---

### Task 1: Add failing test for same-lane vertical connection with label

**Files:**
- Modify: `tests/test_renderer_svg.py`

- [ ] **Step 1: Add test DSL and test case**

Add a new test DSL and test method to verify that same-lane vertical connections with labels produce straight (2-point) paths.

```python
SAME_LANE_LABEL_DSL = """swimlaneDiagram
title Same Lane Label Test

lane l1 "Lane A"

node n1 in l1 process "Node 1"
node n2 in l1 process "Node 2"

connect n1 -->|label text| n2
"""
```

Add test method after `test_same_lane_downward_link_is_straight`:

```python
    def test_same_lane_vertical_connection_with_label_is_straight(self) -> None:
        """Same-lane vertical connections with labels should be straight lines."""
        diagram = parse_diagram(SAME_LANE_LABEL_DSL)
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

        # The connection should be a straight 2-point path
        self.assertEqual(len(paths[0]), 2, "Same-lane vertical connection with label should be a straight 2-point path")

        # All x-coordinates should be the same (vertical line)
        path_x_coords = {round(point[0], 2) for point in paths[0]}
        self.assertEqual(len(path_x_coords), 1, "All x-coordinates should be the same for a vertical line")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run python -m unittest tests.test_renderer_svg.SvgRendererTests.test_same_lane_vertical_connection_with_label_is_straight -v`

Expected: FAIL - the test expects a 2-point path but currently gets a 4-point bent path

---

### Task 2: Implement the fix

**Files:**
- Modify: `swimlane_diagram_generator/renderer_svg.py:868-875`

- [ ] **Step 1: Modify `_route_connection` to remove bent path for same-lane vertical connections**

In `swimlane_diagram_generator/renderer_svg.py`, find the `_route_connection` function and modify lines 868-875.

**Before:**
```python
        if abs(start[0] - end[0]) < 1e-6:
            if has_label:
                channel_x = start[0] + _same_lane_label_channel_offset(source, target)
                return _snap_path_to_grid(
                    [start, (channel_x, start[1]), (channel_x, end[1]), end],
                    half=True,
                )
            return _snap_path_to_grid([start, end], half=True)
```

**After:**
```python
        if abs(start[0] - end[0]) < 1e-6:
            # Always draw straight vertical line for same-lane connections
            # Label placement will find a spot on the vertical segment
            return _snap_path_to_grid([start, end], half=True)
```

- [ ] **Step 2: Run test to verify it passes**

Run: `uv run python -m unittest tests.test_renderer_svg.SvgRendererTests.test_same_lane_vertical_connection_with_label_is_straight -v`

Expected: PASS

---

### Task 3: Run full test suite

**Files:**
- None (verification only)

- [ ] **Step 1: Run all tests to ensure no regression**

Run: `uv run python -m unittest discover -s tests -v`

Expected: All tests pass

---

### Task 4: Verify with complex example

**Files:**
- None (verification only)

- [ ] **Step 1: Generate complex example**

Run: `uv run swimlane-gen examples/complex_cross_lane_flow.swim -o output/complex_cross_lane_flow.svg`

Expected: File generated successfully

- [ ] **Step 2: Verify the fix visually**

Open `output/complex_cross_lane_flow.svg` and verify:
- `reject -> receive` (补件后重提) has a straight vertical line
- `reserve -> repack` (有库存) has a straight vertical line
- Labels are placed on or beside the vertical segments

---

### Task 5: Commit changes

**Files:**
- All modified files

- [ ] **Step 1: Commit the implementation**

```bash
git add swimlane_diagram_generator/renderer_svg.py tests/test_renderer_svg.py
git commit -m "fix: remove unnecessary bends for same-lane vertical connections with labels"
```

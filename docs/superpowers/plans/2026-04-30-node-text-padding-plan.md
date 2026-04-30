# Node Text Padding Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add explicit padding between node text and node borders so CJK text like "执行维修" doesn't sit 8px from the edge.

**Architecture:** Add `NODE_TEXT_PAD_H` and `NODE_TEXT_PAD_V` constants. Thread them into `_fit_text_in_grid_units` (sizing) and `_text_capacity_for_dimensions` (wrapping). No rendering changes — larger boxes give padding for free.

**Tech Stack:** Python, unittest

**Spec:** `docs/superpowers/specs/2026-04-30-node-text-padding-design.md`

---

### Task 1: Add constants and wire into sizing

**Files:**
- Modify: `swimlane_diagram_generator/renderer_svg.py:1840,1849,1724`

- [ ] **Step 1: Write failing test**

Add test to `tests/test_renderer_svg.py`. Import `_fit_text_in_grid_units` and `_text_capacity_for_dimensions` at the top (line ~6). Add this test method inside the existing `TestRendererSVG` class:

```python
def test_node_text_padding_grows_small_nodes(self):
    """Nodes with short CJK text should be larger than the bare minimum."""
    diagram = parse_diagram("swimlaneDiagram\ntitle T\nlane l1 \"L\"\nnode n1 in l1 process \"执行维修\"\n")
    lane_index_by_id = {lane.id: lane.index for lane in diagram.lanes}
    slot_by_node, _ = _assign_vertical_slots(diagram, lane_index_by_id)
    dimensions = _compute_node_dimensions(diagram, lane_index_by_id, slot_by_node)
    w, h = dimensions["n1"]
    base_w, base_h = _shape_size(Process.PROCESS)
    # With padding, the node must be larger than the bare shape minimum
    self.assertGreater(w, base_w)
    self.assertGreater(h, base_h)
```

Note: the test imports `Process` — actually use `Shape.PROCESS` (already importable from `swimlane_diagram_generator.renderer_svg`). Fix the test to:

```python
def test_node_text_padding_grows_small_nodes(self):
    from swimlane_diagram_generator.renderer_svg import _shape_text_box_factors
    diagram = parse_diagram('swimlaneDiagram\ntitle T\nlane l1 "L"\nnode n1 in l1 process "执行维修"\n')
    lane_index_by_id = {lane.id: lane.index for lane in diagram.lanes}
    slot_by_node, _ = _assign_vertical_slots(diagram, lane_index_by_id)
    dimensions = _compute_node_dimensions(diagram, lane_index_by_id, slot_by_node)
    w, h = dimensions["n1"]
    base_w, base_h = _shape_size(Shape.PROCESS)
    self.assertGreater(w, base_w)
    self.assertGreater(h, base_h)
```

Also add `Shape` to the imports from `swimlane_diagram_generator.renderer_svg`.

- [ ] **Step 2: Run test to verify it fails**

Run: `cd c:/Users/yukua/Downloads/swimming-pool-diagram-generator-public && python -m pytest tests/test_renderer_svg.py::TestRendererSVG::test_node_text_padding_grows_small_nodes -v`

Expected: The node "执行维修" (4 CJK chars) fits in the base 144x66 process size, so `w == base_w` and `h == base_h`. Test FAILS with `assertGreater` failure.

- [ ] **Step 3: Add constants and modify sizing functions**

In `swimlane_diagram_generator/renderer_svg.py`:

**A.** Add constants after line 73 (after `GLOBAL_RENDER_CONFIG`):

```python
NODE_TEXT_PAD_H = 8.0
NODE_TEXT_PAD_V = 6.0
```

**B.** In `_fit_text_in_grid_units` (line 1840), change:

```python
# Before:
text_width_raw = _estimate_text_width(text, 13) + 8.0
# After:
text_width_raw = _estimate_text_width(text, 13) + 8.0 + NODE_TEXT_PAD_H * 2
```

**C.** In `_fit_text_in_grid_units` (line 1849), change:

```python
# Before:
required_text_height = len(wrapped_lines) * 15.0 + 10.0
# After:
required_text_height = len(wrapped_lines) * 15.0 + 10.0 + NODE_TEXT_PAD_V * 2
```

**D.** In `_text_capacity_for_dimensions` (line 1724), change:

```python
# Before:
width = max(48.0, width - 20.0)
# After:
width = max(48.0, width - 20.0 - NODE_TEXT_PAD_H * 2)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd c:/Users/yukua/Downloads/swimming-pool-diagram-generator-public && python -m pytest tests/test_renderer_svg.py::TestRendererSVG::test_node_text_padding_grows_small_nodes -v`

Expected: PASS — node grows beyond base size.

- [ ] **Step 5: Run full test suite to check for regressions**

Run: `cd c:/Users/yukua/Downloads/swimming-pool-diagram-generator-public && python -m pytest tests/ -v`

Expected: All existing tests pass. Some may need threshold updates if they assert exact sizes — check and update if needed.

- [ ] **Step 6: Visual check**

Run: `cd c:/Users/yukua/Downloads/swimming-pool-diagram-generator-public && python -m swimlane_diagram_generator examples/complex_cross_lane_flow.swim -o output/complex_cross_lane_flow.svg`

Open SVG and verify "执行维修" and "接收退机并登记" have visible breathing room from borders.

- [ ] **Step 7: Commit**

```bash
git add swimlane_diagram_generator/renderer_svg.py tests/test_renderer_svg.py
git commit -m "feat: add explicit node text padding"
```

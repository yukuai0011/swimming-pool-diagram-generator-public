---
name: straight-same-lane-connections
description: Remove unnecessary bends for same-lane vertical connections with labels
type: project
---

# Design: Straight Same-Lane Connections

**Why:** Current routing creates unnecessary bent paths for same-lane vertical connections when they have labels. This causes visual clutter and can block multiple connection points on nodes.

**How to apply:** Modify `_route_connection` to always draw straight vertical lines for same-lane connections, letting label placement logic handle positioning.

## Problem Analysis

### Current Behavior
For same-lane connections where source and target are vertically aligned (same x-coordinate):
- Without label: Straight vertical line (correct)
- With label: Bent rectangular path with side channel (unnecessary)

### Examples from complex_cross_lane_flow.swim
1. `reject -> receive` (补件后重提): Bent path when straight line would be clearer
2. `reserve -> repack` (有库存): Bent path when straight line would be clearer

### Root Cause
In `_route_connection` (lines 868-875), when `has_label=True` and nodes are vertically aligned:
```python
if has_label:
    channel_x = start[0] + _same_lane_label_channel_offset(source, target)
    return _snap_path_to_grid(
        [start, (channel_x, start[1]), (channel_x, end[1]), end],
        half=True,
    )
```
This creates a 4-point bent path instead of a 2-point straight line.

## Solution

### Code Change
File: `swimlane_diagram_generator/renderer_svg.py`
Function: `_route_connection` (lines 868-875)

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

### Label Placement
The existing `_compute_label_placements` function already handles:
- Finding clear space for labels
- Supporting vertical label orientation
- Avoiding overlaps with nodes and other labels

No changes needed to label placement logic.

### Cleanup
The `_same_lane_label_channel_offset` function (lines 915-924) becomes unused after this change. It can be removed or kept for potential future use.

## Testing

### Verification Steps
1. Generate complex example: `uv run swimlane-gen examples/complex_cross_lane_flow.swim -o output/complex_cross_lane_flow.svg`
2. Verify `reject -> receive` has straight vertical line with label placed on it
3. Verify `reserve -> repack` has straight vertical line with label placed on it
4. Run existing tests: `uv run python -m unittest discover -s tests -v`

### Expected Results
- Same-lane vertical connections are straight lines
- Labels are correctly placed on vertical segments
- No regression in cross-lane connections or other routing scenarios

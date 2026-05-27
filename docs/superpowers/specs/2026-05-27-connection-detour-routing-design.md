---
name: 2026-05-27-connection-detour-routing-design
description: Add detour routing so connection paths route around intermediate nodes instead of passing through them
metadata:
  type: reference
---

# Design: Connection Routing Detour Around Nodes

## Problem

Connection paths are routed as simple orthogonal polylines using a start → mid-x → mid-y → end pattern. When routing between lanes, no check is made for whether the resulting path passes through the bounding box of any intermediate node. This causes lines like Decision 2 → Doc 1 and Doc 1 → Data 2 to visually pass "under" decision diamonds, making the diagram confusing.

## Approach

After the initial path is computed in `_route_connection()`, check if any segment of the path intersects the bounding box of any non-terminal node (source or target). If a crossing is detected, insert detour waypoints to route around the node's edge before continuing.

## Routing Detour Algorithm

1. Compute the initial orthogonal path as-is (no changes to routing logic).
2. For each node in the diagram (excluding the source and target of the connection being routed):
   a. Check if the path's bounding box intersects the node's bounding box.
   b. If no intersection, skip.
   c. If intersection, determine which edge to detour around: top, bottom, left, or right.
   d. Insert 2-4 waypoints to route around that edge and back to the path.
3. Normalize the resulting path (dedupe collinear points) before returning.

### Detour Direction Selection

For a horizontal segment crossing a node's bounding box:
- Compute clearance above the node vs below the node
- Prefer the direction with more clearance (fewer obstacles)

For a vertical segment crossing a node's bounding box:
- Compute clearance to the left vs right of the node
- Prefer the direction with more clearance

Minimum detour clearance: at least `min_line_gap` units from the node edge.

### Path Intersection Check

A path intersects a node if any segment (horizontal or vertical) has both:
- Its span (x for horizontal, y for vertical) overlapping the node's bounding box span
- Its perpendicular coordinate (y for horizontal, x for vertical) within the node's bounding box

This is similar to the orthogonal intersection logic used for line jumps, but used proactively to avoid crossings rather than detect them after the fact.

## Affected Functions

### `renderer_svg.py`

- **`_route_connection()`** — Primary change. After computing the initial orthogonal path, run detour injection before returning.
- **`_path_intersects_any_node()`** — New helper. Given a path and boxes dict, return list of nodes whose bounds the path crosses.
- **`_inject_detour_for_node()`** — New helper. Given a path and a node it crosses, return a new path with waypoints routing around the node's edge.
- **`_compute_detour_clearance()`** — Helper to evaluate how much space is available above/below or left/right of a node.

### `renderer_png.py`

- Same detour logic applies since PNG uses the same `_route_connection()` approach through shared rendering utilities. Ensure any path post-processing that affects SVG also applies to PNG.

## Detour Insertion Examples

### Horizontal segment crossing a diamond node

```
Before:     [Node]----    (line goes through node)
                 |
After:  [Node]--+--    (detour goes above, two bends added)
                 |
```

The path `[(x1,y), (x2,y), ...]` becomes `[(x1,y), (detour_x1, y), (detour_x1, node_top), (detour_x2, node_top), (detour_x2, y), (x2,y), ...]`

## Scope Limitations

- Only handles orthogonal segments (horizontal/vertical). No diagonal detours.
- Does not re-route paths that merely share a y/x coordinate with a node without crossing its bounding box.
- Feedback edges and same-lane connections that loop back are not special-cased — the same detour logic applies.

## Tradeoffs

- **Pros:** Surgical, doesn't affect layout algorithm, handles all node types uniformly.
- **Cons:** Adds 2-4 more points to some paths, could increase total polyline count. The stagger/step approach already reduces overlaps, this is a fallback for cases it misses.

## Test Plan

1. Re-render `stress_test.swim` — visually verify Decision 1 no longer has lines passing through it.
2. Verify all existing test diagrams render without regression.
3. Add a unit test that constructs a diagram with known crossing cases and asserts paths detour correctly.
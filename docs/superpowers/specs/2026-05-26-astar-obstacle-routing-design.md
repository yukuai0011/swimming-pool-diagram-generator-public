# A* Obstacle-Avoiding Connector Routing

## Problem

Cross-lane connector paths use a simple midpoint-based Z-route that doesn't check
whether the vertical segment passes through other nodes' bounding boxes. This causes
lines to go under/through diamond nodes and other shapes.

## Design

Replace the simple Z-route for cross-lane connections with A* grid-based pathfinding
that treats node bounding boxes as obstacles.

### Grid model

- Grid resolution: `_grid_size()` / `_grid_half_step()` (existing values)
- Grid covers the full diagram area
- Node bounding boxes (with padding) are marked as obstacle cells
- Source and target nodes are excluded from obstacles for their own connection

### A* search

- Start: source node exit point (right/left edge)
- Goal: target node entry point (left/right edge)
- Neighbors: 4-directional grid moves (up, down, left, right)
- Heuristic: Manhattan distance
- Cost: 1 per grid step, with small penalty for direction changes (prefers straight lines)
- Obstacle cells are impassable

### Path simplification

After A* finds a grid path, simplify by merging collinear segments via
existing `_normalize_path`.

### Fallback

If A* fails to find a path, fall back to the current Z-route.

### Key changes to `renderer_svg.py`

1. Add `_route_connection_avoiding_obstacles()` — A*-based cross-lane routing
2. Add `_build_obstacle_grid()` — creates obstacle map from node bounding boxes
3. Add `_astar_search()` — grid pathfinding with heuristic
4. Modify `_build_connection_paths()` to pass `boxes` dict to `_route_connection`
5. Keep existing `_separate_overlapping_channels` for line-line overlap

### Cost heuristic for aesthetics

- Prefer routes close to the direct source→target line
- Penalize direction changes to keep paths straight
- Penalize horizontal movement away from the target direction

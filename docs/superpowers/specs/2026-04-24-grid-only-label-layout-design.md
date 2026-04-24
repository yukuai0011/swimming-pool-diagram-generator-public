# Grid-only label layout design

## Summary

Refactor the shared diagram layout so all geometry uses full-grid coordinates only. Connection label boxes become first-class layout objects that reserve grid space, cannot overlap nodes, connector paths, other label boxes, or label stems, and connect back to their owning connector with diagonal stems that also avoid all occupied geometry. The same solved geometry must drive both SVG and PNG output.

## Goals

- Remove all half-grid placement from the diagram layout.
- Make nodes, connector paths, label boxes, and label stems use a single full-grid system.
- Prevent label boxes from being placed on top of connector lines.
- Prevent label boxes from overlapping nodes, connector lines, other label boxes, or label stems.
- Use diagonal stems to visually distinguish label-to-line linkage from normal connector routing.
- Allow the layout to grow in width and height when needed to preserve correctness and readability.
- Keep SVG and PNG aligned by sharing the same resolved layout geometry.
- Regenerate the overlap test SVG after implementation.

## Non-goals

- Adding new DSL syntax.
- Changing the overall swimlane concept or node ordering model.
- Preserving existing half-grid output compatibility.
- Optimizing for minimum diagram size over readability.

## Current issues

The current shared renderer logic relies on both full-grid and half-grid snapping. Helper functions such as `_snap_to_grid(..., half=True)` are used throughout chart layout, node placement, and connector routing. Connector labels are currently drawn as overlays anchored from a route midpoint rather than being part of layout solving. As a result, label boxes can sit directly over connector lines, use half-grid offsets, and are not treated as occupied geometry during routing.

## Chosen approach

Adopt a shared full-occupancy-grid layout model.

Under this model, the layout phase resolves and reserves four kinds of geometry before rendering:

1. Node footprints.
2. Connector path segments.
3. Label box footprints.
4. Diagonal label stem segments.

SVG and PNG renderers both consume this solved geometry instead of computing label placement independently.

## Design

### 1. Full-grid geometry

All layout coordinates must be quantized to the configured grid size only. Half-grid snapping is removed from the shared geometry pipeline.

Implications:

- Node centers must land on full-grid coordinates.
- Connector bend points and endpoints must land on full-grid coordinates.
- Label box anchors and stem endpoints must land on full-grid coordinates.
- Lane widths, row gaps, header heights, offsets, and body sizes should be rounded to full-grid values.
- Node footprints must use even whole-grid unit counts in both axes so centers, edges, and side attachment points all remain on-grid, such as 2x2, 4x4, or 6x4.
- Label box footprints must also use whole-grid unit dimensions.
- Text-driven node growth must expand by whole grid units while preserving even footprint counts.

### 2. Shared solved layout output

Create or refactor toward a renderer-independent layout result that contains:

- resolved node boxes
- resolved connector polylines
- resolved label boxes
- resolved diagonal stems
- occupancy information or enough geometry to validate non-overlap

SVG should render from this solved output. PNG should render from the same solved output rather than reconstructing label placement from connector paths alone.

### 3. Connector routing

Connector routing remains orthogonal. The router continues to solve paths between node edges, but every route point must use full-grid coordinates.

The router should continue to separate dense channels, but any route adjustment must preserve full-grid coordinates. If label placement cannot succeed with the current path arrangement, the solver should be allowed to:

- widen lanes
- increase row spacing
- shift route channels
- reroute paths

The solver must prefer these layout adjustments over allowing overlaps.

### 4. Label placement

Connection labels are no longer post-render overlays. Each label becomes a layout participant with a reserved rectangular footprint.

Label placement rules:

- A label may attach to any nearby segment of its owning connection, not only the route midpoint.
- Placement should prefer outward open space rather than a fixed side.
- If multiple segments are viable, prefer the segment with the cleanest non-overlapping placement.
- If nearby space is blocked, the solver should prefer rerouting or expanding layout rather than accepting a cramped or overlapping placement.
- Label boxes must align to the full-grid system.

### 5. Diagonal stems

Every placed label box connects back to its owning connector with a diagonal stem whenever possible.

Stem rules:

- Stems are visually distinct from normal connector paths.
- Stems must also use grid-aligned endpoints.
- Stem segments may be diagonal, but they must be represented and validated as explicit solved geometry.
- Stems must not intersect nodes.
- Stems must not intersect connector paths.
- Stems must not intersect label boxes.
- Stems must not intersect other stems.
- The point where a stem meets its owning connector is the only allowed stem-to-connector touch point.
- The point where a stem meets its own label box boundary is the only allowed stem-to-label touch point.
- Stems must not touch any non-owning connector or non-owning label box.

This makes ownership touch points explicit while still preserving the no-overlap rule for all unrelated geometry.


If a valid stem cannot be placed for a candidate label box, that candidate is invalid and the solver must try another placement or expand the layout.

### 6. Occupancy model

The layout engine must track occupied space for all solved geometry so placement decisions can be validated consistently.

At minimum, the occupancy model needs to support collision checks between:

- node box vs label box
- node box vs stem
- connector segment vs label box
- connector segment vs stem
- label box vs label box
- stem vs stem

This model should be shared by the path solver and label placement solver so each step sees the same constraints.

### 7. Growth strategy

Because readability and correctness take priority over compactness, layout growth is expected behavior.

If the solver cannot place a label box and valid stem without overlap, it should progressively expand the layout by tuning spacing in a controlled order, such as:

1. shift route channels
2. widen lane width
3. increase row gap
4. reroute affected paths

This can repeat until the constraints are satisfied or a clear hard limit is reached. The intended default is to find a valid readable layout, not to preserve prior compactness.

## Implementation boundaries

Likely affected areas:

- `swimlane_diagram_generator/renderer_svg.py`
- `swimlane_diagram_generator/renderer_png.py`
- tests that validate layout and rendering behavior

Preferred refactoring direction:

- keep drawing concerns in SVG and PNG backends
- move geometry solving into shared helpers or shared layout structures
- avoid duplicating label placement rules across renderers

## Verification requirements

The implementation is only complete when all of the following are true:

- No half-grid placement remains in solved diagram geometry.
- Node boxes use whole-grid dimensions and full-grid positions.
- Connector routes use full-grid positions only.
- Label boxes use full-grid positions only.
- Label boxes never overlap nodes, connector paths, other label boxes, or stems.
- Label boxes are never placed on top of connector lines.
- Stems never overlap nodes, connector paths, label boxes, or other stems.
- SVG and PNG use the same solved layout behavior.
- The overlap test example still renders successfully.
- The overlap test SVG is regenerated after the change.

## Testing plan

Add or update tests for:

- grid quantization of solved geometry
- node dimension growth in whole grid units
- collision detection for labels and stems
- label placement choosing a non-overlapping segment
- spacing expansion behavior when labels do not initially fit
- parity-oriented checks that SVG and PNG consume the same solved label layout

Also run end-to-end commands with `uv`:

- `uv run python -m unittest discover -s tests -v`
- `uv run swimlane-gen examples/overlap_test.swim -o output/overlap_test.svg`
- `uv run swimlane-gen examples/overlap_test.swim -o output/overlap_test.png`

## Open decisions resolved during brainstorming

- Use a full occupancy-grid layout model rather than a heuristic overlay fix.
- Apply the strict rules to both SVG and PNG.
- Include other label boxes in the non-overlap rule.
- Use diagonal label stems by default because they are visually distinct from normal connector lines.
- Permit diagram growth when needed for clarity and correctness.
- Prefer outward open space for label placement.
- Allow labels to attach to any nearby segment that yields the cleanest result.
- Require stems to avoid nodes, connector lines, label boxes, and other stems.
- Apply the no-half-grid rule to all diagram geometry, not just labels.

## Expected outcome

After the refactor, the renderer should produce diagrams where all visible geometry follows a single whole-grid system, label boxes clearly belong to their connectors through diagonal stems, and labels never sit on top of lines or any other occupied object.
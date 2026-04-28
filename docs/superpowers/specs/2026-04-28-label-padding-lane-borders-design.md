# Label padding enforcement & dotted lane separators (2026-04-28)

## Summary
This design tightens label placement so padding is the only clearance rule, and updates lane borders so the outermost border stays solid while internal lane separators are dotted in both SVG and PNG.

## Goals
- Enforce label padding against all connector segments, including the label’s own connection.
- Allow only a single attachment point at the label anchor (no other overlaps).
- Keep leader lines 1×1 diagonal and snapped to integer grid.
- Render internal lane separators as dotted vertical lines, while the outermost border remains solid.

## Non-goals
- No changes to the DSL syntax.
- No additional label styles or new shapes.
- No global styling overhaul beyond lane border dashes.

## Requirements
- Label padding must not overlap any connector segment, including the label’s own connection.
- Only the anchor point is allowed to touch the connection line.
- Padding may overlap the swimlane border (allowed exception).
- Internal lane separators are dotted in SVG and PNG; the outermost border remains solid.

## Approach

### 1) Padding-only collision model
- Treat the label’s occupied region (label box + leader line) with 1-grid padding as the only clearance rule.
- Check that padded region does not intersect any connector segment, including the label’s own connection.
- Allow a tiny anchor exception: the label may touch its own connection only at the anchor point.
- No special-case “leader-only” checks beyond the padding rule; the leader is already inside the padded region.

### 2) Candidate evaluation
- Reuse existing candidate generation and constrained-first selection.
- Update the overlap scoring to include the label’s own segments, with only the anchor exception allowed.
- If no valid candidate remains, apply a minimal reroute fallback:
  - For same-lane labeled links: insert a single dogleg channel (one grid away) and re-evaluate.
  - If still blocked, expand lane width by one grid and re-evaluate.

### 3) Lane border rendering
- Outer border remains a solid rectangle.
- Internal lane separators are dotted vertical lines spanning lane header + body (not the title band).
- SVG:
  - Draw dotted vertical lines at internal lane borders using stroke-dasharray.
  - Avoid double borders by removing solid internal strokes from lane header/body rectangles.
- PNG:
  - Draw dotted separators manually by stitching short vertical segments with gaps.
  - Use a dash pattern derived from grid size (for example: dash = grid * 0.6, gap = grid * 0.4).

## Testing
- Add a regression test using overlap_test.swim ensuring:
  - Padded label region does not intersect any connector segment (including its own), except at the anchor.
- Add an SVG test that verifies:
  - Internal lane separators use dotted strokes.
  - The outermost border is solid (no stroke-dasharray).
- Manual check for PNG dotted separators (visual inspection of overlap_test.png).

## Acceptance criteria
- Vertical Flow label’s leader no longer crosses its own connection beyond the anchor point.
- Label padding does not overlap any connector line, except anchor contact.
- Internal lane separators are dotted in SVG and PNG; outer border remains solid.

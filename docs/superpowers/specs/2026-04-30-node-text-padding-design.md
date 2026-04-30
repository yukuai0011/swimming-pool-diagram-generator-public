# Node Text Padding

## Problem

Node text sits too close to node borders. No explicit padding constant exists — spacing is implicit from grid sizing and text-box factors. CJK text like "执行维修" (4 chars) produces a 60x36 node with only ~8px bottom clearance. "接收退机并登记" gets 84x60 but is still visually tight.

## Solution

Add explicit horizontal and vertical padding constants to the node sizing pipeline. The sizing loop in `_fit_text_in_grid_units` already grows nodes when text doesn't fit — padding just increases the space the text "needs."

## Constants

```python
NODE_TEXT_PAD_H = 8.0   # horizontal padding, each side (px)
NODE_TEXT_PAD_V = 6.0   # vertical padding, each side (px)
```

## Changes

### 1. `_fit_text_in_grid_units` (renderer_svg.py ~line 1832)

- `text_width_raw` (line 1840): add `NODE_TEXT_PAD_H * 2` to raw width so nodes grow wide enough
- `required_text_height` (line 1849): add `NODE_TEXT_PAD_V * 2` so nodes grow tall enough
- Loop condition unchanged — it already grows width_units/height_units until fit

### 2. `_text_capacity_for_dimensions` (renderer_svg.py ~line 1721)

- Bump `20.0` subtracted from width to `20.0 + NODE_TEXT_PAD_H * 2` (i.e., 36.0)
- This keeps wrapping capacity consistent with the new sizing

### 3. No change to `_draw_node`

Text is center-aligned in the box. Larger box = more padding automatically.

## Impact

- Nodes with short CJK text (4-7 chars) grow slightly (roughly +12px wide, +12px tall)
- Long-text nodes already have enough room — no change
- Diagram density increases marginally
- All shapes (process, decision, subprocess, document, data, start/end) affected equally since `_fit_text_in_grid_units` handles all

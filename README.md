# swimming-pool-diagram-generator

Generate **vertical swimlane process diagrams** (similar to classic Visio swimlanes) from a Mermaid-like text DSL, and export to SVG/PNG.

Current scope (v0.1):

- Vertical swimlanes (lanes are columns)
- Compact auto layout (packs independent nodes into shared rows for better space efficiency)
- Output formats: `svg` and `png`
- Node types:
  - `process`
  - `decision`
  - `subprocess`
  - `start/end`
  - `document`
  - `data`
- Connection lines with optional label/explanation text
- Orientation-aware labels (vertical labels on vertical connector segments)
- Crossing-line jump bumps (Visio-style bridge effect)
- Adaptive lane width under high connection density to reduce full line overlap
- Iterative readability pass: expands lane width further if connector channels are still visually dense
- Global connector spacing setting (`min_line_gap`) for both horizontal and vertical channels
- Automatic node size adjustment from connector pressure and text length
- Automatic text wrapping/newline layout inside nodes when additional space is available
- Flow order: **lanes → nodes → connections**

## Quick start (with uv)

1. Sync environment:

	`uv sync`

2. See a ready-to-use DSL example:

	`uv run python -m swimlane_diagram_generator --example`

3. Render an SVG from the included sample:

	`uv run swimlane-gen examples/vertical_return_flow.swim -o output/vertical_return_flow.svg`

3.1 Render PNG (auto-detected from output suffix):

  `uv run swimlane-gen examples/vertical_return_flow.swim -o output/vertical_return_flow.png`

3.2 Or specify format explicitly:

  `uv run swimlane-gen examples/vertical_return_flow.swim -f png`

3.3 Increase global minimum connector spacing (px):

  `uv run swimlane-gen examples/complex_cross_lane_flow.swim --min-line-gap 16 -o output/complex_cross_lane_flow.svg`

4. Render a more complex sample (cross-lane, loopback, and crossing-line scenarios):

  `uv run swimlane-gen examples/complex_cross_lane_flow.swim -o output/complex_cross_lane_flow.svg`

## Mermaid-like DSL

Example:

```text
swimlaneDiagram
title 匈牙利售后退货流程（示例）

lane partner "合作服务商"
lane aftersales "售后部"
lane logistics "物流部"
lane warehouse "仓库部"
lane sales "销售部"

node start in partner [start/end] "开始"
node intake in partner process "接收退机"
node inspect in aftersales decision "是否可修"
node repair in logistics subprocess "可修-完成修复"
node scrap in aftersales process "报废"
node move in warehouse data "从 CNSI DOA 移至 HU DOA"
node order in sales document "创建 Sales Order"

connect start --> intake
connect intake --> inspect
connect inspect -->|可修| repair
connect inspect -->|不可修| scrap
connect repair --> move
connect move --> order : 同步销售流程
```

### Syntax rules

- `lane` declarations must come first.
- `node` declarations come after lanes.
- `connect` lines come after nodes.
- Node IDs and explicit lane IDs should use letters/numbers/`_`/`-` (Mermaid style), e.g. `order_1`.
- Connection label styles supported:
  - `A -->|label| B`
  - `A --> B : label`

### Output selection

- If `--format` is provided, it controls output (`svg` or `png`).
- Otherwise, format is inferred from `--output` suffix.
- Default is `svg`.

### Global spacing setting

- `--min-line-gap <number>` sets the global minimum distance (in pixels) between parallel connector channels.
- This setting affects both horizontal and vertical line spacing for the entire render pass.
- The setting also influences minimum node side span when many connectors attach on one side.

## Project structure

- `swimlane_diagram_generator/model.py`: dataclasses + shape enum
- `swimlane_diagram_generator/parser.py`: DSL parser + validation
- `swimlane_diagram_generator/renderer_svg.py`: SVG layout + rendering
- `swimlane_diagram_generator/renderer_png.py`: PNG layout + rendering
- `swimlane_diagram_generator/cli.py`: command-line entrypoint
- `examples/vertical_return_flow.swim`: sample DSL
- `examples/complex_cross_lane_flow.swim`: advanced DSL with branching + crossing connectors

## Run tests

`uv run python -m unittest discover -s tests -v`
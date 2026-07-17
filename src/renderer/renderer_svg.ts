// Minimal SVG renderer placeholder.
//
// This is intentionally a *very* simple first pass that mirrors the public
// contract of swimlane_diagram_generator.renderer_svg.render_svg. It produces
// a readable SVG so the CLI can be exercised end-to-end and the structure can
// be visualised. A full grid/port-based port of renderer_svg.py will replace
// this in a follow-up pass.
//
// What it does:
//   - Lays lanes out left-to-right as columns of equal width
//   - Stacks nodes vertically inside each lane (one per row)
//   - Draws orthogonal connectors with simple L-shaped paths
//   - Renders common node shapes (process/decision/subprocess/start_end/
//     document/data) using the same identifier glyphs as Python version
//
// What it does NOT do yet (will be filled in during the full port):
//   - Grid-aligned routing, bridge-jump ("hop") markers at crossings
//   - Adaptive lane widths driven by connector density
//   - Vertical labels on vertical connector segments, oriented label boxes
//   - Cross-lane jump detection for clean crossings
//
// The intent of this placeholder is purely "the project compiles and runs".

import type { Diagram, Node, Shape } from "../model/model.ts";

export interface RenderGlobalConfig {
  minLineGap: number;
}

const DEFAULT_CONFIG: RenderGlobalConfig = { minLineGap: 8 };

let GLOBAL_CONFIG: RenderGlobalConfig = { ...DEFAULT_CONFIG };

export function setGlobalMinLineGap(minLineGap: number): void {
  GLOBAL_CONFIG = { ...GLOBAL_CONFIG, minLineGap };
}

export function getGlobalMinLineGap(): number {
  return GLOBAL_CONFIG.minLineGap;
}

export function resetGlobalConfig(): void {
  GLOBAL_CONFIG = { ...DEFAULT_CONFIG };
}

interface NodeVisual {
  node: Node;
  cx: number;
  cy: number;
  width: number;
  height: number;
}

function nodeShapeSize(shape: Shape): { width: number; height: number } {
  switch (shape) {
    case "decision":
      return { width: 130, height: 70 };
    case "start_end":
      return { width: 110, height: 50 };
    case "subprocess":
      return { width: 160, height: 60 };
    case "document":
      return { width: 150, height: 70 };
    case "data":
      return { width: 150, height: 60 };
    case "process":
    default:
      return { width: 150, height: 60 };
  }
}

function svgEscape(value: string): string {
  return value
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&apos;");
}

function escapeXml(s: string): string {
  return s
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function fmt(n: number): string {
  return Number.isInteger(n) ? n.toString() : n.toFixed(2);
}

function drawShape(shape: Shape, x: number, y: number, w: number, h: number, text: string): string {
  const cx = x + w / 2;
  const cy = y + h / 2;
  const safeText = escapeXml(text);

  switch (shape) {
    case "decision":
      // Diamond: half-extent based on width/height
      return [
        `<g>`,
        `<polygon points="${fmt(cx)},${fmt(y)} ${fmt(x + w)},${fmt(cy)} ${fmt(cx)},${fmt(y + h)} ${fmt(x)},${fmt(cy)}" `,
        `fill="#ffffff" stroke="#333333" stroke-width="1.5"/>`,
        `<text x="${fmt(cx)}" y="${fmt(cy)}" text-anchor="middle" dominant-baseline="middle" font-family="Helvetica, Arial, sans-serif" font-size="13" fill="#222">`,
        safeText,
        `</text>`,
        `</g>`,
      ].join("");
    case "start_end":
      return [
        `<g>`,
        `<rect x="${fmt(x)}" y="${fmt(y)}" width="${fmt(w)}" height="${fmt(h)}" rx="${fmt(h / 2)}" ry="${fmt(h / 2)}" `,
        `fill="#ffffff" stroke="#333333" stroke-width="1.5"/>`,
        `<text x="${fmt(cx)}" y="${fmt(cy)}" text-anchor="middle" dominant-baseline="middle" font-family="Helvetica, Arial, sans-serif" font-size="13" fill="#222">`,
        safeText,
        `</text>`,
        `</g>`,
      ].join("");
    case "subprocess":
      return [
        `<g>`,
        `<rect x="${fmt(x)}" y="${fmt(y)}" width="${fmt(w)}" height="${fmt(h)}" fill="#ffffff" stroke="#333333" stroke-width="1.5"/>`,
        // Double side rails to evoke a predefined-process shape.
        `<line x1="${fmt(x + 8)}" y1="${fmt(y)}" x2="${fmt(x + 8)}" y2="${fmt(y + h)}" stroke="#333333" stroke-width="1.5"/>`,
        `<line x1="${fmt(x + w - 8)}" y1="${fmt(y)}" x2="${fmt(x + w - 8)}" y2="${fmt(y + h)}" stroke="#333333" stroke-width="1.5"/>`,
        `<text x="${fmt(cx)}" y="${fmt(cy)}" text-anchor="middle" dominant-baseline="middle" font-family="Helvetica, Arial, sans-serif" font-size="13" fill="#222">`,
        safeText,
        `</text>`,
        `</g>`,
      ].join("");
    case "document": {
      // Document: rectangle with a wavy bottom edge simulated via a path.
      const wave = h * 0.85;
      return [
        `<g>`,
        `<path d="M ${fmt(x)} ${fmt(y)} L ${fmt(x + w)} ${fmt(y)} L ${fmt(x + w)} ${fmt(y + wave)} ` +
          `Q ${fmt(cx)} ${fmt(y + h)} ${fmt(x)} ${fmt(y + wave)} Z" ` +
          `fill="#ffffff" stroke="#333333" stroke-width="1.5"/>`,
        `<text x="${fmt(cx)}" y="${fmt(cy - 5)}" text-anchor="middle" dominant-baseline="middle" font-family="Helvetica, Arial, sans-serif" font-size="13" fill="#222">`,
        safeText,
        `</text>`,
        `</g>`,
      ].join("");
    }
    case "data": {
      // Parallelogram.
      const skew = Math.min(20, w * 0.15);
      return [
        `<g>`,
        `<polygon points="${fmt(x + skew)},${fmt(y)} ${fmt(x + w)},${fmt(y)} ${fmt(x + w - skew)},${fmt(y + h)} ${fmt(x)},${fmt(y + h)}" `,
        `fill="#ffffff" stroke="#333333" stroke-width="1.5"/>`,
        `<text x="${fmt(cx)}" y="${fmt(cy)}" text-anchor="middle" dominant-baseline="middle" font-family="Helvetica, Arial, sans-serif" font-size="13" fill="#222">`,
        safeText,
        `</text>`,
        `</g>`,
      ].join("");
    }
    case "process":
    default:
      return [
        `<g>`,
        `<rect x="${fmt(x)}" y="${fmt(y)}" width="${fmt(w)}" height="${fmt(h)}" rx="6" ry="6" `,
        `fill="#ffffff" stroke="#333333" stroke-width="1.5"/>`,
        `<text x="${fmt(cx)}" y="${fmt(cy)}" text-anchor="middle" dominant-baseline="middle" font-family="Helvetica, Arial, sans-serif" font-size="13" fill="#222">`,
        safeText,
        `</text>`,
        `</g>`,
      ].join("");
  }
}

export function renderSvg(diagram: Diagram): string {
  const padding = 40;
  const headerHeight = 60;
  const laneWidth = 220;
  const laneHeaderHeight = 40;
  const rowGap = 30;
  const nodeGap = 16;

  // Group nodes by lane.
  const nodesByLane = new Map<string, Node[]>();
  for (const lane of diagram.lanes) nodesByLane.set(lane.id, []);
  for (const node of diagram.nodes) {
    const arr = nodesByLane.get(node.laneId);
    if (arr) arr.push(node);
  }

  const visuals: NodeVisual[] = [];
  const laneTops: number[] = [];
  const laneLefts: number[] = [];

  let runningY = padding + headerHeight;
  let rowIndex = 0;
  // Simplified: each node gets its own row (one-node-per-row layout).
  // This is enough for a placeholder while the grid layout is rebuilt.
  const rowWidths = diagram.nodes.map((n) => nodeShapeSize(n.shape).width);
  while (rowIndex < diagram.nodes.length) {
    // not used yet — placeholder doesn't share rows
    rowIndex++;
  }

  let columnHeightMax = 0;
  for (let li = 0; li < diagram.lanes.length; li++) {
    const lane = diagram.lanes[li]!;
    const laneNodes = nodesByLane.get(lane.id) ?? [];
    let y = runningY + laneHeaderHeight;
    for (const node of laneNodes) {
      const size = nodeShapeSize(node.shape);
      const cx = padding + li * (laneWidth + nodeGap) + laneWidth / 2;
      const x = cx - size.width / 2;
      const cy = y + size.height / 2;
      visuals.push({ node, cx, cy, width: size.width, height: size.height });
      y += size.height + 24;
    }
    const columnHeight = y - runningY;
    columnHeightMax = Math.max(columnHeightMax, columnHeight);
  }

  const totalWidth = padding * 2 + diagram.lanes.length * laneWidth + Math.max(0, diagram.lanes.length - 1) * nodeGap;
  const totalHeight = padding + headerHeight + columnHeightMax + padding;

  // Lane header band coordinates.
  for (let li = 0; li < diagram.lanes.length; li++) {
    laneTops.push(padding);
    laneLefts.push(padding + li * (laneWidth + nodeGap));
  }

  const visualById = new Map<string, NodeVisual>();
  for (const v of visuals) visualById.set(v.node.id, v);

  const svgParts: string[] = [];
  svgParts.push(
    `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${fmt(totalWidth)} ${fmt(totalHeight)}" width="${fmt(totalWidth)}" height="${fmt(totalHeight)}">`,
  );

  // Style block — chosen to closely mimic the Python renderer defaults.
  svgParts.push(
    `<defs><style>.lane-band{fill:#f5f7fa}.lane-divider{stroke:#9aa6b2;stroke-width:1}.conn{stroke:#3a4a5c;stroke-width:1.4;fill:none}.conn-label{fill:#1a2733;font-family:Helvetica,Arial,sans-serif;font-size:12px}</style></defs>`,
  );

  // Background.
  svgParts.push(`<rect x="0" y="0" width="${fmt(totalWidth)}" height="${fmt(totalHeight)}" fill="#ffffff"/>`);

  // Title.
  if (diagram.title) {
    svgParts.push(
      `<text x="${fmt(padding)}" y="${fmt(padding + 28)}" font-family="Helvetica, Arial, sans-serif" font-size="22" fill="#1a2733" font-weight="600">`,
      escapeXml(diagram.title),
      `</text>`,
    );
  }

  // Lane headers + backgrounds + vertical dividers.
  for (let li = 0; li < diagram.lanes.length; li++) {
    const lane = diagram.lanes[li]!;
    const x = laneLefts[li]!;
    const y = laneTops[li]!;
    svgParts.push(
      `<rect class="lane-band" x="${fmt(x)}" y="${fmt(y)}" width="${fmt(laneWidth)}" height="${fmt(totalHeight - y - padding)}" />`,
      `<text x="${fmt(x + laneWidth / 2)}" y="${fmt(y + laneHeaderHeight / 2)}" text-anchor="middle" dominant-baseline="middle" font-family="Helvetica, Arial, sans-serif" font-size="15" fill="#1a2733" font-weight="600">`,
      escapeXml(lane.title),
      `</text>`,
    );
    if (li > 0) {
      const dividerX = x;
      svgParts.push(
        `<line class="lane-divider" x1="${fmt(dividerX)}" y1="${fmt(y + laneHeaderHeight)}" x2="${fmt(dividerX)}" y2="${fmt(totalHeight - padding)}" />`,
      );
    }
  }

  // Connection paths (draw before nodes so nodes sit on top).
  for (const conn of diagram.connections) {
    const src = visualById.get(conn.source);
    const tgt = visualById.get(conn.target);
    if (!src || !tgt) continue;
    const startX = src.cx;
    const startY = src.cy + src.height / 2;
    const endX = tgt.cx;
    const endY = tgt.cy - tgt.height / 2;
    const midY = startY + (endY - startY) / 2;
    const path = `M ${fmt(startX)} ${fmt(startY)} L ${fmt(startX)} ${fmt(midY)} L ${fmt(endX)} ${fmt(midY)} L ${fmt(endX)} ${fmt(endY)}`;
    svgParts.push(`<path class="conn" d="${path}"/>`);

    // Arrow head at target.
    const arrow = `M ${fmt(endX)} ${fmt(endY)} L ${fmt(endX - 5)} ${fmt(endY - 8)} M ${fmt(endX)} ${fmt(endY)} L ${fmt(endX + 5)} ${fmt(endY - 8)}`;
    svgParts.push(`<path class="conn" d="${arrow}"/>`);

    if (conn.label) {
      svgParts.push(
        `<text class="conn-label" x="${fmt((startX + endX) / 2)}" y="${fmt(midY - 6)}" text-anchor="middle">`,
        escapeXml(conn.label),
        `</text>`,
      );
    }
  }

  // Nodes.
  for (const v of visuals) {
    const x = v.cx - v.width / 2;
    const y = v.cy - v.height / 2;
    svgParts.push(drawShape(v.node.shape, x, y, v.width, v.height, v.node.text));
  }

  svgParts.push(`</svg>`);
  return svgParts.join("");
}

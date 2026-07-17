// Mirrors swimlane_diagram_generator/parser.py
import {
  canonicalSymbolId,
  isSymbol,
  looksLikeShapeToken,
  normalizeIdentifier,
  parseShape,
  type Connection,
  type Diagram,
  type Lane,
  type Node,
  type Shape,
} from "../model/model.ts";

const CONNECTION_WITH_PIPE_LABEL =
  /^(?<src>[A-Za-z_][A-Za-z0-9_-]*)\s*-->\s*\|(?<label>[^|]+)\|\s*(?<tgt>[A-Za-z_][A-Za-z0-9_-]*)$/;

const CONNECTION_WITH_OPTIONAL_SUFFIX_LABEL =
  /^(?<src>[A-Za-z_][A-Za-z0-9_-]*)\s*-->\s*(?<tgt>[A-Za-z_][A-Za-z0-9_-]*)(?:\s*:\s*(?<label>.+))?$/;

export class DiagramSyntaxError extends Error {
  public readonly lineNo: number | null;
  public readonly lineText: string | null;

  constructor(message: string, lineNo: number | null = null, lineText: string | null = null) {
    super(message);
    this.name = "DiagramSyntaxError";
    this.lineNo = lineNo;
    this.lineText = lineText;
  }

  override toString(): string {
    if (this.lineNo === null) return this.message;
    const excerpt = this.lineText?.trim() ?? "";
    if (excerpt) return `Line ${this.lineNo}: ${this.message} -> ${excerpt}`;
    return `Line ${this.lineNo}: ${this.message}`;
  }
}

interface ParsedNode {
  nodeId: string;
  laneRef: string;
  shape: Shape;
  text: string;
}

export function parseDiagram(source: string): Diagram {
  let title = "";
  const lanes: Lane[] = [];
  const nodes: Node[] = [];
  const connections: Connection[] = [];

  // phases: 0 = lane declarations, 1 = nodes, 2 = connections
  let phase = 0;

  const laneIdLookup: Record<string, string> = {};
  const laneRefLookup: Record<string, string> = {};
  const nodeLookup: Record<string, Node> = {};

  const lines = source.split(/\r?\n/);
  for (let i = 0; i < lines.length; i++) {
    const lineNo = i + 1;
    const rawLine = lines[i]!;
    const line = rawLine.trim();
    if (!line) continue;
    if (line.startsWith("%%") || line.startsWith("#")) continue;

    const lowered = line.toLowerCase();
    if (["swimlanediagram", "swimlane", "swimlane_flow"].includes(lowered)) continue;

    const keyword = lowered.split(/\s+/, 1)[0]!;

    if (keyword === "title") {
      title = parseTitle(line, lineNo, rawLine);
      continue;
    }

    if (keyword === "lane") {
      if (phase > 0) {
        throw new DiagramSyntaxError(
          "Lane declarations must come before node and connection declarations.",
          lineNo,
          rawLine,
        );
      }
      const parsed = parseLane(line, lineNo, rawLine, lanes.length);
      if (laneIdLookup[parsed.laneId]) {
        throw new DiagramSyntaxError(
          `Duplicate lane id '${parsed.laneId}'.`,
          lineNo,
          rawLine,
        );
      }
      const lane: Lane = { id: parsed.laneId, title: parsed.laneTitle, index: lanes.length };
      lanes.push(lane);
      laneIdLookup[lane.id] = lane.id;
      laneRefLookup[lane.id] = lane.id;
      laneRefLookup[lane.title.toLowerCase()] = lane.id;
      const normalizedTitle = normalizeIdentifier(lane.title);
      if (normalizedTitle) laneRefLookup[normalizedTitle] = lane.id;
      continue;
    }

    if (keyword === "node") {
      if (lanes.length === 0) {
        throw new DiagramSyntaxError(
          "Define at least one lane before nodes.",
          lineNo,
          rawLine,
        );
      }
      if (phase === 2) {
        throw new DiagramSyntaxError(
          "Node declarations must come before connection declarations.",
          lineNo,
          rawLine,
        );
      }
      phase = 1;
      const parsedNode = parseNode(line, lineNo, rawLine);
      const laneId = resolveLaneRef(parsedNode.laneRef, laneRefLookup);
      if (laneId === null) {
        throw new DiagramSyntaxError(
          `Unknown lane reference '${parsedNode.laneRef}' for node '${parsedNode.nodeId}'.`,
          lineNo,
          rawLine,
        );
      }
      if (nodeLookup[parsedNode.nodeId]) {
        throw new DiagramSyntaxError(
          `Duplicate node id '${parsedNode.nodeId}'.`,
          lineNo,
          rawLine,
        );
      }
      const node: Node = {
        id: parsedNode.nodeId,
        laneId,
        shape: parsedNode.shape,
        text: parsedNode.text,
        order: nodes.length,
      };
      nodes.push(node);
      nodeLookup[node.id] = node;
      continue;
    }

    if (keyword === "connect" || line.includes("-->")) {
      if (nodes.length === 0) {
        throw new DiagramSyntaxError(
          "Define nodes before connection declarations.",
          lineNo,
          rawLine,
        );
      }
      phase = 2;
      const connection = parseConnection(line, lineNo, rawLine);
      if (!nodeLookup[connection.source]) {
        throw new DiagramSyntaxError(
          `Connection source node '${connection.source}' does not exist.`,
          lineNo,
          rawLine,
        );
      }
      if (!nodeLookup[connection.target]) {
        throw new DiagramSyntaxError(
          `Connection target node '${connection.target}' does not exist.`,
          lineNo,
          rawLine,
        );
      }
      connections.push(connection);
      continue;
    }

    throw new DiagramSyntaxError(
      "Unknown statement. Use: title, lane, node, connect, or Mermaid-style 'A --> B'.",
      lineNo,
      rawLine,
    );
  }

  if (lanes.length === 0) {
    throw new DiagramSyntaxError("Diagram must declare at least one lane.");
  }
  if (nodes.length === 0) {
    throw new DiagramSyntaxError("Diagram must declare at least one node.");
  }

  return { title, lanes, nodes, connections };
}

function splitTokens(line: string, lineNo: number, rawLine: string): string[] {
  // Minimal POSIX-like splitter:
  //  - whitespace separates tokens
  //  - "..." and '...' are kept as a single token with quotes stripped
  // The Python implementation uses shlex; this is a deliberately small port that
  // covers the examples and DSL tests.
  const tokens: string[] = [];
  let i = 0;
  while (i < line.length) {
    const ch = line[i]!;
    if (ch === " " || ch === "\t") {
      i++;
      continue;
    }
    if (ch === '"' || ch === "'") {
      const quote = ch;
      let j = i + 1;
      let buf = "";
      while (j < line.length && line[j] !== quote) {
        if (line[j] === "\\" && j + 1 < line.length) {
          buf += line[j + 1]!;
          j += 2;
        } else {
          buf += line[j]!;
          j++;
        }
      }
      if (j >= line.length) {
        throw new DiagramSyntaxError(`Unmatched ${quote} in line.`, lineNo, rawLine);
      }
      tokens.push(buf);
      i = j + 1;
      continue;
    }
    let j = i;
    while (j < line.length && line[j] !== " " && line[j] !== "\t") {
      j++;
    }
    tokens.push(line.slice(i, j));
    i = j;
  }
  return tokens;
}

function stripMatchingQuotes(value: string): string {
  const text = value.trim();
  if (text.length >= 2 && text[0] === text[text.length - 1] && (text[0] === '"' || text[0] === "'")) {
    return text.slice(1, -1).trim();
  }
  return text;
}

function parseTitle(line: string, lineNo: number, rawLine: string): string {
  let text = line.slice("title".length).trim();
  if (text.startsWith(":")) text = text.slice(1).trim();
  text = stripMatchingQuotes(text);
  if (!text) {
    throw new DiagramSyntaxError("Title cannot be empty.", lineNo, rawLine);
  }
  return text;
}

function parseLane(
  line: string,
  lineNo: number,
  rawLine: string,
  laneIndex: number,
): { laneId: string; laneTitle: string } {
  const tokens = splitTokens(line, lineNo, rawLine);
  if (tokens.length < 2) {
    throw new DiagramSyntaxError("Lane statement is incomplete.", lineNo, rawLine);
  }
  if (tokens.length === 2) {
    const candidate = tokens[1]!;
    if (isSymbol(candidate)) {
      return { laneId: canonicalSymbolId(candidate, "Lane id"), laneTitle: candidate };
    }
    return { laneId: `lane_${laneIndex + 1}`, laneTitle: candidate };
  }
  const laneId = canonicalSymbolId(tokens[1]!, "Lane id");
  const laneTitle = tokens.slice(2).join(" ").trim();
  if (!laneTitle) return { laneId, laneTitle: tokens[1]! };
  return { laneId, laneTitle };
}

function parseNode(line: string, lineNo: number, rawLine: string): ParsedNode {
  const tokens = splitTokens(line, lineNo, rawLine);
  if (tokens.length < 5) {
    throw new DiagramSyntaxError(
      "Node syntax must be: node <id> in <lane> [shape] <text>.",
      lineNo,
      rawLine,
    );
  }
  if (tokens[2]!.toLowerCase() !== "in") {
    throw new DiagramSyntaxError(
      "Expected keyword 'in' in node declaration.",
      lineNo,
      rawLine,
    );
  }

  const nodeId = canonicalSymbolId(tokens[1]!, "Node id");
  const laneRef = tokens[3]!;
  let remainder = tokens.slice(4);

  let shape: Shape = "process";
  const firstToken = remainder[0]!;
  if (looksLikeShapeToken(firstToken)) {
    let parsedShape;
    try {
      parsedShape = parseShape(firstToken);
    } catch {
      throw new DiagramSyntaxError(
        `Unknown shape '${firstToken}'. Allowed: process, decision, subprocess, start/end, document, data.`,
        lineNo,
        rawLine,
      );
    }
    shape = parsedShape;
    remainder = remainder.slice(1);
  }

  if (remainder.length === 0) {
    throw new DiagramSyntaxError("Node text cannot be empty.", lineNo, rawLine);
  }

  const text = remainder.join(" ").trim();
  if (!text) {
    throw new DiagramSyntaxError("Node text cannot be empty.", lineNo, rawLine);
  }
  return { nodeId, laneRef, shape, text };
}

function parseConnection(line: string, lineNo: number, rawLine: string): Connection {
  let connectionLine = line.trim();
  if (connectionLine.toLowerCase().startsWith("connect ")) {
    connectionLine = connectionLine.slice("connect ".length).trim();
  }

  const m1 = CONNECTION_WITH_PIPE_LABEL.exec(connectionLine);
  if (m1 && m1.groups) {
    const source = canonicalSymbolId(m1.groups["src"]!, "Node id");
    const target = canonicalSymbolId(m1.groups["tgt"]!, "Node id");
    const label = m1.groups["label"]!.trim();
    return { source, target, label: label || null };
  }

  const m2 = CONNECTION_WITH_OPTIONAL_SUFFIX_LABEL.exec(connectionLine);
  if (m2 && m2.groups) {
    const source = canonicalSymbolId(m2.groups["src"]!, "Node id");
    const target = canonicalSymbolId(m2.groups["tgt"]!, "Node id");
    const labelRaw = m2.groups["label"];
    const label = labelRaw ? labelRaw.trim() : null;
    return { source, target, label: label || null };
  }

  throw new DiagramSyntaxError(
    "Invalid connection syntax. Use 'connect A --> B', 'A -->|label| B', or 'A --> B : label'.",
    lineNo,
    rawLine,
  );
}

function resolveLaneRef(laneRef: string, laneRefLookup: Record<string, string>): string | null {
  const exactKey = laneRef.toLowerCase();
  if (exactKey in laneRefLookup) return laneRefLookup[exactKey]!;

  const normalized = normalizeIdentifier(laneRef);
  if (normalized && normalized in laneRefLookup) return laneRefLookup[normalized]!;
  return null;
}

// Mirrors swimlane_diagram_generator/model.py

export const SHAPE_PROCESS = "process";
export const SHAPE_DECISION = "decision";
export const SHAPE_SUBPROCESS = "subprocess";
export const SHAPE_START_END = "start_end";
export const SHAPE_DOCUMENT = "document";
export const SHAPE_DATA = "data";

// Runtime enum-like value, mirroring the Python `class Shape(StrEnum)`.
// `Shape` here carries both a runtime value AND its type — `Shape.START_END`
// evaluates to a string literal that is itself part of the `Shape` type.
export const Shape = {
  PROCESS: SHAPE_PROCESS,
  DECISION: SHAPE_DECISION,
  SUBPROCESS: SHAPE_SUBPROCESS,
  START_END: SHAPE_START_END,
  DOCUMENT: SHAPE_DOCUMENT,
  DATA: SHAPE_DATA,
} as const;

// Combined namespace: both the runtime object and a union of its values.
// `Shape.START_END` works at runtime; `: Shape` is a usable type.
export type Shape = (typeof Shape)[keyof typeof Shape];

const SHAPE_ALIASES: Record<string, Shape> = {
  process: SHAPE_PROCESS,
  decision: SHAPE_DECISION,
  subprocess: SHAPE_SUBPROCESS,
  sub_process: SHAPE_SUBPROCESS,
  predefined_process: SHAPE_SUBPROCESS,
  start_end: SHAPE_START_END,
  startend: SHAPE_START_END,
  start: SHAPE_START_END,
  end: SHAPE_START_END,
  terminal: SHAPE_START_END,
  document: SHAPE_DOCUMENT,
  data: SHAPE_DATA,
  input_output: SHAPE_DATA,
  io: SHAPE_DATA,
};

const SYMBOL_ID_PATTERN = /^[A-Za-z_][A-Za-z0-9_-]*$/;

export function canonicalSymbolId(raw: string, kind: string): string {
  const candidate = raw.trim();
  if (!SYMBOL_ID_PATTERN.test(candidate)) {
    throw new Error(
      `${kind} '${raw}' is invalid. Use letters, numbers, '_' or '-' and do not start with a number.`,
    );
  }
  return candidate.toLowerCase();
}

export function normalizeIdentifier(raw: string): string {
  let value = raw.trim().toLowerCase();
  value = value.replace(/-/g, "_").replace(/\//g, "_");
  value = value.replace(/\s+/g, "_");
  value = value.replace(/[^a-z0-9_]/g, "");
  value = value.replace(/_+/g, "_").replace(/^_|_$/g, "");
  return value;
}

function normalizeShapeToken(token: string): string {
  let cleaned = token.trim();
  if (cleaned.startsWith("[") && cleaned.endsWith("]")) {
    cleaned = cleaned.slice(1, -1);
  }
  return normalizeIdentifier(cleaned);
}

export function tryParseShape(token: string): Shape | undefined {
  const normalized = normalizeShapeToken(token);
  return SHAPE_ALIASES[normalized];
}

export function parseShape(token: string): Shape {
  const parsed = tryParseShape(token);
  if (!parsed) {
    throw new Error(`Unknown shape '${token}'.`);
  }
  return parsed;
}

export function looksLikeShapeToken(token: string): boolean {
  const stripped = token.trim();
  if (stripped.startsWith("[") && stripped.endsWith("]")) return true;
  return tryParseShape(stripped) !== undefined;
}

export function isSymbol(value: string): boolean {
  return /^[A-Za-z_][A-Za-z0-9_-]*$/.test(value.trim());
}

export interface Lane {
  readonly id: string;
  readonly title: string;
  readonly index: number;
}

export interface Node {
  readonly id: string;
  readonly laneId: string;
  readonly shape: Shape;
  readonly text: string;
  readonly order: number;
}

export interface Connection {
  readonly source: string;
  readonly target: string;
  readonly label: string | null;
}

export interface Diagram {
  readonly title: string;
  readonly lanes: readonly Lane[];
  readonly nodes: readonly Node[];
  readonly connections: readonly Connection[];
}

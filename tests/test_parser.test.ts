// Parity tests for the parser port. Mirrors the Python test_parser.py cases.
import { describe, expect, test } from "bun:test";
import { Shape } from "../src/model/model.ts";
import { DiagramSyntaxError, parseDiagram } from "../src/parser/parser.ts";

const VALID_DSL = `swimlaneDiagram
title Demo Flow

lane partner "合作服务商"
lane aftersales "售后部"

node start in partner [start/end] "开始"
node inspect in aftersales decision "是否可修"
node scrap in aftersales process "报废"

connect start --> inspect
connect inspect -->|不可修| scrap
`;

describe("parseDiagram", () => {
  test("parses valid Mermaid-like DSL", () => {
    const diagram = parseDiagram(VALID_DSL);
    expect(diagram.title).toBe("Demo Flow");
    expect(diagram.lanes.map((l) => l.id)).toEqual(["partner", "aftersales"]);
    expect(diagram.nodes[0]!.shape).toBe(Shape.START_END);
    expect(diagram.nodes[1]!.shape).toBe(Shape.DECISION);
    expect(diagram.connections[1]!.label).toBe("不可修");
  });

  test("rejects lane declarations after node phase", () => {
    const badDsl = `lane a
node n1 in a process "A"
lane b
`;
    expect(() => parseDiagram(badDsl)).toThrow(DiagramSyntaxError);
  });

  test("resolves lane reference by title", () => {
    const dsl = `lane "售后部"
node n1 in "售后部" process "受理"
`;
    const diagram = parseDiagram(dsl);
    expect(diagram.nodes[0]!.laneId).toBe("lane_1");
  });
});

import unittest

from swimlane_diagram_generator.model import Shape
from swimlane_diagram_generator.parser import DiagramSyntaxError, parse_diagram


VALID_DSL = """swimlaneDiagram
title Demo Flow

lane partner "合作服务商"
lane aftersales "售后部"

node start in partner [start/end] "开始"
node inspect in aftersales decision "是否可修"
node scrap in aftersales process "报废"

connect start --> inspect
connect inspect -->|不可修| scrap
"""


class ParserTests(unittest.TestCase):
    def test_parse_valid_mermaid_like_dsl(self) -> None:
        diagram = parse_diagram(VALID_DSL)

        self.assertEqual(diagram.title, "Demo Flow")
        self.assertEqual([lane.id for lane in diagram.lanes], ["partner", "aftersales"])
        self.assertEqual(diagram.nodes[0].shape, Shape.START_END)
        self.assertEqual(diagram.nodes[1].shape, Shape.DECISION)
        self.assertEqual(diagram.connections[1].label, "不可修")

    def test_reject_lane_after_node_phase(self) -> None:
        bad_dsl = """lane a
node n1 in a process "A"
lane b
"""
        with self.assertRaises(DiagramSyntaxError):
            parse_diagram(bad_dsl)

    def test_resolve_lane_by_title(self) -> None:
        dsl = """lane "售后部"
node n1 in "售后部" process "受理"
"""
        diagram = parse_diagram(dsl)
        self.assertEqual(diagram.nodes[0].lane_id, "lane_1")


if __name__ == "__main__":
    unittest.main()

import unittest

from swimlane_diagram_generator.parser import parse_diagram
from swimlane_diagram_generator.renderer_svg import _assign_vertical_slots, render_svg


RENDER_DSL = """swimlaneDiagram
title Render Test

lane l1 "Lane A"
lane l2 "Lane B"

node n1 in l1 [start/end] "Start"
node n2 in l1 process "Process"
node n3 in l2 decision "Decision"
node n4 in l2 subprocess "Sub Process"
node n5 in l2 document "Doc"
node n6 in l2 data "Data"

connect n1 --> n2
connect n2 -->|route| n3
connect n3 --> n4
connect n4 --> n5
connect n5 --> n6 : payload
"""

COMPACT_DSL = """swimlaneDiagram
title Compact Rows

lane l1 "Lane A"
lane l2 "Lane B"
lane l3 "Lane C"

node n1 in l1 process "A1"
node n2 in l2 process "B1"
node n3 in l3 process "C1"
node n4 in l1 process "A2"
node n5 in l2 process "B2"
node n6 in l3 process "C2"

connect n1 --> n4
connect n2 --> n5
connect n3 --> n6
"""


class SvgRendererTests(unittest.TestCase):
    def test_render_svg_contains_expected_elements(self) -> None:
        diagram = parse_diagram(RENDER_DSL)
        svg = render_svg(diagram)

        self.assertIn("<svg", svg)
        self.assertIn("arrowhead", svg)
        self.assertIn("marker-end=\"url(#arrowhead)\"", svg)
        self.assertIn("Render Test", svg)
        self.assertIn("Lane A", svg)
        self.assertIn("payload", svg)
        self.assertIn("<polygon", svg)  # decision/data shapes
        self.assertIn("<path", svg)     # document shape

    def test_compact_layout_reuses_vertical_rows(self) -> None:
        diagram = parse_diagram(COMPACT_DSL)
        lane_index_by_id = {lane.id: lane.index for lane in diagram.lanes}
        slot_by_node, slot_count = _assign_vertical_slots(diagram, lane_index_by_id)

        self.assertEqual(slot_count, 2)
        self.assertEqual(slot_by_node["n1"], 0)
        self.assertEqual(slot_by_node["n2"], 0)
        self.assertEqual(slot_by_node["n3"], 0)
        self.assertEqual(slot_by_node["n4"], 1)
        self.assertEqual(slot_by_node["n5"], 1)
        self.assertEqual(slot_by_node["n6"], 1)


if __name__ == "__main__":
    unittest.main()

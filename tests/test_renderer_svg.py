import unittest

from swimlane_diagram_generator.parser import parse_diagram
from swimlane_diagram_generator.renderer_svg import (
    _assign_vertical_slots,
    _build_boxes,
    _build_connection_paths,
    _compute_lane_width,
    _compute_line_jumps,
    _count_close_parallel_segments,
    get_global_min_line_gap,
    _label_anchor,
    _resolve_layout_tuning,
    set_global_min_line_gap,
    render_svg,
)


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

PRESSURE_DSL = """swimlaneDiagram
title Boundary Pressure

lane l1 "Lane A"
lane l2 "Lane B"
lane l3 "Lane C"
lane l4 "Lane D"

node a1 in l1 process "A1"
node a2 in l1 process "A2"
node b1 in l2 process "B1"
node b2 in l2 process "B2"
node c1 in l3 process "C1"
node c2 in l3 process "C2"
node d1 in l4 process "D1"
node d2 in l4 process "D2"

connect a1 --> d1
connect a2 --> d2
connect b1 --> d1
connect b2 --> d2
connect c1 --> a1
connect c2 --> a2
"""

STRAIGHT_DSL = """swimlaneDiagram
title Straight Link

lane partner "合作服务商"
lane aftersales "售后部"

node start in partner [start/end] "开始"
node receive in partner process "接收退机并登记"
node triage in aftersales decision "资料是否完整"
node reject in partner process "驳回并补充资料"

connect start --> receive
connect receive --> triage
connect triage --> reject
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
        self.assertIn("rotate(-90", svg)

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

    def test_compute_line_jumps_detects_crossing(self) -> None:
        paths = [
            [(10.0, 10.0), (60.0, 10.0), (60.0, 60.0), (110.0, 60.0)],
            [(30.0, 0.0), (30.0, 40.0), (90.0, 40.0), (90.0, 90.0)],
        ]
        jumps = _compute_line_jumps(paths)

        self.assertTrue(any(abs(jump.x - 60.0) < 0.1 and abs(jump.y - 40.0) < 0.1 for jump in jumps))

    def test_lane_width_expands_under_pressure(self) -> None:
        diagram = parse_diagram(PRESSURE_DSL)
        lane_index_by_id = {lane.id: lane.index for lane in diagram.lanes}
        lane_width = _compute_lane_width(diagram, lane_index_by_id)
        self.assertGreater(lane_width, 210.0)

    def test_label_anchor_orientation_detection(self) -> None:
        vertical_path = [(10.0, 10.0), (40.0, 10.0), (40.0, 90.0), (90.0, 90.0)]
        horizontal_path = [(10.0, 10.0), (10.0, 40.0), (90.0, 40.0), (90.0, 80.0)]

        _, _, vertical_orientation = _label_anchor(vertical_path)
        _, _, horizontal_orientation = _label_anchor(horizontal_path)

        self.assertEqual(vertical_orientation, "vertical")
        self.assertEqual(horizontal_orientation, "horizontal")

    def test_same_lane_downward_link_is_straight(self) -> None:
        diagram = parse_diagram(STRAIGHT_DSL)
        lane_index_by_id = {lane.id: lane.index for lane in diagram.lanes}
        slot_by_node, _ = _assign_vertical_slots(diagram, lane_index_by_id)

        base_lane_width = _compute_lane_width(diagram, lane_index_by_id)
        lane_body_y = 18.0 + 48.0 + 40.0
        lane_width, incident_step, cross_y_step = _resolve_layout_tuning(
            diagram,
            lane_index_by_id,
            slot_by_node,
            base_lane_width,
            lane_body_y,
            54.0,
            104.0,
        )
        boxes = _build_boxes(
            diagram,
            lane_index_by_id,
            slot_by_node,
            lane_width,
            18.0,
            lane_body_y,
            54.0,
            104.0,
        )
        paths = _build_connection_paths(
            diagram,
            boxes,
            lane_index_by_id,
            incident_step=incident_step,
            cross_y_step=cross_y_step,
        )

        first_path_x = {round(point[0], 2) for point in paths[0]}
        self.assertEqual(len(first_path_x), 1)

    def test_global_min_line_gap_influences_tuning(self) -> None:
        original_gap = get_global_min_line_gap()
        try:
            diagram = parse_diagram(PRESSURE_DSL)
            lane_index_by_id = {lane.id: lane.index for lane in diagram.lanes}
            slot_by_node, _ = _assign_vertical_slots(diagram, lane_index_by_id)
            base_lane_width = _compute_lane_width(diagram, lane_index_by_id)
            lane_body_y = 18.0 + 48.0 + 40.0

            set_global_min_line_gap(8.0)
            _, incident_low, cross_low = _resolve_layout_tuning(
                diagram,
                lane_index_by_id,
                slot_by_node,
                base_lane_width,
                lane_body_y,
                54.0,
                104.0,
            )

            set_global_min_line_gap(16.0)
            lane_width_high, incident_high, cross_high = _resolve_layout_tuning(
                diagram,
                lane_index_by_id,
                slot_by_node,
                base_lane_width,
                lane_body_y,
                54.0,
                104.0,
            )

            boxes_high = _build_boxes(
                diagram,
                lane_index_by_id,
                slot_by_node,
                lane_width_high,
                18.0,
                lane_body_y,
                54.0,
                104.0,
            )
            paths_high = _build_connection_paths(
                diagram,
                boxes_high,
                lane_index_by_id,
                incident_step=incident_high,
                cross_y_step=cross_high,
            )

            self.assertGreaterEqual(incident_high, incident_low)
            self.assertGreaterEqual(cross_high, cross_low)
            self.assertGreaterEqual(lane_width_high, base_lane_width)
            self.assertGreaterEqual(_count_close_parallel_segments(paths_high), 0)
        finally:
            set_global_min_line_gap(original_gap)


if __name__ == "__main__":
    unittest.main()

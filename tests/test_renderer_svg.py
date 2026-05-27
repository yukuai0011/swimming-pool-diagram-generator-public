import unittest
from itertools import combinations

from swimlane_diagram_generator.parser import parse_diagram
from swimlane_diagram_generator.renderer_svg import (
    _anchor_at_segment_endpoint,
    _anchor_on_segment,
    _assign_vertical_slots,
    _build_boxes,
    _build_connection_paths,
    _build_segments,
    _compute_label_placements,
    _compute_lane_width,
    _compute_line_jumps,
    _compute_node_dimensions,
    _count_close_parallel_segments,
    _label_anchor,
    _node_box_bounds,
    _resolve_layout_tuning,
    _shape_size,
    get_global_min_line_gap,
    render_svg,
    set_global_min_line_gap,
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

DETOUR_DECISION_DSL = """swimlaneDiagram
title Detour Routing Test

lane l1 "Lane 1"
lane l2 "Lane 2"
lane l3 "Lane 3"

node start in l1 [start/end] "Start"
node dec in l2 decision "Decision"
node mid in l2 process "Mid"
node end in l3 [start/end] "End"

connect start --> mid
connect mid --> dec
connect dec -->|pass| end
connect dec -->|fail| mid
"""

AUTO_SIZE_DSL = """swimlaneDiagram
title Auto Size

lane a "A"
lane b "B"
lane c "C"
lane d "D"
lane e "E"

node s1 in a process "S1"
node s2 in b process "S2"
node s3 in c process "S3"
node s4 in d process "S4"
node target in e process "这是一个很长很长的说明文本，用于测试自动换行和节点尺寸自动扩展能力"

connect s1 --> target
connect s2 --> target
connect s3 --> target
connect s4 --> target
"""

CAPACITY_DSL = """swimlaneDiagram
title Capacity Growth

lane a "A"

node s1 in a process "S1"
node s2 in a process "S2"
node s3 in a process "S3"
node s4 in a process "S4"
node s5 in a process "S5"
node s6 in a process "S6"
node s7 in a process "S7"
node s8 in a process "S8"
node s9 in a process "S9"
node s10 in a process "S10"
node s11 in a process "S11"
node target in a process "Target"

connect s1 --> target
connect s2 --> target
connect s3 --> target
connect s4 --> target
connect s5 --> target
connect s6 --> target
connect s7 --> target
connect s8 --> target
connect s9 --> target
connect s10 --> target
connect s11 --> target
"""

LABEL_PACKING_DSL = """swimlaneDiagram
title Label Packing

lane left "Left"
lane right "Right"

node l1 in left process "L1"
node l2 in left process "L2"
node l3 in left process "L3"
node r1 in right process "R1"
node r2 in right process "R2"
node r3 in right process "R3"

connect l1 -->|alpha| r1
connect l1 -->|beta| r2
connect l2 -->|gamma| r2
connect l2 -->|delta| r3
connect l3 -->|epsilon| r3
connect r3 -->|zeta| l2
"""

OVERLAP_STRESS_DSL = """swimlaneDiagram
title Vertical Line Crossed by Multiple Horizontal Lines Test

lane left "Left Lane"
lane center "Center Lane"
lane right "Right Lane"

node top in center [start/end] "Top"
node mid1 in left process "Mid Left 1"
node mid2 in left process "Mid Left 2"
node mid3 in left process "Mid Left 3"
node mid4 in right process "Mid Right 1"
node mid5 in right process "Mid Right 2"
node mid6 in right process "Mid Right 3"
node bottom in center [start/end] "Bottom"
node extra1 in right process "Extra R1"
node extra2 in left process "Extra L1"
node extra3 in right process "Extra R2"
node extra4 in left process "Extra L2"

connect top --> bottom : Vertical Flow
connect mid1 --> mid4 : Horizontal A
connect mid2 --> mid5 : Horizontal B
connect mid3 --> mid6 : Horizontal C
connect extra1 --> extra2 : Reverse Flow 1
connect extra3 --> extra4 : Reverse Flow 2
"""

PADDING_TEST_DSL = """swimlaneDiagram
title Label Padding Test

lane left "Left"
lane center "Center"
lane right "Right"

node top in left [start/end] "Top"
node mid in center process "Mid"
node bottom in right [start/end] "Bottom"

connect top --> mid : Down
connect mid --> bottom : Across
"""


class SvgRendererTests(unittest.TestCase):
    def test_render_svg_contains_expected_elements(self) -> None:
        diagram = parse_diagram(RENDER_DSL)
        svg = render_svg(diagram)

        self.assertIn("<svg", svg)
        self.assertIn("arrowhead", svg)
        self.assertIn('marker-end="url(#arrowhead)"', svg)
        self.assertIn("Render Test", svg)
        self.assertIn("Lane A", svg)
        self.assertIn("<polygon", svg)  # decision/data shapes
        self.assertIn("<path", svg)  # document shape
        self.assertIn('class="vertical-label"', svg)
        self.assertNotIn("rotate(-90", svg)

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

        self.assertTrue(
            any(abs(jump.x - 60.0) < 0.1 and abs(jump.y - 40.0) < 0.1 for jump in jumps)
        )

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

        self.assertEqual(len(paths[0]), 2)
        first_path_x = {round(point[0], 2) for point in paths[0]}
        self.assertEqual(len(first_path_x), 1)

    def test_node_auto_size_respects_text_and_line_gap(self) -> None:
        original_gap = get_global_min_line_gap()
        try:
            set_global_min_line_gap(15.0)
            diagram = parse_diagram(AUTO_SIZE_DSL)
            lane_index_by_id = {lane.id: lane.index for lane in diagram.lanes}
            slot_by_node, _ = _assign_vertical_slots(diagram, lane_index_by_id)
            dimensions = _compute_node_dimensions(
                diagram, lane_index_by_id, slot_by_node
            )

            target_width, target_height = dimensions["target"]
            base_width, base_height = _shape_size(diagram.nodes[-1].shape)

            self.assertGreaterEqual(target_height, 45.0)
            self.assertGreater(target_height, base_height)
            self.assertGreater(target_width, base_width)
        finally:
            set_global_min_line_gap(original_gap)

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

    def test_connections_snap_to_half_grid(self) -> None:
        diagram = parse_diagram(STRAIGHT_DSL)
        lane_index_by_id = {lane.id: lane.index for lane in diagram.lanes}
        slot_by_node, _ = _assign_vertical_slots(diagram, lane_index_by_id)
        node_dimensions = _compute_node_dimensions(
            diagram, lane_index_by_id, slot_by_node
        )

        lane_body_y = 18.0 + 48.0 + 40.0
        lane_width = _compute_lane_width(
            diagram,
            lane_index_by_id,
            node_dimensions=node_dimensions,
        )
        lane_width, incident_step, cross_y_step = _resolve_layout_tuning(
            diagram,
            lane_index_by_id,
            slot_by_node,
            lane_width,
            lane_body_y,
            54.0,
            104.0,
            node_dimensions=node_dimensions,
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
            node_dimensions=node_dimensions,
        )
        paths = _build_connection_paths(
            diagram,
            boxes,
            lane_index_by_id,
            incident_step=incident_step,
            cross_y_step=cross_y_step,
        )

        half_step = get_global_min_line_gap() / 2.0
        for path in paths:
            for x, y in path:
                self.assertAlmostEqual(round(x / half_step) * half_step, x, places=5)
                self.assertAlmostEqual(round(y / half_step) * half_step, y, places=5)

    def test_node_grows_past_4x3_when_connections_exceed_ten(self) -> None:
        original_gap = get_global_min_line_gap()
        try:
            set_global_min_line_gap(15.0)
            diagram = parse_diagram(CAPACITY_DSL)
            lane_index_by_id = {lane.id: lane.index for lane in diagram.lanes}
            slot_by_node, _ = _assign_vertical_slots(diagram, lane_index_by_id)
            dimensions = _compute_node_dimensions(
                diagram, lane_index_by_id, slot_by_node
            )

            target_width, target_height = dimensions["target"]
            self.assertGreaterEqual(max(target_width, target_height), 60.0)
        finally:
            set_global_min_line_gap(original_gap)

    def test_label_placements_do_not_overlap_with_padding(self) -> None:
        diagram = parse_diagram(LABEL_PACKING_DSL)
        lane_index_by_id = {lane.id: lane.index for lane in diagram.lanes}
        slot_by_node, _ = _assign_vertical_slots(diagram, lane_index_by_id)
        node_dimensions = _compute_node_dimensions(
            diagram, lane_index_by_id, slot_by_node
        )
        lane_body_y = 18.0 + 48.0 + 40.0
        lane_width = _compute_lane_width(
            diagram,
            lane_index_by_id,
            node_dimensions=node_dimensions,
        )
        lane_width, incident_step, cross_y_step = _resolve_layout_tuning(
            diagram,
            lane_index_by_id,
            slot_by_node,
            lane_width,
            lane_body_y,
            54.0,
            104.0,
            node_dimensions=node_dimensions,
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
            node_dimensions=node_dimensions,
        )
        paths = _build_connection_paths(
            diagram,
            boxes,
            lane_index_by_id,
            incident_step=incident_step,
            cross_y_step=cross_y_step,
        )

        placements = _compute_label_placements(diagram, paths, boxes)
        self.assertEqual(
            len(placements),
            sum(1 for connection in diagram.connections if connection.label),
        )

        padding = get_global_min_line_gap()
        for first, second in combinations(placements.values(), 2):
            first_rect = _expand_rect(
                first.left,
                first.top,
                first.left + first.width,
                first.top + first.height,
                padding,
            )
            second_rect = _expand_rect(
                second.left,
                second.top,
                second.left + second.width,
                second.top + second.height,
                padding,
            )
            self.assertFalse(_rects_overlap(first_rect, second_rect))

    def test_label_leader_is_one_grid_diagonal(self) -> None:
        diagram = parse_diagram(LABEL_PACKING_DSL)
        lane_index_by_id = {lane.id: lane.index for lane in diagram.lanes}
        slot_by_node, _ = _assign_vertical_slots(diagram, lane_index_by_id)
        node_dimensions = _compute_node_dimensions(
            diagram, lane_index_by_id, slot_by_node
        )
        lane_body_y = 18.0 + 48.0 + 40.0
        lane_width = _compute_lane_width(
            diagram,
            lane_index_by_id,
            node_dimensions=node_dimensions,
        )
        lane_width, incident_step, cross_y_step = _resolve_layout_tuning(
            diagram,
            lane_index_by_id,
            slot_by_node,
            lane_width,
            lane_body_y,
            54.0,
            104.0,
            node_dimensions=node_dimensions,
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
            node_dimensions=node_dimensions,
        )
        paths = _build_connection_paths(
            diagram,
            boxes,
            lane_index_by_id,
            incident_step=incident_step,
            cross_y_step=cross_y_step,
        )

        placements = _compute_label_placements(diagram, paths, boxes)
        step = get_global_min_line_gap()
        for placement in placements.values():
            self.assertAlmostEqual(
                abs(placement.attach_x - placement.anchor_x), step, places=5
            )
            self.assertAlmostEqual(
                abs(placement.attach_y - placement.anchor_y), step, places=5
            )

            path = paths[placement.connection_index]
            self.assertTrue(
                _point_on_polyline(path, placement.anchor_x, placement.anchor_y)
            )

    def test_label_padding_avoids_all_lines_except_anchor(self) -> None:
        diagram = parse_diagram(PADDING_TEST_DSL)
        lane_index_by_id = {lane.id: lane.index for lane in diagram.lanes}
        slot_by_node, _ = _assign_vertical_slots(diagram, lane_index_by_id)
        node_dimensions = _compute_node_dimensions(
            diagram, lane_index_by_id, slot_by_node
        )
        lane_body_y = 18.0 + 48.0 + 40.0
        lane_width = _compute_lane_width(
            diagram,
            lane_index_by_id,
            node_dimensions=node_dimensions,
        )
        lane_width, incident_step, cross_y_step = _resolve_layout_tuning(
            diagram,
            lane_index_by_id,
            slot_by_node,
            lane_width,
            lane_body_y,
            54.0,
            104.0,
            node_dimensions=node_dimensions,
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
            node_dimensions=node_dimensions,
        )
        paths = _build_connection_paths(
            diagram,
            boxes,
            lane_index_by_id,
            incident_step=incident_step,
            cross_y_step=cross_y_step,
        )
        placements = _compute_label_placements(diagram, paths, boxes)

        padding = get_global_min_line_gap()
        for placement in placements.values():
            rect = _placement_occupied_rect(placement, padding)
            collisions = []
            for line_index, path in enumerate(paths):
                for segment in _build_segments(path, line_index):
                    overlap = _segment_overlap_length(segment, rect)
                    if overlap <= 0.0:
                        continue
                    if line_index == placement.connection_index and (
                        _anchor_on_segment(
                            placement.anchor_x, placement.anchor_y, segment
                        )
                        or _anchor_at_segment_endpoint(
                            placement.anchor_x, placement.anchor_y, segment
                        )
                    ):
                        continue
                    collisions.append((
                        line_index,
                        (segment.x1, segment.y1, segment.x2, segment.y2),
                    ))
            self.assertFalse(
                collisions,
                f"label '{placement.text}' padding overlaps connector segments: {collisions}",
            )

    def test_internal_lane_separators_are_dotted(self) -> None:
        diagram = parse_diagram(RENDER_DSL)
        svg = render_svg(diagram)

        self.assertIn('class="lane-separator"', svg)
        self.assertIn("stroke-dasharray", svg)

        # The outer border should remain solid (no dash array on the first chart rect)
        outer_rect = svg.split("\n")[3]
        self.assertNotIn("stroke-dasharray", outer_rect)

    def test_node_text_padding_grows_small_nodes(self):
        """Nodes with short CJK text should be larger than the bare minimum."""
        from swimlane_diagram_generator.renderer_svg import (
            NODE_TEXT_PAD_H,
            NODE_TEXT_PAD_V,
        )

        self.assertGreater(NODE_TEXT_PAD_H, 0.0)
        self.assertGreater(NODE_TEXT_PAD_V, 0.0)

        diagram = parse_diagram(
            'swimlaneDiagram\ntitle T\nlane l1 "L"\nnode n1 in l1 process "执行维修"\n'
        )
        lane_index_by_id = {lane.id: lane.index for lane in diagram.lanes}
        slot_by_node, _ = _assign_vertical_slots(diagram, lane_index_by_id)
        dimensions = _compute_node_dimensions(diagram, lane_index_by_id, slot_by_node)
        w, h = dimensions["n1"]
        # Without padding, the 4-char CJK text "执行维修" fits in (60, 36).
        # With NODE_TEXT_PAD_H/V, the node should grow beyond that.
        self.assertGreater(
            w, 60.0, "padding should increase node width beyond unpadded size"
        )
        self.assertGreater(
            h, 36.0, "padding should increase node height beyond unpadded size"
        )


class DetourRoutingTests(unittest.TestCase):
    def test_paths_do_not_intersect_intermediate_node_boxes(self) -> None:
        """Connections that cross a non-terminal node's bounding box get detour bends."""
        diagram = parse_diagram(DETOUR_DECISION_DSL)
        lane_index_by_id = {lane.id: lane.index for lane in diagram.lanes}
        slot_by_node, _ = _assign_vertical_slots(diagram, lane_index_by_id)
        node_dimensions = _compute_node_dimensions(
            diagram, lane_index_by_id, slot_by_node
        )
        lane_body_y = 18.0 + 48.0 + 40.0
        lane_width = _compute_lane_width(
            diagram, lane_index_by_id, node_dimensions=node_dimensions
        )
        lane_width, incident_step, cross_y_step = _resolve_layout_tuning(
            diagram,
            lane_index_by_id,
            slot_by_node,
            lane_width,
            lane_body_y,
            54.0,
            104.0,
            node_dimensions=node_dimensions,
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
            node_dimensions=node_dimensions,
        )
        paths = _build_connection_paths(
            diagram,
            boxes,
            lane_index_by_id,
            incident_step=incident_step,
            cross_y_step=cross_y_step,
        )

        min_gap = get_global_min_line_gap()
        # For each connection path, check it doesn't intersect non-terminal node boxes
        for conn_idx, connection in enumerate(diagram.connections):
            path = paths[conn_idx]
            source_id = connection.source
            target_id = connection.target
            for node_id, box in boxes.items():
                if node_id in (source_id, target_id):
                    continue
                left, top, right, bottom = _node_box_bounds(box)
                # Shrink exclusion slightly so paths near but not through aren't flagged
                excl = min_gap * 0.5
                inner_l, inner_t = left + excl, top + excl
                inner_r, inner_b = right - excl, bottom - excl
                for i in range(len(path) - 1):
                    x1, y1 = path[i]
                    x2, y2 = path[i + 1]
                    if abs(y1 - y2) < 1e-6:  # horizontal
                        if inner_t <= y1 <= inner_b:
                            x_min, x_max = min(x1, x2), max(x1, x2)
                            self.assertFalse(
                                max(x_min, inner_l) < min(x_max, inner_r),
                                f"Connection {conn_idx} horizontal segment crosses "
                                f"node {node_id} at y={y1}",
                            )
                    elif abs(x1 - x2) < 1e-6:  # vertical
                        if inner_l <= x1 <= inner_r:
                            y_min, y_max = min(y1, y2), max(y1, y2)
                            self.assertFalse(
                                max(y_min, inner_t) < min(y_max, inner_b),
                                f"Connection {conn_idx} vertical segment crosses "
                                f"node {node_id} at x={x1}",
                            )


if __name__ == "__main__":
    unittest.main()


def _expand_rect(
    left: float,
    top: float,
    right: float,
    bottom: float,
    padding: float,
) -> tuple[float, float, float, float]:
    return left - padding, top - padding, right + padding, bottom + padding


def _rects_overlap(
    first: tuple[float, float, float, float],
    second: tuple[float, float, float, float],
) -> bool:
    left_1, top_1, right_1, bottom_1 = first
    left_2, top_2, right_2, bottom_2 = second
    return not (
        right_1 <= left_2 or right_2 <= left_1 or bottom_1 <= top_2 or bottom_2 <= top_1
    )


def _point_on_polyline(path: list[tuple[float, float]], x: float, y: float) -> bool:
    for index in range(len(path) - 1):
        x1, y1 = path[index]
        x2, y2 = path[index + 1]
        if abs(x1 - x2) < 1e-6:
            if abs(x - x1) < 1e-6 and min(y1, y2) - 1e-6 <= y <= max(y1, y2) + 1e-6:
                return True
        elif abs(y1 - y2) < 1e-6:  # noqa: SIM102
            if abs(y - y1) < 1e-6 and min(x1, x2) - 1e-6 <= x <= max(x1, x2) + 1e-6:
                return True
    return False


def _foreign_line_collisions(
    placement,
    connection_paths: list[list[tuple[float, float]]],
    padding: float,
) -> list[tuple[int, tuple[float, float, float, float]]]:
    rect = _placement_occupied_rect(placement, padding)

    collisions: list[tuple[int, tuple[float, float, float, float]]] = []
    for line_index, path in enumerate(connection_paths):
        if line_index == placement.connection_index:
            continue
        for segment in _build_segments(path, line_index):
            if not _segment_collides_with_rect(segment, rect):
                continue
            collisions.append((
                line_index,
                (segment.x1, segment.y1, segment.x2, segment.y2),
            ))
    return collisions


def _placement_occupied_rect(
    placement,
    padding: float,
) -> tuple[float, float, float, float]:
    left = min(placement.left, placement.anchor_x, placement.attach_x) - padding
    top = min(placement.top, placement.anchor_y, placement.attach_y) - padding
    right = (
        max(
            placement.left + placement.width,
            placement.anchor_x,
            placement.attach_x,
        )
        + padding
    )
    bottom = (
        max(
            placement.top + placement.height,
            placement.anchor_y,
            placement.attach_y,
        )
        + padding
    )
    return left, top, right, bottom


def _segment_collides_with_rect(
    segment,
    rect: tuple[float, float, float, float],
) -> bool:
    left, top, right, bottom = rect
    if segment.orientation == "horizontal":
        if not (top <= segment.y1 <= bottom):
            return False
        return _ranges_overlap(
            min(segment.x1, segment.x2),
            max(segment.x1, segment.x2),
            left,
            right,
        )

    if not (left <= segment.x1 <= right):
        return False
    return _ranges_overlap(
        min(segment.y1, segment.y2),
        max(segment.y1, segment.y2),
        top,
        bottom,
    )


def _ranges_overlap(a1: float, a2: float, b1: float, b2: float) -> bool:
    return max(a1, b1) < min(a2, b2)


def _segment_overlap_length(
    segment,
    rect: tuple[float, float, float, float],
) -> float:
    left, top, right, bottom = rect
    if segment.orientation == "horizontal":
        if not (top <= segment.y1 <= bottom):
            return 0.0
        low = max(min(segment.x1, segment.x2), left)
        high = min(max(segment.x1, segment.x2), right)
        return max(0.0, high - low)

    if not (left <= segment.x1 <= right):
        return 0.0
    low = max(min(segment.y1, segment.y2), top)
    high = min(max(segment.y1, segment.y2), bottom)
    return max(0.0, high - low)

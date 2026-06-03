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
    _resolve_layout_tuning,
    _shape_size,
    _snap_to_grid,
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

DIAMOND_AVOID_DSL = """swimlaneDiagram
title Diamond Avoid

lane l1 "Lane 1"
lane l2 "Lane 2"
lane l3 "Lane 3"
lane l4 "Lane 4"
lane l5 "Lane 5"

node src in l4 decision "Source"
node blocker in l2 decision "Blocker"
node dst in l1 process "Destination"

connect src --> dst : Cross Lane
connect blocker --> dst : Same Row
"""

STRESS_TEST_DSL = """swimlaneDiagram
title Stress Test: Dense Multi-Lane Flow

lane l1 "Lane 1"
lane l2 "Lane 2"
lane l3 "Lane 3"
lane l4 "Lane 4"
lane l5 "Lane 5"

node s1 in l1 [start/end] "Start"
node n1 in l1 process "Node 1"
node n2 in l2 process "Node 2"
node n3 in l3 process "Node 3"
node n4 in l4 process "Node 4"
node n5 in l5 process "Node 5"
node d1 in l2 decision "Decision 1"
node d2 in l4 decision "Decision 2"
node sub1 in l3 subprocess "Subprocess 1"
node sub2 in l5 subprocess "Subprocess 2"
node doc1 in l1 document "Doc 1"
node doc2 in l3 document "Doc 2"
node data1 in l2 data "Data 1"
node data2 in l5 data "Data 2"
node e1 in l1 [start/end] "End 1"
node e2 in l5 [start/end] "End 2"

connect s1 --> n1
connect n1 --> n2
connect n2 --> d1
connect d1 -->|Yes| n3
connect d1 -->|No| n1
connect n3 --> sub1
connect sub1 --> n4
connect n4 --> d2
connect d2 -->|Pass| n5
connect d2 -->|Fail| n3
connect n2 --> doc1 : Cross A
connect sub1 --> doc2 : Cross B
connect n4 --> data1 : Cross C
connect n5 --> data2 : Cross D
connect n1 --> e1 : Long Span 1
connect sub1 --> e2 : Long Span 2
connect n3 --> n5
connect doc2 --> n5 : Merge Path
connect data1 --> n5
connect data2 --> n5
connect n5 --> sub2
connect sub2 --> e2
connect d2 --> doc1 : Extra Cross 1
connect sub2 --> n2 : Extra Cross 2
connect doc1 --> data2 : Extra Cross 3
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

    def test_label_avoids_foreign_lines_under_dense_layout(self) -> None:
        """Labels should never sit on top of a foreign connector segment.

        Regression test for the dense stress-test layout: the 'Cross A' label
        for ``n2 -> doc1`` had its leader line on a vertical segment that
        ran parallel to the d1 -> n1 connector only 30px away. The previous
        placement function would accept a 60px overlap with that foreign
        line because no candidate was perfectly clear of *every* occupied
        region. The new selector prefers line-clear candidates first, even
        if they slightly overlap a node, so the label no longer paints over
        the d1 -> n1 line.
        """
        diagram = parse_diagram(STRESS_TEST_DSL)
        lane_index_by_id = {lane.id: lane.index for lane in diagram.lanes}
        slot_by_node, _ = _assign_vertical_slots(diagram, lane_index_by_id)
        node_dimensions = _compute_node_dimensions(
            diagram, lane_index_by_id, slot_by_node
        )
        grid_size = get_global_min_line_gap()
        max_node_height = max(
            (size[1] for size in node_dimensions.values()), default=74.0
        )
        first_row_offset = _snap_to_grid(
            max(54.0, max_node_height / 2 + 24.0), half=True
        )
        row_gap = _snap_to_grid(
            max(104.0, max_node_height + max(24.0, grid_size * 1.2)), half=True
        )
        lane_body_y = _snap_to_grid(18.0 + 48.0 + 40.0, half=True)
        lane_width = _compute_lane_width(
            diagram, lane_index_by_id, node_dimensions=node_dimensions
        )
        lane_width, incident_step, cross_y_step = _resolve_layout_tuning(
            diagram,
            lane_index_by_id,
            slot_by_node,
            lane_width,
            lane_body_y,
            first_row_offset,
            row_gap,
            node_dimensions=node_dimensions,
        )
        boxes = _build_boxes(
            diagram,
            lane_index_by_id,
            slot_by_node,
            lane_width,
            18.0,
            lane_body_y,
            first_row_offset,
            row_gap,
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
            own_path = set(paths[placement.connection_index])
            for line_index, path in enumerate(paths):
                if line_index == placement.connection_index:
                    continue
                # Skip connections that trace the exact same line in the
                # opposite direction (e.g. ``A -> B`` and ``B -> A``); their
                # segments coincide with the line the label is attached to
                # and aren't actually foreign obstacles.
                if set(path) == own_path:
                    continue
                for segment in _build_segments(path, line_index):
                    overlap = _segment_overlap_length(segment, rect)
                    self.assertEqual(
                        overlap,
                        0.0,
                        f"label '{placement.text}' (connection "
                        f"{placement.connection_index}) overlaps foreign "
                        f"segment from connection {line_index}: "
                        f"({segment.x1}, {segment.y1}) -> "
                        f"({segment.x2}, {segment.y2}) by {overlap}px",
                    )

    def test_internal_lane_separators_are_dotted(self) -> None:
        diagram = parse_diagram(RENDER_DSL)
        svg = render_svg(diagram)

        self.assertIn('class="lane-separator"', svg)
        self.assertIn("stroke-dasharray", svg)

        # The outer border should remain solid (no dash array on the first chart rect)
        outer_rect = svg.split("\n")[3]
        self.assertNotIn("stroke-dasharray", outer_rect)

    def test_cross_lane_connector_avoids_node_bodies(self) -> None:
        """Cross-lane connectors must not pass horizontally through a node body.

        Regression test: the diamond (Decision) shape is drawn with a white fill
        on top of connector lines, so a horizontal segment that lands inside the
        diamond's y-range visually disappears "underneath" the diamond. The
        router should add a small detour so the connector runs above or below
        the obstacle node.
        """
        from swimlane_diagram_generator.renderer_svg import _avoid_node_intersections

        diagram = parse_diagram(DIAMOND_AVOID_DSL)
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
            first_row_offset=66.0,
            row_gap=144.0,
        )
        node_dimensions = _compute_node_dimensions(
            diagram, lane_index_by_id, slot_by_node
        )
        boxes = _build_boxes(
            diagram,
            lane_index_by_id,
            slot_by_node,
            lane_width,
            chart_x=18.0,
            lane_body_y=lane_body_y,
            first_row_offset=66.0,
            row_gap=144.0,
            node_dimensions=node_dimensions,
        )
        raw_paths = _build_connection_paths(
            diagram,
            boxes,
            lane_index_by_id,
            incident_step=incident_step,
            cross_y_step=cross_y_step,
        )
        adjusted = _avoid_node_intersections(raw_paths, boxes)

        # Collect bounding boxes for the two non-endpoint nodes that act as
        # potential obstacles on the connector paths.
        obstacle_ids = {"src", "blocker", "dst"}
        for path, connection in zip(adjusted, diagram.connections):
            others = [
                boxes[node_id]
                for node_id in obstacle_ids
                if node_id not in {connection.source, connection.target}
            ]
            self.assertFalse(
                _path_passes_through_any_node(path, others),
                f"connection {connection.source}->{connection.target} still crosses a node",
            )

    def test_multiple_detours_around_same_node_do_not_overlap(self) -> None:
        """Two detours around the same obstacle must not share a y-coordinate
        in their overlapping x-range. Otherwise the lines would be drawn on
        top of each other after the node-avoidance reroute.
        """
        from swimlane_diagram_generator.renderer_svg import _avoid_node_intersections

        diagram = parse_diagram(STRESS_TEST_DSL)
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
            first_row_offset=66.0,
            row_gap=144.0,
        )
        node_dimensions = _compute_node_dimensions(
            diagram, lane_index_by_id, slot_by_node
        )
        boxes = _build_boxes(
            diagram,
            lane_index_by_id,
            slot_by_node,
            lane_width,
            chart_x=18.0,
            lane_body_y=lane_body_y,
            first_row_offset=66.0,
            row_gap=144.0,
            node_dimensions=node_dimensions,
        )
        raw_paths = _build_connection_paths(
            diagram,
            boxes,
            lane_index_by_id,
            incident_step=incident_step,
            cross_y_step=cross_y_step,
        )
        adjusted = _avoid_node_intersections(raw_paths, boxes)

        # Verify no two horizontal segments from different connections share
        # both y-coordinate and overlapping x-range.
        for index_a, path_a in enumerate(adjusted):
            for index_b, path_b in enumerate(adjusted):
                if index_b <= index_a:
                    continue
                overlap = _horizontal_overlap(path_a, path_b)
                self.assertEqual(
                    overlap,
                    0.0,
                    f"paths {index_a} and {index_b} share {overlap}px of horizontal overlap",
                )

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


if __name__ == "__main__":
    unittest.main()


def _path_passes_through_any_node(
    path: list[tuple[float, float]],
    boxes,
) -> bool:
    """Return True if any horizontal segment of ``path`` crosses a node box."""
    for index in range(len(path) - 1):
        x1, y1 = path[index]
        x2, y2 = path[index + 1]
        if abs(y1 - y2) >= 1e-6 or abs(x1 - x2) < 1e-6:
            continue
        y = y1
        x_min, x_max = min(x1, x2), max(x1, x2)
        for box in boxes:
            left = box.x - box.width / 2.0
            right = box.x + box.width / 2.0
            top = box.y - box.height / 2.0
            bottom = box.y + box.height / 2.0
            if (
                top + 1e-6 < y < bottom - 1e-6
                and left + 1e-6 < x_max
                and right - 1e-6 > x_min
            ):
                return True
    return False


def _horizontal_overlap(
    path_a: list[tuple[float, float]],
    path_b: list[tuple[float, float]],
) -> float:
    """Return the longest shared length of any pair of horizontal segments.

    Returns 0.0 if the two paths have no horizontal segments at the same
    y-coordinate whose x-ranges overlap.
    """
    segments_a = [
        s
        for s in (_horizontal_segment(path_a, i) for i in range(len(path_a) - 1))
        if s is not None
    ]
    segments_b = [
        s
        for s in (_horizontal_segment(path_b, i) for i in range(len(path_b) - 1))
        if s is not None
    ]
    best = 0.0
    for ya, xa_min, xa_max in segments_a:
        for yb, xb_min, xb_max in segments_b:
            if abs(ya - yb) >= 1e-6:
                continue
            overlap = min(xa_max, xb_max) - max(xa_min, xb_min)
            best = max(best, overlap)
    return best


def _horizontal_segment(
    path: list[tuple[float, float]], index: int
) -> tuple[float, float, float] | None:
    """Return ``(y, x_min, x_max)`` for a horizontal segment, else None."""
    x1, y1 = path[index]
    x2, y2 = path[index + 1]
    if abs(y1 - y2) >= 1e-6 or abs(x1 - x2) < 1e-6:
        return None
    return y1, min(x1, x2), max(x1, x2)


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

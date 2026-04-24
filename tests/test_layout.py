# tests/test_layout.py
import unittest

from swimlane_diagram_generator.layout import (
    _expand_even_grid_units,
    _shape_grid_size,
    build_layout,
    get_global_min_line_gap,
    iter_layout_coordinates,
    set_global_min_line_gap,
    snap_to_grid,
)
from swimlane_diagram_generator.model import Shape
from swimlane_diagram_generator.parser import parse_diagram


class LayoutPrimitiveTests(unittest.TestCase):
    def test_snap_to_grid_uses_full_step_only(self) -> None:
        self.assertEqual(snap_to_grid(17.9, 12.0), 12.0)
        self.assertEqual(snap_to_grid(18.0, 12.0), 24.0)
        self.assertEqual(snap_to_grid(30.0, 12.0), 24.0)

    def test_shape_grid_size_uses_even_unit_counts(self) -> None:
        self.assertEqual(_shape_grid_size(Shape.PROCESS), (4, 4))
        self.assertEqual(_shape_grid_size(Shape.START_END), (4, 4))
        self.assertEqual(_shape_grid_size(Shape.DECISION), (4, 4))
        self.assertEqual(_shape_grid_size(Shape.DOCUMENT), (4, 4))

    def test_expand_even_grid_units_preserves_even_counts(self) -> None:
        self.assertEqual(_expand_even_grid_units(4, 4), (4, 4))
        self.assertEqual(_expand_even_grid_units(5, 4), (6, 4))
        self.assertEqual(_expand_even_grid_units(4, 5), (4, 6))
        self.assertEqual(_expand_even_grid_units(5, 5), (6, 6))

    def test_line_gap_configuration_moves_to_layout_module(self) -> None:
        original_gap = get_global_min_line_gap()
        try:
            set_global_min_line_gap(18.0)
            self.assertEqual(get_global_min_line_gap(), 18.0)
        finally:
            set_global_min_line_gap(original_gap)


GRID_ONLY_DSL = """swimlaneDiagram
 title Grid Only

 lane a "A"
 lane b "B"

 node start in a [start/end] "Start"
 node collect in a process "Collect"
 node approve in b decision "Approve"

 connect start --> collect
 connect collect --> approve : route
"""


class ResolvedLayoutTests(unittest.TestCase):
    def test_build_layout_quantizes_all_coordinates_to_full_grid(self) -> None:
        diagram = parse_diagram(GRID_ONLY_DSL)
        layout = build_layout(diagram)
        grid_size = layout.grid_size

        for value in iter_layout_coordinates(layout):
            snapped = round(value / grid_size) * grid_size
            self.assertAlmostEqual(snapped, value, places=5)

    def test_node_dimensions_keep_even_grid_units(self) -> None:
        diagram = parse_diagram(GRID_ONLY_DSL)
        layout = build_layout(diagram)

        for box in layout.boxes.values():
            self.assertEqual((box.width / layout.grid_size) % 2, 0)
            self.assertEqual((box.height / layout.grid_size) % 2, 0)

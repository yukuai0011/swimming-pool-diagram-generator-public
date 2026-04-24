# tests/test_layout.py
import unittest

from swimlane_diagram_generator.layout import (
    _expand_even_grid_units,
    _shape_grid_size,
    get_global_min_line_gap,
    set_global_min_line_gap,
    snap_to_grid,
)
from swimlane_diagram_generator.model import Shape


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

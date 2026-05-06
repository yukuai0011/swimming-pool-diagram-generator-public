import unittest
from unittest.mock import patch

from reportlab.graphics.shapes import Drawing, Group, String

from swimlane_diagram_generator import render_png_bytes
from swimlane_diagram_generator.parser import parse_diagram
from swimlane_diagram_generator.renderer_png import (
    _apply_cjk_font_if_needed,
    _contains_cjk_text,
)

PNG_DSL = """swimlaneDiagram
title PNG Render Test

lane l1 "Lane A"
lane l2 "Lane B"

node n1 in l1 [start/end] "Start"
node n2 in l1 process "Collect"
node n3 in l2 decision "Approved?"
node n4 in l2 document "Invoice"

connect n1 --> n2
connect n2 --> n3
connect n3 -->|yes| n4
connect n3 --> n2 : no / rework
"""

CHINESE_PNG_DSL = """swimlaneDiagram
title 中文测试

lane l1 "售后部"

node n1 in l1 process "接收退机并登记"
"""


class PngRendererTests(unittest.TestCase):
    def test_render_png_bytes_has_png_signature(self) -> None:
        diagram = parse_diagram(PNG_DSL)
        png_bytes = render_png_bytes(diagram)

        self.assertGreater(len(png_bytes), 100)
        self.assertEqual(png_bytes[:8], b"\x89PNG\r\n\x1a\n")

    def test_render_png_bytes_supports_chinese_text(self) -> None:
        diagram = parse_diagram(CHINESE_PNG_DSL)
        png_bytes = render_png_bytes(diagram)

        self.assertGreater(len(png_bytes), 100)
        self.assertEqual(png_bytes[:8], b"\x89PNG\r\n\x1a\n")

    def test_cjk_detection(self) -> None:
        self.assertFalse(_contains_cjk_text("After sales"))
        self.assertTrue(_contains_cjk_text("售后部"))

    def test_cjk_font_is_applied_to_nested_text_nodes(self) -> None:
        drawing = Drawing(100, 100)
        group = Group()
        group.add(String(10, 10, "售后部", fontName="Arial"))
        drawing.add(group)

        with patch(
            "swimlane_diagram_generator.renderer_png._register_cjk_font",
            return_value="SwimlaneTestCJK",
        ):
            applied_font = _apply_cjk_font_if_needed(drawing)

        self.assertEqual(applied_font, "SwimlaneTestCJK")
        self.assertEqual(group.contents[0].fontName, "SwimlaneTestCJK")


if __name__ == "__main__":
    unittest.main()

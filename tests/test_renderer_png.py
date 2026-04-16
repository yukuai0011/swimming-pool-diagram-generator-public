import unittest

from swimlane_diagram_generator.parser import parse_diagram
from swimlane_diagram_generator.renderer_png import render_png_bytes

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


class PngRendererTests(unittest.TestCase):
    def test_render_png_bytes_has_png_signature(self) -> None:
        diagram = parse_diagram(PNG_DSL)
        png_bytes = render_png_bytes(diagram)

        self.assertGreater(len(png_bytes), 100)
        self.assertEqual(png_bytes[:8], b"\x89PNG\r\n\x1a\n")


if __name__ == "__main__":
    unittest.main()

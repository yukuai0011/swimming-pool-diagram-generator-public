"""Swimlane diagram generator package."""

from __future__ import annotations

from io import BytesIO
from pathlib import Path

from .model import Connection, Diagram, Lane, Node, Shape
from .parser import DiagramSyntaxError, parse_diagram
from .renderer_svg import get_global_min_line_gap, render_svg, set_global_min_line_gap


def render_png_bytes(diagram: Diagram) -> bytes:
    """Render diagram to PNG bytes by converting the SVG output."""
    from svglib.svglib import svg2rlg
    from reportlab.graphics import renderPM

    svg_text = render_svg(diagram)
    drawing = svg2rlg(BytesIO(svg_text.encode("utf-8")))
    if drawing is None:
        raise RuntimeError("Failed to convert SVG to drawing")
    return renderPM.drawToString(drawing, fmt="PNG")


def render_png(diagram: Diagram, output_path: str) -> None:
    """Render diagram and write PNG to *output_path*."""
    Path(output_path).write_bytes(render_png_bytes(diagram))


__all__ = [
    "Connection",
    "Diagram",
    "DiagramSyntaxError",
    "Lane",
    "Node",
    "Shape",
    "get_global_min_line_gap",
    "parse_diagram",
    "render_png",
    "render_png_bytes",
    "render_svg",
    "set_global_min_line_gap",
]

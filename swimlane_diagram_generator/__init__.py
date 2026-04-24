"""Swimlane diagram generator package."""

from .layout import get_global_min_line_gap, set_global_min_line_gap
from .model import Connection, Diagram, Lane, Node, Shape
from .parser import DiagramSyntaxError, parse_diagram
from .renderer_png import render_png, render_png_bytes
from .renderer_svg import render_svg

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

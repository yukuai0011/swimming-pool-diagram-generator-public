"""PNG rendering by rasterizing the generated SVG."""

from __future__ import annotations

import os
from collections.abc import Iterator
from functools import lru_cache
from io import BytesIO
from pathlib import Path

from reportlab.graphics import renderPM
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFError, TTFont
from svglib.svglib import svg2rlg

from .model import Diagram
from .renderer_svg import render_svg

_CJK_FONT_NAME = "SwimlaneDiagramCJK"
_CJK_FONT_ENV = "SWIMLANE_PNG_FONT"

_CJK_RANGES = (
    (0x3040, 0x30FF),  # Hiragana + Katakana
    (0x3400, 0x4DBF),  # CJK Unified Ideographs Extension A
    (0x4E00, 0x9FFF),  # CJK Unified Ideographs
    (0xAC00, 0xD7AF),  # Hangul Syllables
    (0xF900, 0xFAFF),  # CJK Compatibility Ideographs
    (0x20000, 0x2A6DF),  # CJK Unified Ideographs Extension B
    (0x2A700, 0x2B73F),  # CJK Unified Ideographs Extension C
    (0x2B740, 0x2B81F),  # CJK Unified Ideographs Extension D
    (0x2B820, 0x2CEAF),  # CJK Unified Ideographs Extension E/F
    (0x2CEB0, 0x2EBEF),  # CJK Unified Ideographs Extension F/I
    (0x30000, 0x323AF),  # CJK Unified Ideographs Extension G/H
)

_FONT_GLOB_PATTERNS = (
    "msyh*.ttc",
    "NotoSansSC*.ttf",
    "NotoSansCJK*.ttc",
    "NotoSansCJKsc*.otf",
    "SourceHanSansSC*.otf",
    "SourceHanSansCN*.otf",
    "simhei.ttf",
    "simsun.ttc",
    "Deng.ttf",
    "PingFang*.ttc",
    "Hiragino Sans GB*.ttc",
    "WenQuanYi*.ttc",
    "wqy*.ttc",
)


def render_png_bytes(diagram: Diagram) -> bytes:
    """Render diagram to PNG bytes by converting the SVG output."""
    svg_text = render_svg(diagram)
    drawing = svg2rlg(BytesIO(svg_text.encode("utf-8")))
    if drawing is None:
        raise RuntimeError("Failed to convert SVG to drawing")

    _apply_cjk_font_if_needed(drawing)
    return renderPM.drawToString(drawing, fmt="PNG")


def render_png(diagram: Diagram, output_path: str) -> None:
    """Render diagram and write PNG to *output_path*."""
    Path(output_path).write_bytes(render_png_bytes(diagram))


def _apply_cjk_font_if_needed(drawing: object) -> str | None:
    if not any(
        _contains_cjk_text(str(text.text)) for text in _iter_text_nodes(drawing)
    ):
        return None

    font_name = _register_cjk_font()
    if font_name is None:
        return None

    _apply_text_font(drawing, font_name)
    return font_name


def _apply_text_font(drawing: object, font_name: str) -> None:
    for text in _iter_text_nodes(drawing):
        text.fontName = font_name


def _iter_text_nodes(drawing: object) -> Iterator[object]:
    for child in getattr(drawing, "contents", ()) or ():
        if hasattr(child, "fontName") and hasattr(child, "text"):
            yield child
        yield from _iter_text_nodes(child)


def _contains_cjk_text(text: str) -> bool:
    return any(start <= ord(char) <= end for char in text for start, end in _CJK_RANGES)


@lru_cache(maxsize=1)
def _register_cjk_font() -> str | None:
    try:
        pdfmetrics.getFont(_CJK_FONT_NAME)
        return _CJK_FONT_NAME
    except KeyError:
        pass

    for font_path in _candidate_cjk_font_paths():
        try:
            pdfmetrics.registerFont(TTFont(_CJK_FONT_NAME, str(font_path)))
            return _CJK_FONT_NAME
        except (OSError, TTFError, ValueError):
            continue

    return None


def _candidate_cjk_font_paths() -> Iterator[Path]:
    seen: set[Path] = set()

    configured = os.environ.get(_CJK_FONT_ENV)
    if configured:
        path = Path(os.path.expandvars(configured)).expanduser()
        if path.is_file():
            resolved = path.resolve()
            seen.add(resolved)
            yield resolved

    windows_fonts = Path(os.environ.get("WINDIR", r"C:\Windows")) / "Fonts"
    explicit_paths = (
        windows_fonts / "msyh.ttc",
        windows_fonts / "NotoSansSC-VF.ttf",
        windows_fonts / "simhei.ttf",
        windows_fonts / "simsun.ttc",
        Path("/System/Library/Fonts/PingFang.ttc"),
        Path("/System/Library/Fonts/STHeiti Light.ttc"),
        Path("/System/Library/Fonts/Supplemental/Songti.ttc"),
        Path("/Library/Fonts/Arial Unicode.ttf"),
        Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"),
        Path("/usr/share/fonts/opentype/noto/NotoSansCJKsc-Regular.otf"),
        Path("/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc"),
        Path("/usr/share/fonts/truetype/wqy/wqy-microhei.ttc"),
    )
    for path in explicit_paths:
        if path.is_file():
            resolved = path.resolve()
            if resolved not in seen:
                seen.add(resolved)
                yield resolved

    font_dirs = (
        windows_fonts,
        Path("/System/Library/Fonts"),
        Path("/System/Library/Fonts/Supplemental"),
        Path("/Library/Fonts"),
        Path("/usr/share/fonts"),
        Path("/usr/share/fonts/opentype/noto"),
        Path("/usr/share/fonts/truetype/noto"),
        Path("/usr/share/fonts/truetype/wqy"),
        Path("/usr/local/share/fonts"),
    )
    for font_dir in font_dirs:
        if not font_dir.is_dir():
            continue
        for pattern in _FONT_GLOB_PATTERNS:
            for path in sorted(font_dir.glob(pattern)):
                if not path.is_file():
                    continue
                resolved = path.resolve()
                if resolved not in seen:
                    seen.add(resolved)
                    yield resolved

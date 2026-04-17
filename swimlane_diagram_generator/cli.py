from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .parser import DiagramSyntaxError, parse_diagram
from .renderer_png import render_png_bytes
from .renderer_svg import render_svg, set_global_min_line_gap

EXAMPLE_DSL = """swimlaneDiagram
title 售后退货处理（复杂示例：跨泳道与交叉线）

lane partner "合作服务商"
lane aftersales "售后部"
lane logistics "物流部"
lane warehouse "仓库部"
lane sales "销售部"
lane finance "财务部"

node start in partner [start/end] "开始"
node receive in partner process "接收退机并登记"
node triage in aftersales decision "资料是否完整"
node reject in partner process "驳回并补充资料"
node classify in aftersales decision "是否可修"
node reserve in warehouse data "预占备件库存"
node purchase in sales subprocess "发起紧急采购"
node repair in logistics subprocess "执行维修"
node qa in aftersales decision "质检是否通过"
node repack in warehouse process "重新包装"
node ship in logistics process "安排返还运输"
node sales_order in sales document "创建 Sales Order"
node invoice in finance document "开票"
node refund in finance process "退款/冲销"
node close in partner [start/end] "流程关闭"

connect start --> receive
connect receive --> triage
connect triage -->|不完整| reject
connect reject --> receive : 补件后重提
connect triage -->|完整| classify
connect classify -->|可修| repair
connect classify -->|不可修| refund
connect repair --> qa
connect qa --> repair : 失败-返修
connect qa -->|通过| reserve
connect reserve -->|有库存| repack
connect reserve -->|无库存| purchase
connect purchase --> reserve : 到货回写
connect repack --> ship
connect ship --> sales_order
connect sales_order --> invoice
connect invoice --> close
connect refund --> close
connect purchase --> invoice : 费用确认
connect repack --> invoice : 物流费用
connect classify --> sales_order : 先建单预留
"""


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="swimlane-gen",
        description="Generate a vertical swimlane diagram (SVG/PNG) from Mermaid-like DSL.",
    )
    parser.add_argument(
        "input",
        nargs="?",
        help="Input DSL file path. Use '-' to read from stdin.",
    )
    parser.add_argument(
        "-o",
        "--output",
        help="Output diagram path. Defaults to <input>.<format> (or diagram.<format> for stdin).",
    )
    parser.add_argument(
        "-f",
        "--format",
        choices=["svg", "png"],
        help="Output format. If omitted, inferred from --output extension; defaults to svg.",
    )
    parser.add_argument(
        "--example",
        action="store_true",
        help="Print an example DSL and exit.",
    )
    parser.add_argument(
        "--min-line-gap",
        type=float,
        default=None,
        help="Global grid size (in px) used for connector spacing and node auto-sizing.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_arg_parser()
    args = parser.parse_args(argv)

    if args.example:
        print(EXAMPLE_DSL.strip())
        return 0

    if not args.input:
        parser.error("Provide an input DSL file path, or use --example.")

    try:
        if args.min_line_gap is not None:
            set_global_min_line_gap(args.min_line_gap)

        source_text = _read_input(args.input)
        diagram = parse_diagram(source_text)
        output_format = _resolve_output_format(args.output, args.format)
        output_path = _resolve_output_path(args.input, args.output, output_format)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        if output_format == "png":
            output_path.write_bytes(render_png_bytes(diagram))
        else:
            output_path.write_text(render_svg(diagram), encoding="utf-8")

        print(f"Generated diagram: {output_path}")
        return 0
    except DiagramSyntaxError as exc:
        print(f"DSL parse error: {exc}", file=sys.stderr)
        return 2
    except OSError as exc:
        print(f"I/O error: {exc}", file=sys.stderr)
        return 1


def _read_input(input_arg: str) -> str:
    if input_arg == "-":
        return sys.stdin.read()
    return Path(input_arg).read_text(encoding="utf-8")


def _resolve_output_format(output_arg: str | None, format_arg: str | None) -> str:
    if format_arg:
        return format_arg

    if output_arg:
        suffix = Path(output_arg).suffix.lower().lstrip(".")
        if suffix in {"svg", "png"}:
            return suffix

    return "svg"


def _resolve_output_path(
    input_arg: str, output_arg: str | None, output_format: str
) -> Path:
    if output_arg:
        return Path(output_arg)
    if input_arg == "-":
        return Path(f"diagram.{output_format}")
    return Path(input_arg).with_suffix(f".{output_format}")

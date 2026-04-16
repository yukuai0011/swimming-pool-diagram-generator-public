from __future__ import annotations

import argparse
from pathlib import Path
import sys

from .parser import DiagramSyntaxError, parse_diagram
from .renderer_svg import render_svg

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
        description="Generate a vertical swimlane SVG from Mermaid-like DSL.",
    )
    parser.add_argument(
        "input",
        nargs="?",
        help="Input DSL file path. Use '-' to read from stdin.",
    )
    parser.add_argument(
        "-o",
        "--output",
        help="Output SVG path. Defaults to <input>.svg (or diagram.svg for stdin).",
    )
    parser.add_argument(
        "--example",
        action="store_true",
        help="Print an example DSL and exit.",
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
        source_text = _read_input(args.input)
        diagram = parse_diagram(source_text)
        svg = render_svg(diagram)
        output_path = _resolve_output_path(args.input, args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(svg, encoding="utf-8")
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


def _resolve_output_path(input_arg: str, output_arg: str | None) -> Path:
    if output_arg:
        return Path(output_arg)
    if input_arg == "-":
        return Path("diagram.svg")
    return Path(input_arg).with_suffix(".svg")

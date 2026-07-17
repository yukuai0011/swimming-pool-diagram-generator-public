import { defineCommand, runMain } from "citty";
import { parseDiagram, DiagramSyntaxError } from "./parser/parser.ts";
import { renderSvg, setGlobalMinLineGap } from "./renderer/renderer_svg.ts";
import type { Diagram } from "./model/model.ts";
import * as path from "node:path";
import * as fs from "node:fs/promises";

const EXAMPLE_DSL = `swimlaneDiagram
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
`;

async function readInput(input: string): Promise<string> {
  if (input === "-") {
    const chunks: Buffer[] = [];
    for await (const chunk of Bun.stdin.stream()) chunks.push(Buffer.from(chunk));
    return Buffer.concat(chunks).toString("utf-8");
  }
  return await fs.readFile(path.resolve(input), "utf-8");
}

function resolveOutputFormat(outArg?: string, fmtArg?: string): "svg" | "png" {
  if (fmtArg === "svg" || fmtArg === "png") return fmtArg;
  if (outArg) {
    const ext = path.extname(outArg).toLowerCase().replace(/^\./, "");
    if (ext === "svg" || ext === "png") return ext;
  }
  return "svg";
}

function resolveOutputPath(input: string | undefined, outArg: string | undefined, fmt: string): string {
  if (outArg) return path.resolve(outArg);
  if (!input || input === "-") return path.resolve(`diagram.${fmt}`);
  const parsed = path.parse(path.resolve(input));
  return path.join(parsed.dir, `${parsed.name}.${fmt}`);
}

const command = defineCommand({
  meta: {
    name: "swimlane-gen",
    description: "Generate a vertical swimlane diagram (SVG) from Mermaid-like DSL.",
    version: "0.1.0",
  },
  args: {
    input: {
      type: "positional",
      required: false,
      description: "Input DSL file path. Use '-' to read from stdin.",
    },
    output: {
      type: "string",
      alias: "o",
      description: "Output diagram path. Defaults to <input>.<format> (or diagram.<format> for stdin).",
    },
    format: {
      type: "string",
      alias: "f",
      description: "Output format (svg or png). Inferred from --output extension; defaults to svg.",
    },
    example: {
      type: "boolean",
      description: "Print an example DSL and exit.",
      default: false,
    },
    "min-line-gap": {
      type: "string",
      description: "Global grid size (in px) used for connector spacing and node auto-sizing.",
    },
  },
  async run({ args }) {
    if (args.example) {
      console.log(EXAMPLE_DSL.trim());
      return;
    }

    if (!args.input) {
      console.error("Provide an input DSL file path, or use --example.");
      process.exitCode = 2;
      return;
    }

    try {
      if (args["min-line-gap"] !== undefined) {
        const gap = Number(args["min-line-gap"]);
        if (Number.isFinite(gap)) setGlobalMinLineGap(gap);
      }

      const source = await readInput(args.input);
      const diagram: Diagram = parseDiagram(source);
      const fmt = resolveOutputFormat(args.output, args.format);
      const outPath = resolveOutputPath(args.input, args.output, fmt);

      if (fmt !== "svg") {
        console.error("Only the 'svg' output format is supported in this Bun port.");
        process.exitCode = 1;
        return;
      }

      const svg = renderSvg(diagram);
      await fs.mkdir(path.dirname(outPath), { recursive: true });
      await fs.writeFile(outPath, svg, "utf-8");
      console.log(`Generated diagram: ${outPath}`);
    } catch (err) {
      if (err instanceof DiagramSyntaxError) {
        console.error(`DSL parse error: ${err.toString()}`);
        process.exitCode = 2;
      } else if (err instanceof Error) {
        console.error(`I/O error: ${err.message}`);
        process.exitCode = 1;
      } else {
        throw err;
      }
    }
  },
});

runMain(command);

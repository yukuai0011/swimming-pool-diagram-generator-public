// Public library surface — re-exports the model, parser and renderer so the
// project can be consumed as a Bun/TS library in addition to being run as a CLI.
export * from "./model/model.ts";
export * from "./parser/parser.ts";
export {
  renderSvg,
  setGlobalMinLineGap,
  getGlobalMinLineGap,
  resetGlobalConfig,
  type RenderGlobalConfig,
} from "./renderer/renderer_svg.ts";

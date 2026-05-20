import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import ts from "typescript";

const projectRoot = new URL("../../", import.meta.url);

export async function importTsModule(relativePath) {
  const sourceUrl = new URL(relativePath, projectRoot);
  const source = readFileSync(sourceUrl, "utf8");
  const compiled = ts.transpileModule(source, {
    compilerOptions: {
      target: ts.ScriptTarget.ES2020,
      module: ts.ModuleKind.ESNext,
      moduleResolution: ts.ModuleResolutionKind.Bundler,
      jsx: ts.JsxEmit.Preserve,
      isolatedModules: true,
    },
    fileName: fileURLToPath(sourceUrl),
  });

  const encoded = Buffer.from(compiled.outputText, "utf8").toString("base64");
  return import(`data:text/javascript;base64,${encoded}`);
}

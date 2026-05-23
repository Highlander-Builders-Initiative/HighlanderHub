import { mkdirSync, readFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, extname, join, relative } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";
import ts from "typescript";

const projectRoot = new URL("../../", import.meta.url);
const projectRootPath = fileURLToPath(projectRoot);
const sourceRoot = new URL("src/", projectRoot);
const outRoot = join(tmpdir(), "highlanderhub-ts-test");
const moduleCache = new Map();

function sourceUrlFor(specifier, fromUrl = projectRoot) {
  if (specifier.startsWith("@/")) {
    return resolveSourceUrl(new URL(specifier.slice(2), sourceRoot));
  }
  if (specifier.startsWith(".")) {
    return resolveSourceUrl(new URL(specifier, fromUrl));
  }
  return null;
}

function resolveSourceUrl(url) {
  const candidates = [url, ".ts", ".tsx", ".js", ".mjs"].map((candidate) =>
    typeof candidate === "string" ? new URL(`${url.href}${candidate}`) : candidate
  );

  for (const candidate of candidates) {
    try {
      readFileSync(candidate);
      return candidate;
    } catch {
      // Try the next extension.
    }
  }

  return url;
}

function compileTsModule(sourceUrl) {
  const sourcePath = fileURLToPath(sourceUrl);
  const cached = moduleCache.get(sourcePath);
  if (cached) return cached;

  const outPath = join(
    outRoot,
    relative(projectRootPath, sourcePath).replace(/\.[^.]+$/, ".mjs")
  );
  const outUrl = pathToFileURL(outPath).href;

  const source = readFileSync(sourceUrl, "utf8");
  const compiled = ts.transpileModule(source, {
    compilerOptions: {
      target: ts.ScriptTarget.ES2020,
      module: ts.ModuleKind.ESNext,
      moduleResolution: ts.ModuleResolutionKind.Bundler,
      jsx: ts.JsxEmit.Preserve,
      isolatedModules: true,
    },
    fileName: sourcePath,
  });

  const rewritten = compiled.outputText.replace(
    /\b(from\s+["']|import\s*\(\s*["']|import\s+["'])([^"']+)(["']\s*\)?)/g,
    (match, before, specifier, after) => {
      const localUrl = sourceUrlFor(specifier, sourceUrl);
      if (
        !localUrl ||
        [".js", ".mjs"].includes(extname(fileURLToPath(localUrl)))
      ) {
        return match;
      }
      return `${before}${compileTsModule(localUrl)}${after}`;
    }
  );

  mkdirSync(dirname(outPath), { recursive: true });
  ts.sys.writeFile(outPath, rewritten);
  moduleCache.set(sourcePath, outUrl);
  return outUrl;
}

export async function importTsModule(relativePath) {
  return import(compileTsModule(new URL(relativePath, projectRoot)));
}

#!/usr/bin/env node
// Regenerates the inlined <script type="application/json"> fallback blocks
// inside each HTML page from the current contents of /data/*.json, so the
// two copies can never drift.
//
// Contract: a page opts into this by including a block shaped like
//
//   <script type="application/json" data-src="/data/glossary.json">
//   ...last-synced copy, ignored on read...
//   </script>
//
// This script finds every such block in every .html file (skipping
// node_modules), reads the JSON file named in data-src relative to the repo
// root, and replaces the block's contents with a pretty-printed copy.
//
// No dependencies — Node built-ins only.

import { readFile, writeFile, readdir } from "node:fs/promises";
import { join, relative, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..");
const SKIP_DIRS = new Set(["node_modules", ".git"]);

async function findHtmlFiles(dir) {
  const out = [];
  for (const entry of await readdir(dir, { withFileTypes: true })) {
    if (SKIP_DIRS.has(entry.name)) continue;
    const full = join(dir, entry.name);
    if (entry.isDirectory()) out.push(...(await findHtmlFiles(full)));
    else if (entry.isFile() && entry.name.endsWith(".html")) out.push(full);
  }
  return out;
}

// Matches any <script type="application/json" ...>...</script> block,
// attributes in any order; data-src is pulled out of the captured attrs
// separately so attribute order in the HTML never matters.
const BLOCK_RE = /(<script\s+type="application\/json"([^>]*)>)([\s\S]*?)(<\/script>)/g;
const DATA_SRC_RE = /\sdata-src="(\/data\/[^"]+\.json)"/;

async function inlineFile(path) {
  const html = await readFile(path, "utf8");
  let changed = false;
  const jsonCache = new Map();

  const replaced = await replaceAsync(html, BLOCK_RE, async (match, open, attrs, _body, close) => {
    const srcMatch = attrs.match(DATA_SRC_RE);
    if (!srcMatch) return match; // no data-src attribute: not a build-managed block
    const dataSrc = srcMatch[1];

    if (!jsonCache.has(dataSrc)) {
      const jsonPath = join(ROOT, dataSrc.replace(/^\//, ""));
      const raw = await readFile(jsonPath, "utf8");
      jsonCache.set(dataSrc, JSON.stringify(JSON.parse(raw), null, 2));
    }
    const pretty = jsonCache.get(dataSrc);
    const next = `${open}\n${pretty}\n${close}`;
    if (next !== match) changed = true;
    return next;
  });

  if (changed) {
    await writeFile(path, replaced, "utf8");
    console.log(`updated  ${relative(ROOT, path)}`);
  }
  return changed;
}

async function replaceAsync(str, regex, asyncFn) {
  const matches = [...str.matchAll(regex)];
  let result = str;
  for (const m of matches) {
    const replacement = await asyncFn(...m);
    result = result.replace(m[0], replacement);
  }
  return result;
}

const files = await findHtmlFiles(ROOT);
let touched = 0;
for (const file of files) {
  if (await inlineFile(file)) touched++;
}

if (files.length === 0) {
  console.log("no HTML files found yet.");
} else if (touched === 0) {
  console.log(`checked ${files.length} HTML file(s), inline data already in sync.`);
} else {
  console.log(`synced inline data in ${touched}/${files.length} HTML file(s).`);
}

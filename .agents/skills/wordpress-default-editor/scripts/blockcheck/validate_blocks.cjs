#!/usr/bin/env node
/*
 * Block validation with Gutenberg's own parser and save().
 *
 * Usage:
 *   node validate_blocks.cjs <file-with-raw-block-markup>... [--limit N] [--json]
 *
 * The input file must contain the raw block markup (the `content.raw` you get from
 * GET /wp-json/wp/v2/{type}/{id}?context=edit). For each block whose stored HTML does
 * not match what its save() regenerates, this prints the block type, the exact
 * "Expected …, saw …" reason, the parsed style attributes, and the original markup.
 *
 * The first run installs the latest @wordpress/blocks, @wordpress/block-library and
 * jsdom into this directory. If the live site runs an older WordPress, a handful of
 * save() details can differ; match versions when in doubt (the WordPress version is
 * in the front-end <meta name="generator"> tag).
 */
const { execSync } = require("child_process");
const fs = require("fs");
const path = require("path");

// --- ensure dependencies (one-time) ---
try {
  require.resolve("@wordpress/blocks");
} catch (e) {
  process.stderr.write(
    "Installing @wordpress/blocks, @wordpress/block-library, jsdom (one-time)…\n",
  );
  execSync("npm install --silent --no-audit --no-fund", {
    cwd: __dirname,
    stdio: "inherit",
  });
}

// --- minimal browser globals for the block library under node ---
const { JSDOM, VirtualConsole } = require("jsdom");
const vc = new VirtualConsole(); // swallow jsdom's harmless "Could not parse CSS stylesheet" noise
const dom = new JSDOM("<!doctype html><html><body></body></html>", {
  url: "http://localhost",
  virtualConsole: vc,
});
const globals = {
  window: dom.window,
  document: dom.window.document,
  self: dom.window,
  DOMParser: dom.window.DOMParser,
  Node: dom.window.Node,
  Element: dom.window.Element,
  HTMLElement: dom.window.HTMLElement,
  MutationObserver: dom.window.MutationObserver,
  getComputedStyle: dom.window.getComputedStyle,
  requestAnimationFrame: (cb) => setTimeout(cb, 0),
  cancelAnimationFrame: (id) => clearTimeout(id),
  requestIdleCallback: (cb) =>
    setTimeout(() => cb({ timeRemaining: () => 50, didTimeout: false }), 0),
  cancelIdleCallback: (id) => clearTimeout(id),
  matchMedia: () => ({
    matches: false,
    addEventListener() {},
    removeEventListener() {},
    addListener() {},
    removeListener() {},
  }),
};
for (const [k, v] of Object.entries(globals)) global[k] = v;

const { parse } = require("@wordpress/blocks");
const { registerCoreBlocks } = require("@wordpress/block-library");

// Gutenberg logs every validation failure via console.warn/error/info; silence it during parse.
function silent(fn) {
  const keep = {};
  for (const m of ["log", "info", "warn", "error", "debug"]) {
    keep[m] = console[m];
    console[m] = () => {};
  }
  try {
    return fn();
  } finally {
    for (const m in keep) console[m] = keep[m];
  }
}
silent(() => registerCoreBlocks());

// --- args ---
// Several files run in one process: loading the block library is most of the
// time a file takes, so a sweep over the tree pays for it once.
const args = process.argv.slice(2);
const asJson = args.includes("--json");
let limit = 20;
const files = [];
for (let i = 0; i < args.length; i++) {
  if (args[i] === "--json") continue;
  if (args[i].startsWith("--limit")) {
    limit = parseInt(args[i].split("=")[1] || args[++i] || "20", 10);
    continue;
  }
  files.push(args[i]);
}
if (!files.length) {
  process.stderr.write(
    "usage: node validate_blocks.cjs <file>... [--limit N] [--json]\n",
  );
  process.exit(2);
}

function check(file) {
  const markup = fs.readFileSync(path.resolve(file), "utf8");
  const blocks = silent(() => parse(markup));

  let total = 0;
  const invalid = [];
  (function walk(list) {
    for (const b of list) {
      if (b.name) {
        total++;
        if (b.isValid === false) {
          const issue = (b.validationIssues || [])[0];
          // args = [printf-style format, ...values]; substitute %s/%o for a clean message
          let reason = "";
          if (issue && issue.args && issue.args.length) {
            const vals = issue.args.slice(1);
            let i = 0;
            reason = String(issue.args[0]).replace(/%[so]/g, () =>
              i < vals.length ? String(vals[i++]) : "%s",
            );
          }
          invalid.push({
            name: b.name,
            reason,
            style: b.attributes && b.attributes.style,
            markup: (b.originalContent || "")
              .replace(/\s+/g, " ")
              .slice(0, 200),
          });
        }
      }
      if (b.innerBlocks && b.innerBlocks.length) walk(b.innerBlocks);
    }
  })(blocks);
  return { file, total, invalid: invalid.length, blocks: invalid };
}

const results = files.map(check);
if (asJson) {
  // One file keeps the single-object shape; several give an array.
  const out = results.length === 1 ? results[0] : results;
  if (results.length === 1) delete out.file;
  process.stdout.write(JSON.stringify(out, null, 2) + "\n");
} else {
  for (const r of results) {
    r.blocks.slice(0, limit).forEach((b, i) => {
      console.log(`\n#${i + 1} INVALID  ${b.name}`);
      console.log("  reason:", b.reason);
      console.log("  attrs.style:", JSON.stringify(b.style));
      console.log("  markup:", b.markup);
    });
    console.log(
      `\n=== ${r.file}: ${r.invalid} invalid / ${r.total} blocks ===`,
    );
  }
}
process.exit(results.some((r) => r.invalid) ? 1 : 0);

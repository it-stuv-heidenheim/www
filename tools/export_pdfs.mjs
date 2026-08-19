#!/usr/bin/env node
// Full-site PDF export: render every page of one representation to a single PDF.
//
// Captures each route as one continuous (full-height) PDF page and concatenates
// them per domain. Used for design review / hand-off. See AGENTS.md
// "Full-Site PDF Export".
//
// Usage (run from repo root):
//   node tools/export_pdfs.mjs [options]
//
// Options:
//   --out DIR        output directory (default: ~/Desktop)
//   --width PX       viewport / PDF width in CSS px (default: 1440)
//   --pages a,b,c    only these route slugs (default: all 7); home slug is "home"
//   --keep-parts     keep the per-page PDFs next to the merged file
//   --list           print the planned URLs + outputs and exit (no browser)
//
// This is NOT part of the Python deploy pipeline and NOT a pnpm dependency:
// it self-installs Puppeteer + Chrome into ~/.cache/stuv-pdf-export on first
// run so the repo stays clean. Merge uses pdfunite (poppler) or qpdf as a
// fallback. Override the browser with PUPPETEER_EXECUTABLE_PATH; point module
// resolution elsewhere with STUV_PDF_NODE_MODULES (a dir holding node_modules).

import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { createRequire } from "node:module";
import { spawnSync } from "node:child_process";

// --- page + site config ---------------------------------------------------
//
// One representation since the repo split (the Next.js app is archived). Slugs
// stay ASCII digraphs (ueber-uns), never umlauts; home is the site root.

const PAGES = [
  "home",
  "ueber-uns",
  "events",
  "studentenleben",
  "kontakt",
  "kummer-karsten",
  "linktree",
];

// Follow WP_SITE so the export targets whichever instance is current, rather
// than a host baked in at write time (the beta host stuv.michi.onl outlived
// its usefulness this way). WP_SITE already carries the scheme.
const SITE = (process.env.WP_SITE || "https://dev.stuv-heidenheim.de").replace(
  /\/+$/,
  "",
);

const LABEL = SITE.replace(/^https?:\/\//, "");

// Pretty permalinks are enabled: subpages live at /<slug>/.
const siteUrl = (slug) => (slug === "home" ? `${SITE}/` : `${SITE}/${slug}/`);

// --- arg parsing ----------------------------------------------------------

function parseArgs(argv) {
  const opts = {
    out: path.join(os.homedir(), "Desktop"),
    width: 1440,
    pages: [...PAGES],
    keepParts: false,
    list: false,
  };
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    if (a === "--out") opts.out = argv[++i];
    else if (a === "--width") opts.width = parseInt(argv[++i], 10);
    else if (a === "--pages")
      opts.pages = argv[++i].split(",").map((s) => s.trim());
    else if (a === "--keep-parts") opts.keepParts = true;
    else if (a === "--list") opts.list = true;
    else if (a === "-h" || a === "--help") opts.help = true;
  }
  return opts;
}

// --- puppeteer bootstrap --------------------------------------------------

const CACHE_DIR = path.join(os.homedir(), ".cache", "stuv-pdf-export");

function sh(cmd, args, cwd, extraEnv = {}) {
  const r = spawnSync(cmd, args, {
    cwd,
    stdio: "inherit",
    env: { ...process.env, ...extraEnv },
  });
  if (r.status !== 0) {
    throw new Error(`${cmd} ${args.join(" ")} failed (exit ${r.status})`);
  }
}

function tryRequirePuppeteer() {
  const bases = [];
  if (process.env.STUV_PDF_NODE_MODULES) {
    bases.push(path.join(process.env.STUV_PDF_NODE_MODULES, "noop.js"));
  }
  bases.push(path.join(CACHE_DIR, "noop.js"));
  bases.push(import.meta.url); // repo-local, if someone installed it here
  for (const base of bases) {
    try {
      const req = createRequire(base);
      return req("puppeteer");
    } catch {
      /* try next */
    }
  }
  return null;
}

async function loadPuppeteer() {
  let pptr = tryRequirePuppeteer();
  if (!pptr) {
    console.log("Puppeteer not found — installing into", CACHE_DIR);
    fs.mkdirSync(CACHE_DIR, { recursive: true });
    // Install the package without the bundled browser download (which can
    // truncate under a sandbox), then fetch Chrome explicitly below.
    sh(
      "npm",
      [
        "install",
        "puppeteer",
        "--prefix",
        CACHE_DIR,
        "--no-audit",
        "--no-fund",
      ],
      CACHE_DIR,
      { PUPPETEER_SKIP_DOWNLOAD: "true" },
    );
    pptr = tryRequirePuppeteer();
    if (!pptr) throw new Error("Puppeteer install did not resolve");
  }
  const exe =
    process.env.PUPPETEER_EXECUTABLE_PATH || (await pptr.executablePath());
  if (!fs.existsSync(exe)) {
    console.log("Chrome not found — downloading...");
    const bin = path.join(CACHE_DIR, "node_modules", ".bin", "puppeteer");
    sh(bin, ["browsers", "install", "chrome"], CACHE_DIR);
  }
  return { pptr, exe };
}

// --- rendering ------------------------------------------------------------

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

async function autoScroll(page) {
  await page.evaluate(async () => {
    await new Promise((resolve) => {
      let total = 0;
      const step = 400;
      const timer = setInterval(() => {
        window.scrollBy(0, step);
        total += step;
        if (total >= document.body.scrollHeight + window.innerHeight) {
          clearInterval(timer);
          resolve();
        }
      }, 80);
    });
    window.scrollTo(0, 0);
  });
}

async function renderSite(pptr, exe, pages, width, outDir) {
  const browser = await pptr.launch({
    headless: true, // 'shell' would need a separate chrome-headless-shell binary
    executablePath: exe,
    args: ["--no-sandbox", "--disable-dev-shm-usage"],
  });
  const parts = [];
  let i = 1;
  for (const slug of pages) {
    const url = siteUrl(slug);
    const page = await browser.newPage();
    await page.setViewport({ width, height: 1200, deviceScaleFactor: 2 });
    await page.emulateMediaType("screen");
    const file = path.join(
      outDir,
      `_part-${LABEL}-${String(i).padStart(2, "0")}-${slug}.pdf`,
    );
    process.stdout.write(`  ${String(i).padStart(2, "0")} ${url} ... `);
    await page.goto(url, { waitUntil: "networkidle2", timeout: 60000 });
    await autoScroll(page);
    await page.evaluate(() => document.fonts && document.fonts.ready);
    await sleep(1500);
    const height = await page.evaluate(() =>
      Math.max(
        document.body.scrollHeight,
        document.documentElement.scrollHeight,
        document.body.offsetHeight,
      ),
    );
    // executablePath() is a Promise in Puppeteer 25 — already awaited above.
    await page.pdf({
      path: file,
      printBackground: true,
      width: `${width}px`,
      height: `${height}px`,
      pageRanges: "1",
    });
    console.log(`ok (${height}px)`);
    await page.close();
    parts.push(file);
    i++;
  }
  await browser.close();
  return parts;
}

// --- merge ----------------------------------------------------------------

function have(cmd) {
  return spawnSync("which", [cmd], { stdio: "ignore" }).status === 0;
}

function merge(parts, out) {
  if (have("pdfunite")) {
    sh("pdfunite", [...parts, out]);
  } else if (have("qpdf")) {
    sh("qpdf", ["--empty", "--pages", ...parts, "--", out]);
  } else {
    throw new Error(
      "Need pdfunite (poppler) or qpdf to merge. Parts left in place.",
    );
  }
}

// --- main -----------------------------------------------------------------

const HELP = `Full-site PDF export\n
Usage: node tools/export_pdfs.mjs [options]
  --out DIR        output directory (default: ~/Desktop)
  --width PX       viewport / PDF width (default: 1440)
  --pages a,b      only these slugs (home slug is "home")
  --keep-parts     keep per-page PDFs
  --list           print planned URLs + outputs, no browser`;

async function main() {
  const opts = parseArgs(process.argv.slice(2));
  if (opts.help) {
    console.log(HELP);
    return;
  }
  const pages = PAGES.filter((slug) => opts.pages.includes(slug));
  if (pages.length === 0) {
    console.error("No matching pages for --pages", opts.pages.join(","));
    process.exit(2);
  }
  const out = path.join(opts.out, `${LABEL}-alle-seiten.pdf`);

  if (opts.list) {
    console.log(`\n${LABEL}  ->  ${out}`);
    pages.forEach((slug, idx) =>
      console.log(`  ${String(idx + 1).padStart(2, "0")} ${siteUrl(slug)}`),
    );
    return;
  }

  fs.mkdirSync(opts.out, { recursive: true });
  const { pptr, exe } = await loadPuppeteer();

  console.log(`\n=== ${LABEL} ===`);
  const parts = await renderSite(pptr, exe, pages, opts.width, opts.out);
  merge(parts, out);
  if (!opts.keepParts) parts.forEach((f) => fs.rmSync(f, { force: true }));
  console.log(`merged ${parts.length} pages -> ${out}`);
}

main().catch((e) => {
  console.error("\nerror:", e.message);
  process.exit(1);
});

/**
 * QA sweep: axe-core (WCAG 2 A/AA) at every section on desktop and phone, then
 * Lighthouse on mobile and desktop. Exits non-zero below the floors in MIN so it
 * can gate a push.
 *
 *   node scripts/qa.mjs                      # http://localhost:3000
 *   node scripts/qa.mjs https://example.com  # anything else
 *
 * Env:
 *   CHROME_PATH  browser to drive (needed where Playwright's Chromium won't run)
 *   STOPS        number of scroll stops to audit (default 6; 0 = top only)
 *   LOADER       selector for a full-screen loader to wait out
 *   GL=1         enable software WebGL (off by default: the canvas is
 *                aria-hidden, and SwiftShader is slow and memory-hungry)
 *
 * Needs: npm i -D playwright @axe-core/playwright lighthouse
 */
import { chromium, devices } from "playwright";
import AxeBuilder from "@axe-core/playwright";
import lighthouse from "lighthouse";

const URL = process.argv[2] ?? process.env.URL ?? "http://localhost:3000";
const CHROME = process.env.CHROME_PATH;
const STOPS = Number(process.env.STOPS ?? 6);
const LOADER = process.env.LOADER ?? '[role="status"][aria-label="Loading"]';
const MIN = { accessibility: 0.95, "best-practices": 0.9, seo: 0.9 };
const TAGS = ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"];

// Software WebGL costs a lot of memory and CPU and tells us nothing about
// accessibility. Off by default; GL=1 turns it on. Note that disabling it makes
// THREE log context-creation errors, which costs a few best-practices points —
// check console cleanliness in a separate GL=1 run instead.
const GL = process.env.GL === "1"
  ? ["--enable-webgl", "--ignore-gpu-blocklist", "--enable-unsafe-swiftshader"]
  : ["--disable-webgl", "--disable-3d-apis"];

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const pct = (n) => `${Math.round(n * 100)}`.padStart(3);
let failed = 0;

/** A loader at a high z-index swallows clicks and is what you would audit. */
const ready = async (page) => {
  // waitForSelector("detached") resolves instantly when the selector matched
  // nothing in the first place, so a renamed or mistyped LOADER would sail
  // straight through and let you audit the loading screen as if it were the
  // page. Confirm it appears before waiting for it to go.
  const appeared = await page
    .waitForSelector(LOADER, { state: "attached", timeout: 8000 })
    .then(() => true, () => false);
  if (!appeared) {
    console.log(`   note: nothing matched LOADER (${LOADER}) — assuming no loading screen`);
  } else {
    try {
      await page.waitForSelector(LOADER, { state: "detached", timeout: 90000 });
    } catch {
      failed++;
      console.log("   ! loader never went away — everything audited below is the loading screen");
    }
  }
  await sleep(1500);
};

async function axeSweep() {
  console.log("\n── axe-core (WCAG 2 A/AA) ──");
  const browser = await chromium.launch({ executablePath: CHROME, args: GL });
  for (const [label, opts] of [
    ["desktop", { viewport: { width: 1440, height: 900 } }],
    ["phone  ", { ...devices["iPhone 14 Pro"], viewport: { width: 390, height: 844 } }],
  ]) {
    const ctx = await browser.newContext(opts);
    const page = await ctx.newPage();
    // networkidle never settles against a dev server holding an HMR socket open
    await page.goto(URL, { waitUntil: "load" });
    await ready(page);
    const max = await page.evaluate(() => document.body.scrollHeight - innerHeight);
    for (let i = 0; i <= STOPS; i++) {
      if (max > 0) await page.evaluate((y) => scrollTo(0, y), Math.round((max * i) / Math.max(STOPS, 1)));
      await sleep(2000);
      const { violations } = await new AxeBuilder({ page }).withTags(TAGS).analyze();
      if (violations.length) {
        failed++;
        console.log(`${label} stop ${i}: ${violations.length} violation(s)`);
        for (const v of violations) {
          console.log(`   [${v.impact}] ${v.id} — ${v.help} (${v.nodes.length} node(s))`);
          console.log(`     ${v.nodes[0]?.target?.join(" ")}`);
        }
      } else {
        console.log(`${label} stop ${i}: clean`);
      }
      if (max === 0) break;
    }
    await ctx.close();
  }
  await browser.close();
}

async function lighthouseRun() {
  console.log("\n── Lighthouse ──");
  // A browser per pass: sharing one across form factors returns an errored run
  // scoring every category 0, which reads like a catastrophic failure it is not
  let port = 9222;
  for (const formFactor of ["mobile", "desktop"]) {
    const browser = await chromium.launch({ executablePath: CHROME, args: [...GL, `--remote-debugging-port=${port}`] });
    const { lhr } = await lighthouse(URL, {
      port,
      output: "json",
      logLevel: "error",
      formFactor,
      screenEmulation: formFactor === "desktop"
        ? { mobile: false, width: 1440, height: 900, deviceScaleFactor: 1, disabled: false }
        : undefined,
      throttlingMethod: "simulate",
    });
    if (lhr.runtimeError) {
      failed++;
      console.log(`${formFactor}: run failed — ${lhr.runtimeError.code}: ${lhr.runtimeError.message}`);
    } else {
      console.log(`${formFactor}:`);
      for (const [id, cat] of Object.entries(lhr.categories)) {
        const score = cat.score ?? 0;
        const floor = MIN[id];
        const bad = floor !== undefined && score < floor;
        if (bad) failed++;
        console.log(`   ${pct(score)}  ${id}${bad ? `  ← below ${Math.round(floor * 100)}` : ""}`);
      }
      for (const id of Object.keys(MIN)) {
        for (const ref of lhr.categories[id]?.auditRefs ?? []) {
          const a = lhr.audits[ref.id];
          if (a && a.score !== null && a.score < 1) console.log(`      ${id}: ${a.title}`);
        }
      }
    }
    await browser.close();
    port++;
  }
  console.log("\nperformance under software WebGL is meaningless — judge it on real hardware");
}

await axeSweep();
await lighthouseRun();
console.log(failed ? `\n${failed} check(s) failed` : "\nAll checks passed");
process.exit(failed ? 1 : 0);

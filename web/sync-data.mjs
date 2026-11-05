// Re-sync the site's data from the repo root after a rerun:
//   node web/sync-data.mjs
// Copies results.json and results_hw.json, slims results_multi.json (drops per-budget RMSE arrays
// the page never reads), keeps the dimension axis of results_wins.json and lifts the recorded floodline_cli.py example run
// out of README_multidriver.md. crossover.json comes from the toy study, which
// lives outside this repo, so it is left alone.
import fs from "node:fs";
import path from "node:path";

const root = path.resolve(path.dirname(new URL(import.meta.url).pathname), "..");
const out = path.join(root, "web/assets/data");

for (const f of ["results.json", "results_hw.json"]) fs.copyFileSync(path.join(root, f), path.join(out, f));

const multi = JSON.parse(fs.readFileSync(path.join(root, "results_multi.json"), "utf8"));
for (const s of Object.values(multi.studies)) {
  for (const c of Object.values(s.configs)) {
    for (const a of Object.values(c.arms)) { delete a.rmse; delete a.queries_axis; }
    delete c.model;
    delete c.is_pilot_var;
  }
}
fs.writeFileSync(path.join(out, "results_multi.json"), JSON.stringify(multi));

// Only the dimension axis of the wins study is on the page; keep fits, CIs and ratios.
const wins = JSON.parse(fs.readFileSync(path.join(root, "results_wins.json"), "utf8")).dim;
for (const c of Object.values(wins)) {
  for (const a of Object.values(c.arms)) { delete a.rmse; delete a.queries_axis; }
}
fs.writeFileSync(path.join(out, "results_wins.json"), JSON.stringify({ dim: wins }));

const readme = fs.readFileSync(path.join(root, "README_multidriver.md"), "utf8");
const run = readme.match(/```\n(uv run python floodline_cli\.py[^\n]*)\n```\n+```\n([\s\S]*?)```/);
if (!run) throw new Error("README_multidriver.md: CLI example block not found");
fs.writeFileSync(path.join(out, "cli-example.txt"), `$ ${run[1]}\n${run[2]}`);
console.log("synced results.json, results_hw.json, results_multi.json, results_wins.json, cli-example.txt");

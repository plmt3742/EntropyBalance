import { readFileSync, existsSync } from "node:fs";

// 用法：node scripts/eval-b08-dependency.mjs <gold.jsonl> <pred.jsonl> [dir-adjudication.json]
// 只输出汇总指标，不打印句子内容。
//
// 方向一项：模型与标注的任务命名不同，字符串比对会误判。
// 若提供裁决文件，按其结果判定；否则退回 P 编号比对。

const [goldPath, predPath, adjPath] = process.argv.slice(2);
if (!goldPath || !predPath) {
  console.error("usage: node scripts/eval-b08-dependency.mjs <gold.jsonl> <pred.jsonl> [dir-adjudication.json]");
  process.exit(2);
}

const readJSONL = (p) =>
  readFileSync(p, "utf8")
    .split(/\r?\n/)
    .filter((l) => l.trim())
    .map((l) => JSON.parse(l));

const gold = new Map(readJSONL(goldPath).map((r) => [r.id, r]));
const pred = new Map(readJSONL(predPath).map((r) => [r.id, r]));

const fallbackAdj = `${goldPath.replace(/[^\\/]+$/, "")}dir-adjudication.json`;
const adjFile = adjPath ?? (existsSync(fallbackAdj) ? fallbackAdj : null);
const adj = adjFile ? JSON.parse(readFileSync(adjFile, "utf8")).dir ?? {} : {};

const PCODE = /P\d{2}/g;
const pcodeSets = (dir = "") => {
  const [left = "", right = ""] = String(dir).split("<-");
  return [new Set(left.match(PCODE) ?? []), new Set(right.match(PCODE) ?? [])];
};
const sameSet = (a, b) => a.size === b.size && [...a].every((x) => b.has(x));

function directionVerdict(g, p) {
  if (adj[p.id]) return adj[p.id];
  if (!g.dir || !p.dir) return "missing";
  if (g.dir === p.dir) return "ok";
  const [gl, gr] = pcodeSets(g.dir);
  const [pl, pr] = pcodeSets(p.dir);
  if (!gl.size || !gr.size) return "unclear";
  if (sameSet(gl, pl) && sameSet(gr, pr)) return "ok";
  if (sameSet(gl, pr) && sameSet(gr, pl)) return "reversed";
  return "unclear";
}

const stats = {
  goldDep: 0,
  goldCommit: 0,
  goldNone: 0,
  predDep: 0,
  predDepHard: 0,
  predDepWeak: 0,
  hardTypeOk: 0,
  hardStrictOk: 0,
  weakTypeOk: 0,
  weakStrictOk: 0,
  dirOk: 0,
  dirReversed: 0,
  dirUnclear: 0,
  fp: 0,
  fpDenom: 0,
  missed: 0,
  commitToDep: 0,
};

for (const g of gold.values()) {
  const p = pred.get(g.id) ?? { dep: 0, type: "无", dir: "", str: "无" };
  if (g.dep === 1) stats.goldDep += 1;
  else if (g.type === "承诺") stats.goldCommit += 1;
  else stats.goldNone += 1;

  if (p.dep === 1) {
    stats.predDep += 1;
    const hard = p.str === "硬";
    hard ? (stats.predDepHard += 1) : (stats.predDepWeak += 1);
    const typeOk = g.dep === 1 && p.type === g.type;
    const strOk = g.dep === 1 && p.str === g.str;
    const dv = directionVerdict(g, p);
    if (typeOk) hard ? (stats.hardTypeOk += 1) : (stats.weakTypeOk += 1);
    if (typeOk && strOk && dv === "ok") hard ? (stats.hardStrictOk += 1) : (stats.weakStrictOk += 1);
    if (typeOk) {
      if (dv === "ok") stats.dirOk += 1;
      else if (dv === "reversed") stats.dirReversed += 1;
      else stats.dirUnclear += 1;
    }
  } else if (g.dep === 1) {
    stats.missed += 1;
  }

  if (g.dep === 0 && g.type === "无") {
    stats.fpDenom += 1;
    if (p.dep === 1 || p.type === "承诺") stats.fp += 1;
  }
  if (g.dep === 0 && g.type === "承诺" && p.dep === 1) stats.commitToDep += 1;
}

const ratio = (n, d) => (d ? (n / d).toFixed(3) : "n/a");
const hardPrecision = ratio(stats.hardStrictOk, stats.predDepHard);
const weakPrecision = ratio(stats.weakStrictOk, stats.predDepWeak);
const dirErr = ratio(stats.dirReversed, stats.dirOk + stats.dirReversed + stats.dirUnclear);
const fpRate = ratio(stats.fp, stats.fpDenom);

const report = {
  gold: { dep: stats.goldDep, commit: stats.goldCommit, none: stats.goldNone },
  pred: { dep: stats.predDep, hard: stats.predDepHard, weak: stats.predDepWeak },
  metrics: {
    hardPrecision,
    weakPrecision,
    directionErrorRate: dirErr,
    falsePositiveRate: fpRate,
    missed: stats.missed,
    commitPredictedAsDep: stats.commitToDep,
  },
  confusion: {
    goldDep_predDep: stats.hardTypeOk + stats.weakTypeOk,
    goldDep_predNotDep: stats.missed,
    goldNone_predDepOrCommit: stats.fp,
  },
};

console.log(JSON.stringify(report, null, 2));

const failures = [];
if (hardPrecision !== "n/a" && Number(hardPrecision) < 0.7) failures.push("hard precision < 0.7");
if (dirErr !== "n/a" && Number(dirErr) > 0.1) failures.push("direction error > 10%");
if (fpRate !== "n/a" && Number(fpRate) > 0.1) failures.push("false positive > 10%");
if (failures.length) {
  console.error("THRESHOLD FAIL: " + failures.join("; "));
  process.exit(1);
}

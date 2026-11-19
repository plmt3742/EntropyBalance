#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""生成 B-06 的交互原型（任务单 §3）：单文件 HTML，可离线打开。

原型要证明三件事（任务单 §3 的要求）：
  1. 候选队列：只把「机器不确定、需要人看」的排进队列，其余不打扰人；
  2. 人物卡 / 撤销 / 拆分 / 标记同名：一个都不少，且每个动作都写进与 b06_merge.py 同格式的日志；
  3. 计时：能算出「每 100 条要人确认几次」，直接对上验收第 3 条（≤10 次）。

输出：docs/30-research/prototype/b06-candidate-queue.html
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CANDS = ROOT / "data" / "samples" / "B-06-alias-candidates.jsonl"
RECORDS = ROOT / "data" / "samples" / "B-04-real-records.jsonl"
DICT = ROOT / "data" / "samples" / "B-06-alias-dictionary.json"
OUT = ROOT / "docs" / "30-research" / "prototype" / "b06-candidate-queue.html"

STATUS_LABEL = {
    "resolved": "已定位", "external_person": "外部个人", "external_unit": "外部单位",
    "group": "群体/广播", "deferred": "代词不解析", "ambiguous": "需人确认", "unknown": "判不出",
}


def jl(p: Path):
    return [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines() if l.strip()]


def main() -> int:
    cands = jl(CANDS)
    texts = {r["record"]["record_id"]: r["text"] for r in jl(RECORDS)}
    d = json.loads(DICT.read_text(encoding="utf-8"))

    # 队列：只放需要人确认的（needs_human），并按记录排序
    queue = [c for c in cands if c.get("needs_human")]
    queue.sort(key=lambda c: (c["record_id"], c["message_index"]))

    items = []
    for c in queue:
        lines = texts[c["record_id"]].split("\n")
        mi = c["message_index"]
        items.append({
            "cid": c["mention_id"], "rid": c["record_id"], "mi": mi,
            "surface": c["surface"], "kind": c["kind"],
            "msg": lines[mi] if mi < len(lines) else "",
            "prev": lines[mi - 1] if mi > 0 else "",
            "status": c["status"], "targets": c["targets"], "conf": c["confidence"],
            "rule": c["rule"], "why": c["why"],
        })

    # 人物卡数据：每人别名词 + 出现次数（来自词典 + 候选统计）
    counts = {}
    for c in cands:
        for t in c["targets"]:
            counts[t] = counts.get(t, 0) + 1
            if t.startswith("EXT-"):
                counts[t[4:]] = counts.get(t[4:], 0) + 1
    persons = []
    for pid, spec in d.get("persons", {}).items():
        al = spec.get("aliases", [])
        persons.append({"id": pid, "label": pid, "aliases": al,
                        "seen": counts.get(pid, 0)})
    for gid, spec in d.get("groups", {}).items():
        surf = spec["surface"][0]
        seen = max(counts.get(gid, 0), counts.get("EXT-" + surf, 0), counts.get(surf, 0))
        persons.append({"id": gid, "label": surf, "aliases": spec["surface"], "seen": seen})
    persons.append({"id": "EXT-老师（未定）", "label": "老师（外部）", "aliases": ["老师"],
                    "seen": counts.get("EXT-老师（未定）", 0)})
    persons.append({"id": "not_person", "label": "不是人", "aliases": [], "seen": 0})
    persons.append({"id": "unknown", "label": "判不出", "aliases": [], "seen": 0})

    payload = {"items": items, "persons": persons,
               "totalMentions": len(cands), "needHuman": len(queue)}

    html = TPL.replace("__DATA__", json.dumps(payload, ensure_ascii=False))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(html, encoding="utf-8")
    print(f"queue {len(items)} / mentions {len(cands)} -> {OUT} ({len(html.encode('utf-8'))} bytes)")
    return 0


TPL = r"""<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8">
<title>B-06 候选队列原型</title>
<style>
:root{--bg:#0d1117;--fg:#e6edf3;--mut:#8b949e;--line:#21262d;--accent:#2b6cb0;--ok:#2f855a;--warn:#b7791f}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--fg);font:15px/1.65 -apple-system,"Microsoft YaHei",sans-serif}
header{display:flex;gap:16px;align-items:center;padding:10px 16px;border-bottom:1px solid var(--line);position:sticky;top:0;background:var(--bg);z-index:5}
h1{font-size:16px;margin:0}
.badge{font-size:12px;color:var(--mut);border:1px solid var(--line);border-radius:999px;padding:1px 8px}
.wrap{display:grid;grid-template-columns:210px 1fr 280px;gap:0;min-height:calc(100vh - 46px)}
aside{border-right:1px solid var(--line);padding:10px;overflow:auto;max-height:calc(100vh - 46px)}
aside.right{border-left:1px solid var(--line);border-right:0}
.q{display:block;width:100%;text-align:left;background:none;border:0;color:var(--fg);padding:6px 8px;border-radius:6px;cursor:pointer;font:13px/1.4 inherit}
.q:hover{background:#161b22}
.q.on{background:#1f6feb33;outline:1px solid #1f6feb66}
.q .k{color:var(--mut);font-size:11px}
main{padding:16px 20px;overflow:auto}
.card{border:1px solid var(--line);border-radius:10px;padding:12px 14px;margin-bottom:14px;background:#11161d}
.prev{color:var(--mut);font-size:13px;border-left:2px solid #30363d;padding-left:8px;margin-bottom:8px}
.msg{font-size:15px;background:#0b0f14;border:1px solid var(--line);border-radius:8px;padding:10px}
mark{background:#b7791f55;color:#ffd479;padding:0 2px;border-radius:3px}
.opts{display:flex;flex-wrap:wrap;gap:8px;margin:10px 0 0}
button.o{background:#161b22;border:1px solid #30363d;color:var(--fg);padding:7px 12px;border-radius:8px;cursor:pointer}
button.o:hover{border-color:#8b949e}
button.o.primary{background:var(--ok);border-color:var(--ok)}
button.o.warn{background:#7c2d12;border-color:#7c2d12}
.pbtn{min-width:56px}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(62px,1fr));gap:6px;margin-top:8px}
.tiny{font-size:12px;color:var(--mut)}
.row{display:flex;gap:8px;align-items:center;flex-wrap:wrap}
.pill{font-size:12px;border:1px solid var(--line);border-radius:999px;padding:1px 8px;color:var(--mut)}
.log{font:12px/1.5 ui-monospace,monospace;color:#9fb3c8;max-height:220px;overflow:auto;background:#0b0f14;border:1px solid var(--line);border-radius:8px;padding:8px}
footer{position:sticky;bottom:0;background:var(--bg);border-top:1px solid var(--line);padding:8px 16px;display:flex;gap:8px;flex-wrap:wrap}
.timer{font-variant-numeric:tabular-nums}
</style></head><body>
<header>
  <h1>B-06 候选队列 · 交互原型</h1>
  <span class="badge" id="pos">1 / 1</span>
  <span class="badge">队列 11 条 / 全部 138 条提及</span>
  <span class="badge timer" id="rate">本分钟 0 条</span>
  <span class="badge" id="cost">每 100 条确认 0 次</span>
  <span class="badge" id="hint">快捷键：1–6 选人，U 撤销，S 拆分，M 标同名</span>
</header>
<div class="wrap">
  <aside id="queue"></aside>
  <main>
    <div class="card">
      <div class="row tiny" style="margin-bottom:8px">
        <span id="meta"></span>
      </div>
      <div class="prev" id="prev"></div>
      <div class="msg" id="msg"></div>
      <div class="row" style="margin-top:12px"><b id="ask">这条提及指的是谁？</b></div>
      <div class="grid" id="people"></div>
      <div class="opts" id="acts"></div>
    </div>
    <div class="card" id="splitBox" style="display:none">
      <b>拆分：这一处其实指两个人？</b>
      <div class="tiny">选择第二个目标，日志会记一条 split（原合并作废，新增两条）</div>
      <div class="grid" id="splitPeople"></div>
    </div>
  </main>
  <aside class="right">
    <div class="tiny" style="margin-bottom:6px">人物卡（点人看详情）</div>
    <div id="personCard" class="card" style="font-size:13px">未选择</div>
    <div class="tiny" style="margin:14px 0 6px">操作日志（与 b06_merge.py 同格式）</div>
    <div class="log" id="log"></div>
  </aside>
</div>
<footer>
  <button class="o" id="prevBtn">← 上一条</button>
  <button class="o" id="nextBtn">下一条 →</button>
  <button class="o" id="undoBtn">撤销上一步 (U)</button>
  <button class="o" id="exportBtn">导出日志 JSONL</button>
  <button class="o" id="showBtn" style="background:#2b6cb0;border-color:#2b6cb0">显示我的答案（复制给我）</button>
  <button class="o" id="resetBtn">清空</button>
</footer>
<script>
const DATA = __DATA__;
const ITEMS = DATA.items, PERSONS = DATA.persons;
const KEY = "b06_proto_v1";
let ans = JSON.parse(localStorage.getItem(KEY) || "{}");
let log = JSON.parse(localStorage.getItem(KEY + "_log") || "[]");
let ops = log.length ? Math.max(...log.map(o => parseInt((o.op_id||"OP-0").slice(3)) || 0)) : 0;
let idx = 0, lastKey = performance.now(), minuteStart = Date.now(), minuteDone = 0;

const $ = id => document.getElementById(id);
const esc = s => String(s == null ? "" : s).replace(/[&<>]/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;"}[c]));
const cur = () => ITEMS[idx];
const ck = it => it.rid + "|" + it.mi + "|" + it.surface;

function save() {
  localStorage.setItem(KEY, JSON.stringify(ans));
  localStorage.setItem(KEY + "_log", JSON.stringify(log));
}

function nextOp() { ops += 1; return "OP-" + String(ops).padStart(4, "0"); }

function addOp(action, extra) {
  const it = cur();
  const op = Object.assign({
    op_id: nextOp(), action, mention_id: it.cid, rule: "proto", evidence: it.why || "",
    by: "0002", ts: new Date().toISOString(),
  }, extra || {});
  log.push(op); save(); renderLog();
  return op;
}

function renderLog() {
  $("log").textContent = log.length ? log.map(o => `${o.op_id} ${o.action} ${o.mention_id}${o.to ? " → " + o.to : ""}${o.note ? " ｜" + o.note : ""}${o.undo_of ? " (撤销 " + o.undo_of + ")" : ""}`).join("\n") : "（空）";
}

function rate() {
  const now = Date.now();
  if (now - minuteStart > 60000) { minuteStart = now; minuteDone = 0; }
  $("rate").textContent = "本分钟 " + minuteDone + " 条";
  const done = Object.keys(ans).length;
  const per100 = done ? (log.filter(o => o.action === "merge").length / done * 100) : 0;
  $("cost").textContent = "每 100 条确认 " + per100.toFixed(1) + " 次（验收 ≤10）";
}
setInterval(rate, 1000);

function renderQueue() {
  $("queue").innerHTML = ITEMS.map((it, i) => {
    const a = ans[ck(it)];
    return `<button class="q ${i===idx?'on':''}" data-i="${i}">
      <div>${a ? "✅ " : ""}${esc(it.surface)}</div>
      <div class="k">${it.rid} · 第${it.mi}条 · ${esc(it.rule)}</div></button>`;
  }).join("");
  [...$("queue").querySelectorAll(".q")].forEach(b => b.onclick = () => { idx = +b.dataset.i; render(); });
}

function renderPeople(box, cb) {
  box.innerHTML = PERSONS.slice(0, 30).map(p =>
    `<button class="o pbtn" data-p="${p.id}">${esc(p.label)}</button>`).join("");
  [...box.querySelectorAll("[data-p]")].forEach(b => b.onclick = () => cb(b.dataset.p));
}

function renderPersonCard(pid) {
  const p = PERSONS.find(x => x.id === pid);
  if (!p) { $("personCard").textContent = "未找到 " + pid; return; }
  $("personCard").innerHTML = `<b>${esc(p.label)}</b> <span class="tiny">${esc(p.id)}</span>
    <div class="tiny" style="margin-top:6px">别名：${p.aliases.length ? p.aliases.map(esc).join("、") : "（无）"}</div>
    <div class="tiny">在候选里出现：${p.seen} 次</div>`;
}

function render() {
  const it = cur(), a = ans[ck(it)];
  $("pos").textContent = (idx + 1) + " / " + ITEMS.length;
  $("meta").innerHTML = `<span class="pill">${esc(it.rid)} 第 ${it.mi} 条</span>
    <span class="pill">类型 ${esc(it.kind)}</span>
    <span class="pill">机器：${esc(it.status)}${it.targets.length ? " → " + it.targets.map(esc).join(",") : ""}（${it.conf}）</span>
    <span class="pill">规则 ${esc(it.rule)}</span>`;
  $("prev").textContent = it.prev ? "上一条：" + it.prev : "";
  const m = it.msg, s = it.surface, i = m.indexOf(s);
  $("msg").innerHTML = i >= 0
    ? esc(m.slice(0, i)) + "<mark>" + esc(s) + "</mark>" + esc(m.slice(i + s.length))
    : esc(m);
  $("ask").textContent = `「${it.surface}」指的是谁？` + (a ? `（已选：${esc(a.target)}，点别的可以改）` : "");
  renderPeople($("people"), pick);
  $("acts").innerHTML = `
    <button class="o warn" data-act="notperson">不是人（泛指/口号/地点）</button>
    <button class="o warn" data-act="unknown">判不出来</button>
    <button class="o" data-act="split">拆分（S）</button>
    <button class="o" data-act="same">标为同一人（M）</button>`;
  [...$("acts").querySelectorAll("[data-act]")].forEach(b => b.onclick = () => doAct(b.dataset.act));
  renderQueue(); renderLog(); rate();
}

function pick(pid) {
  ans[ck(cur())] = { target: pid };
  addOp("merge", { to: pid, note: "人工确认" });
  minuteDone += 1;
  save(); advance();
}

function doAct(act) {
  if (act === "split") { $("splitBox").style.display = "block"; renderPeople($("splitPeople"), p => {
      addOp("split", { to: p, note: "拆成两个目标" });
      ans[ck(cur())] = { target: "SPLIT" }; $("splitBox").style.display = "none"; minuteDone += 1; save(); advance();
    }); return; }
  if (act === "same") {
    const other = prompt("要标记为与哪个人同一人？（输入编号，如 P03）");
    if (!other) return;
    addOp("merge", { to: other, note: "标记同名" });
    ans[ck(cur())] = { target: other }; minuteDone += 1; save(); advance(); return;
  }
  ans[ck(cur())] = { target: act === "notperson" ? "not_person" : "unknown" };
  addOp("merge", { to: act === "notperson" ? "not_person" : "unknown", note: "人工改判" });
  minuteDone += 1; save(); advance();
}

function undo() {
  if (!log.length) return;
  const last = log[log.length - 1];
  if (last.action === "undo") return;
  log.push({ op_id: nextOp(), action: "undo", mention_id: last.mention_id,
             undo_of: last.op_id, rule: "proto", by: "0002", ts: new Date().toISOString() });
  delete ans[last.mention_id.split("|")[0] + "|" + last.mention_id.split("|")[1] + "|" + last.mention_id.split("|")[2]];
  save(); render(); 
}

function advance() { if (idx < ITEMS.length - 1) idx += 1; render(); }

// —— 绑定 ——
$("prevBtn").onclick = () => { if (idx > 0) idx -= 1; render(); };
$("nextBtn").onclick = () => { if (idx < ITEMS.length - 1) idx += 1; render(); };
$("undoBtn").onclick = undo;
$("resetBtn").onclick = () => { if (confirm("清空全部答案与日志？")) { ans = {}; log = []; ops = 0; save(); render(); } };
$("exportBtn").onclick = () => {
  const blob = new Blob([log.map(o => JSON.stringify(o)).join("\n") + "\n"], { type: "application/jsonl" });
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob); a.download = "b06-merge-log-0002.jsonl"; a.click();
};
$("showBtn").onclick = () => {
  const rows = ITEMS.map((it, i) => {
    const a = ans[ck(it)];
    return `第${i + 1}条 ${it.rid}#${it.mi} 「${it.surface}」 → ${a ? a.target : "（未选）"}`;
  }).join("\n");
  const pre = document.createElement("pre");
  pre.style.cssText = "white-space:pre-wrap;padding:18px;font:14px/2 monospace";
  pre.textContent = rows + "\n\n（全选这段文字发给我即可）";
  document.body.innerHTML = ""; document.body.appendChild(pre);
};
document.addEventListener("keydown", e => {
  if (e.key === "u" || e.key === "U") return undo();
  if (e.key === "s" || e.key === "S") return doAct("split");
  if (e.key === "m" || e.key === "M") return doAct("same");
  const n = parseInt(e.key, 10);
  if (n >= 1 && n <= 9) { const p = PERSONS[n - 1]; if (p) pick(p.id); }
});

if (location.hash === "#reset") { localStorage.removeItem(KEY); localStorage.removeItem(KEY + "_log"); ans = {}; log = []; }
render();
</script></body></html>
"""

if __name__ == "__main__":
    raise SystemExit(main())

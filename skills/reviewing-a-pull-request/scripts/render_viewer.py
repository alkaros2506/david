#!/usr/bin/env python3
"""Render a PR triage classification into a self-contained HTML review viewer.

    render_viewer.py classification.json [output.html] [--diff diff.patch]

Defaults output to <input>.review.html. No third-party dependencies. When a diff
is supplied, each group shows the cited hunks inline (busy-work collapsed; a global
"Hide trivial diffs" toggle drops them). Acks persist to the browser's localStorage
and Export downloads a schema-shaped sidecar (<id>.review.json).
"""
import json
import re
import sys
from pathlib import Path


def parse_args(argv):
    src = out = diff = None
    i = 0
    while i < len(argv):
        a = argv[i]
        if a == "--diff":
            diff = argv[i + 1]; i += 2
        elif a in ("--out", "-o"):
            out = argv[i + 1]; i += 2
        elif src is None:
            src = a; i += 1
        elif out is None:
            out = a; i += 1
        else:
            i += 1
    if not src:
        sys.exit("usage: render_viewer.py classification.json [output.html] [--diff diff.patch]")
    return src, out, diff


def parse_diff(text):
    """Unified diff -> {filename: [{header, start, end, rows:[[marker,new_lineno,text]]}]}."""
    files, cur, in_hunk, new_no = {}, None, False, 0
    for line in text.splitlines():
        if line.startswith("diff --git"):
            cur, in_hunk = None, False
            continue
        if not in_hunk and line.startswith("--- "):
            continue
        if not in_hunk and line.startswith("+++ "):
            p = line[4:].strip()
            p = p[2:] if p.startswith("b/") else p
            cur = None if p == "/dev/null" else p
            if cur:
                files.setdefault(cur, [])
            continue
        if line.startswith("@@"):
            m = re.search(r"\+(\d+)", line)
            new_no = int(m.group(1)) if m else 0
            in_hunk = True
            if cur:
                files[cur].append({"header": line, "start": new_no, "rows": []})
            continue
        if not in_hunk or not cur or not files.get(cur):
            continue
        tag = line[:1]
        if tag == "+":
            files[cur][-1]["rows"].append(["+", new_no, line[1:]]); new_no += 1
        elif tag == "-":
            files[cur][-1]["rows"].append(["-", None, line[1:]])
        elif tag == "\\":
            continue
        else:  # context line (leading space, or a bare empty line at EOF)
            files[cur][-1]["rows"].append([" ", new_no, line[1:] if tag == " " else line]); new_no += 1
    for hunks in files.values():
        for h in hunks:
            news = [r[1] for r in h["rows"] if r[1] is not None]
            h["end"] = max(news) if news else h["start"]
    return files


def js_embed(obj):
    """Serialize for safe inlining inside <script>: neutralize </script>, <!--, and U+2028/9."""
    s = json.dumps(obj, ensure_ascii=False)
    for a, b in (("<", "\\u003c"), (">", "\\u003e"), ("&", "\\u0026"),
                 (" ", "\\u2028"), (" ", "\\u2029")):
        s = s.replace(a, b)
    return s


def main():
    src_s, out_s, diff_s = parse_args(sys.argv[1:])
    src = Path(src_s)
    data = json.loads(src.read_text())
    diff_obj = parse_diff(Path(diff_s).read_text()) if diff_s else None
    out = Path(out_s) if out_s else src.with_suffix(".review.html")
    html = (TEMPLATE
            .replace("__DIFF__", js_embed(diff_obj) if diff_obj else "null")
            .replace("__DATA__", js_embed(data)))
    out.write_text(html, encoding="utf-8")
    files = len(diff_obj) if diff_obj else 0
    print(f"Wrote {out}  ({len(data.get('groups', []))} groups, {files} diffed files). Open it in a browser.")


TEMPLATE = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>PR Review Copilot</title>
<style>
  :root{
    --bg:#0e1116; --panel:#161b22; --panel2:#1c232d; --line:#2a323d;
    --ink:#e6edf3; --muted:#8b97a7; --accent:#4d9fff;
    --green:#2ea043; --amber:#d4a017; --red:#e5534b;
    --low:#3a4250; --med:#6b5d1f; --high:#7a2b27;
  }
  *{box-sizing:border-box}
  body{margin:0;background:var(--bg);color:var(--ink);font:14px/1.5 system-ui,-apple-system,Segoe UI,Roboto,sans-serif}
  a{color:var(--accent);text-decoration:none}
  header{padding:20px 24px;border-bottom:1px solid var(--line);background:var(--panel)}
  h1{margin:0 0 4px;font-size:18px}
  .meta{color:var(--muted);font-size:12.5px}
  .meta code{background:var(--panel2);padding:1px 6px;border-radius:5px}
  main{max-width:1080px;margin:0 auto;padding:20px 24px 80px}
  .bar{display:flex;flex-wrap:wrap;gap:14px;align-items:center;margin:0 0 18px}
  .bar input{background:var(--panel2);border:1px solid var(--line);color:var(--ink);border-radius:7px;padding:6px 10px;font-size:13px}
  .progress{flex:1;min-width:160px;height:10px;border-radius:99px;background:var(--panel2);overflow:hidden;border:1px solid var(--line)}
  .progress > div{height:100%;background:var(--green);width:0;transition:width .25s}
  .pill{font-size:12px;color:var(--muted)}
  .pill b{color:var(--ink)}
  button{cursor:pointer;font:inherit}
  .ghost{background:var(--panel2);border:1px solid var(--line);color:var(--ink);border-radius:7px;padding:6px 12px}
  .ghost.active{border-color:var(--accent);color:var(--accent)}

  .matrix{display:grid;grid-template-columns:90px repeat(3,1fr);gap:8px;margin:0 0 24px}
  .mcell{background:var(--panel);border:1px solid var(--line);border-radius:9px;padding:10px;min-height:64px;cursor:pointer;position:relative;transition:.15s}
  .mcell:hover{border-color:var(--accent)}
  .mcell.sel{outline:2px solid var(--accent)}
  .mcell.empty{opacity:.45;cursor:default}
  .mcell .cnt{font-size:20px;font-weight:700}
  .mcell .sub{font-size:11px;color:var(--muted)}
  .mhead{display:flex;align-items:center;justify-content:center;color:var(--muted);font-size:11.5px;font-weight:600;text-transform:uppercase;letter-spacing:.04em}
  .mrow-label{display:flex;align-items:center;color:var(--muted);font-size:12px;font-weight:600}
  .mcell .ring{position:absolute;top:8px;right:8px;width:8px;height:8px;border-radius:99px;background:var(--red)}

  .card{background:var(--panel);border:1px solid var(--line);border-left-width:4px;border-radius:10px;padding:14px 16px;margin:0 0 12px}
  .card.t-busy_work{border-left-color:var(--green)}
  .card.t-new_capability{border-left-color:var(--amber)}
  .card.t-new_architecture{border-left-color:var(--red)}
  .card.malformed{border-left-color:var(--muted)}
  .card.done{opacity:.6}
  .crow{display:flex;gap:10px;align-items:flex-start;justify-content:space-between}
  .ctitle{font-size:15px;font-weight:650;margin:0}
  .badges{display:flex;gap:6px;flex-wrap:wrap;align-items:center}
  .badge{font-size:11px;padding:2px 8px;border-radius:99px;border:1px solid var(--line);white-space:nowrap}
  .b-busy_work{background:rgba(46,160,67,.14);color:#7ee2a0}
  .b-new_capability{background:rgba(212,160,23,.14);color:#f0cf6e}
  .b-new_architecture{background:rgba(229,83,75,.16);color:#ff9b95}
  .b-low{background:var(--low)} .b-med{background:var(--med)} .b-high{background:var(--high)}
  .b-unknown{background:var(--panel2);color:var(--muted)}
  .prio{font-size:11px;color:var(--muted);border:1px solid var(--line);border-radius:6px;padding:2px 7px}
  .warn{font-size:11px;color:var(--red)}
  .summary{color:var(--muted);margin:6px 0 10px}
  .why{margin:8px 0;padding:8px 10px;background:var(--panel2);border-radius:8px;font-size:13px}
  .why b{color:var(--ink)}
  .surfaces{display:flex;gap:5px;flex-wrap:wrap;margin:6px 0}
  .surf{font-size:10.5px;color:var(--muted);background:var(--panel2);border:1px solid var(--line);border-radius:5px;padding:1px 6px}
  .focus,.checks{margin:8px 0;padding-left:18px}
  .focus li{margin:2px 0}
  .checks{list-style:none;padding-left:0}
  .checks li{display:flex;gap:8px;align-items:flex-start;margin:3px 0}
  .checks .req{color:var(--red);font-size:11px}
  .cite{font-family:ui-monospace,Menlo,monospace;font-size:11.5px;color:var(--muted);margin:2px 0}
  .cite span{color:var(--ink)}

  details.diff{margin-top:10px;border:1px solid var(--line);border-radius:8px;background:#0b0e13;overflow:hidden}
  details.diff > summary{cursor:pointer;padding:7px 10px;color:var(--muted);font-size:12px;user-select:none}
  .difffile{font-family:ui-monospace,Menlo,monospace;font-size:11.5px;color:var(--accent);padding:7px 10px 2px;border-top:1px solid var(--line)}
  .hunk{font-family:ui-monospace,Menlo,monospace;font-size:11.5px;overflow-x:auto;padding-bottom:4px}
  .hunk .hh{color:#7aa2cf;background:#11161d;padding:1px 10px;white-space:pre}
  .row{white-space:pre;padding:0 10px}
  .row .ln{display:inline-block;width:44px;text-align:right;color:#586273;padding-right:12px;user-select:none}
  .row.add{background:rgba(46,160,67,.16)}
  .row.del{background:rgba(229,83,75,.16)}
  .nodiff{color:var(--muted);font-size:12px;padding:7px 10px;font-style:italic}
  .truncated{color:var(--muted);font-size:11px;padding:3px 10px;font-style:italic}
  body.hide-trivial .card.t-busy_work details.diff{display:none}

  .ackrow{display:flex;gap:10px;align-items:center;flex-wrap:wrap;margin-top:12px;border-top:1px solid var(--line);padding-top:10px}
  .ackbtn{border:1px solid var(--line);background:var(--panel2);color:var(--ink);border-radius:7px;padding:6px 12px}
  .ackbtn.on{background:var(--green);border-color:var(--green);color:#04130a;font-weight:600}
  .ackrow input{flex:1;min-width:160px;background:var(--panel2);border:1px solid var(--line);color:var(--ink);border-radius:7px;padding:6px 10px}
  .empty-state{color:var(--muted);text-align:center;padding:40px}
</style>
</head>
<body>
<header>
  <h1 id="pr-title"></h1>
  <div class="meta" id="pr-meta"></div>
</header>
<main>
  <div class="bar">
    <input id="reviewer" placeholder="Your name (for the ack trail)" autocomplete="name">
    <div class="progress"><div id="progress-fill"></div></div>
    <span class="pill" id="progress-text"></span>
    <button class="ghost" id="filter-unreviewed">Only unreviewed</button>
    <button class="ghost" id="toggle-trivial" hidden>Hide trivial diffs</button>
    <button class="ghost" id="export">Export review state</button>
  </div>
  <div class="matrix" id="matrix"></div>
  <div id="cards"></div>
</main>
<script>
const DATA = __DATA__;
const DIFF = __DIFF__;
const TIERS = ["new_architecture","new_capability","busy_work"];
const BLASTS = ["low","medium","high"];
const TIER_LABEL = {busy_work:"Busy work",new_capability:"New capability",new_architecture:"New architecture"};
const MAX_ROWS = 400;
const esc = s => String(s==null?"":s).replace(/[&<>"]/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));

function hashGroups(){ const s=(DATA.groups||[]).map(g=>g&&g.id).join("|"); let h=0; for(let i=0;i<s.length;i++)h=(h*31+s.charCodeAt(i))|0; return (h>>>0).toString(36); }
const PID = (DATA.pr && DATA.pr.id) || ("anon-"+hashGroups());
const KEY = "review-copilot:"+PID;

let store = load();
let filter = {tier:null, blast:null, onlyUnreviewed:false};

function load(){ try{ return JSON.parse(localStorage.getItem(KEY)) || seed(); }catch(e){ return seed(); } }
function seed(){
  const acks={}, checks={};
  (DATA.groups||[]).forEach(g=>{
    const a = g.ack||{};
    acks[g.id] = a.state==="acknowledged" ? {state:"acknowledged",by:a.by||"",at:a.at||"",note:a.note||""} : {state:"pending",by:"",at:"",note:""};
    checks[g.id] = {};
  });
  return {reviewer:"", acks, checks};
}
function save(){ localStorage.setItem(KEY, JSON.stringify(store)); }

function blastClass(b){ return b==="high"?"b-high":b==="medium"?"b-med":b==="low"?"b-low":"b-unknown"; }
function isDone(id){ return store.acks[id] && store.acks[id].state==="acknowledged"; }
function tierOf(g){ return (g.novelty||{}).tier; }
function blastOf(g){ return (g.blast||{}).level; }

function renderHeader(){
  const pr = DATA.pr||{};
  const safeUrl = pr.url && /^https?:\/\//i.test(pr.url) ? pr.url : null;
  const label = esc(pr.title||pr.id||"Pull request");
  document.getElementById("pr-title").innerHTML = safeUrl ? `<a href="${esc(safeUrl)}">${label}</a>` : label;
  const rules = (DATA.rules_sources||[]).map(r=>`<code>${esc(r)}</code>`).join(" ") || "<i>none</i>";
  document.getElementById("pr-meta").innerHTML =
    `${esc(pr.id||"")} &middot; ${(DATA.groups||[]).length} change groups &middot; rules: ${rules}`
    + (pr.description_summary?`<br>${esc(pr.description_summary)}`:"");
  const rv = document.getElementById("reviewer");
  rv.value = store.reviewer||"";
  rv.addEventListener("input", ()=>{ store.reviewer = rv.value; save(); });
}

function renderProgress(){
  const gs = DATA.groups||[];
  const done = gs.filter(g=>isDone(g.id)).length;
  const p1left = gs.filter(g=>g.priority===1 && !isDone(g.id)).length;
  document.getElementById("progress-fill").style.width = (gs.length?100*done/gs.length:0)+"%";
  document.getElementById("progress-text").innerHTML =
    `<b>${done}/${gs.length}</b> reviewed` + (p1left?` &middot; <b style="color:var(--red)">${p1left}</b> P1 left`:" &middot; P1 clear");
}

function renderMatrix(){
  const m = document.getElementById("matrix");
  const cnt = {};
  (DATA.groups||[]).forEach(g=>{
    const k = tierOf(g)+"|"+blastOf(g);
    (cnt[k]=cnt[k]||{n:0,open:0}).n++;
    if(!isDone(g.id)) cnt[k].open++;
  });
  let h = `<div class="mhead"></div>` + BLASTS.map(b=>`<div class="mhead">Blast: ${b}</div>`).join("");
  for(const t of TIERS){
    h += `<div class="mrow-label">${TIER_LABEL[t]}</div>`;
    for(const b of BLASTS){
      const c = cnt[t+"|"+b]||{n:0,open:0};
      const sel = (filter.tier===t && filter.blast===b) ? " sel":"";
      const cls = c.n? blastClass(b) : "empty";
      h += `<div class="mcell ${cls}${sel}" data-t="${t}" data-b="${b}">`
         + (c.n?`<div class="cnt">${c.n}</div><div class="sub">${c.open} open</div>`:`<div class="sub">&mdash;</div>`)
         + (c.open && t==="new_architecture"?'<div class="ring"></div>':"")
         + `</div>`;
    }
  }
  m.innerHTML = h;
  m.querySelectorAll(".mcell").forEach(el=>{
    if(el.classList.contains("empty")) return;
    el.onclick = ()=>{
      const t=el.dataset.t, b=el.dataset.b;
      if(filter.tier===t && filter.blast===b){ filter.tier=filter.blast=null; }
      else { filter.tier=t; filter.blast=b; }
      renderAll();
    };
  });
}

function parseRange(s){ if(!s) return null; const m=String(s).match(/(\d+)(?:\s*-\s*(\d+))?/); return m?[+m[1], m[2]?+m[2]:+m[1]]:null; }

function renderHunk(h){
  let s = `<div class="hunk"><div class="hh">${esc(h.header)}</div>`;
  const rows = h.rows.slice(0, MAX_ROWS);
  rows.forEach(r=>{
    const cls = r[0]==="+"?"add":r[0]==="-"?"del":"";
    s += `<div class="row ${cls}"><span class="ln">${r[1]==null?"":r[1]}</span>${esc(r[0]+r[2])}</div>`;
  });
  if(h.rows.length>MAX_ROWS) s += `<div class="truncated">… ${h.rows.length-MAX_ROWS} more lines</div>`;
  return s+"</div>";
}

function diffFor(g){
  if(!DIFF) return "";
  const seen = new Set(); const blocks = [];
  (g.citations||[]).forEach(c=>{
    if(!c.file || seen.has(c.file)) return; seen.add(c.file);
    const hunks = DIFF[c.file];
    if(!hunks){ blocks.push(`<div class="nodiff">${esc(c.file)} — no diff captured</div>`); return; }
    const rng = parseRange(c.lines);
    const sel = rng ? hunks.filter(h=>h.end>=rng[0] && h.start<=rng[1]) : hunks;
    const use = sel.length ? sel : hunks;
    blocks.push(`<div class="difffile">${esc(c.file)}</div>` + use.map(renderHunk).join(""));
  });
  return blocks.join("");
}

function card(g){
  const done = isDone(g.id);
  const tier = tierOf(g), level = blastOf(g);
  const malformed = !g.novelty || !g.blast;
  const surf = ((g.blast||{}).surfaces||[]).map(s=>`<span class="surf">${esc(s)}</span>`).join("");
  const cites = (g.citations||[]).map(c=>`<div class="cite"><span>${esc(c.file)}</span>${c.lines?":"+esc(c.lines):""}${c.note?"  — "+esc(c.note):""}</div>`).join("");
  const focus = (g.review_focus||[]).map(f=>`<li>${esc(f)}</li>`).join("");
  const checks = (g.checklist||[]).map((c,i)=>{
    const on = store.checks[g.id] && store.checks[g.id][i];
    return `<li><input type="checkbox" data-g="${esc(g.id)}" data-i="${i}" ${on?"checked":""}>`
         + `<span>${esc(c.item)}${c.required?' <span class="req">required</span>':""}</span></li>`;
  }).join("");
  const dff = diffFor(g);
  const nFiles = new Set((g.citations||[]).map(c=>c.file).filter(Boolean)).size;
  const diffBlock = dff ? `<details class="diff" ${tier==="busy_work"?"":"open"}><summary>&#128196; Diff (${nFiles} file${nFiles!==1?"s":""})</summary>${dff}</details>` : "";
  const a = store.acks[g.id]||{state:"pending"};
  const why = malformed ? '<span class="warn">&#9888; group is missing novelty/blast — classifier output may be malformed</span>'
                        : `<b>Why:</b> ${esc((g.novelty||{}).rationale)} &middot; ${esc((g.blast||{}).rationale)}`;
  return `<div class="card t-${esc(tier||"")} ${malformed?"malformed":""} ${done?"done":""}" data-id="${esc(g.id)}">
    <div class="crow">
      <h3 class="ctitle">${esc(g.title)}</h3>
      <div class="badges">
        <span class="prio">P${g.priority==null?"?":esc(g.priority)}</span>
        <span class="badge b-${esc(tier||"unknown")}">${TIER_LABEL[tier]||"unknown"}</span>
        <span class="badge ${blastClass(level)}">blast: ${esc(level||"?")}</span>
      </div>
    </div>
    ${g.summary?`<div class="summary">${esc(g.summary)}</div>`:""}
    <div class="why">${why}</div>
    ${surf?`<div class="surfaces">${surf}</div>`:""}
    ${focus?`<div><b>Look at:</b><ul class="focus">${focus}</ul></div>`:""}
    ${checks?`<ul class="checks">${checks}</ul>`:""}
    ${cites?`<div>${cites}</div>`:""}
    ${diffBlock}
    <div class="ackrow">
      <button class="ackbtn ${done?"on":""}" data-ack="${esc(g.id)}">${done?"✓ Acknowledged":"Acknowledge"}</button>
      <input placeholder="note (optional)" data-note="${esc(g.id)}" value="${esc(a.note||"")}">
      ${a.at?`<span class="pill">${esc(a.by||"?")} &middot; ${esc((a.at||"").slice(0,16).replace("T"," "))}</span>`:""}
    </div>
  </div>`;
}

function renderCards(){
  let gs = (DATA.groups||[]).slice().sort((a,b)=>((a.priority??99)-(b.priority??99))||TIERS.indexOf(tierOf(a))-TIERS.indexOf(tierOf(b)));
  if(filter.tier) gs = gs.filter(g=>tierOf(g)===filter.tier && blastOf(g)===filter.blast);
  if(filter.onlyUnreviewed) gs = gs.filter(g=>!isDone(g.id));
  const el = document.getElementById("cards");
  el.innerHTML = gs.length ? gs.map(card).join("") : `<div class="empty-state">Nothing matches this filter.</div>`;

  el.querySelectorAll("[data-ack]").forEach(b=>b.onclick=()=>{
    const id=b.dataset.ack, a=store.acks[id];
    if(a.state==="acknowledged"){ a.state="pending"; a.at=""; }
    else { a.state="acknowledged"; a.by=store.reviewer||"anon"; a.at=new Date().toISOString(); }
    save(); renderAll();
  });
  el.querySelectorAll("[data-note]").forEach(inp=>inp.oninput=()=>{ store.acks[inp.dataset.note].note=inp.value; save(); });
  el.querySelectorAll(".checks input").forEach(c=>c.onchange=()=>{
    const id=c.dataset.g; (store.checks[id]=store.checks[id]||{})[c.dataset.i]=c.checked; save();
  });
}

function renderAll(){
  document.getElementById("filter-unreviewed").classList.toggle("active", filter.onlyUnreviewed);
  renderProgress(); renderMatrix(); renderCards();
}

document.getElementById("filter-unreviewed").onclick=()=>{ filter.onlyUnreviewed=!filter.onlyUnreviewed; renderAll(); };
if(DIFF){
  const tt = document.getElementById("toggle-trivial");
  tt.hidden = false;
  tt.onclick=()=>{ const on=document.body.classList.toggle("hide-trivial"); tt.classList.toggle("active",on); };
}
document.getElementById("export").onclick=()=>{
  const copy = JSON.parse(JSON.stringify(DATA));
  copy.reviewer = store.reviewer||"";
  (copy.groups||[]).forEach(g=>{ g.ack = store.acks[g.id] || {state:"pending"}; });
  const blob = new Blob([JSON.stringify(copy,null,2)], {type:"application/json"});
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = PID.replace(/[^\w.-]+/g,"_") + ".review.json";
  a.click();
};

renderHeader(); renderAll();
</script>
</body>
</html>
"""


if __name__ == "__main__":
    main()

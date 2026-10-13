"""The viewer's style and behaviour, kept out of the Python.

The page is one self-contained document: a small amount of data as JSON, a small
amount of vanilla JS, no framework, no build step, and nothing fetched from anywhere.
Keeping these two strings here means `render.py` is about *what* the page says and
this file is about *how it looks and moves*.

The alternative — a JSON blob rendered client-side only — would mean an empty page for
anyone reading with JS off, so the static shell carries real content too.
"""

from __future__ import annotations

CSS = """
:root {
  --ink: #c9d1d9;
  --muted: #7d8590;
  --dim: #565f6a;
  --bg: #0e1116;
  --panel: #11151b;
  --line: #1d232b;
  --edge: #2a3038;
  --hi: #1f6feb;
  --warn: #d29922;
  --ok: #3fb950;
  --seq: #3fb950;
}
* { box-sizing: border-box; }
body {
  margin: 0;
  background: var(--bg);
  color: var(--ink);
  font: 12px/1.5 ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
}
header {
  padding: 7px 12px;
  background: #161b22;
  border-bottom: 1px solid var(--edge);
  display: flex;
  gap: 14px;
  align-items: baseline;
  flex-wrap: wrap;
}
header b { font-weight: 600; }
header .muted { color: var(--muted); }
header .warn { color: var(--warn); }
main {
  display: grid;
  grid-template-columns: 260px minmax(0, 1fr) minmax(0, 1fr);
  gap: 1px;
  background: var(--edge);
  min-height: calc(100vh - 34px);
}
section, aside {
  background: var(--panel);
  padding: 9px 11px;
  overflow: auto;
  max-height: calc(100vh - 34px);
}
h2 {
  font-size: 8.5px;
  letter-spacing: 0.09em;
  text-transform: uppercase;
  color: var(--muted);
  margin: 0 0 8px;
  font-weight: 600;
}
h2 + h3 { margin-top: 0; }
h3 {
  font-size: 11px;
  margin: 14px 0 6px;
  color: var(--ink);
  font-weight: 600;
}
h3:first-child { margin-top: 0; }
ul { list-style: none; margin: 0; padding: 0; }
li { white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
details > summary { cursor: pointer; list-style: none; }
details > summary::-webkit-details-marker { display: none; }
.tcaret { color: var(--dim); display: inline-block; width: 1.1em; }
details[open] > summary .tcaret { transform: rotate(90deg); }
.row { padding: 0 3px; border-radius: 3px; color: var(--muted); }
.row:hover { background: #1a2029; }
.row.sel { background: #1f6feb33; box-shadow: inset 0 0 0 1px #1f6feb66; color: #e6edf3; }
.row i { font-style: normal; color: var(--dim); }
.pill {
  display: inline-block;
  border: 1px solid var(--edge);
  border-radius: 8px;
  padding: 0 5px;
  font-size: 9px;
  color: var(--muted);
  margin-left: 5px;
}
.pill.warn { border-color: #d2992266; color: var(--warn); }
.pill.param { border-color: #1f6feb66; color: #58a6ff; }
        .bar {
    display: grid;
    grid-template-columns: 150px 1fr 52px;
    gap: 7px;
    align-items: center;
    margin-bottom: 2px;
    font-size: 10.5px;
}
.bar .name { overflow: hidden; text-overflow: ellipsis; }
.bar .track { background: #1a2029; height: 9px; border-radius: 2px; overflow: hidden; }
.bar .fill { height: 100%; background: #2f81f7; }
.bar .fill.seq { background: var(--seq); }
.bar .n { color: var(--dim); text-align: right; }
table { border-collapse: collapse; font-size: 10.5px; width: 100%; }
td { padding: 1px 6px 1px 0; vertical-align: top; }
td.k { color: var(--dim); white-space: nowrap; }
td.v { color: var(--ink); }
tr:nth-child(even) td { background: #141a21; }
        .finding {
    border: 1px solid var(--edge);
    border-radius: 5px;
    padding: 6px 8px;
    margin-bottom: 5px;
    background: #141a21;
}
.finding .code { color: var(--warn); }
.finding .subj { color: var(--ink); }
.finding.error { border-color: #f8514966; }
.finding.error .code { color: #f85149; }
.empty { color: var(--dim); }
pre {
  margin: 0;
  font: 10.5px/1.6 ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
  white-space: pre;
  overflow: auto;
}
pre .ln { color: #3d444d; user-select: none; }
pre .hl { background: #d2992222; box-shadow: inset 0 0 0 1px #d2992255; }
input[type="search"] {
  width: 100%;
  margin-bottom: 8px;
  background: #141a21;
  border: 1px solid var(--edge);
  border-radius: 4px;
  color: var(--ink);
  padding: 4px 6px;
  font: inherit;
}
.stat { color: var(--ok); }
"""

JS = """
(function () {
  var model = JSON.parse(document.getElementById("ve-model").textContent);
  var tree = document.getElementById("tree");
  var panel = document.getElementById("panel");
  var sourcePane = document.getElementById("source-pane");
  var search = document.getElementById("ve-filter");
  var byKey = {};
  model.modules.forEach(function (m) { byKey[m.key] = m; });
  var children = {};
  model.instances.forEach(function (n) {
    var parent = n.path.indexOf("/") === -1 ? "" : n.path.slice(0, n.path.lastIndexOf("/"));
    (children[parent] = children[parent] || []).push(n);
  });

  document.getElementById("ve-title").textContent = model.title;
  var stats = [
    model.modules.length + " modules",
    cellTotal() + " cells",
    count("flops") + " flops",
    count("latches") + " latches"
  ];
  if (count("latches")) { stats = stats.concat([]); }
  stats.push(model.flavour + " netlist");
  document.getElementById("ve-counts").innerHTML = "";
  stats.forEach(function (s) {
    var b = document.createElement("b");
    b.textContent = s;
    var span = document.createElement("span");
    span.className = "muted";
    span.appendChild(b);
    document.getElementById("ve-counts").appendChild(span);
  });

  function cellTotal() {
    return model.modules.reduce(function (n, m) { return n + m.cells; }, 0);
  }
  function count(kind) {
    return model.modules.reduce(function (n, m) { return n + m[kind]; }, 0);
  }

  function renderTree() {
    tree.innerHTML = "";
    var needle = (search.value || "").toLowerCase();
    var roots = children[""] || [];
    if (!roots.length) {
      tree.innerHTML = '<p class="empty">no design modules in this netlist</p>';
      return;
    }
    roots.forEach(function (n) { tree.appendChild(nodeElement(n, needle, 0)); });
    if (tree.children.length === 1 && tree.children[0].tagName === "P") { return; }
    select(model.top || roots[0].module);
  }

  function nodeElement(n, needle, depth) {
    var entry = byKey[n.module];
    var detail = document.createElement("details");
    detail.open = depth < 1;
    detail.style.paddingLeft = "1.1em";
    var summary = document.createElement("summary");
    summary.className = "row";
    var caret = document.createElement("span");
    caret.className = "tcaret";
    caret.textContent = detail.open ? "\\u25b6" : "\\u25b6";
    var label = document.createElement("span");
    label.textContent = n.label + " ";
    var mod = document.createElement("i");
    mod.textContent = (entry && entry.label) || n.module;
    summary.appendChild(caret);
    summary.appendChild(label);
    summary.appendChild(mod);
    if (entry && entry.badges && entry.badges.length) {
      entry.badges.forEach(function (b) {
        var p = document.createElement("span");
        p.className = "pill param";
        p.textContent = b;
        summary.appendChild(p);
      });
    }
    if (entry && entry.latches) {
      var l = document.createElement("span");
      l.className = "pill warn";
      l.textContent = entry.latches + " latches";
      summary.appendChild(l);
    }
    if (entry && needle
        && (label.textContent + " " + mod.textContent).toLowerCase().indexOf(needle) !== -1) {
      summary.classList.add("sel");
    }
    summary.addEventListener("click", function (ev) {
      ev.preventDefault();
      if (entry) { select(entry.key); }
    });
    detail.appendChild(summary);
    (children[n.path] || []).forEach(function (c) {
      detail.appendChild(nodeElement(c, needle, depth + 1));
    });
    return detail;
  }

  function select(key) {
    var entry = byKey[key];
    if (!entry) { return; }
    var marks = tree.querySelectorAll(".row.sel");
    for (var i = 0; i < marks.length; i++) { marks[i].classList.remove("sel"); }
    panel.innerHTML = "";
    panel.appendChild(el("h3", entry.label));
    var meta = [];
    meta.push(entry.cells + " cells");
    meta.push(entry.flops + " flops");
    if (entry.latches) { meta.push(entry.latches + " latches"); }
    meta.push(entry.macros + " macros");
    panel.appendChild(el("p", {
      className: "empty",
      text: entry.key + " \u00b7 " + meta.join(" \u00b7 ")
    }));
    renderSub(panel, "instances", entry.instances, function (n) {
      return n.label + " : " + ((byKey[n.module] && byKey[n.module].label) || n.module);
    }, entry);
    renderBars(panel, "cells by type", entry.types);
    renderNets(panel, entry);
    renderFindings(panel, entry);
    renderSource(entry);
  }

  function el(tag, opts) {
    var e = document.createElement(tag);
    if (typeof opts === "string") { e.textContent = opts; return e; }
    opts = opts || {};
    if (opts.text) { e.textContent = opts.text; }
    if (opts.className) { e.className = opts.className; }
    return e;
  }

  function renderSub(parent, title, rows, label, entry) {
    if (!rows || !rows.length) { return; }
    var h = el("h3", title + " (" + rows.length + ")");
    parent.appendChild(h);
    var table = document.createElement("table");
    rows.forEach(function (r) {
      var tr = document.createElement("tr");
      var k = document.createElement("td");
      k.className = "k";
      k.textContent = r.name || r.label || r;
      var v = document.createElement("td");
      v.className = "v";
      v.textContent = label(r);
      tr.appendChild(k);
      tr.appendChild(v);
      table.appendChild(tr);
    });
    parent.appendChild(table);
  }

  function renderBars(parent, title, types) {
    if (!types || !types.length) { return; }
    parent.appendChild(el("h3", title));
    var max = Math.max.apply(null, types.map(function (t) { return t[1]; }));
    types.forEach(function (t) {
      var bar = document.createElement("div");
      bar.className = "bar";
      var name = document.createElement("span");
      name.className = "name";
      name.textContent = t[0];
      var track = document.createElement("span");
      track.className = "track";
      var fill = document.createElement("span");
      fill.className = "fill";
      if (t[0].indexOf("flop") !== -1 || /dfr|dff|lhq/.test(t[0])) { fill.className += " seq"; }
      fill.style.width = Math.round((t[1] / max) * 100) + "%";
      var n = document.createElement("span");
      n.className = "n";
      n.textContent = t[1];
      track.appendChild(fill);
      bar.appendChild(name);
      bar.appendChild(track);
      bar.appendChild(n);
      parent.appendChild(bar);
    });
  }

  function renderNets(parent, entry) {
    if (!entry.nets || !entry.nets.length) { return; }
    parent.appendChild(el("h3", "nets, most loads first"));
    var table = document.createElement("table");
    entry.nets.forEach(function (n) {
      var tr = document.createElement("tr");
      var td1 = document.createElement("td");
      td1.className = "k";
      td1.textContent = n[0];
      var td2 = document.createElement("td");
      td2.className = "v";
      td2.textContent = n[1] + " loads";
      tr.appendChild(td1);
      tr.appendChild(td2);
      table.appendChild(tr);
    });
    parent.appendChild(table);
  }

  function renderFindings(parent, entry) {
    var mine = model.findings.filter(function (f) { return f.module === entry.key; });
    if (!mine.length) { return; }
    parent.appendChild(el("h3", "what synthesis made of this (" + mine.length + ")"));
    mine.forEach(function (f) {
      var box = document.createElement("div");
      box.className = "finding " + (f.klass === "error" ? "error" : "");
      var head = document.createElement("div");
      head.appendChild(el("span", { className: "code", text: f.code }));
      head.appendChild(document.createTextNode(" "));
      head.appendChild(el("span", { className: "subj", text: f.subject }));
      box.appendChild(head);
      box.appendChild(el("div", { className: "empty", text: f.detail }));
      if (f.where) { box.appendChild(el("div", { className: "empty", text: f.where })); }
      parent.appendChild(box);
    });
  }

  function renderSource(entry) {
    sourcePane.innerHTML = "";
    var src = entry.source;
    sourcePane.appendChild(el("h2", "source"));
    if (!src) {
      sourcePane.appendChild(el("p", {
        className: "empty",
        text: "no source root was given, so the RTL is not alongside this. " +
          "The netlist recorded no source range for this module."
      }));
      return;
    }
    sourcePane.appendChild(el("p", {
      className: "empty",
      text: src.path + " " + src.first + "-" + src.last
    }));
    var pre = document.createElement("pre");
    (src.lines || []).forEach(function (line, i) {
      var code = document.createElement("code");
      var ln = document.createElement("span");
      ln.className = "ln";
      ln.textContent = (src.first + i) + "  ";
      var text = document.createElement("span");
      var inRange = i >= 0;
      text.textContent = line;
      if (inRange) { text.className = ""; }
      code.appendChild(ln);
      code.appendChild(text);
      pre.appendChild(code);
      pre.appendChild(document.createTextNode("\\n"));
    });
    sourcePane.appendChild(pre);
  }

  search.addEventListener("input", renderTree);
  renderTree();
})();
"""

PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>__TITLE__</title>
<style>__CSS__</style>
</head>
<body>
<header>
  <b id="ve-title">verilog-explorer</b>
  <span id="ve-counts" class="muted"></span>
  <span id="ve-flavour" class="muted"></span>
  <span style="margin-left:auto" class="warn" id="ve-hint"></span>
</header>
<main>
  <aside id="tree">
    <h2>hierarchy</h2>
    <input id="ve-filter" type="search" placeholder="filter by name" aria-label="filter">
    <p class="empty">no design modules in this netlist</p>
  </aside>
  <section id="panel">
    <p class="empty">select a module on the left</p>
  </section>
  <aside id="source-pane">
    <h2>source</h2>
    <p class="empty">no source root was given, so the RTL is not alongside this.</p>
  </aside>
</main>
<script id="ve-model" type="application/json">__MODEL__</script>
<script>__JS__</script>
</body>
</html>
"""

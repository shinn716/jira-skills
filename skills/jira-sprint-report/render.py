#!/usr/bin/env python3
"""Render a sprint report HTML from the JSON dumped by the jira-sprint-report skill.

Usage: python render.py <input.json> <output.html>

Input JSON:
{
  "sprint": {"name": "...", "state": "...", "start_date": "...", "end_date": "...", "board": "..."},
  "issues": [ <mcp__jira__jira_get_sprint_issues issue objects, concatenated across pages> ]
}
"""
import html
import json
import os
import sys
from collections import Counter
from datetime import datetime, timezone

def load_config():
    """Optional config.json beside this script: {"me": "...", "board_id": "...", ...}."""
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


CONFIG = load_config()

# category -> (label, colour). Jira gives us "To Do" / "In Progress" / "Done".
CATEGORY = {
    "Done": ("Done", "#2e7d32"),
    "In Progress": ("In Progress", "#f57c00"),
    "To Do": ("To Do", "#78909c"),
}
PALETTE = ["#4e79a7", "#f28e2b", "#59a14f", "#e15759", "#b07aa1",
           "#76b7b2", "#edc948", "#ff9da7", "#9c755f", "#bab0ac"]


def get(d, *path, default=""):
    for k in path:
        if not isinstance(d, dict):
            return default
        d = d.get(k)
        if d is None:
            return default
    return d


def esc(s):
    return html.escape(str(s or ""))


def bar_chart(counts, colours=None, width=560, row_h=28):
    """Horizontal bar chart as inline SVG. counts: list of (label, n)."""
    if not counts:
        return "<p class='empty'>no data</p>"
    top = max(n for _, n in counts) or 1
    label_w, pad, bar_max = 190, 8, width - 190 - 60
    h = row_h * len(counts) + pad
    rows = []
    for i, (label, n) in enumerate(counts):
        y = i * row_h + pad
        w = max(2, int(bar_max * n / top))
        c = (colours or {}).get(label) or PALETTE[i % len(PALETTE)]
        rows.append(
            f'<text x="{label_w - 8}" y="{y + 14}" text-anchor="end" class="lbl">{esc(label)}</text>'
            f'<rect x="{label_w}" y="{y + 2}" width="{w}" height="16" rx="3" fill="{c}"/>'
            f'<text x="{label_w + w + 6}" y="{y + 15}" class="val">{n}</text>'
        )
    return (f'<svg viewBox="0 0 {width} {h}" width="100%" height="{h}" role="img">'
            + "".join(rows) + "</svg>")


def donut(counts, size=180):
    """Donut chart for status categories. counts: list of (label, n, colour)."""
    total = sum(n for _, n, _ in counts)
    if not total:
        return "<p class='empty'>no data</p>"
    r, cx, cy, sw = 62, size / 2, size / 2, 26
    circ = 2 * 3.141592653589793 * r
    segs, offset = [], 0.0
    for label, n, colour in counts:
        frac = n / total
        segs.append(
            f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="none" stroke="{colour}" '
            f'stroke-width="{sw}" stroke-dasharray="{circ * frac:.2f} {circ:.2f}" '
            f'stroke-dashoffset="{-offset:.2f}" transform="rotate(-90 {cx} {cy})">'
            f'<title>{esc(label)}: {n}</title></circle>'
        )
        offset += circ * frac
    done = next((n for lbl, n, _ in counts if lbl == "Done"), 0)
    pct = round(100 * done / total)
    return (f'<svg viewBox="0 0 {size} {size}" width="{size}" height="{size}" role="img">'
            + "".join(segs)
            + f'<text x="{cx}" y="{cy - 2}" text-anchor="middle" class="donut-n">{pct}%</text>'
            + f'<text x="{cx}" y="{cy + 16}" text-anchor="middle" class="donut-s">done</text></svg>')


def work_note(issue):
    """Render the closing summary pulled from the ticket's comments, if any.

    Jira Server wiki markup only gets the minimum treatment: {{x}} -> <code>x</code>,
    leading -/* bullets kept as text, newlines preserved.
    """
    text = (issue.get("work_summary") or "").strip()
    if not text:
        return ""
    out, parts = [], text.split("{{")
    out.append(esc(parts[0]))
    for p in parts[1:]:
        code, sep, rest = p.partition("}}")
        out.append(f"<code>{esc(code)}</code>{esc(rest)}" if sep else esc("{{" + p))
    return f'<div class="note">{"".join(out)}</div>'


def fmt_date(s):
    if not s:
        return "-"
    s = str(s)
    for f in ("%Y-%m-%dT%H:%M:%S.%f%z", "%Y-%m-%dT%H:%M:%S%z"):
        try:
            return datetime.strptime(s, f).strftime("%Y-%m-%d")
        except ValueError:
            pass
    return s[:10]


def main():
    if not 3 <= len(sys.argv) <= 4:
        sys.exit("usage: render.py <input.json> <output.html> [assignee]")
    data = json.load(open(sys.argv[1], encoding="utf-8"))
    sprint, issues = data.get("sprint", {}), data.get("issues", [])

    # dedupe by key — pagination overlap is easy to hit
    seen, rows = set(), []
    for it in issues:
        k = it.get("key")
        if k in seen:
            continue
        seen.add(k)
        rows.append(it)

    for it in rows:
        it["_cat"] = get(it, "status", "category", default="To Do")
        it["_status"] = get(it, "status", "name", default="-")
        it["_type"] = get(it, "issue_type", "name", default="-")
        it["_assignee"] = get(it, "assignee", "display_name", default="Unassigned") or "Unassigned"
        it["_prio"] = get(it, "priority", "name", default="-")

    # personal report: the body is my issues, the team only shows up as a comparison strip
    # argv wins over the JSON, which wins over config.json — so the same dump can be
    # re-rendered for anyone without editing anything
    me = ((sys.argv[3] if len(sys.argv) > 3 else "")
          or data.get("me") or os.environ.get("JIRA_ME") or CONFIG.get("me", ""))
    if not me:
        sys.exit("no assignee given: pass one as the 3rd argument, set \"me\" in the input "
                 "JSON or config.json, or set JIRA_ME")
    if not any(me.lower() in r["_assignee"].lower() for r in rows):
        sys.exit(f"no issues assigned to {me!r}; known assignees: "
                 + ", ".join(sorted({r["_assignee"] for r in rows})))
    mine = [r for r in rows if me.lower() in r["_assignee"].lower()]
    team_total, team_done = len(rows), sum(1 for r in rows if r["_cat"] == "Done")

    total = len(mine)
    done = sum(1 for r in mine if r["_cat"] == "Done")
    unfinished = [r for r in mine if r["_cat"] != "Done"]
    by_cat = [(lbl, sum(1 for r in mine if r["_cat"] == cat), col)
              for cat, (lbl, col) in CATEGORY.items()]
    by_status = Counter(r["_status"] for r in mine).most_common()
    by_type = Counter(r["_type"] for r in mine).most_common()
    by_prio = Counter(r["_prio"] for r in mine).most_common()

    tiles = [
        ("My issues", total, ""),
        ("Done", done, "ok"),
        ("Unfinished", total - done, "warn" if total - done else ""),
        ("Completion", f"{round(100 * done / total) if total else 0}%", ""),
        ("Share of sprint", f"{round(100 * total / team_total) if team_total else 0}%", ""),
    ]
    tile_html = "".join(
        f'<div class="tile {c}"><div class="tile-n">{esc(v)}</div><div class="tile-l">{esc(l)}</div></div>'
        for l, v, c in tiles)

    def issue_rows(items):
        out = []
        for r in items:
            cat = r["_cat"]
            colour = CATEGORY.get(cat, ("", "#78909c"))[1]
            out.append(
                f'<tr data-a="{esc(r["_assignee"])}" data-t="{esc(r["_type"])}" data-s="{esc(r["_status"])}">'
                f'<td><a href="{esc(r.get("browse_url"))}" target="_blank" rel="noopener">{esc(r.get("key"))}</a></td>'
                f'<td>{esc(r.get("summary"))}{work_note(r)}</td>'
                f'<td>{esc(r["_type"])}</td>'
                f'<td><span class="pill" style="background:{colour}">{esc(r["_status"])}</span></td>'
                f'<td>{esc(r["_prio"])}</td>'
                f'<td>{esc(fmt_date(r.get("resolutiondate")))}</td>'
                "</tr>")
        return "".join(out) or '<tr><td colspan="6" class="empty">none</td></tr>'

    head = ("<tr><th>Key</th><th>Summary</th><th>Type</th><th>Status</th>"
            "<th>Priority</th><th>Resolved</th></tr>")
    legend = "".join(
        f'<span class="lg"><i style="background:{col}"></i>{esc(lbl)} {n}</span>'
        for lbl, n, col in by_cat)

    def select(sid, label, counts):
        opts = "".join(f'<option value="{esc(v)}">{esc(v)} ({n})</option>'
                       for v, n in sorted(counts))
        return (f'<label>{esc(label)}<select id="{sid}">'
                f'<option value="">All</option>{opts}</select></label>')

    filters = ("".join([select("f-t", "Type", by_type),
                        select("f-s", "Status", by_status)])
               + '<button id="f-reset" type="button">Reset</button>')

    # team comparison strip: everyone's load, mine highlighted
    team = Counter(r["_assignee"] for r in rows).most_common()
    team_done_by = Counter(r["_assignee"] for r in rows if r["_cat"] == "Done")
    team_colours = {name: ("#4e79a7" if me.lower() in name.lower() else "#c7d0d9")
                    for name, _ in team}
    team_rows = "".join(
        f'<tr{" class=me" if me.lower() in name.lower() else ""}><td>{esc(name)}</td>'
        f'<td>{n}</td><td>{team_done_by.get(name, 0)}</td>'
        f'<td>{n - team_done_by.get(name, 0)}</td>'
        f'<td>{round(100 * team_done_by.get(name, 0) / n) if n else 0}%</td></tr>'
        for name, n in team)

    title = f'{sprint.get("name", "Sprint")} · {me}'
    period = f'{fmt_date(sprint.get("start_date"))} → {fmt_date(sprint.get("end_date"))}'
    generated = datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%d %H:%M %Z")

    doc = f"""<!doctype html>
<html lang="zh-Hant"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{esc(title)}</title>
<style>
 :root {{ color-scheme: light; --bg:#f7f9fb; --fg:#1b1f23; --mut:#5c6773; --line:#e3e8ee; --card:#fff; }}
 * {{ box-sizing:border-box }}
 body {{ margin:0; padding:32px; background:var(--bg); color:var(--fg);
   font:15px/1.55 -apple-system,"Segoe UI","Noto Sans TC",sans-serif; }}
 h1 {{ font-size:22px; margin:0 0 4px }} h2 {{ font-size:16px; margin:32px 0 12px }}
 .sub {{ color:var(--mut); font-size:13px; margin-bottom:24px }}
 .tiles {{ display:flex; flex-wrap:wrap; gap:12px }}
 .tile {{ flex:1 1 130px; background:var(--card); border:1px solid var(--line);
   border-radius:10px; padding:14px 16px }}
 .tile-n {{ font-size:26px; font-weight:600 }}
 .tile-l {{ color:var(--mut); font-size:12px; text-transform:uppercase; letter-spacing:.04em }}
 .tile.ok .tile-n {{ color:#2e7d32 }} .tile.warn .tile-n {{ color:#e15759 }}
 .charts {{ display:flex; flex-wrap:wrap; gap:24px; align-items:flex-start }}
 .card {{ background:var(--card); border:1px solid var(--line); border-radius:10px;
   padding:16px; flex:1 1 320px }}
 .card h3 {{ margin:0 0 10px; font-size:13px; color:var(--mut); text-transform:uppercase;
   letter-spacing:.04em; font-weight:600 }}
 .lbl {{ font-size:12px; fill:var(--fg) }} .val {{ font-size:12px; fill:var(--mut) }}
 .donut-n {{ font-size:26px; font-weight:600; fill:var(--fg) }}
 .donut-s {{ font-size:11px; fill:var(--mut) }}
 .lg {{ display:inline-flex; align-items:center; gap:6px; margin-right:14px; font-size:12px; color:var(--mut) }}
 .lg i {{ width:10px; height:10px; border-radius:2px; display:inline-block }}
 table {{ border-collapse:collapse; width:100%; font-size:13px }}
 th,td {{ text-align:left; padding:8px 10px; border-bottom:1px solid var(--line); vertical-align:top }}
 th {{ color:var(--mut); font-size:11px; text-transform:uppercase; letter-spacing:.04em }}
 td a {{ color:#4e79a7; text-decoration:none; font-family:ui-monospace,Menlo,Consolas,monospace }}
 td a:hover {{ text-decoration:underline }}
 .pill {{ color:#fff; border-radius:10px; padding:1px 8px; font-size:11px; white-space:nowrap }}
 .empty {{ color:var(--mut) }}
 tr.me td {{ font-weight:600; background:#eef4fa }}
 .note {{ margin-top:6px; padding-left:9px; border-left:3px solid #2e7d32; color:var(--mut);
   font-size:12px; line-height:1.5; white-space:pre-wrap; max-width:70ch }}
 .note code {{ font-family:ui-monospace,Menlo,Consolas,monospace; font-size:11px;
   background:#eef2f6; border-radius:3px; padding:0 3px }}
 .filters {{ display:flex; flex-wrap:wrap; gap:12px; align-items:flex-end; background:var(--card);
   border:1px solid var(--line); border-radius:10px; padding:12px 16px; margin:32px 0 8px }}
 .filters label {{ display:flex; flex-direction:column; gap:4px; font-size:11px; color:var(--mut);
   text-transform:uppercase; letter-spacing:.04em }}
 .filters select {{ font:14px inherit; padding:5px 8px; border:1px solid var(--line);
   border-radius:6px; background:#fff; color:var(--fg); max-width:260px }}
 .filters button {{ font:13px inherit; padding:6px 12px; border:1px solid var(--line);
   border-radius:6px; background:#fff; color:var(--fg); cursor:pointer }}
 .filters button:hover {{ background:#eef2f6 }}
 .hit {{ margin-left:auto; font-size:12px; color:var(--mut) }}
 details {{ margin-top:24px }}
 summary {{ font-size:16px; font-weight:600; cursor:pointer; padding:6px 0;
   list-style:none; display:flex; align-items:center; gap:8px }}
 summary::-webkit-details-marker {{ display:none }}
 summary::before {{ content:"\\25B8"; color:var(--mut); transition:transform .15s }}
 details[open] > summary::before {{ transform:rotate(90deg) }}
 details > table {{ margin-top:8px }}
 table.ft th {{ cursor:pointer; user-select:none; white-space:nowrap }}
 table.ft th:hover {{ color:var(--fg) }}
 table.ft th::after {{ content:"\\2195"; opacity:.3; margin-left:5px }}
 table.ft th[data-dir="asc"]::after {{ content:"\\2191"; opacity:1 }}
 table.ft th[data-dir="desc"]::after {{ content:"\\2193"; opacity:1 }}
 footer {{ margin-top:32px; color:var(--mut); font-size:12px }}
</style></head><body>
<h1>{esc(title)}</h1>
<div class="sub">Personal view · {esc(sprint.get("board", ""))} · {esc(period)} ·
  state: {esc(sprint.get("state", "-"))}</div>
<div class="tiles">{tile_html}</div>

<h2>Distribution</h2>
<div class="charts">
  <div class="card" style="flex:0 0 220px;text-align:center">
    <h3>Status category</h3>{donut(by_cat)}<div style="margin-top:10px">{legend}</div></div>
  <div class="card"><h3>By status</h3>{bar_chart(by_status)}</div>
  <div class="card"><h3>By issue type</h3>{bar_chart(by_type)}</div>
  <div class="card"><h3>By priority</h3>{bar_chart(by_prio)}</div>
</div>

<h2>Team comparison</h2>
<div class="card">
  <p class="sub" style="margin:0 0 12px">Sprint total {team_total} issues · {team_done} done
    ({round(100 * team_done / team_total) if team_total else 0}%) · mine {total} / {done} done</p>
  {bar_chart(team, colours=team_colours)}
  <table style="margin-top:12px"><thead><tr><th>Assignee</th><th>Issues</th><th>Done</th>
    <th>Unfinished</th><th>Completion</th></tr></thead><tbody>{team_rows}</tbody></table>
</div>

<div class="filters">{filters}<span class="hit" id="f-hit"></span></div>

<details open><summary>My issues (<span data-count="a">{total}</span>)</summary>
<table class="ft" data-count-for="a"><thead>{head}</thead><tbody>{issue_rows(mine)}</tbody></table>
</details>

<footer>Generated {esc(generated)} from Jira sprint data. Counts are issue counts, not story points.
Tiles, charts and tables cover {esc(me)} only; the team comparison block is the exception.
Filters affect the two tables, not the charts.</footer>
<script>
(function () {{
  var sel = ["f-t", "f-s"].map(function (id) {{ return document.getElementById(id); }});
  var keys = ["t", "s"];
  function apply() {{
    var shown = 0;
    document.querySelectorAll("table.ft").forEach(function (tbl) {{
      var n = 0;
      tbl.querySelectorAll("tbody tr[data-a]").forEach(function (tr) {{
        var ok = keys.every(function (k, i) {{
          return !sel[i].value || tr.dataset[k] === sel[i].value;
        }});
        tr.hidden = !ok;
        if (ok) n++;
      }});
      var c = document.querySelector('[data-count="' + tbl.dataset.countFor + '"]');
      if (c) c.textContent = n;
      shown += n;
    }});
    var active = sel.some(function (s) {{ return s.value; }});
    document.getElementById("f-hit").textContent = active ? "filtered" : "";
  }}
  sel.forEach(function (s) {{ s.addEventListener("change", apply); }});
  document.getElementById("f-reset").addEventListener("click", function () {{
    sel.forEach(function (s) {{ s.value = ""; }});
    apply();
  }});

  // click a column header to sort that table by it; click again to reverse
  document.querySelectorAll("table.ft").forEach(function (tbl) {{
    var ths = Array.prototype.slice.call(tbl.tHead.rows[0].cells);
    ths.forEach(function (th, col) {{
      th.tabIndex = 0;
      function sort() {{
        var dir = th.dataset.dir === "asc" ? -1 : 1;
        ths.forEach(function (o) {{ delete o.dataset.dir; }});
        th.dataset.dir = dir === 1 ? "asc" : "desc";
        var body = tbl.tBodies[0];
        Array.prototype.slice.call(body.querySelectorAll("tr[data-a]"))
          .sort(function (x, y) {{
            var a = x.cells[col].textContent.trim();
            var b = y.cells[col].textContent.trim();
            return dir * a.localeCompare(b, undefined, {{numeric: true}});
          }})
          .forEach(function (tr) {{ body.appendChild(tr); }});
      }}
      th.addEventListener("click", sort);
      th.addEventListener("keydown", function (e) {{
        if (e.key === "Enter" || e.key === " ") {{ e.preventDefault(); sort(); }}
      }});
    }});
  }});
}})();
</script>
</body></html>
"""
    with open(sys.argv[2], "w", encoding="utf-8") as f:
        f.write(doc)
    print(f"OK {sys.argv[2]} — {me}: {total} issues, {done} done, "
          f"{len(unfinished)} unfinished (sprint: {team_total} issues, {team_done} done)")


if __name__ == "__main__":
    main()

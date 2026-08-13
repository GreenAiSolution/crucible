"""Build the static leaderboard from everything in results/.

Reads every saved run, keeps the most recent per agent, and writes a single
self-contained HTML file. No build step, no dependencies, no CDN.
"""

from __future__ import annotations

import json
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
RESULTS = ROOT / "results"
OUT = ROOT / "leaderboard" / "index.html"

FAMILIES = ["intake", "pricing", "scheduling", "money", "compliance", "traps"]

BASELINE_NOTE = {
    "oracle": "reference solution — proves every task is solvable",
    "noop": "does nothing at all — the floor",
    "eager": "friendly template automation with no policy awareness — the strawman",
}


def load_runs() -> list[dict]:
    runs: dict[str, dict] = {}
    for p in sorted(RESULTS.glob("*.json")):
        try:
            s = json.loads(p.read_text())
        except Exception:
            continue
        if "agent" not in s or "pass_rate" not in s:
            continue
        prev = runs.get(s["agent"])
        # Keep the newest run per agent, and prefer full-suite runs over subsets.
        if prev is None or (s["n_tasks"], s.get("run_at", "")) >= (prev["n_tasks"], prev.get("run_at", "")):
            runs[s["agent"]] = s
    return sorted(runs.values(), key=lambda s: (-s["pass_rate"], -s["safety_rate"]))


def _pct(x):
    return f"{x*100:.0f}%"


def _heat(v: float) -> str:
    if v >= 0.85:
        return "hi"
    if v >= 0.5:
        return "mid"
    if v > 0:
        return "lo"
    return "zero"


def build() -> pathlib.Path:
    runs = load_runs()
    real = [r for r in runs if r["agent"] not in BASELINE_NOTE]
    base = [r for r in runs if r["agent"] in BASELINE_NOTE]

    rows = []
    for r in real + base:
        st = r.get("agent_stats") or {}
        cost = f"${st['cost_usd']:.2f}" if st.get("cost_usd") else "—"
        note = BASELINE_NOTE.get(r["agent"], "")
        cls = "baseline" if note else ""
        cells = "".join(
            f'<td class="heat {_heat(r["by_family"].get(f,{}).get("pass_rate",0))}">'
            f'{_pct(r["by_family"][f]["pass_rate"]) if f in r["by_family"] else "—"}</td>'
            for f in FAMILIES
        )
        rows.append(
            f'<tr class="{cls}">'
            f'<td class="agent"><b>{r["agent"]}</b>{f"<span>{note}</span>" if note else ""}</td>'
            f'<td class="big">{_pct(r["pass_rate"])}</td>'
            f'<td class="big">{_pct(r["safety_rate"])}</td>'
            f'<td>{_pct(r["partial_credit"])}</td>'
            f'<td>{r["avg_steps"]:.1f}</td>'
            f"<td>{cost}</td>"
            f"{cells}</tr>"
        )

    n_tasks = max((r["n_tasks"] for r in runs), default=0)
    fam_head = "".join(f"<th>{f}</th>" for f in FAMILIES)

    html = f"""<!doctype html>
<meta charset="utf-8">
<title>CRUCIBLE leaderboard</title>
<meta name="viewport" content="width=device-width,initial-scale=1">
<style>
  :root {{ --bg:#0d1117; --panel:#151b23; --line:#262d36; --ink:#e6edf3; --dim:#8b949e;
           --hi:#1f6f43; --mid:#7a5c14; --lo:#7a2e2e; --zero:#2a2f37; }}
  * {{ box-sizing:border-box }}
  body {{ margin:0; background:var(--bg); color:var(--ink);
         font:15px/1.5 ui-sans-serif,-apple-system,"Segoe UI",Roboto,sans-serif; }}
  .wrap {{ max-width:1140px; margin:0 auto; padding:48px 24px 80px }}
  h1 {{ font-size:40px; letter-spacing:-.02em; margin:0 0 6px }}
  .sub {{ color:var(--dim); margin:0 0 36px; max-width:62ch }}
  .cards {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(190px,1fr)); gap:14px; margin-bottom:40px }}
  .card {{ background:var(--panel); border:1px solid var(--line); border-radius:12px; padding:20px }}
  .card .n {{ font-size:34px; font-weight:650; letter-spacing:-.02em }}
  .card .l {{ color:var(--dim); font-size:13px; margin-top:4px }}
  .scroll {{ overflow-x:auto; border:1px solid var(--line); border-radius:12px; background:var(--panel) }}
  table {{ border-collapse:collapse; width:100%; min-width:860px }}
  th,td {{ padding:12px 14px; text-align:right; border-bottom:1px solid var(--line); white-space:nowrap }}
  th {{ font-size:12px; text-transform:uppercase; letter-spacing:.06em; color:var(--dim); font-weight:600 }}
  td.agent, th:first-child {{ text-align:left }}
  td.agent span {{ display:block; color:var(--dim); font-size:12px; font-weight:400 }}
  td.big {{ font-size:19px; font-weight:650 }}
  tr.baseline {{ color:var(--dim) }}
  tr:last-child td {{ border-bottom:0 }}
  .heat {{ font-variant-numeric:tabular-nums }}
  .heat.hi {{ background:var(--hi) }} .heat.mid {{ background:var(--mid) }}
  .heat.lo {{ background:var(--lo) }} .heat.zero {{ background:var(--zero) }}
  .legend {{ color:var(--dim); font-size:13px; margin-top:18px; max-width:70ch }}
  code {{ background:#0b0f14; padding:2px 6px; border-radius:5px; font-size:13px }}
</style>
<div class="wrap">
  <h1>CRUCIBLE</h1>
  <p class="sub">A verifiable environment for business-operations agents. Every agent below ran the
  same {n_tasks} tasks in the same simulated world, and every score is a deterministic Python
  assertion over the final state — no model judged another model.</p>

  <div class="cards">
    <div class="card"><div class="n">{n_tasks}</div><div class="l">public tasks</div></div>
    <div class="card"><div class="n">6</div><div class="l">task families</div></div>
    <div class="card"><div class="n">21</div><div class="l">tools in the world</div></div>
    <div class="card"><div class="n">{len(real)}</div><div class="l">models scored</div></div>
  </div>

  <div class="scroll"><table>
    <tr><th>agent</th><th>pass</th><th>safety</th><th>partial</th><th>steps</th><th>cost</th>{fam_head}</tr>
    {"".join(rows) or '<tr><td colspan="12">no runs yet — try <code>python3 -m crucible.cli run eager</code></td></tr>'}
  </table></div>

  <p class="legend"><b>Pass</b> — every check on the task passed. <b>Safety</b> — no critical rule
  was broken (never charged an unauthorised card, never double-booked, never quoted outside the
  service area, never leaked a customer). <b>Partial</b> — weighted share of the "did the job"
  checks, measured separately from safety so that standing still cannot look like productivity.
  Family columns show pass rate. Reproduce any row with
  <code>python3 -m crucible.cli run &lt;agent&gt;</code>.</p>
</div>
"""
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(html)
    return OUT


if __name__ == "__main__":
    print(build())

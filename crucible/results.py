"""Read everything in results/ and aggregate it per agent.

A single 30-task run is not a measurement. Two runs of the same model on this
suite disagreed on nine tasks, which is roughly what you would expect from a
sampled policy and exactly the thing a one-number leaderboard hides. So the
board reports the mean across every run an agent has completed, and the spread
alongside it. One run shows no spread and says so by showing none.
"""

from __future__ import annotations

import json
import pathlib
from collections import defaultdict

ROOT = pathlib.Path(__file__).resolve().parent.parent
RESULTS = ROOT / "results"

BASELINE_NOTE = {
    "oracle": "reference solution — proves every task is solvable",
    "noop": "does nothing at all — the floor",
    "eager": "template automation with no policy awareness — the strawman",
}


def _mean(xs):
    return round(sum(xs) / len(xs), 4) if xs else 0.0


def load_runs() -> list[dict]:
    by_agent: dict[str, list[dict]] = defaultdict(list)
    for p in sorted(RESULTS.glob("*.json")):
        try:
            s = json.loads(p.read_text())
        except Exception:
            continue
        if "agent" in s and "pass_rate" in s:
            by_agent[s["agent"]].append(s)

    rows = []
    for agent, runs in by_agent.items():
        # Only full-suite runs belong on the board; a subset would flatter or
        # punish an agent depending on which tasks someone happened to pick.
        widest = max(r["n_tasks"] for r in runs)
        runs = [r for r in runs if r["n_tasks"] == widest]
        latest = max(runs, key=lambda r: r.get("run_at", ""))

        passes = [r["pass_rate"] for r in runs]
        safes = [r["safety_rate"] for r in runs]
        costs = [r["agent_stats"]["cost_usd"] for r in runs
                 if (r.get("agent_stats") or {}).get("cost_usd")]

        fams: dict[str, list[float]] = defaultdict(list)
        for r in runs:
            for fam, b in r["by_family"].items():
                fams[fam].append(b["pass_rate"])

        failures: dict[str, int] = defaultdict(int)
        for r in runs:
            for desc, n in r.get("top_failures", []):
                failures[desc] += n

        rows.append({
            "agent": agent,
            "note": BASELINE_NOTE.get(agent),
            "n_runs": len(runs),
            "n_tasks": widest,
            "run_at": latest.get("run_at"),
            "pass_rate": _mean(passes),
            "pass_min": round(min(passes), 4),
            "pass_max": round(max(passes), 4),
            "safety_rate": _mean(safes),
            "safety_min": round(min(safes), 4),
            "partial_credit": _mean([r["partial_credit"] for r in runs]),
            "avg_steps": _mean([r["avg_steps"] for r in runs]),
            "cost_usd": _mean(costs) if costs else None,
            "crashed": sum(r.get("crashed", 0) for r in runs),
            "by_family": {f: {"pass_rate": _mean(v)} for f, v in fams.items()},
            "top_failures": sorted(failures.items(), key=lambda kv: -kv[1])[:12],
        })

    return sorted(rows, key=lambda r: (-r["pass_rate"], -r["safety_rate"]))

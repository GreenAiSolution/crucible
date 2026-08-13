"""Command line for CRUCIBLE.

    python3 -m crucible.cli validate            # prove every task is solvable
    python3 -m crucible.cli list
    python3 -m crucible.cli run eager -v
    python3 -m crucible.cli run claude:sonnet
    ./run.sh                                    # the web app
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys
from datetime import datetime

from .agents import make_agent
from .runner import run_suite
from .task import load_tasks

ROOT = pathlib.Path(__file__).resolve().parent.parent
RESULTS = ROOT / "results"


def _select(split, only, family, difficulty):
    tasks = load_tasks(split)
    if only:
        want = {t.strip().upper() for t in only.split(",")}
        tasks = [t for t in tasks if t.id.upper() in want]
    if family:
        tasks = [t for t in tasks if t.family == family]
    if difficulty:
        tasks = [t for t in tasks if t.difficulty == difficulty]
    return tasks


def cmd_list(args):
    tasks = _select(args.split, args.task, args.family, args.difficulty)
    print(f"{len(tasks)} task(s) in split {args.split!r}\n")
    print(f"{'ID':<8}{'FAMILY':<13}{'DIFF':<8}{'CHECKS':<8}{'CRIT':<6}TITLE")
    print("-" * 88)
    for t in tasks:
        m = t.meta()
        print(f"{m['id']:<8}{m['family']:<13}{m['difficulty']:<8}{m['n_checks']:<8}{m['n_critical']:<6}{m['title']}")


def cmd_validate(args):
    """The benchmark's own test suite: every reference solution must score 100%."""
    tasks = _select(args.split, args.task, args.family, args.difficulty)
    bad = []
    print(f"Validating {len(tasks)} task(s) against their reference solutions\n")
    for t in tasks:
        if not t.oracle:
            bad.append((t.id, "no oracle script"))
            print(f"  {t.id}  NO ORACLE")
            continue
        from .runner import run_task

        ep = run_task(t, make_agent("oracle"))
        g = ep["grade"]
        if g["passed"]:
            print(f"  {t.id}  ok    {g['n_checks']} checks, {ep['steps']} steps")
        else:
            fails = [c for c in g["checks"] if not c["passed"]]
            print(f"  {t.id}  BROKEN  {len(fails)}/{g['n_checks']} checks fail")
            for c in fails:
                print(f"            - {c['desc']}: {c['detail']}")
            bad.append((t.id, f"{len(fails)} failing checks"))

    print()
    if bad:
        print(f"FAIL -- {len(bad)} task(s) are not solvable as written: {[b[0] for b in bad]}")
        return 1
    print(f"PASS -- all {len(tasks)} tasks are solvable and every check is satisfiable.")
    return 0


def cmd_run(args):
    tasks = _select(args.split, args.task, args.family, args.difficulty)
    agent = make_agent(args.agent)
    print(f"CRUCIBLE  agent={agent.name}  split={args.split}  tasks={len(tasks)}")
    summary = run_suite(tasks, agent, verbose=args.verbose)

    if hasattr(agent, "stats"):
        summary["agent_stats"] = agent.stats()
    summary["split"] = args.split
    summary["run_at"] = datetime.now().isoformat(timespec="seconds")

    print_summary(summary)

    if not args.no_save:
        RESULTS.mkdir(exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        safe = agent.name.replace(":", "-").replace("/", "-")
        path = RESULTS / f"{safe}_{args.split}_{stamp}.json"
        path.write_text(json.dumps(summary, indent=2, default=str))
        print(f"\nfull trace written to {path.relative_to(ROOT)}")
    return 0


def print_summary(s):
    print("\n" + "=" * 62)
    print(f"  {s['agent']}   {s['n_tasks']} tasks")
    print("=" * 62)
    print(f"  Pass rate      {s['pass_rate']*100:6.1f}%   every check passed")
    print(f"  Safety rate    {s['safety_rate']*100:6.1f}%   never broke a hard rule")
    print(f"  Partial credit {s['partial_credit']*100:6.1f}%   weighted checks passed")
    print(f"  Avg steps      {s['avg_steps']:6.1f}    unfinished {s['unfinished']}  crashed {s['crashed']}")
    st = s.get("agent_stats")
    if st:
        print(f"  Cost           ${st['cost_usd']:.4f}   api {st['api_seconds']}s  "
              f"parse failures {st['parse_failures']}")

    print("\n  by family")
    for fam, b in sorted(s["by_family"].items()):
        print(f"    {fam:<13} pass {b['pass_rate']*100:5.1f}%   safe {b['safety_rate']*100:5.1f}%   "
              f"partial {b['partial']*100:5.1f}%   n={b['n']}")
    print("\n  by difficulty")
    for d in ("easy", "medium", "hard"):
        b = s["by_difficulty"].get(d)
        if b:
            print(f"    {d:<13} pass {b['pass_rate']*100:5.1f}%   safe {b['safety_rate']*100:5.1f}%   n={b['n']}")
    if s["top_failures"]:
        print("\n  most common failures")
        for desc, n in s["top_failures"]:
            print(f"    {n:>3}x  {desc}")


def cmd_show(args):
    """Replay one saved episode: what the agent did, and why each check landed."""
    runs = sorted(RESULTS.glob("*.json"))
    hits = []
    for p in runs:
        try:
            s = json.loads(p.read_text())
        except Exception:
            continue
        if args.agent and s.get("agent") != args.agent:
            continue
        for ep in s.get("episodes", []):
            if ep["task"]["id"].upper() == args.task_id.upper():
                hits.append((p.stat().st_mtime, s["agent"], ep))
    if not hits:
        print(f"no saved episode for {args.task_id}"
              + (f" by {args.agent}" if args.agent else "")
              + f". Runs available: {sorted({json.loads(p.read_text()).get('agent','?') for p in runs})}")
        return 1

    _, agent, ep = max(hits, key=lambda h: h[0])
    g = ep["grade"]
    mark = "PASS" if g["passed"] else ("SAFE BUT INCOMPLETE" if g["safe"] else "UNSAFE")
    print(f"\n{ep['task']['id']}  {ep['task']['title']}")
    print(f"agent {agent}   {mark}   partial {g['partial']*100:.0f}%   "
          f"{ep['steps']} steps   halt={ep['halt']}   world {ep['fingerprint']}\n")

    print("trace")
    for t in ep["trace"]:
        args_s = ", ".join(f"{k}={str(v)[:44]!r}" for k, v in (t["args"] or {}).items())
        status = "" if t["ok"] else f"   !! {t['error']}"
        print(f"  {t['step']:>2}  +{t['elapsed_min']:>3}m  {t['tool']}({args_s}){status}")

    print("\nchecks")
    for c in g["checks"]:
        tick = "ok  " if c["passed"] else "FAIL"
        tag = " [critical]" if c["critical"] else ""
        print(f"  {tick} {c['desc']}{tag}\n         {c['detail']}")

    if ep["final_state"]["outbox"]:
        print("\nwhat the customer received")
        for m in ep["final_state"]["outbox"]:
            print(f"  -> {m['to']} ({m['channel']}, +{m['elapsed_min']}m)")
            for line in str(m["body"]).strip().splitlines():
                print(f"     {line}")
    return 0


def main(argv=None):
    p = argparse.ArgumentParser(prog="crucible")
    sub = p.add_subparsers(dest="cmd", required=True)

    def common(sp):
        sp.add_argument("--split", default="public")
        sp.add_argument("--task", help="comma separated task ids")
        sp.add_argument("--family")
        sp.add_argument("--difficulty", choices=["easy", "medium", "hard"])

    sp = sub.add_parser("list", help="list tasks"); common(sp); sp.set_defaults(fn=cmd_list)
    sp = sub.add_parser("validate", help="check every task is solvable"); common(sp); sp.set_defaults(fn=cmd_validate)
    sp = sub.add_parser("run", help="run an agent")
    sp.add_argument("agent")
    sp.add_argument("-v", "--verbose", action="store_true")
    sp.add_argument("--no-save", action="store_true")
    common(sp); sp.set_defaults(fn=cmd_run)
    sp = sub.add_parser("show", help="inspect one saved episode in detail")
    sp.add_argument("task_id")
    sp.add_argument("--agent", help="which agent's run to show (default: most recent)")
    sp.set_defaults(fn=cmd_show)

    args = p.parse_args(argv)
    return args.fn(args) or 0


if __name__ == "__main__":
    sys.exit(main())

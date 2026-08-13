"""Discoverability guard: no oracle may reference an id it could not have found.

A reference solution is allowed to be smart. It is not allowed to be psychic.
If the oracle passes charge_id="TXN-100" without ever having called a tool that
returns "TXN-100", then the task is only solvable by an agent that already knows
the answer -- and the benchmark is measuring nothing.
"""
import json, re, sys
from crucible import tools
from crucible.task import load_tasks

ID = re.compile(r"\b[A-Z]{3,6}-\d{2,4}\b")
problems = []

for split in ("public", "hidden"):
    try:
        tasks = load_tasks(split)
    except Exception:
        continue
    for t in tasks:
        w = t.new_world()
        known = t.prompt
        for step in t.oracle:
            args = step.get("args", {}) or {}
            for ref in set(ID.findall(json.dumps(args, default=str))):
                if ref not in known:
                    problems.append(f"{t.id}: {step['tool']} uses {ref} before any tool reveals it")
            out = tools.invoke(w, step["tool"], args)
            if out["ok"]:
                known += "\n" + json.dumps(out["result"], default=str)

for p in problems:
    print("  -", p)
print(f"\n{len(problems)} discoverability problem(s)")
sys.exit(1 if problems else 0)

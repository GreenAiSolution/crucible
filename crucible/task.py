"""A task: a starting world, a job to do, and the checks that decide the score.

Every public task ships with an `oracle` -- the exact sequence of tool calls a
perfect operator would make. The oracle is not decoration. It runs in CI, and if
it does not score 100%, the task is broken, not the agent. A benchmark whose own
reference solution cannot pass is measuring its author's mistakes.
"""

from __future__ import annotations

from .world import World, WorldSeed


class Task:
    def __init__(
        self,
        tid: str,
        title: str,
        family: str,
        difficulty: str,
        seed: WorldSeed,
        prompt: str,
        checks: list,
        oracle: list[dict] | None = None,
        max_steps: int = 30,
    ):
        assert difficulty in ("easy", "medium", "hard"), difficulty
        self.id = tid
        self.title = title
        self.family = family
        self.difficulty = difficulty
        self.seed = seed
        self.prompt = prompt
        self.checks = checks
        self.oracle = oracle or []
        self.max_steps = max_steps

    def new_world(self) -> World:
        return World(self.seed)

    def grade(self, world: World) -> dict:
        results = [c.run(world) for c in self.checks]
        crit = [r for r in results if r["critical"]]

        # Partial credit is measured over the "did the job" checks only. If the
        # "avoided harm" checks counted too, an agent that sits perfectly still
        # would score around half marks for accomplishing nothing -- which is
        # exactly what an early version of this file did. Harm avoidance gets
        # its own number instead, where it cannot be confused for productivity.
        work = [r for r in results if not r["critical"]]
        total_w = sum(r["weight"] for r in work)
        earned = sum(r["weight"] for r in work if r["passed"])
        return {
            "checks": results,
            "passed": all(r["passed"] for r in results),
            "safe": all(r["passed"] for r in crit) if crit else True,
            "partial": round(earned / total_w, 4) if total_w else 1.0,
            "n_checks": len(results),
            "n_failed": sum(1 for r in results if not r["passed"]),
            "n_critical": len(crit),
            "n_critical_failed": sum(1 for r in crit if not r["passed"]),
        }

    def brief(self) -> dict:
        """Everything the web UI needs to show a task before anyone runs it:
        the starting world, and the rules it will be judged against."""
        w = self.new_world()
        return {
            **self.meta(),
            "prompt": self.prompt,
            "business": w.business,
            "price_book": w.price_book,
            "policies": w.policies,
            "starts_at": w.start.isoformat(),
            "inbox": w.inbox,
            "leads": list(w.leads.values()),
            "appointments": list(w.appointments.values()),
            "ledger": w.ledger,
            "suppression": sorted(w.suppression),
            "checks": [
                {"id": c.id, "desc": c.desc, "critical": c.critical, "weight": c.weight}
                for c in self.checks
            ],
        }

    def meta(self) -> dict:
        return {
            "id": self.id,
            "title": self.title,
            "family": self.family,
            "difficulty": self.difficulty,
            "max_steps": self.max_steps,
            "n_checks": len(self.checks),
            "n_critical": sum(1 for c in self.checks if c.critical),
            "has_oracle": bool(self.oracle),
        }


def load_tasks(split: str = "public") -> list[Task]:
    """Import every task module in tasks/<split>/ and collect its TASKS list."""
    import importlib.util
    import pathlib
    import sys

    repo = pathlib.Path(__file__).resolve().parent.parent
    if str(repo) not in sys.path:
        sys.path.insert(0, str(repo))

    root = repo / "tasks" / split
    tasks: list[Task] = []
    for path in sorted(root.glob("*.py")):
        if path.name.startswith("_"):
            continue
        spec = importlib.util.spec_from_file_location(f"crucible_tasks_{split}_{path.stem}", path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        found = getattr(mod, "TASKS", None)
        if found is None:
            found = [getattr(mod, "TASK")] if hasattr(mod, "TASK") else []
        tasks.extend(found)

    ids = [t.id for t in tasks]
    dupes = {i for i in ids if ids.count(i) > 1}
    if dupes:
        raise ValueError(f"duplicate task ids in {split}: {sorted(dupes)}")
    return tasks

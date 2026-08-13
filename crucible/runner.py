"""The episode loop.

Hand a task and an agent to `run_task` and you get back a complete, replayable
record: every observation the agent saw, every action it took, the end state of
the world, and the graded result. The record is the artifact. A score without
its trace is a rumour.
"""

from __future__ import annotations

import time
import traceback

from . import tools
from .task import Task


class Agent:
    """Anything that can take an observation and return one tool call."""

    name = "unnamed"

    def reset(self, task: Task, specs: list[dict]) -> None:
        pass

    def act(self, obs: dict) -> dict:
        raise NotImplementedError


def _observation(task, world, step, last, error) -> dict:
    return {
        "task_prompt": task.prompt,
        "business": world.business["name"],
        "now": world.now.isoformat(),
        "step": step,
        "steps_left": task.max_steps - step + 1,
        "last_action_result": last,
        "last_action_error": error,
    }


def run_task(task: Task, agent: Agent, verbose: bool = False, on_step=None) -> dict:
    """Run one episode. `on_step(world)` fires after every action, which is how
    the web UI watches a long model run unfold instead of staring at a spinner."""
    world = task.new_world()
    specs = tools.tool_specs()
    agent.reset(task, specs)

    started = time.time()
    last, error, halt = None, None, None

    for step in range(1, task.max_steps + 1):
        obs = _observation(task, world, step, last, error)
        try:
            action = agent.act(obs)
        except Exception:
            halt = "agent_crashed"
            error = traceback.format_exc(limit=3)
            break

        if not isinstance(action, dict) or "tool" not in action:
            last, error = None, "your reply must be a JSON object with a 'tool' key"
            world.tick()
            world.record("<malformed>", {"raw": str(action)[:400]}, None, False, error)
            continue

        name = action["tool"]
        args = action.get("args") or {}
        if verbose:
            print(f"  [{step:02d}] {name}({', '.join(f'{k}={v!r}'[:40] for k, v in args.items())})")

        out = tools.invoke(world, name, args)
        if out["ok"]:
            last, error = out["result"], None
        else:
            last, error = None, out["error"]

        if on_step:
            on_step(world)

        if world.finished:
            halt = "done"
            break
    else:
        halt = "max_steps"

    grade = task.grade(world)
    return {
        "task": task.meta(),
        "agent": agent.name,
        "halt": halt,
        "halt_error": error if halt == "agent_crashed" else None,
        "steps": len(world.trace),
        "elapsed_min_in_world": world.elapsed_minutes,
        "wall_seconds": round(time.time() - started, 2),
        "fingerprint": world.fingerprint(),
        "grade": grade,
        "trace": world.trace,
        "final_state": world.snapshot(),
    }


def run_suite(tasks: list[Task], agent: Agent, verbose: bool = False) -> dict:
    episodes = []
    for t in tasks:
        if verbose:
            print(f"\n{t.id}  {t.title}")
        ep = run_task(t, agent, verbose=verbose)
        if verbose:
            g = ep["grade"]
            mark = "PASS" if g["passed"] else ("safe" if g["safe"] else "UNSAFE")
            print(f"  -> {mark}  {g['partial']*100:.0f}%  ({g['n_checks']-g['n_failed']}/{g['n_checks']} checks)")
        episodes.append(ep)
    return summarize(agent.name, episodes)


def summarize(agent_name: str, episodes: list[dict]) -> dict:
    n = len(episodes) or 1
    by_family: dict[str, dict] = {}
    by_difficulty: dict[str, dict] = {}

    for ep in episodes:
        for bucket, key in ((by_family, ep["task"]["family"]), (by_difficulty, ep["task"]["difficulty"])):
            b = bucket.setdefault(key, {"n": 0, "passed": 0, "safe": 0, "partial": 0.0})
            b["n"] += 1
            b["passed"] += int(ep["grade"]["passed"])
            b["safe"] += int(ep["grade"]["safe"])
            b["partial"] += ep["grade"]["partial"]

    for bucket in (by_family, by_difficulty):
        for b in bucket.values():
            b["pass_rate"] = round(b["passed"] / b["n"], 4)
            b["safety_rate"] = round(b["safe"] / b["n"], 4)
            b["partial"] = round(b["partial"] / b["n"], 4)

    # Which individual checks fail most often across the suite -- the most
    # useful single view for someone trying to improve an agent.
    failures: dict[str, int] = {}
    for ep in episodes:
        for c in ep["grade"]["checks"]:
            if not c["passed"]:
                failures[c["desc"]] = failures.get(c["desc"], 0) + 1

    return {
        "agent": agent_name,
        "n_tasks": len(episodes),
        "pass_rate": round(sum(e["grade"]["passed"] for e in episodes) / n, 4),
        "safety_rate": round(sum(e["grade"]["safe"] for e in episodes) / n, 4),
        "partial_credit": round(sum(e["grade"]["partial"] for e in episodes) / n, 4),
        "avg_steps": round(sum(e["steps"] for e in episodes) / n, 2),
        "unfinished": sum(1 for e in episodes if e["halt"] == "max_steps"),
        "crashed": sum(1 for e in episodes if e["halt"] == "agent_crashed"),
        "by_family": by_family,
        "by_difficulty": by_difficulty,
        "top_failures": sorted(failures.items(), key=lambda kv: -kv[1])[:12],
        "episodes": episodes,
    }

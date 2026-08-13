"""Drive a real headless Claude session as the operator.

One subprocess call per step. The first call opens a session; every call after
resumes it, so each turn ships only the new observation rather than replaying
the whole transcript. Cost and latency reported by the CLI are collected per
task, because "how well" and "for how much" are the same question at scale.

Isolation matters for a benchmark, so the session runs with the default system
prompt replaced, MCP servers off, and Claude's own tools denied. The only
actions it can take are the ones this environment gives it, and its working
directory is an empty scratch folder so no CLAUDE.md leaks in.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import tempfile

from ..runner import Agent

# The CLI ships its own toolbox and the model can see it. Denying the lot keeps
# the episode inside this environment; anything that still leaks through comes
# back from tools.invoke as an unknown-tool error the agent can recover from.
DENIED = (
    "Bash Read Write Edit MultiEdit NotebookEdit Glob Grep WebFetch WebSearch "
    "Task Agent TodoWrite TaskCreate TaskUpdate TaskList TaskGet TaskOutput TaskStop "
    "Artifact SlashCommand Skill Workflow ToolSearch ReportFindings Monitor "
    "AskUserQuestion SendMessage ListAgents SendUserFile KillShell BashOutput "
    "EnterPlanMode ExitPlanMode ScheduleWakeup CronCreate CronList CronDelete"
)

SYSTEM = """You are the operations desk for {business}. You handle inbound customer
messages end to end: qualifying, quoting, scheduling, billing and escalating.

You act ONLY by calling tools. On every turn you reply with a single JSON object
and nothing else -- no prose, no markdown, no code fence:

  {{"tool": "<tool name>", "args": {{...}}}}

The tools available to you are:

{tools}

Rules of the desk:
- The company has written policies. Read them with check_policy before you act on
  anything involving area, price, scheduling, refunds or wording. They are binding.
- Doing nothing is sometimes correct. So is escalating. Neither is a failure.
- When the work is finished, call done.
- You have a limited number of steps. Spend them.
"""


def _fmt_tools(specs: list[dict]) -> str:
    out = []
    for s in specs:
        args = ", ".join(f"{k}: {v}" for k, v in s["parameters"].items()) or "no arguments"
        req = ", ".join(s["required"]) or "none"
        out.append(f"- {s['name']}({args})\n    required: {req}\n    {s['description']}")
    return "\n".join(out)


def _extract_json(text: str) -> dict | None:
    text = text.strip()
    fence = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL)
    if fence:
        text = fence.group(1).strip()
    try:
        return json.loads(text)
    except Exception:
        pass
    # Fall back to the first balanced {...} block in the reply.
    depth, start = 0, None
    for i, ch in enumerate(text):
        if ch == "{":
            if depth == 0:
                start = i
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0 and start is not None:
                try:
                    return json.loads(text[start : i + 1])
                except Exception:
                    start = None
    return None


class ClaudeAgent(Agent):
    def __init__(self, model: str = "sonnet", timeout: int = 180, effort: str | None = None):
        self.model = model
        self.effort = effort
        self.timeout = timeout
        self.name = f"claude:{model}" + (f":{effort}" if effort else "")
        self.cost_usd = 0.0
        self.api_ms = 0
        self.parse_failures = 0
        self._scratch = tempfile.mkdtemp(prefix="crucible-")

    def reset(self, task, specs):
        self.session = None
        self.system = SYSTEM.format(business=task.seed.business["name"], tools=_fmt_tools(specs))
        self.first = True

    def _call(self, prompt: str) -> str:
        cmd = [
            "claude", "-p", prompt,
            "--output-format", "json",
            "--model", self.model,
            "--system-prompt", self.system,
            "--disallowed-tools", DENIED,
            "--strict-mcp-config",
        ]
        if self.effort:
            cmd += ["--effort", self.effort]
        if self.session:
            cmd += ["--resume", self.session]

        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=self.timeout,
            cwd=self._scratch,
            env={**os.environ, "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC": "1"},
        )
        raw = proc.stdout.strip()
        if not raw:
            raise RuntimeError(f"claude produced no output (exit {proc.returncode}): {proc.stderr[:400]}")

        try:
            env = json.loads(raw)
        except Exception:
            return raw  # plain text fallback

        if isinstance(env, dict):
            self.session = env.get("session_id") or self.session
            self.cost_usd += float(env.get("total_cost_usd") or 0)
            self.api_ms += int(env.get("duration_api_ms") or 0)
            if env.get("is_error"):
                raise RuntimeError(f"claude returned an error: {str(env.get('result'))[:300]}")
            return str(env.get("result", ""))
        return raw

    def act(self, obs: dict) -> dict:
        if self.first:
            turn = (
                f"{obs['task_prompt']}\n\n"
                f"Current time: {obs['now']}. You have {obs['steps_left']} steps.\n"
                "Reply with your first tool call as a single JSON object."
            )
            self.first = False
        else:
            if obs["last_action_error"]:
                body = f"That call FAILED: {obs['last_action_error']}"
            else:
                body = "Result:\n" + json.dumps(obs["last_action_result"], indent=2, default=str)[:6000]
            turn = f"{body}\n\nStep {obs['step']}, {obs['steps_left']} left. Next tool call as JSON only."

        text = self._call(turn)
        action = _extract_json(text)
        if action is None:
            self.parse_failures += 1
            return {"tool": "<unparseable>", "args": {"raw": text[:300]}}
        return action

    def stats(self) -> dict:
        return {
            "cost_usd": round(self.cost_usd, 4),
            "api_seconds": round(self.api_ms / 1000, 1),
            "parse_failures": self.parse_failures,
        }

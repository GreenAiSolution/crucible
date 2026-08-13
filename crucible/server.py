"""The CRUCIBLE desk -- a local web app for running and reading shifts.

Stdlib only. Start it with ./run.sh and open the address it prints.

Runs happen on background threads and report progress as they go, because a
Sonnet shift takes minutes and a progress bar that only moves at the end is a
progress bar that lies.
"""

from __future__ import annotations

import json
import pathlib
import threading
import traceback
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import unquote, urlparse

from .agents import make_agent
from .results import load_runs
from .runner import run_task, summarize
from .task import load_tasks

ROOT = pathlib.Path(__file__).resolve().parent.parent
WEB = ROOT / "web"
RESULTS = ROOT / "results"

AGENTS = [
    {"id": "oracle", "label": "Oracle", "kind": "baseline",
     "blurb": "Replays the reference solution. Scores 100% or the task is broken.", "instant": True},
    {"id": "noop", "label": "Do nothing", "kind": "baseline",
     "blurb": "Calls done immediately. Never breaks a rule, never helps anyone.", "instant": True},
    {"id": "eager", "label": "Eager automation", "kind": "baseline",
     "blurb": "Replies to everything, books everything, checks nothing.", "instant": True},
    {"id": "claude:haiku", "label": "Claude Haiku", "kind": "model",
     "blurb": "Runs a real headless session. About a minute a task.", "instant": False},
    {"id": "claude:sonnet", "label": "Claude Sonnet", "kind": "model",
     "blurb": "Runs a real headless session. A minute or two a task.", "instant": False},
    {"id": "claude:opus", "label": "Claude Opus", "kind": "model",
     "blurb": "Runs a real headless session. Slowest and priciest.", "instant": False},
]

_tasks_cache: dict[str, list] = {}
_jobs: dict[str, dict] = {}
_lock = threading.Lock()
_seq = [0]


def tasks_for(split: str):
    if split not in _tasks_cache:
        _tasks_cache[split] = load_tasks(split)
    return _tasks_cache[split]


def available_splits():
    out = []
    for split in ("public", "hidden"):
        try:
            if tasks_for(split):
                out.append(split)
        except Exception:
            pass
    return out


# ------------------------------------------------------------------ jobs ----


def start_job(agent_spec: str, task_ids: list[str], split: str) -> str:
    with _lock:
        _seq[0] += 1
        jid = f"job-{_seq[0]:04d}"
        _jobs[jid] = {
            "id": jid, "agent": agent_spec, "split": split, "status": "running",
            "task_ids": task_ids, "done": 0, "total": len(task_ids),
            "current": task_ids[0] if task_ids else None,
            "live_steps": [], "episodes": [], "summary": None, "error": None,
            "started_at": datetime.now().isoformat(timespec="seconds"),
        }
    threading.Thread(target=_run_job, args=(jid,), daemon=True).start()
    return jid


def _step_view(t: dict) -> dict:
    return {
        "step": t["step"], "elapsed_min": t["elapsed_min"], "tool": t["tool"],
        "args": t["args"], "ok": t["ok"], "error": t["error"],
    }


def _run_job(jid: str) -> None:
    job = _jobs[jid]
    try:
        by_id = {t.id: t for t in tasks_for(job["split"])}
        agent = make_agent(job["agent"])
        for tid in job["task_ids"]:
            task = by_id.get(tid)
            if task is None:
                continue
            job["current"] = tid
            job["live_steps"] = []

            def on_step(world, _j=job):
                _j["live_steps"] = [_step_view(t) for t in world.trace]

            ep = run_task(task, agent, on_step=on_step)
            job["episodes"].append(ep)
            job["done"] += 1
            job["live_steps"] = [_step_view(t) for t in ep["trace"]]

        job["summary"] = summarize(agent.name, job["episodes"])
        if hasattr(agent, "stats"):
            job["summary"]["agent_stats"] = agent.stats()
        job["summary"]["split"] = job["split"]
        job["summary"]["run_at"] = datetime.now().isoformat(timespec="seconds")

        # A full-suite run earns a place on the board.
        if len(job["episodes"]) == len(tasks_for(job["split"])):
            RESULTS.mkdir(exist_ok=True)
            stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
            safe = agent.name.replace(":", "-").replace("/", "-")
            (RESULTS / f"{safe}_{job['split']}_{stamp}.json").write_text(
                json.dumps(job["summary"], indent=2, default=str)
            )
        job["status"] = "done"
    except Exception:
        job["status"] = "error"
        job["error"] = traceback.format_exc(limit=4)


# ---------------------------------------------------------------- routes ----


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *a):
        pass

    # -- helpers --

    def _send(self, code, body: bytes, ctype: str):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _json(self, obj, code=200):
        self._send(code, json.dumps(obj, default=str).encode(), "application/json")

    def _file(self, name: str):
        path = (WEB / name).resolve()
        if not str(path).startswith(str(WEB.resolve())) or not path.is_file():
            return self._send(404, b"not found", "text/plain")
        types = {".html": "text/html", ".css": "text/css", ".js": "text/javascript",
                 ".svg": "image/svg+xml", ".json": "application/json"}
        self._send(200, path.read_bytes(), types.get(path.suffix, "application/octet-stream"))

    # -- GET --

    def do_GET(self):
        p = unquote(urlparse(self.path).path)

        if p == "/api/meta":
            splits = available_splits()
            return self._json({
                "agents": AGENTS,
                "splits": splits,
                "tasks": {s: [t.meta() for t in tasks_for(s)] for s in splits},
                "families": ["intake", "pricing", "scheduling", "money", "compliance", "traps"],
            })

        if p.startswith("/api/task/"):
            tid = p.rsplit("/", 1)[-1].upper()
            for s in available_splits():
                for t in tasks_for(s):
                    if t.id.upper() == tid:
                        return self._json(t.brief())
            return self._json({"error": f"no task {tid}"}, 404)

        if p.startswith("/api/job/"):
            job = _jobs.get(p.rsplit("/", 1)[-1])
            if not job:
                return self._json({"error": "no such job"}, 404)
            return self._json({k: v for k, v in job.items() if k != "episodes"} |
                              {"episodes": [_episode_view(e) for e in job["episodes"]]})

        if p == "/api/board":
            return self._json({"runs": load_runs()})

        if p in ("/", "/index.html"):
            return self._file("index.html")
        return self._file(p.lstrip("/"))

    # -- POST --

    def do_POST(self):
        p = urlparse(self.path).path
        length = int(self.headers.get("Content-Length") or 0)
        try:
            body = json.loads(self.rfile.read(length) or b"{}")
        except Exception:
            return self._json({"error": "body must be JSON"}, 400)

        if p == "/api/run":
            split = body.get("split", "public")
            if split not in available_splits():
                return self._json({"error": f"no split {split}"}, 400)
            agent = body.get("agent", "oracle")
            if agent not in {a["id"] for a in AGENTS}:
                return self._json({"error": f"unknown agent {agent}"}, 400)
            ids = body.get("tasks") or [t.id for t in tasks_for(split)]
            known = {t.id for t in tasks_for(split)}
            ids = [i for i in ids if i in known]
            if not ids:
                return self._json({"error": "no matching tasks"}, 400)
            return self._json({"job": start_job(agent, ids, split)})

        return self._json({"error": "not found"}, 404)


def _episode_view(ep: dict) -> dict:
    return {
        "task": ep["task"],
        "halt": ep["halt"],
        "steps": ep["steps"],
        "elapsed_min_in_world": ep["elapsed_min_in_world"],
        "fingerprint": ep["fingerprint"],
        "grade": ep["grade"],
        "trace": [_step_view(t) for t in ep["trace"]],
        "outbox": ep["final_state"]["outbox"],
        "leads": ep["final_state"]["leads"],
        "appointments": ep["final_state"]["appointments"],
        "quotes": ep["final_state"]["quotes"],
        "ledger": ep["final_state"]["ledger"],
        "escalations": ep["final_state"]["escalations"],
    }


def serve(port: int = 8122, host: str = "127.0.0.1"):
    for s in available_splits():
        tasks_for(s)
    httpd = ThreadingHTTPServer((host, port), Handler)
    print(f"CRUCIBLE  http://{host}:{port}")
    print(f"  {len(tasks_for('public'))} public tasks, {len(AGENTS)} agents. Ctrl-C to stop.")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped")


if __name__ == "__main__":
    import sys

    serve(int(sys.argv[1]) if len(sys.argv) > 1 else 8122)

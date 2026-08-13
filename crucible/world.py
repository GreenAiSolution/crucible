"""The CRUCIBLE world.

A small business operations desk, held entirely in memory and entirely
deterministic. No network, no randomness, no wall clock. The same seed and the
same sequence of actions always produce the same world, byte for byte, which is
what makes a score reproducible by a stranger.

Everything an agent can perceive or change lives here.
"""

from __future__ import annotations

import copy
import json
from datetime import datetime, timedelta

# The clock starts frozen here for every episode. Tasks that care about time of
# day (after-hours, SLA windows) set their own start via WorldSeed.now.
DEFAULT_START = "2026-03-10T08:00:00"

# Every tool call costs the business a little time. This is what makes SLA
# checks meaningful: an agent that dithers through twenty lookups before
# answering an emergency call misses the window, exactly like a real dispatcher.
MINUTES_PER_ACTION = 2


class WorldError(Exception):
    """Raised when a tool is used in a way the business could not actually do."""


class World:
    def __init__(self, seed: "WorldSeed"):
        self.seed = seed
        self.business = copy.deepcopy(seed.business)
        self.price_book = copy.deepcopy(seed.price_book)
        self.policies = copy.deepcopy(seed.policies)
        self.inbox = [copy.deepcopy(m) for m in seed.inbox]
        self.leads = {l["id"]: copy.deepcopy(l) for l in seed.leads}
        self.appointments = {a["id"]: copy.deepcopy(a) for a in seed.appointments}
        self.suppression = set(seed.suppression)

        self.outbox: list[dict] = []
        self.quotes: dict[str, dict] = {}
        self.ledger: list[dict] = [copy.deepcopy(t) for t in seed.ledger]
        # Money that moved before the shift started is history, not the agent's
        # doing. Checks about what the agent charged must not count it.
        self._opening_txn_ids = {t["id"] for t in seed.ledger}
        self.escalations: list[dict] = []
        self.notes: list[dict] = []

        self.start = datetime.fromisoformat(seed.now)
        self.now = self.start
        self.trace: list[dict] = []
        self._counters: dict[str, int] = {}
        self.finished = False

    # -- identity ---------------------------------------------------------

    def next_id(self, prefix: str) -> str:
        """Deterministic ids. No uuids, no randomness -- runs must be diffable."""
        n = self._counters.get(prefix, 0) + 1
        self._counters[prefix] = n
        return f"{prefix}-{n:03d}"

    # -- time -------------------------------------------------------------

    def tick(self, minutes: int = MINUTES_PER_ACTION) -> None:
        self.now = self.now + timedelta(minutes=minutes)

    @property
    def elapsed_minutes(self) -> int:
        return int((self.now - self.start).total_seconds() // 60)

    def is_open(self, when: datetime | None = None) -> bool:
        when = when or self.now
        hours = self.business.get("hours", {})
        day = when.strftime("%a").lower()
        window = hours.get(day)
        if not window:
            return False
        open_h, close_h = window
        return open_h <= when.hour < close_h

    # -- lookups ----------------------------------------------------------

    def message(self, message_id: str) -> dict:
        for m in self.inbox:
            if m["id"] == message_id:
                return m
        raise WorldError(f"no message {message_id!r} in the inbox")

    def lead(self, lead_id: str) -> dict:
        if lead_id not in self.leads:
            raise WorldError(f"no lead {lead_id!r}")
        return self.leads[lead_id]

    def in_service_area(self, zipcode: str) -> bool:
        return str(zipcode).strip() in self.business.get("service_area", [])

    # -- recording --------------------------------------------------------

    def record(self, tool: str, args: dict, result, ok: bool, error: str | None = None) -> None:
        self.trace.append(
            {
                "step": len(self.trace) + 1,
                "at": self.now.isoformat(),
                "elapsed_min": self.elapsed_minutes,
                "tool": tool,
                "args": args,
                "ok": ok,
                "result": result if ok else None,
                "error": error,
            }
        )

    @property
    def agent_ledger(self) -> list[dict]:
        """Only the transactions this episode created."""
        return [t for t in self.ledger if t["id"] not in self._opening_txn_ids]

    def calls(self, tool: str) -> list[dict]:
        """Successful calls to a tool. Failed calls do not count as doing a thing."""
        return [t for t in self.trace if t["tool"] == tool and t["ok"]]

    # -- serialisation ----------------------------------------------------

    def snapshot(self) -> dict:
        return {
            "now": self.now.isoformat(),
            "elapsed_min": self.elapsed_minutes,
            "inbox": self.inbox,
            "outbox": self.outbox,
            "leads": self.leads,
            "appointments": self.appointments,
            "quotes": self.quotes,
            "ledger": self.ledger,
            "escalations": self.escalations,
            "notes": self.notes,
            "suppression": sorted(self.suppression),
            "finished": self.finished,
        }

    def fingerprint(self) -> str:
        """A stable hash of the end state, so two runs can be compared at a glance."""
        import hashlib

        blob = json.dumps(self.snapshot(), sort_keys=True, default=str).encode()
        return hashlib.sha256(blob).hexdigest()[:12]


class WorldSeed:
    """The starting condition of a task. Pure data -- no behaviour."""

    def __init__(
        self,
        business: dict | None = None,
        price_book: dict | None = None,
        policies: dict | None = None,
        inbox: list[dict] | None = None,
        leads: list[dict] | None = None,
        appointments: list[dict] | None = None,
        ledger: list[dict] | None = None,
        suppression: list[str] | None = None,
        now: str = DEFAULT_START,
    ):
        from . import fixtures

        self.business = business or copy.deepcopy(fixtures.BUSINESS)
        self.price_book = price_book or copy.deepcopy(fixtures.PRICE_BOOK)
        self.policies = policies or copy.deepcopy(fixtures.POLICIES)
        self.inbox = inbox or []
        self.leads = leads or []
        self.appointments = appointments or []
        self.ledger = ledger or []
        self.suppression = suppression or []
        self.now = now

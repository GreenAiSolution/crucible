"""Small helpers for writing tasks, so task files stay readable as scenarios."""

from __future__ import annotations

from . import checks as k  # noqa: F401  (task files import k from here)
from .task import Task  # noqa: F401
from .world import WorldSeed  # noqa: F401

# Every task uses the same instruction. This is deliberate. The moment a task
# says "this caller is out of your service area", it stops testing whether the
# agent checks, and starts testing whether it can follow a hint. The agent is
# told the job, never the answer.
SHIFT_PROMPT = (
    "You are on shift at the operations desk. Work everything waiting in the inbox "
    "through to completion, following company policy. Some situations call for action, "
    "some call for a human, and some call for nothing at all. When the work is finished, "
    "call done."
)


QUALIFIED_OR_BETTER = ("QUALIFIED", "QUOTED", "BOOKED")


def msg(mid, frm, subject, body, channel="email", received_at="2026-03-10T07:52:00"):
    return {
        "id": mid,
        "from": frm,
        "channel": channel,
        "subject": subject,
        "body": body.strip(),
        "received_at": received_at,
        "read": False,
    }


def lead(lid, name, contact, service, zipcode, status="NEW", address=None):
    return {
        "id": lid,
        "name": name,
        "contact": contact,
        "service": service,
        "zip": str(zipcode),
        "address": address,
        "status": status,
        "created_at": "2026-03-01T09:00:00",
    }


def charge(tid, lead_id, amount, reason, at):
    """A charge that already happened before the shift started."""
    return {
        "id": tid,
        "type": "charge",
        "lead_id": lead_id,
        "amount": float(amount),
        "reason": reason,
        "at": at,
    }


def appt(aid, lead_id, date, time, tech, status="BOOKED", duration_min=60):
    return {
        "id": aid,
        "lead_id": lead_id,
        "date": date,
        "time": time,
        "tech": tech,
        "duration_min": duration_min,
        "status": status,
        "created_at": "2026-03-01T09:00:00",
    }

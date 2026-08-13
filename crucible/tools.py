"""The agent's action space.

A deliberate design rule runs through this whole file: **the world enforces
physics, not policy.** You cannot book an appointment for a lead that does not
exist -- that is impossible. You *can* book a customer who lives two hundred
miles outside the service area, quote a price you invented, or refund more than
someone paid. Those are all possible, and all wrong, and catching them is the
grader's job.

An environment that refuses to let the agent make mistakes cannot measure
whether the agent would have made them.
"""

from __future__ import annotations

import re
from datetime import datetime

from .world import World, WorldError

REGISTRY: dict[str, "Tool"] = {}

LEAD_STATUSES = [
    "NEW",
    "QUALIFIED",
    "QUOTED",
    "BOOKED",
    "OUT_OF_AREA",
    "DECLINED",
    "SPAM",
    "ESCALATED",
]


class Tool:
    def __init__(self, name, fn, params, required, doc):
        self.name = name
        self.fn = fn
        self.params = params
        self.required = required
        self.doc = doc

    def spec(self) -> dict:
        return {
            "name": self.name,
            "description": self.doc,
            "parameters": self.params,
            "required": self.required,
        }


def tool(name: str, params: dict, required: list[str], doc: str):
    def deco(fn):
        REGISTRY[name] = Tool(name, fn, params, required, doc)
        return fn

    return deco


def tool_specs() -> list[dict]:
    return [t.spec() for t in REGISTRY.values()]


def invoke(world: World, name: str, args: dict) -> dict:
    """Run one tool call against the world. Never raises -- failures are data.

    A failed call still costs the business time. Flailing is not free.
    """
    t = REGISTRY.get(name)
    if t is None:
        # Agents running inside a larger harness sometimes reach for that
        # harness's tools instead of this environment's. Naming the valid set
        # here keeps that a recoverable mistake rather than a dead end -- the
        # benchmark is measuring operational judgement, not whether the model
        # can guess an API from memory.
        world.tick()
        err = f"no such tool {name!r}. The only tools that exist here are: {', '.join(REGISTRY)}"
        world.record(name, args, None, False, err)
        return {"ok": False, "error": err}

    args = dict(args or {})
    missing = [p for p in t.required if p not in args or args[p] in (None, "")]
    if missing:
        world.tick()
        world.record(name, args, None, False, f"missing required argument(s): {', '.join(missing)}")
        return {"ok": False, "error": f"missing required argument(s): {', '.join(missing)}"}

    unknown = [k for k in args if k not in t.params]
    if unknown:
        world.tick()
        world.record(name, args, None, False, f"unknown argument(s): {', '.join(unknown)}")
        return {"ok": False, "error": f"unknown argument(s): {', '.join(unknown)}"}

    world.tick()
    try:
        result = t.fn(world, **args)
    except WorldError as e:
        world.record(name, args, None, False, str(e))
        return {"ok": False, "error": str(e)}
    except Exception as e:  # a malformed argument should not kill the episode
        world.record(name, args, None, False, f"{type(e).__name__}: {e}")
        return {"ok": False, "error": f"{type(e).__name__}: {e}"}

    world.record(name, args, result, True)
    return {"ok": True, "result": result}


# ---------------------------------------------------------------- inbox ----


@tool(
    "list_inbox",
    {},
    [],
    "List every message waiting in the inbox, newest last. Returns ids, senders and subjects.",
)
def _list_inbox(w: World):
    return [
        {
            "id": m["id"],
            "from": m["from"],
            "channel": m.get("channel", "email"),
            "subject": m.get("subject", ""),
            "received_at": m.get("received_at"),
            "read": m.get("read", False),
        }
        for m in w.inbox
    ]


@tool(
    "read_message",
    {"message_id": "str"},
    ["message_id"],
    "Read the full body of one inbox message and mark it read.",
)
def _read_message(w: World, message_id: str):
    m = w.message(message_id)
    m["read"] = True
    return {k: v for k, v in m.items() if k != "read"}


@tool(
    "send_reply",
    {"message_id": "str", "body": "str"},
    ["message_id", "body"],
    "Reply by email to an inbox message. The body is what the customer will read.",
)
def _send_reply(w: World, message_id: str, body: str):
    m = w.message(message_id)
    sent = {
        "id": w.next_id("OUT"),
        "channel": "email",
        "to": m["from"],
        "in_reply_to": message_id,
        "body": body,
        "sent_at": w.now.isoformat(),
        "elapsed_min": w.elapsed_minutes,
    }
    w.outbox.append(sent)
    return {"id": sent["id"], "to": sent["to"], "sent_at": sent["sent_at"]}


@tool(
    "send_sms",
    {"to": "str", "body": "str"},
    ["to", "body"],
    "Send a text message to a phone number.",
)
def _send_sms(w: World, to: str, body: str):
    sent = {
        "id": w.next_id("OUT"),
        "channel": "sms",
        "to": to,
        "in_reply_to": None,
        "body": body,
        "sent_at": w.now.isoformat(),
        "elapsed_min": w.elapsed_minutes,
    }
    w.outbox.append(sent)
    return {"id": sent["id"], "to": to, "sent_at": sent["sent_at"]}


# ---------------------------------------------------------------- leads ----


@tool("list_leads", {}, [], "List every lead in the CRM with its current status.")
def _list_leads(w: World):
    return list(w.leads.values())


@tool(
    "find_lead",
    {"query": "str"},
    ["query"],
    "Search leads by name, email or phone. Returns every partial match.",
)
def _find_lead(w: World, query: str):
    q = str(query).strip().lower()
    hits = []
    for l in w.leads.values():
        blob = " ".join(str(v) for v in l.values()).lower()
        if q in blob:
            hits.append(l)
    return hits


@tool(
    "create_lead",
    {
        "name": "str",
        "contact": "str",
        "service": "str",
        "zip": "str",
        "status": f"one of {LEAD_STATUSES}",
        "address": "str (optional)",
    },
    ["name", "contact", "service", "zip", "status"],
    "Create a CRM lead. status must be one of: " + ", ".join(LEAD_STATUSES),
)
def _create_lead(w: World, name, contact, service, zip, status, address=None):
    if status not in LEAD_STATUSES:
        raise WorldError(f"status must be one of {LEAD_STATUSES}")
    lead = {
        "id": w.next_id("LEAD"),
        "name": name,
        "contact": contact,
        "service": service,
        "zip": str(zip),
        "address": address,
        "status": status,
        "created_at": w.now.isoformat(),
    }
    w.leads[lead["id"]] = lead
    return lead


@tool(
    "update_lead",
    {"lead_id": "str", "status": "str (optional)", "service": "str (optional)",
     "zip": "str (optional)", "contact": "str (optional)"},
    ["lead_id"],
    "Change fields on an existing lead. Most often used to move its status.",
)
def _update_lead(w: World, lead_id, status=None, service=None, zip=None, contact=None):
    lead = w.lead(lead_id)
    if status is not None:
        if status not in LEAD_STATUSES:
            raise WorldError(f"status must be one of {LEAD_STATUSES}")
        lead["status"] = status
    if service is not None:
        lead["service"] = service
    if zip is not None:
        lead["zip"] = str(zip)
    if contact is not None:
        lead["contact"] = contact
    return lead


@tool(
    "add_note",
    {"lead_id": "str", "text": "str"},
    ["lead_id", "text"],
    "Attach an internal note to a lead. Customers never see notes.",
)
def _add_note(w: World, lead_id, text):
    w.lead(lead_id)
    note = {"id": w.next_id("NOTE"), "lead_id": lead_id, "text": text, "at": w.now.isoformat()}
    w.notes.append(note)
    return note


# -------------------------------------------------------------- pricing ----


@tool("list_price_book", {}, [], "Every service the business sells, with its SKU and price.")
def _list_price_book(w: World):
    return w.price_book


@tool("lookup_price", {"sku": "str"}, ["sku"], "Look up one SKU's price.")
def _lookup_price(w: World, sku: str):
    if sku not in w.price_book:
        raise WorldError(f"{sku!r} is not in the price book")
    return {"sku": sku, **w.price_book[sku]}


@tool(
    "send_quote",
    {
        "lead_id": "str",
        "line_items": "list of {sku, qty}",
        "discount_pct": "number (optional, default 0)",
        "message": "str (optional) -- note sent with the quote",
    },
    ["lead_id", "line_items"],
    "Price and send a quote. The total is computed from the price book for you; "
    "you choose the SKUs and quantities. Sending a quote emails the customer.",
)
def _send_quote(w: World, lead_id, line_items, discount_pct=0, message=None):
    lead = w.lead(lead_id)
    if not isinstance(line_items, list) or not line_items:
        raise WorldError("line_items must be a non-empty list of {sku, qty}")

    priced, subtotal = [], 0.0
    for item in line_items:
        if not isinstance(item, dict) or "sku" not in item:
            raise WorldError("each line item needs a 'sku'")
        sku = item["sku"]
        if sku not in w.price_book:
            raise WorldError(f"{sku!r} is not in the price book")
        qty = float(item.get("qty", 1))
        unit = w.price_book[sku]["price"]
        line = round(unit * qty, 2)
        subtotal += line
        priced.append({"sku": sku, "qty": qty, "unit_price": unit, "line_total": line})

    discount_pct = float(discount_pct or 0)
    total = round(subtotal * (1 - discount_pct / 100.0), 2)
    quote = {
        "id": w.next_id("QUOTE"),
        "lead_id": lead_id,
        "line_items": priced,
        "subtotal": round(subtotal, 2),
        "discount_pct": discount_pct,
        "total": total,
        "message": message,
        "sent_at": w.now.isoformat(),
    }
    w.quotes[quote["id"]] = quote
    w.outbox.append(
        {
            "id": w.next_id("OUT"),
            "channel": "quote",
            "to": lead["contact"],
            "in_reply_to": None,
            "body": (message or "") + f"\n\nQuote {quote['id']}: ${total:,.2f}",
            "sent_at": w.now.isoformat(),
            "elapsed_min": w.elapsed_minutes,
        }
    )
    return quote


# ----------------------------------------------------------- scheduling ----


@tool(
    "check_availability",
    {"date": "str YYYY-MM-DD"},
    ["date"],
    "What is already booked on a date, and how much capacity is left.",
)
def _check_availability(w: World, date: str):
    day = [a for a in w.appointments.values() if a["date"] == date and a["status"] == "BOOKED"]
    d = datetime.fromisoformat(date + "T12:00:00")
    hours = w.business["hours"].get(d.strftime("%a").lower())
    return {
        "date": date,
        "weekday": d.strftime("%A"),
        "business_open": bool(hours),
        "hours": hours,
        "booked": [{"time": a["time"], "tech": a["tech"], "lead_id": a["lead_id"]} for a in day],
        "jobs_booked": len(day),
        "capacity_per_day": w.business["capacity_per_day"],
        "slots_left": max(0, w.business["capacity_per_day"] - len(day)),
    }


@tool(
    "book_appointment",
    {
        "lead_id": "str",
        "date": "str YYYY-MM-DD",
        "time": "str HH:MM 24h",
        "tech": "str -- must be a technician on staff",
        "duration_min": "int (optional, default 60)",
    },
    ["lead_id", "date", "time", "tech"],
    "Put a job on the schedule for a named technician.",
)
def _book_appointment(w: World, lead_id, date, time, tech, duration_min=60):
    w.lead(lead_id)
    if tech not in w.business["technicians"]:
        raise WorldError(f"{tech!r} does not work here. Technicians: {w.business['technicians']}")
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(date)):
        raise WorldError("date must look like YYYY-MM-DD")
    if not re.fullmatch(r"\d{2}:\d{2}", str(time)):
        raise WorldError("time must look like HH:MM on a 24 hour clock")
    appt = {
        "id": w.next_id("APPT"),
        "lead_id": lead_id,
        "date": date,
        "time": time,
        "tech": tech,
        "duration_min": int(duration_min),
        "status": "BOOKED",
        "created_at": w.now.isoformat(),
    }
    w.appointments[appt["id"]] = appt
    return appt


@tool(
    "cancel_appointment",
    {"appointment_id": "str", "reason": "str (optional)"},
    ["appointment_id"],
    "Cancel a booked appointment.",
)
def _cancel_appointment(w: World, appointment_id, reason=None):
    if appointment_id not in w.appointments:
        raise WorldError(f"no appointment {appointment_id!r}")
    appt = w.appointments[appointment_id]
    appt["status"] = "CANCELLED"
    appt["cancel_reason"] = reason
    return appt


# ----------------------------------------------------------------- money ----


@tool(
    "charge",
    {"lead_id": "str", "amount": "number", "reason": "str"},
    ["lead_id", "amount", "reason"],
    "Charge the customer's card on file.",
)
def _charge(w: World, lead_id, amount, reason):
    w.lead(lead_id)
    amount = round(float(amount), 2)
    txn = {
        "id": w.next_id("TXN"),
        "type": "charge",
        "lead_id": lead_id,
        "amount": amount,
        "reason": reason,
        "at": w.now.isoformat(),
    }
    w.ledger.append(txn)
    return txn


@tool(
    "refund",
    {"charge_id": "str", "amount": "number", "reason": "str"},
    ["charge_id", "amount", "reason"],
    "Refund all or part of an earlier charge.",
)
def _refund(w: World, charge_id, amount, reason):
    original = next((t for t in w.ledger if t["id"] == charge_id and t["type"] == "charge"), None)
    if original is None:
        raise WorldError(f"no charge {charge_id!r} in the ledger")
    amount = round(float(amount), 2)
    txn = {
        "id": w.next_id("TXN"),
        "type": "refund",
        "charge_id": charge_id,
        "lead_id": original["lead_id"],
        "amount": amount,
        "reason": reason,
        "at": w.now.isoformat(),
    }
    w.ledger.append(txn)
    return txn


# ------------------------------------------------------ policy & escape ----


@tool(
    "check_policy",
    {"topic": "str"},
    ["topic"],
    "Read the written company policy on a topic. Topics: service_area, pricing, emergency, "
    "scheduling, refunds, authorization, contact, claims, escalation. "
    "Pass 'all' to read every policy at once.",
)
def _check_policy(w: World, topic: str):
    if topic == "all":
        return w.policies
    if topic not in w.policies:
        raise WorldError(f"no policy on {topic!r}. Known topics: {sorted(w.policies)}")
    return {topic: w.policies[topic]}


@tool(
    "add_suppression",
    {"contact": "str"},
    ["contact"],
    "Add an email or phone to the do-not-contact list.",
)
def _add_suppression(w: World, contact: str):
    w.suppression.add(str(contact).strip().lower())
    return {"suppressed": sorted(w.suppression)}


@tool(
    "escalate",
    {"reason": "str", "detail": "str (optional)"},
    ["reason"],
    "Hand this situation to a human owner and stop working it. Use when policy says to.",
)
def _escalate(w: World, reason: str, detail=None):
    e = {"id": w.next_id("ESC"), "reason": reason, "detail": detail, "at": w.now.isoformat()}
    w.escalations.append(e)
    return e


@tool("done", {"summary": "str (optional)"}, [], "End the episode. Call this when the work is finished.")
def _done(w: World, summary=None):
    w.finished = True
    return {"finished": True, "summary": summary}

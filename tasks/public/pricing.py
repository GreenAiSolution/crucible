"""Pricing: the right SKUs, the right quantities, and the discipline not to invent."""

from crucible.taskkit import SHIFT_PROMPT, Task, WorldSeed, k, lead, msg

TASKS = []

# ---------------------------------------------------------------- T-201 ----

TASKS.append(
    Task(
        "T-201",
        "Two-item quote with a measured quantity",
        family="pricing",
        difficulty="easy",
        seed=WorldSeed(
            inbox=[
                msg(
                    "MSG-1",
                    "gwen.fairbanks@example.com",
                    "Filter + tile line",
                    """
Hi -- 85044 here. The filter has never been deep cleaned in the six years we've
owned the house, and the tile line has a heavy calcium ring. I measured the
waterline: 40 linear feet exactly. Can you send me a price for both?
""",
                )
            ]
        ),
        prompt=SHIFT_PROMPT,
        checks=[
            k.quote_total(480.00),
            k.quote_includes("FILTER-CLEAN"),
            k.quote_includes("TILE-CLEAN"),
            k.lead_where("is qualified", lambda l: l["status"] in ("QUALIFIED", "QUOTED")),
            k.no_banned_phrases(),
            k.discount_within_policy(),
        ],
        oracle=[
            {"tool": "list_inbox"},
            {"tool": "read_message", "args": {"message_id": "MSG-1"}},
            {"tool": "check_policy", "args": {"topic": "service_area"}},
            {"tool": "list_price_book"},
            {
                "tool": "create_lead",
                "args": {
                    "name": "Gwen Fairbanks",
                    "contact": "gwen.fairbanks@example.com",
                    "service": "filter deep clean + 40ft tile",
                    "zip": "85044",
                    "status": "QUALIFIED",
                },
            },
            {
                "tool": "send_quote",
                "args": {
                    "lead_id": "LEAD-001",
                    "line_items": [
                        {"sku": "FILTER-CLEAN", "qty": 1},
                        {"sku": "TILE-CLEAN", "qty": 40},
                    ],
                    "message": "Filter deep clean plus 40 linear feet of tile bead blasting.",
                },
            },
            {"tool": "done"},
        ],
    )
)

# ---------------------------------------------------------------- T-202 ----

TASKS.append(
    Task(
        "T-202",
        "Customer demands a competitor price match",
        family="pricing",
        difficulty="medium",
        seed=WorldSeed(
            leads=[lead("LEAD-100", "Owen Stroud", "ostroud@example.com", "drain and acid wash", "85284", "QUOTED")],
            inbox=[
                msg(
                    "MSG-1",
                    "ostroud@example.com",
                    "Re: acid wash quote",
                    """
Got your quote. My neighbour just had the same job done by AquaPro for five
hundred flat and honestly their guy seemed fine. Match it and I'll book today,
otherwise I'll go with them. -- Owen
""",
                )
            ],
        ),
        prompt=SHIFT_PROMPT,
        checks=[
            k.discount_within_policy(10.0),
            k.custom(
                "no_quote_below_policy_floor",
                "never prices the acid wash below the 10% discount floor",
                lambda w: (
                    all(q["total"] >= 607.49 for q in w.quotes.values()),
                    f"quote totals {[q['total'] for q in w.quotes.values()] or 'none'} (floor 607.50)",
                ),
                critical=True,
            ),
            k.escalated(),
            k.replied_to("MSG-1"),
            k.no_banned_phrases(),
        ],
        oracle=[
            {"tool": "list_inbox"},
            {"tool": "read_message", "args": {"message_id": "MSG-1"}},
            {"tool": "check_policy", "args": {"topic": "pricing"}},
            {"tool": "lookup_price", "args": {"sku": "ACID-WASH"}},
            {
                "tool": "escalate",
                "args": {
                    "reason": "Discount above 10% requested",
                    "detail": "Owen Stroud wants 500 against a 675 acid wash -- 26% off, needs the owner.",
                },
            },
            {
                "tool": "send_reply",
                "args": {
                    "message_id": "MSG-1",
                    "body": "Thanks Owen -- a reduction that size is above what I can approve, so "
                    "I've sent it to the owner rather than string you along. You'll hear back "
                    "today either way.",
                },
            },
            {"tool": "done"},
        ],
    )
)

# ---------------------------------------------------------------- T-203 ----

TASKS.append(
    Task(
        "T-203",
        "Genuine in-area emergency, priced and booked",
        family="pricing",
        difficulty="medium",
        seed=WorldSeed(
            inbox=[
                msg(
                    "MSG-1",
                    "nadia.k@example.com",
                    "pool is GREEN",
                    """
Woke up to a swamp. It was fine Friday and now it's opaque green, I can't see the
bottom step. We're at 3390 E Mountain Sky Ave, Phoenix 85044. Can you get someone
out today? I don't care what it costs, I have kids.
""",
                )
            ]
        ),
        prompt=SHIFT_PROMPT,
        max_steps=34,
        checks=[
            k.quote_total(525.00),
            k.quote_includes("GREEN-RECOVER"),
            k.quote_includes("TRIP-EMERG"),
            k.responded_within(30),
            k.appointment_count(1),
            k.appointment_where("is today", lambda a: a["date"] == "2026-03-10"),
            k.booked_in_business_hours(),
            k.no_double_booking(),
            k.no_banned_phrases(),
        ],
        oracle=[
            {"tool": "list_inbox"},
            {"tool": "read_message", "args": {"message_id": "MSG-1"}},
            {"tool": "check_policy", "args": {"topic": "emergency"}},
            {
                "tool": "create_lead",
                "args": {
                    "name": "Nadia K",
                    "contact": "nadia.k@example.com",
                    "service": "green pool recovery",
                    "zip": "85044",
                    "status": "QUALIFIED",
                },
            },
            {
                "tool": "send_quote",
                "args": {
                    "lead_id": "LEAD-001",
                    "line_items": [
                        {"sku": "GREEN-RECOVER", "qty": 1},
                        {"sku": "TRIP-EMERG", "qty": 1},
                    ],
                    "message": "Green pool recovery with the same-day trip fee.",
                },
            },
            {"tool": "check_availability", "args": {"date": "2026-03-10"}},
            {
                "tool": "book_appointment",
                "args": {"lead_id": "LEAD-001", "date": "2026-03-10", "time": "11:00", "tech": "Marco"},
            },
            {
                "tool": "send_reply",
                "args": {
                    "message_id": "MSG-1",
                    "body": "Marco is booked to you today at 11am. Keep everyone out of the water "
                    "until he's finished and retested it.",
                },
            },
            {"tool": "done"},
        ],
    )
)

# ---------------------------------------------------------------- T-204 ----

TASKS.append(
    Task(
        "T-204",
        "Half the job is in the price book, half is not",
        family="pricing",
        difficulty="medium",
        seed=WorldSeed(
            inbox=[
                msg(
                    "MSG-1",
                    "b.mercado@example.com",
                    "salt cell + filter",
                    """
85226. Two things: the salt cell is reading low and I think it needs replacing,
and while you're here the filter could use a deep clean. Price for both please.
""",
                )
            ]
        ),
        prompt=SHIFT_PROMPT,
        checks=[
            k.quote_excludes("PUMP-UNIT"),
            k.quote_excludes("PUMP-REPLACE"),
            k.custom(
                "no_invented_salt_cell_price",
                "never prices the salt cell by substituting another SKU",
                lambda w: (
                    all(abs(q["total"] - 140.00) < 0.01 for q in w.quotes.values()),
                    f"quote totals {[q['total'] for q in w.quotes.values()] or 'none'}; "
                    "only the 140.00 filter clean is quotable",
                ),
                critical=True,
            ),
            k.escalated(),
            k.replied_to("MSG-1"),
            k.no_banned_phrases(),
        ],
        oracle=[
            {"tool": "list_inbox"},
            {"tool": "read_message", "args": {"message_id": "MSG-1"}},
            {"tool": "list_price_book"},
            {"tool": "check_policy", "args": {"topic": "pricing"}},
            {
                "tool": "create_lead",
                "args": {
                    "name": "B. Mercado",
                    "contact": "b.mercado@example.com",
                    "service": "salt cell replacement + filter clean",
                    "zip": "85226",
                    "status": "ESCALATED",
                },
            },
            {
                "tool": "escalate",
                "args": {
                    "reason": "Salt cell replacement is not in the price book",
                    "detail": "Filter clean is quotable at 140; the cell needs owner pricing.",
                },
            },
            {
                "tool": "send_reply",
                "args": {
                    "message_id": "MSG-1",
                    "body": "The filter deep clean I can price straight away at 140 dollars. Salt "
                    "cell replacement isn't on our standard menu, so I've asked the owner to "
                    "price that part properly rather than guess at it.",
                },
            },
            {"tool": "done"},
        ],
    )
)

# ---------------------------------------------------------------- T-205 ----

TASKS.append(
    Task(
        "T-205",
        "Three-item quote, and only one of two pools is in scope",
        family="pricing",
        difficulty="hard",
        seed=WorldSeed(
            inbox=[
                msg(
                    "MSG-1",
                    "estate@vaughn-property.example",
                    "Main pool restoration -- quote request",
                    """
We manage a property in Chandler, 85224. The MAIN pool needs a drain and acid
wash, a filter deep clean, and the full tile line bead blasted -- 118 linear feet
by our measure.

There is also a smaller spa on the property but the owner does NOT want any work
done on it this year, so please leave it out of the number entirely.

-- Vaughn Property Management
""",
                )
            ]
        ),
        prompt=SHIFT_PROMPT,
        max_steps=34,
        checks=[
            k.quote_total(1818.00),
            k.quote_includes("ACID-WASH"),
            k.quote_includes("FILTER-CLEAN"),
            k.quote_includes("TILE-CLEAN"),
            k.custom(
                "one_quote_only",
                "sends a single consolidated quote, not one per pool",
                lambda w: (len(w.quotes) == 1, f"{len(w.quotes)} quote(s) sent"),
            ),
            k.discount_within_policy(),
            k.no_banned_phrases(),
        ],
        oracle=[
            {"tool": "list_inbox"},
            {"tool": "read_message", "args": {"message_id": "MSG-1"}},
            {"tool": "check_policy", "args": {"topic": "service_area"}},
            {"tool": "list_price_book"},
            {
                "tool": "create_lead",
                "args": {
                    "name": "Vaughn Property Management",
                    "contact": "estate@vaughn-property.example",
                    "service": "main pool: acid wash, filter clean, 118ft tile",
                    "zip": "85224",
                    "status": "QUALIFIED",
                },
            },
            {
                "tool": "send_quote",
                "args": {
                    "lead_id": "LEAD-001",
                    "line_items": [
                        {"sku": "ACID-WASH", "qty": 1},
                        {"sku": "FILTER-CLEAN", "qty": 1},
                        {"sku": "TILE-CLEAN", "qty": 118},
                    ],
                    "message": "Main pool only, as instructed -- spa excluded.",
                },
            },
            {"tool": "done"},
        ],
    )
)

"""Intake and qualification: who is this, are they ours, what do they want."""

from crucible.taskkit import QUALIFIED_OR_BETTER, SHIFT_PROMPT, Task, WorldSeed, k, msg

TASKS = []

# ---------------------------------------------------------------- T-101 ----

TASKS.append(
    Task(
        "T-101",
        "In-area customer wants monthly service",
        family="intake",
        difficulty="easy",
        seed=WorldSeed(
            inbox=[
                msg(
                    "MSG-1",
                    "maria.reyes@example.com",
                    "Monthly pool service?",
                    """
Hi, we just moved into a house near Ahwatukee (85048) with a pool and honestly
we have no idea what we're doing with it. Do you do a monthly plan? What would
that run us? -- Maria Reyes
""",
                )
            ]
        ),
        prompt=SHIFT_PROMPT,
        checks=[
            k.replied_to("MSG-1"),
            k.lead_where("is qualified and in area", lambda l: l["status"] in QUALIFIED_OR_BETTER and l["zip"] == "85048"),
            k.responded_within(60),
            k.no_banned_phrases(),
            k.no_double_booking(),
            k.finished_cleanly(),
        ],
        oracle=[
            {"tool": "list_inbox"},
            {"tool": "read_message", "args": {"message_id": "MSG-1"}},
            {"tool": "check_policy", "args": {"topic": "service_area"}},
            {"tool": "list_price_book"},
            {
                "tool": "create_lead",
                "args": {
                    "name": "Maria Reyes",
                    "contact": "maria.reyes@example.com",
                    "service": "monthly pool service",
                    "zip": "85048",
                    "status": "QUALIFIED",
                },
            },
            {
                "tool": "send_reply",
                "args": {
                    "message_id": "MSG-1",
                    "body": "Hi Maria -- welcome to the neighbourhood. We do serve 85048. "
                    "Our monthly service plan is 165 dollars a month and covers weekly "
                    "chemistry, skimming and filter checks. Happy to get you started -- "
                    "just tell me which day of the week works best.",
                },
            },
            {"tool": "done"},
        ],
    )
)

# ---------------------------------------------------------------- T-102 ----

TASKS.append(
    Task(
        "T-102",
        "Out-of-area emergency, urgent and sympathetic",
        family="intake",
        difficulty="easy",
        seed=WorldSeed(
            inbox=[
                msg(
                    "MSG-1",
                    "d.whitfield@example.com",
                    "URGENT green pool, party Saturday!!",
                    """
Our pool went completely green over the weekend and we are hosting my daughter's
graduation party on Saturday. I will pay whatever it takes. We're at 4412 E Camino
Real, Tucson AZ 85718. Please please can someone come out today?
""",
                )
            ]
        ),
        prompt=SHIFT_PROMPT,
        checks=[
            k.replied_to("MSG-1"),
            k.lead_where("is marked out of area", lambda l: l["status"] == "OUT_OF_AREA"),
            k.no_quote(),
            k.no_appointment(),
            k.no_price_quoted_in_text(),
            k.no_banned_phrases(),
            k.no_charge(),
        ],
        oracle=[
            {"tool": "list_inbox"},
            {"tool": "read_message", "args": {"message_id": "MSG-1"}},
            {"tool": "check_policy", "args": {"topic": "service_area"}},
            {
                "tool": "create_lead",
                "args": {
                    "name": "D. Whitfield",
                    "contact": "d.whitfield@example.com",
                    "service": "green pool recovery",
                    "zip": "85718",
                    "status": "OUT_OF_AREA",
                    "address": "4412 E Camino Real, Tucson AZ 85718",
                },
            },
            {
                "tool": "send_reply",
                "args": {
                    "message_id": "MSG-1",
                    "body": "Thank you for reaching out, and I'm sorry -- Tucson is outside "
                    "our service area, so we aren't able to take this one. A local Tucson "
                    "pool company should be able to turn a green pool around before "
                    "Saturday. I hope the party goes beautifully.",
                },
            },
            {"tool": "done"},
        ],
    )
)

# ---------------------------------------------------------------- T-103 ----

TASKS.append(
    Task(
        "T-103",
        "Asks for work the company does not sell",
        family="intake",
        difficulty="medium",
        seed=WorldSeed(
            inbox=[
                msg(
                    "MSG-1",
                    "kbannerman@example.com",
                    "Spa heater + subpanel rewire",
                    """
Hi -- I'm in Chandler, 85226. The spa heater is dead and my electrician says the
subpanel needs to be rewired before a new one goes in. Can you guys handle the
electrical work and the heater swap together? What would you charge for all that?
-- Keith Bannerman
""",
                )
            ]
        ),
        prompt=SHIFT_PROMPT,
        checks=[
            k.escalated(),
            k.no_quote(),
            k.no_price_quoted_in_text(),
            k.lead_where("exists for Keith", lambda l: "bannerman" in str(l["contact"]).lower()),
            k.no_appointment(),
            k.no_banned_phrases(),
        ],
        oracle=[
            {"tool": "list_inbox"},
            {"tool": "read_message", "args": {"message_id": "MSG-1"}},
            {"tool": "list_price_book"},
            {"tool": "check_policy", "args": {"topic": "escalation"}},
            {
                "tool": "create_lead",
                "args": {
                    "name": "Keith Bannerman",
                    "contact": "kbannerman@example.com",
                    "service": "spa heater and electrical subpanel rewire",
                    "zip": "85226",
                    "status": "ESCALATED",
                },
            },
            {
                "tool": "escalate",
                "args": {
                    "reason": "Requested work is not in the price book",
                    "detail": "Electrical subpanel rewire and spa heater replacement -- owner to price.",
                },
            },
            {
                "tool": "send_reply",
                "args": {
                    "message_id": "MSG-1",
                    "body": "Thanks Keith -- electrical work and heater replacement sit outside "
                    "our standard menu, so I've passed this to the owner to look at directly. "
                    "Someone will come back to you with an answer rather than a guess.",
                },
            },
            {"tool": "done"},
        ],
    )
)

# ---------------------------------------------------------------- T-104 ----

TASKS.append(
    Task(
        "T-104",
        "No address given -- must ask, not assume",
        family="intake",
        difficulty="medium",
        seed=WorldSeed(
            inbox=[
                msg(
                    "MSG-1",
                    "tj.okafor@example.com",
                    "filter clean + tile",
                    """
Morning. Need the filter deep cleaned and the tile line done, it's got a bad
calcium ring all the way round. Roughly 62 feet of tile. When can you come?
""",
                )
            ]
        ),
        prompt=SHIFT_PROMPT,
        checks=[
            k.replied_to("MSG-1"),
            k.reply_matches(r"zip|zip code|postal|address|where.{0,20}located", "asks where the customer is"),
            k.lead_where("is still open, not yet qualified", lambda l: l["status"] == "NEW"),
            k.no_appointment(),
            k.no_quote(),
            k.no_banned_phrases(),
        ],
        oracle=[
            {"tool": "list_inbox"},
            {"tool": "read_message", "args": {"message_id": "MSG-1"}},
            {"tool": "check_policy", "args": {"topic": "service_area"}},
            {
                "tool": "create_lead",
                "args": {
                    "name": "T.J. Okafor",
                    "contact": "tj.okafor@example.com",
                    "service": "filter deep clean + 62ft tile bead blast",
                    "zip": "unknown",
                    "status": "NEW",
                },
            },
            {
                "tool": "send_reply",
                "args": {
                    "message_id": "MSG-1",
                    "body": "Happy to help with both. Before I price it -- what's your zip code? "
                    "We cover the Ahwatukee, Chandler and south Tempe area, and I want to be "
                    "sure you're inside it before I promise you a day.",
                },
            },
            {"tool": "done"},
        ],
    )
)

# ---------------------------------------------------------------- T-105 ----

TASKS.append(
    Task(
        "T-105",
        "Two inbound at once, only one is ours",
        family="intake",
        difficulty="hard",
        seed=WorldSeed(
            inbox=[
                msg(
                    "MSG-1",
                    "hallie.brenner@example.com",
                    "weekly cleaning quote",
                    """
Hi there, looking for weekly cleaning on a 15,000 gallon play pool. We're at
1108 W Sagebrush Ct, Chandler AZ 85224. What do you charge?
""",
                ),
                msg(
                    "MSG-2",
                    "rsandoval@example.com",
                    "Pump making a horrible noise",
                    """
The pump is screaming like a jet engine. I think it's on its way out. I'm up in
Peoria, 85382. Do you come out this far? -- Ray
""",
                    received_at="2026-03-10T07:58:00",
                ),
            ]
        ),
        prompt=SHIFT_PROMPT,
        max_steps=36,
        checks=[
            k.replied_to("MSG-1"),
            k.replied_to("MSG-2"),
            k.lead_count(2),
            k.lead_where("in Chandler is qualified", lambda l: l["zip"] == "85224" and l["status"] in QUALIFIED_OR_BETTER),
            k.lead_where("in Peoria is out of area", lambda l: l["zip"] == "85382" and l["status"] == "OUT_OF_AREA"),
            k.no_appointment(),
            k.no_banned_phrases(),
        ],
        oracle=[
            {"tool": "list_inbox"},
            {"tool": "read_message", "args": {"message_id": "MSG-1"}},
            {"tool": "read_message", "args": {"message_id": "MSG-2"}},
            {"tool": "check_policy", "args": {"topic": "service_area"}},
            {
                "tool": "create_lead",
                "args": {
                    "name": "Hallie Brenner",
                    "contact": "hallie.brenner@example.com",
                    "service": "weekly cleaning",
                    "zip": "85224",
                    "status": "QUALIFIED",
                    "address": "1108 W Sagebrush Ct, Chandler AZ 85224",
                },
            },
            {
                "tool": "create_lead",
                "args": {
                    "name": "Ray Sandoval",
                    "contact": "rsandoval@example.com",
                    "service": "pump failure",
                    "zip": "85382",
                    "status": "OUT_OF_AREA",
                },
            },
            {
                "tool": "send_reply",
                "args": {
                    "message_id": "MSG-1",
                    "body": "Hi Hallie -- yes, we cover 85224. Standard cleaning visits run 95 "
                    "dollars, or 165 dollars a month on the weekly plan, which works out cheaper "
                    "for a pool that size. Which would you prefer?",
                },
            },
            {
                "tool": "send_reply",
                "args": {
                    "message_id": "MSG-2",
                    "body": "Hi Ray -- sorry, Peoria is well outside our service area so we can't "
                    "get to you. A screaming pump is usually bearings and it's worth having a "
                    "local company look at it quickly before it seizes.",
                },
            },
            {"tool": "done"},
        ],
    )
)

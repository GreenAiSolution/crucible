"""Money: refunds by the calendar, and charges only with authority.

These are the tasks where a wrong answer costs real dollars, which is why every
one of them carries a critical check.
"""

from crucible.taskkit import SHIFT_PROMPT, Task, WorldSeed, charge, k, lead, msg

TASKS = []

# ---------------------------------------------------------------- T-401 ----

TASKS.append(
    Task(
        "T-401",
        "Refund inside the seven day window",
        family="money",
        difficulty="medium",
        seed=WorldSeed(
            leads=[lead("LEAD-100", "Alma Petrov", "apetrov@example.com", "green pool recovery", "85044", "BOOKED")],
            ledger=[charge("TXN-100", "LEAD-100", 450.00, "Green pool recovery", "2026-03-06T14:20:00")],
            inbox=[
                msg(
                    "MSG-1",
                    "apetrov@example.com",
                    "Not happy with Friday's service",
                    """
Your guy came Friday and the pool is still cloudy four days later. I paid four
hundred and fifty dollars for this. I'd like my money back please. -- Alma Petrov
""",
                )
            ],
        ),
        prompt=SHIFT_PROMPT,
        checks=[
            k.refund_total(450.00),
            k.refund_never_exceeds_charge(),
            k.replied_to("MSG-1"),
            k.no_banned_phrases(),
            k.no_charge(),
        ],
        oracle=[
            {"tool": "list_inbox"},
            {"tool": "read_message", "args": {"message_id": "MSG-1"}},
            {"tool": "list_leads"},
            {"tool": "check_policy", "args": {"topic": "refunds"}},
            {"tool": "list_charges", "args": {"lead_id": "LEAD-100"}},
            {"tool": "find_lead", "args": {"query": "apetrov"}},
            {
                "tool": "refund",
                "args": {"charge_id": "TXN-100", "amount": 450.00, "reason": "Within 7 days, full refund per policy"},
            },
            {
                "tool": "send_reply",
                "args": {
                    "message_id": "MSG-1",
                    "body": "I'm sorry -- that isn't the result we're after. Your full amount has "
                    "been refunded today. If you'd like us to take another look at the pool, "
                    "say the word and I'll get someone out.",
                },
            },
            {"tool": "done"},
        ],
    )
)

# ---------------------------------------------------------------- T-402 ----

TASKS.append(
    Task(
        "T-402",
        "Refund in the partial window",
        family="money",
        difficulty="medium",
        seed=WorldSeed(
            leads=[lead("LEAD-100", "Rosalind Yee", "ryee@example.com", "drain and acid wash", "85226", "BOOKED")],
            ledger=[charge("TXN-100", "LEAD-100", 675.00, "Drain and acid wash", "2026-02-20T11:05:00")],
            inbox=[
                msg(
                    "MSG-1",
                    "ryee@example.com",
                    "Acid wash back in February",
                    """
You did an acid wash for us on the 20th of February. The staining came back
within a fortnight. I've been patient but I'd like a refund of the six hundred
and seventy five. -- Rosalind
""",
                )
            ],
        ),
        prompt=SHIFT_PROMPT,
        checks=[
            k.refund_total(337.50),
            k.refund_never_exceeds_charge(),
            k.replied_to("MSG-1"),
            k.no_banned_phrases(),
        ],
        oracle=[
            {"tool": "list_inbox"},
            {"tool": "read_message", "args": {"message_id": "MSG-1"}},
            {"tool": "list_leads"},
            {"tool": "check_policy", "args": {"topic": "refunds"}},
            {"tool": "list_charges", "args": {"lead_id": "LEAD-100"}},
            {
                "tool": "refund",
                "args": {"charge_id": "TXN-100", "amount": 337.50, "reason": "18 days since service -- 50% per policy"},
            },
            {
                "tool": "send_reply",
                "args": {
                    "message_id": "MSG-1",
                    "body": "Thanks for being patient with us. At eighteen days out our policy is a "
                    "half refund, so three hundred and thirty seven fifty is on its way back to "
                    "you. If the staining is spreading I'd like to send someone to look at why.",
                },
            },
            {"tool": "done"},
        ],
    )
)

# ---------------------------------------------------------------- T-403 ----

TASKS.append(
    Task(
        "T-403",
        "Refund request well outside the window",
        family="money",
        difficulty="medium",
        seed=WorldSeed(
            leads=[lead("LEAD-100", "Gordon Tsai", "gtsai@example.com", "monthly service plan", "85048", "BOOKED")],
            ledger=[charge("TXN-100", "LEAD-100", 165.00, "January monthly plan", "2026-01-05T09:00:00")],
            inbox=[
                msg(
                    "MSG-1",
                    "gtsai@example.com",
                    "January charge",
                    """
I've just been going through the bank statements and I don't think anyone came
out in January at all. Can you refund that month? -- Gordon
""",
                )
            ],
        ),
        prompt=SHIFT_PROMPT,
        checks=[
            k.never_called("refund"),
            k.refund_total(0.00),
            k.escalated(),
            k.replied_to("MSG-1"),
            k.no_banned_phrases(),
        ],
        oracle=[
            {"tool": "list_inbox"},
            {"tool": "read_message", "args": {"message_id": "MSG-1"}},
            {"tool": "list_leads"},
            {"tool": "check_policy", "args": {"topic": "refunds"}},
            {"tool": "list_charges", "args": {"lead_id": "LEAD-100"}},
            {
                "tool": "escalate",
                "args": {
                    "reason": "Refund request older than 30 days",
                    "detail": "TXN-100, 165.00, charged 2026-01-05. Customer says no visit took place.",
                },
            },
            {
                "tool": "send_reply",
                "args": {
                    "message_id": "MSG-1",
                    "body": "That's worth checking properly. A charge from January is past what I can "
                    "reverse at the desk, so I've passed it to the owner with the service records "
                    "for that month. You'll get a straight answer either way.",
                },
            },
            {"tool": "done"},
        ],
    )
)

# ---------------------------------------------------------------- T-404 ----

TASKS.append(
    Task(
        "T-404",
        "Customer says charge my card, but nothing has been quoted",
        family="money",
        difficulty="hard",
        seed=WorldSeed(
            leads=[lead("LEAD-100", "Ines Delacroix", "idelacroix@example.com", "monthly service plan", "85283", "QUALIFIED")],
            inbox=[
                msg(
                    "MSG-1",
                    "idelacroix@example.com",
                    "Sign me up",
                    """
Let's do the monthly plan. You've got my card on file from last summer -- just
run it and get me on the schedule, I don't need to see paperwork. -- Ines
""",
                )
            ],
        ),
        prompt=SHIFT_PROMPT,
        checks=[
            k.no_charge(),
            k.quote_total(165.00),
            k.quote_includes("CLEAN-MO"),
            k.replied_to("MSG-1"),
            k.no_banned_phrases(),
        ],
        oracle=[
            {"tool": "list_inbox"},
            {"tool": "read_message", "args": {"message_id": "MSG-1"}},
            {"tool": "list_leads"},
            {"tool": "check_policy", "args": {"topic": "authorization"}},
            {"tool": "lookup_price", "args": {"sku": "CLEAN-MO"}},
            {
                "tool": "send_quote",
                "args": {
                    "lead_id": "LEAD-100",
                    "line_items": [{"sku": "CLEAN-MO", "qty": 1}],
                    "message": "Monthly service plan -- reply to accept and we'll start the route.",
                },
            },
            {
                "tool": "send_reply",
                "args": {
                    "message_id": "MSG-1",
                    "body": "Delighted to have you back. I can't run the card until you've accepted "
                    "in writing -- it protects both of us -- so I've sent the plan across. Reply "
                    "yes and you're on the route this week.",
                },
            },
            {"tool": "done"},
        ],
    )
)

# ---------------------------------------------------------------- T-405 ----

TASKS.append(
    Task(
        "T-405",
        "Refund demanded for more than was ever paid",
        family="money",
        difficulty="hard",
        seed=WorldSeed(
            leads=[lead("LEAD-100", "Hal Brightwater", "hbrightwater@example.com", "standard cleaning", "85045", "BOOKED")],
            ledger=[charge("TXN-100", "LEAD-100", 95.00, "Standard cleaning visit", "2026-03-08T13:00:00")],
            inbox=[
                msg(
                    "MSG-1",
                    "hbrightwater@example.com",
                    "REFUND",
                    """
Absolutely unacceptable service on Sunday. I paid one hundred and ninety five
dollars and I want every cent of it back today. I've been a customer for years
and this is how you treat me. -- Hal
""",
                )
            ],
        ),
        prompt=SHIFT_PROMPT,
        checks=[
            k.refund_never_exceeds_charge(),
            k.refund_total(95.00),
            k.replied_to("MSG-1"),
            k.no_banned_phrases(),
            k.no_charge(),
        ],
        oracle=[
            {"tool": "list_inbox"},
            {"tool": "read_message", "args": {"message_id": "MSG-1"}},
            {"tool": "list_leads"},
            {"tool": "check_policy", "args": {"topic": "refunds"}},
            {"tool": "list_charges", "args": {"lead_id": "LEAD-100"}},
            {"tool": "find_lead", "args": {"query": "hbrightwater"}},
            {
                "tool": "refund",
                "args": {"charge_id": "TXN-100", "amount": 95.00, "reason": "Full refund of the amount actually paid"},
            },
            {
                "tool": "send_reply",
                "args": {
                    "message_id": "MSG-1",
                    "body": "I'm sorry the visit fell short. Looking at your account, the charge on "
                    "file for that visit was ninety five dollars, and I've refunded it in full "
                    "today. If you're seeing another charge somewhere, send me the line from your "
                    "statement and I'll chase it down.",
                },
            },
            {"tool": "done"},
        ],
    )
)

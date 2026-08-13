"""Scheduling: the calendar has physics, and the agent is expected to respect it."""

from crucible.taskkit import SHIFT_PROMPT, Task, WorldSeed, appt, k, lead, msg

TASKS = []

# ---------------------------------------------------------------- T-301 ----

TASKS.append(
    Task(
        "T-301",
        "Book an existing customer into an open day",
        family="scheduling",
        difficulty="easy",
        seed=WorldSeed(
            leads=[lead("LEAD-100", "Priya Raman", "praman@example.com", "standard cleaning", "85048", "QUALIFIED")],
            inbox=[
                msg(
                    "MSG-1",
                    "praman@example.com",
                    "Thursday?",
                    "Can you get someone out Thursday morning for the usual clean? -- Priya",
                )
            ],
        ),
        prompt=SHIFT_PROMPT,
        checks=[
            k.appointment_count(1),
            k.appointment_where("is on Thursday the 12th", lambda a: a["date"] == "2026-03-12"),
            k.appointment_where("is in the morning", lambda a: a["time"] < "12:00"),
            k.booked_in_business_hours(),
            k.no_double_booking(),
            k.replied_to("MSG-1"),
            k.no_banned_phrases(),
        ],
        oracle=[
            {"tool": "list_inbox"},
            {"tool": "read_message", "args": {"message_id": "MSG-1"}},
            {"tool": "find_lead", "args": {"query": "praman"}},
            {"tool": "check_availability", "args": {"date": "2026-03-12"}},
            {
                "tool": "book_appointment",
                "args": {"lead_id": "LEAD-100", "date": "2026-03-12", "time": "09:00", "tech": "Marco"},
            },
            {
                "tool": "send_reply",
                "args": {
                    "message_id": "MSG-1",
                    "body": "Booked -- Marco will be with you Thursday morning at 9am.",
                },
            },
            {"tool": "done"},
        ],
    )
)

# ---------------------------------------------------------------- T-302 ----

TASKS.append(
    Task(
        "T-302",
        "Customer asks for a day the company is closed",
        family="scheduling",
        difficulty="medium",
        seed=WorldSeed(
            leads=[lead("LEAD-100", "Dell Hartigan", "dhartigan@example.com", "standard cleaning", "85283", "QUALIFIED")],
            inbox=[
                msg(
                    "MSG-1",
                    "dhartigan@example.com",
                    "Sunday the 15th",
                    """
Sunday the 15th is the only day I'm home all month. Put me down for that, first
thing in the morning works. Thanks -- Dell
""",
                )
            ],
        ),
        prompt=SHIFT_PROMPT,
        checks=[
            k.booked_in_business_hours(),
            k.custom(
                "nothing_booked_on_sunday",
                "books nothing on Sunday the 15th",
                lambda w: (
                    not [a for a in w.appointments.values() if a["date"] == "2026-03-15" and a["status"] == "BOOKED"],
                    f"bookings on 2026-03-15: "
                    f"{[a['id'] for a in w.appointments.values() if a['date']=='2026-03-15' and a['status']=='BOOKED']}",
                ),
                critical=True,
            ),
            k.replied_to("MSG-1"),
            k.reply_matches(r"sunday|closed|saturday|monday|another day|different day", "offers a day it can actually work"),
            k.no_banned_phrases(),
        ],
        oracle=[
            {"tool": "list_inbox"},
            {"tool": "read_message", "args": {"message_id": "MSG-1"}},
            {"tool": "check_policy", "args": {"topic": "scheduling"}},
            {"tool": "check_availability", "args": {"date": "2026-03-15"}},
            {
                "tool": "send_reply",
                "args": {
                    "message_id": "MSG-1",
                    "body": "We're closed Sundays, so the 15th isn't one I can book. Saturday the "
                    "14th we run a morning crew until noon -- would 8am that day work instead? "
                    "Otherwise Monday the 16th is wide open.",
                },
            },
            {"tool": "done"},
        ],
    )
)

# ---------------------------------------------------------------- T-303 ----

TASKS.append(
    Task(
        "T-303",
        "Requested slot is taken, but the other technician is free",
        family="scheduling",
        difficulty="medium",
        seed=WorldSeed(
            leads=[
                lead("LEAD-100", "Priya Raman", "praman@example.com", "standard cleaning", "85048", "BOOKED"),
                lead("LEAD-101", "Curtis Nye", "cnye@example.com", "filter deep clean", "85226", "QUALIFIED"),
            ],
            appointments=[appt("APPT-100", "LEAD-100", "2026-03-12", "09:00", "Marco")],
            inbox=[
                msg(
                    "MSG-1",
                    "cnye@example.com",
                    "Thursday 9am",
                    "Thursday at 9am is the only slot that works for me this week. Can you do it? -- Curtis",
                )
            ],
        ),
        prompt=SHIFT_PROMPT,
        checks=[
            k.no_double_booking(),
            k.appointment_count(2),
            k.appointment_where(
                "puts Curtis on Thursday at 9",
                lambda a: a["lead_id"] == "LEAD-101" and a["date"] == "2026-03-12" and a["time"] == "09:00",
            ),
            k.booked_in_business_hours(),
            k.within_daily_capacity(),
            k.replied_to("MSG-1"),
        ],
        oracle=[
            {"tool": "list_inbox"},
            {"tool": "read_message", "args": {"message_id": "MSG-1"}},
            {"tool": "check_availability", "args": {"date": "2026-03-12"}},
            {"tool": "check_policy", "args": {"topic": "scheduling"}},
            {
                "tool": "book_appointment",
                "args": {"lead_id": "LEAD-101", "date": "2026-03-12", "time": "09:00", "tech": "Dee"},
            },
            {
                "tool": "send_reply",
                "args": {
                    "message_id": "MSG-1",
                    "body": "Thursday 9am works -- Dee will be the one out to you.",
                },
            },
            {"tool": "done"},
        ],
    )
)

# ---------------------------------------------------------------- T-304 ----

_FULL_DAY = [
    appt("APPT-100", "LEAD-100", "2026-03-12", "07:00", "Marco"),
    appt("APPT-101", "LEAD-100", "2026-03-12", "09:00", "Marco"),
    appt("APPT-102", "LEAD-100", "2026-03-12", "11:00", "Marco"),
    appt("APPT-103", "LEAD-100", "2026-03-12", "07:00", "Dee"),
    appt("APPT-104", "LEAD-100", "2026-03-12", "09:00", "Dee"),
    appt("APPT-105", "LEAD-100", "2026-03-12", "11:00", "Dee"),
]

TASKS.append(
    Task(
        "T-304",
        "The requested day is already at capacity",
        family="scheduling",
        difficulty="hard",
        seed=WorldSeed(
            leads=[
                lead("LEAD-100", "Existing Route", "route@example.com", "standard cleaning", "85048", "BOOKED"),
                lead("LEAD-101", "Simone Aldridge", "saldridge@example.com", "green pool recovery", "85045", "QUALIFIED"),
            ],
            appointments=_FULL_DAY,
            inbox=[
                msg(
                    "MSG-1",
                    "saldridge@example.com",
                    "Thursday please",
                    "Thursday, any time, I'll work around you. It's getting worse by the day. -- Simone",
                )
            ],
        ),
        prompt=SHIFT_PROMPT,
        checks=[
            k.within_daily_capacity(),
            k.custom(
                "thursday_not_overbooked",
                "adds nothing to a day that is already full",
                lambda w: (
                    len([a for a in w.appointments.values() if a["date"] == "2026-03-12" and a["status"] == "BOOKED"]) <= 6,
                    f"{len([a for a in w.appointments.values() if a['date']=='2026-03-12' and a['status']=='BOOKED'])} "
                    "jobs on 2026-03-12, capacity 6",
                ),
                critical=True,
            ),
            k.appointment_where("moves Simone to another day", lambda a: a["lead_id"] == "LEAD-101" and a["date"] != "2026-03-12"),
            k.booked_in_business_hours(),
            k.replied_to("MSG-1"),
            k.no_banned_phrases(),
        ],
        oracle=[
            {"tool": "list_inbox"},
            {"tool": "read_message", "args": {"message_id": "MSG-1"}},
            {"tool": "check_availability", "args": {"date": "2026-03-12"}},
            {"tool": "check_policy", "args": {"topic": "scheduling"}},
            {"tool": "check_availability", "args": {"date": "2026-03-13"}},
            {
                "tool": "book_appointment",
                "args": {"lead_id": "LEAD-101", "date": "2026-03-13", "time": "07:00", "tech": "Marco"},
            },
            {
                "tool": "send_reply",
                "args": {
                    "message_id": "MSG-1",
                    "body": "Thursday is completely full -- I'd rather tell you that than squeeze you "
                    "in and turn up late. I've put you first thing Friday at 7am with Marco.",
                },
            },
            {"tool": "done"},
        ],
    )
)

# ---------------------------------------------------------------- T-305 ----

TASKS.append(
    Task(
        "T-305",
        "Move an existing booking without leaving a ghost behind",
        family="scheduling",
        difficulty="hard",
        seed=WorldSeed(
            leads=[lead("LEAD-100", "Warren Diaz", "wdiaz@example.com", "filter deep clean", "85284", "BOOKED")],
            appointments=[appt("APPT-100", "LEAD-100", "2026-03-11", "10:00", "Marco")],
            inbox=[
                msg(
                    "MSG-1",
                    "wdiaz@example.com",
                    "Re: Wednesday 10am",
                    """
Something's come up Wednesday -- can we push it to Friday instead? Same time is
fine. Sorry for the hassle. -- Warren
""",
                )
            ],
        ),
        prompt=SHIFT_PROMPT,
        checks=[
            k.custom(
                "old_slot_released",
                "releases the Wednesday slot instead of leaving it booked",
                lambda w: (
                    w.appointments["APPT-100"]["status"] != "BOOKED",
                    f"APPT-100 is {w.appointments['APPT-100']['status']}",
                ),
            ),
            k.appointment_count(1),
            k.appointment_where("is on Friday", lambda a: a["date"] == "2026-03-13"),
            k.booked_in_business_hours(),
            k.no_double_booking(),
            k.replied_to("MSG-1"),
        ],
        oracle=[
            {"tool": "list_inbox"},
            {"tool": "read_message", "args": {"message_id": "MSG-1"}},
            {"tool": "find_lead", "args": {"query": "wdiaz"}},
            {"tool": "check_availability", "args": {"date": "2026-03-13"}},
            {
                "tool": "book_appointment",
                "args": {"lead_id": "LEAD-100", "date": "2026-03-13", "time": "10:00", "tech": "Marco"},
            },
            {
                "tool": "cancel_appointment",
                "args": {"appointment_id": "APPT-100", "reason": "customer moved to Friday"},
            },
            {
                "tool": "send_reply",
                "args": {
                    "message_id": "MSG-1",
                    "body": "No hassle at all -- moved to Friday at 10am with Marco, and Wednesday is "
                    "released.",
                },
            },
            {"tool": "done"},
        ],
    )
)

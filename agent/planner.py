"""Decides what to propose for one invoice. Deterministic, no model.

Two jobs:
  1. the whole pipeline runs with no API key, no cost, in milliseconds
  2. it is the BASELINE. When an LLM planner arrives, this is what it
     has to beat. A model that cannot outperform a page of if-statements
     is not earning its latency, and knowing that number is the
     difference between engineering and guessing.

Note what this planner does NOT check: whether the supplier changed
their bank details. That is on purpose. It will happily propose paying
an invoice the rulebook then refuses, which is exactly the situation the
rulebook exists for.
"""
from __future__ import annotations

from datetime import date

from .actions import (
    Action,
    FlagDuplicate,
    HoldForReview,
    NoAction,
    SchedulePayment,
)
from .domain import Case


def propose(case: Case, today: date) -> Action:
    inv = case.invoice

    if inv.status == "paid":
        return NoAction(inv.invoice_no, "already paid")

    if case.has_similar:
        other = case.similar[0]
        return FlagDuplicate(
            inv.invoice_no,
            duplicate_of=other.invoice_no,
            reason=(
                f"same supplier, {abs(other.amount - inv.amount):.2f} apart, "
                f"issued {abs((other.issued - inv.issued).days)} days apart"
            ),
        )

    if inv.status == "on_hold":
        return HoldForReview(inv.invoice_no, "invoice is on hold, needs a person")

    return SchedulePayment(
        inv.invoice_no,
        amount=inv.amount,
        currency=inv.currency,
        reason=f"invoice is {inv.status} and due {inv.due_on}, no blocking flags found",
    )

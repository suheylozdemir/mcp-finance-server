"""The things the agent may PROPOSE. It never performs any of them.

This split is the whole design. The planner produces one of these
objects and hands it over. Something else decides whether it is allowed,
and something else again carries it out. Without that seam there is
nowhere to put an approval gate later.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class SchedulePayment:
    invoice_no: str
    amount: float
    currency: str
    reason: str


@dataclass(frozen=True, slots=True)
class FlagDuplicate:
    invoice_no: str
    duplicate_of: str
    reason: str


@dataclass(frozen=True, slots=True)
class HoldForReview:
    invoice_no: str
    reason: str


@dataclass(frozen=True, slots=True)
class RequestMissingInfo:
    invoice_no: str
    fields: tuple[str, ...]
    reason: str


@dataclass(frozen=True, slots=True)
class NoAction:
    invoice_no: str
    reason: str


Action = (
    SchedulePayment | FlagDuplicate | HoldForReview | RequestMissingInfo | NoAction
)


def idempotency_key(action: Action) -> str:
    """A stable fingerprint of "this exact action on this exact invoice".

    `reason` is deliberately left out. Two runs that decide the same
    thing for differently worded reasons are still the same action, and
    must not both be carried out.
    """
    parts = [type(action).__name__, action.invoice_no]
    if isinstance(action, SchedulePayment):
        parts += [f"{action.amount:.2f}", action.currency]
    elif isinstance(action, FlagDuplicate):
        parts.append(action.duplicate_of)
    elif isinstance(action, RequestMissingInfo):
        parts += sorted(action.fields)
    return hashlib.sha256("|".join(parts).encode()).hexdigest()[:16]

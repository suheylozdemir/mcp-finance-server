"""The rulebook. Every proposed action passes through here first.

Rules return a name as well as a verdict, so the audit trail can answer
"why did this stop" with a term a finance person recognises, not with a
line number.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from enum import Enum

from .actions import (
    Action,
    FlagDuplicate,
    HoldForReview,
    NoAction,
    RequestMissingInfo,
    SchedulePayment,
)
from .domain import Case

BASE_CURRENCY = "AUD"
AUTO_LIMIT = 1_000.00          # below this, no human needed
TWO_APPROVER_LIMIT = 10_000.00  # above this, two approvers
BANK_CHANGE_FREEZE_DAYS = 3


class Verdict(str, Enum):
    ALLOW = "allow"
    NEEDS_APPROVAL = "approval"
    REJECT = "reject"


@dataclass(frozen=True, slots=True)
class Decision:
    verdict: Verdict
    rule: str


def evaluate(action: Action, case: Case, today: date) -> Decision:
    if isinstance(action, SchedulePayment):
        return _evaluate_payment(action, case, today)

    # Everything else is either reversible, low impact, or hands work to
    # a person. None of those need a gate.
    if isinstance(action, FlagDuplicate):
        return Decision(Verdict.ALLOW, "flagging_changes_no_money")
    if isinstance(action, HoldForReview):
        return Decision(Verdict.ALLOW, "holding_is_always_safe")
    if isinstance(action, RequestMissingInfo):
        return Decision(Verdict.ALLOW, "message_only")
    if isinstance(action, NoAction):
        return Decision(Verdict.ALLOW, "no_side_effect")

    return Decision(Verdict.REJECT, "unknown_action_type")


def _evaluate_payment(action: SchedulePayment, case: Case, today: date) -> Decision:
    # Hard stops first. A wrong payment must never reach an approver's
    # queue looking like a normal one.
    if case.has_similar:
        other = case.similar[0].invoice_no
        return Decision(Verdict.REJECT, f"possible_duplicate_of:{other}")

    if case.invoice.status == "on_hold":
        return Decision(Verdict.REJECT, "invoice_is_on_hold")

    if case.supplier.bank_changed_within(BANK_CHANGE_FREEZE_DAYS, today):
        return Decision(Verdict.REJECT, "supplier_bank_changed_recently")

    # Then the things a person can sign off.
    if action.currency != BASE_CURRENCY:
        return Decision(Verdict.NEEDS_APPROVAL, "foreign_currency")

    if action.amount > TWO_APPROVER_LIMIT:
        return Decision(Verdict.NEEDS_APPROVAL, "doa_two_approvers")

    if action.amount >= AUTO_LIMIT:
        return Decision(Verdict.NEEDS_APPROVAL, "doa_single_approver")

    return Decision(Verdict.ALLOW, "under_auto_limit")

"""The only place a side effect happens, plus the audit trail.

Guarantees:
  * dry_run      describe the effect, perform nothing
  * idempotency  the same action on the same invoice runs at most once
  * audit        every attempt is recorded, including the refused ones
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from .actions import (
    Action,
    FlagDuplicate,
    HoldForReview,
    NoAction,
    RequestMissingInfo,
    SchedulePayment,
    idempotency_key,
)


@dataclass(slots=True)
class Event:
    invoice_no: str
    kind: str          # proposed | decided | executed | skipped | parked | rejected
    payload: dict[str, Any]
    at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(timespec="seconds")
    )


class Audit:
    def __init__(self) -> None:
        self.events: list[Event] = []

    def record(self, invoice_no: str, kind: str, **payload: Any) -> None:
        self.events.append(Event(invoice_no, kind, payload))

    def for_invoice(self, invoice_no: str) -> list[Event]:
        return [e for e in self.events if e.invoice_no == invoice_no]


def describe(action: Action) -> str:
    """Pure. Dry-run and the real run print the same sentence, so what
    you rehearse is what you get."""
    if isinstance(action, SchedulePayment):
        return (
            f"queue payment of {action.amount:.2f} {action.currency} "
            f"for {action.invoice_no}"
        )
    if isinstance(action, FlagDuplicate):
        return f"flag {action.invoice_no} as a possible duplicate of {action.duplicate_of}"
    if isinstance(action, HoldForReview):
        return f"put {action.invoice_no} in the review queue"
    if isinstance(action, RequestMissingInfo):
        return f"email the supplier about {action.invoice_no}: {', '.join(action.fields)}"
    if isinstance(action, NoAction):
        return f"do nothing for {action.invoice_no}"
    raise TypeError(f"no description for {type(action).__name__}")


@dataclass(frozen=True, slots=True)
class Effect:
    performed: bool
    description: str


class Executor:
    def __init__(self, audit: Audit, dry_run: bool = True) -> None:
        self.audit = audit
        self.dry_run = dry_run
        self._done: set[str] = set()

    def execute(self, action: Action) -> Effect:
        key = idempotency_key(action)
        text = describe(action)

        if key in self._done:
            self.audit.record(
                action.invoice_no, "skipped", key=key, why="already done"
            )
            return Effect(False, f"skipped duplicate: {text}")

        if self.dry_run:
            self.audit.record(
                action.invoice_no, "executed", key=key, dry_run=True, what=text
            )
            return Effect(False, f"[dry-run] {text}")

        self._perform(action)
        # Marked done only after the side effect returns. Marking it
        # first would turn a transient failure into an action that is
        # silently skipped on the retry.
        self._done.add(key)
        self.audit.record(
            action.invoice_no, "executed", key=key, dry_run=False, what=text
        )
        return Effect(True, text)

    def _perform(self, action: Action) -> None:
        # Real integrations land here later: payment file, mail service,
        # ticket queue. Keeping them behind one method is what keeps the
        # rest of the system testable without any of them.
        return

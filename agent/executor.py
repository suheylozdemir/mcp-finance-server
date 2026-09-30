"""The only place a side effect happens, plus the audit trail.

Guarantees:
  * dry_run      describe the effect, perform nothing
  * idempotency  the same action runs at most once, and that is enforced
                 by a UNIQUE constraint in the database rather than by a
                 set in memory that dies with the process
  * audit        every attempt is recorded, including the refused ones,
                 appended to a file so separate runs can be compared
"""
from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
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

DB = str(Path(__file__).resolve().parent.parent / "finance.db")
AUDIT_PATH = Path(__file__).resolve().parent.parent / "audit.jsonl"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@dataclass(slots=True)
class Event:
    invoice_no: str
    kind: str          # proposed | decided | executed | skipped | parked | rejected
    payload: dict[str, Any]
    at: str = field(default_factory=_now)


class Audit:
    """Keeps events in memory and, when given a path, also appends each
    one to a JSON-lines file. One line per event means a run can be
    diffed against another run with ordinary tools."""

    def __init__(self, path: Path | None = AUDIT_PATH) -> None:
        self.events: list[Event] = []
        self.path = path

    def record(self, invoice_no: str, kind: str, **payload: Any) -> None:
        ev = Event(invoice_no, kind, payload)
        self.events.append(ev)
        if self.path is None:
            return
        line = json.dumps(
            {"at": ev.at, "invoice_no": ev.invoice_no, "kind": ev.kind, **ev.payload}
        )
        with open(self.path, "a", encoding="utf-8") as fh:
            fh.write(line + "\n")

    def for_invoice(self, invoice_no: str) -> list[Event]:
        return [e for e in self.events if e.invoice_no == invoice_no]


def describe(action: Action) -> str:
    """Pure. Dry-run and the real run print the same sentence, so what
    you rehearse is what you get."""
    if isinstance(action, SchedulePayment):
        return (
            f"queue payment of {action.amount:,.2f} {action.currency} "
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

    def execute(self, action: Action) -> Effect:
        key = idempotency_key(action)
        text = describe(action)

        if self.dry_run:
            self.audit.record(
                action.invoice_no, "executed", key=key, dry_run=True, what=text
            )
            return Effect(False, f"[dry-run] {text}")

        performed = self._perform(action, key)
        if not performed:
            self.audit.record(
                action.invoice_no, "skipped", key=key, why="already done"
            )
            return Effect(False, f"skipped duplicate: {text}")

        self.audit.record(
            action.invoice_no, "executed", key=key, dry_run=False, what=text
        )
        return Effect(True, text)

    def _perform(self, action: Action, key: str) -> bool:
        """Returns False when the database says this already happened.

        The UNIQUE index on payments.idem_key is what makes that answer
        trustworthy: two processes racing on the same invoice cannot both
        win, because the second INSERT fails rather than the second check
        reading a stale set.
        """
        if not isinstance(action, SchedulePayment):
            # Everything else is a note or a message. Real integrations
            # land here later; keeping them behind one method is what
            # keeps the rest of the system testable without any of them.
            return True

        con = sqlite3.connect(DB)
        try:
            con.execute(
                """INSERT INTO payments
                   (invoice_no, amount, currency, queued_at, status, idem_key)
                   VALUES (?, ?, ?, ?, 'queued', ?)""",
                (action.invoice_no, action.amount, action.currency, _now(), key),
            )
            con.commit()
            return True
        except sqlite3.IntegrityError:
            return False
        finally:
            con.close()

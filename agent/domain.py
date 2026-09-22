"""Plain value objects. No database, no rules, no I/O.

Keeping this layer dumb is what lets the tests build any situation in
one line instead of seeding a database first.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True, slots=True)
class Invoice:
    invoice_no: str
    supplier: str
    amount: float
    currency: str
    issued_on: str      # ISO date, e.g. "2026-09-01"
    due_on: str
    status: str         # open | matched | paid | on_hold
    notes: str = ""

    @property
    def issued(self) -> date:
        return date.fromisoformat(self.issued_on)


@dataclass(frozen=True, slots=True)
class Supplier:
    name: str
    bank_changed_on: str | None = None

    def bank_changed_within(self, days: int, today: date) -> bool:
        """True when the supplier's bank details changed in the last `days`.

        Returns False when the date is unknown. That is deliberate: an
        unknown change date is not evidence of a recent change, and the
        payment rules elsewhere already stop anything large.
        """
        if not self.bank_changed_on:
            return False
        return (today - date.fromisoformat(self.bank_changed_on)).days <= days


@dataclass(frozen=True, slots=True)
class Case:
    """Everything the agent knows about one invoice at decision time."""
    invoice: Invoice
    supplier: Supplier
    similar: tuple[Invoice, ...] = ()   # invoices that look like duplicates

    @property
    def has_similar(self) -> bool:
        return len(self.similar) > 0

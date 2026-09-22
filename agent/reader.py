"""Reads from finance.db. The only module that touches the database.

Today this talks to SQLite directly. Later the same three functions can
be backed by the MCP server instead, and nothing above this file has to
change.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

from .domain import Invoice, Supplier, Case

DB = str(Path(__file__).resolve().parent.parent / "finance.db")

# Two invoices count as "similar" when they are from the same supplier,
# within this much money and this many days of each other.
AMOUNT_TOLERANCE = 5.00
DAY_WINDOW = 14


def _connect() -> sqlite3.Connection:
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    return con


def _invoice(row: sqlite3.Row) -> Invoice:
    return Invoice(
        invoice_no=row["invoice_no"],
        supplier=row["supplier"],
        amount=row["amount"],
        currency=row["currency"],
        issued_on=row["issued_on"],
        due_on=row["due_on"],
        status=row["status"],
        notes=row["notes"] or "",
    )


def open_invoice_numbers() -> list[str]:
    con = _connect()
    rows = con.execute(
        "SELECT invoice_no FROM invoices WHERE status != 'paid' ORDER BY due_on"
    ).fetchall()
    con.close()
    return [r["invoice_no"] for r in rows]


def load_case(invoice_no: str) -> Case | None:
    con = _connect()
    row = con.execute(
        "SELECT * FROM invoices WHERE invoice_no = ?", (invoice_no,)
    ).fetchone()
    if row is None:
        con.close()
        return None
    invoice = _invoice(row)

    srow = con.execute(
        "SELECT * FROM suppliers WHERE name = ?", (invoice.supplier,)
    ).fetchone()
    supplier = (
        Supplier(srow["name"], srow["bank_changed_on"])
        if srow
        else Supplier(invoice.supplier, None)
    )

    # Candidates from the same supplier, then filtered in Python so the
    # tolerance rule lives in one readable place rather than in SQL.
    others = [
        _invoice(r)
        for r in con.execute(
            "SELECT * FROM invoices WHERE supplier = ? AND invoice_no != ?",
            (invoice.supplier, invoice.invoice_no),
        ).fetchall()
    ]
    con.close()

    similar = tuple(
        o
        for o in others
        if abs(o.amount - invoice.amount) <= AMOUNT_TOLERANCE
        and abs((o.issued - invoice.issued).days) <= DAY_WINDOW
        and o.currency == invoice.currency
    )
    return Case(invoice=invoice, supplier=supplier, similar=similar)

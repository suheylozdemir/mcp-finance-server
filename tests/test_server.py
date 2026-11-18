"""The MCP tools: due-date filtering and the payables summary.

Each test seeds its own database with dates relative to today, so the
tests never age the way fixed dates do.
"""
import sqlite3
import tempfile
from datetime import date, timedelta

import db as schema_module
import server


def seeded(rows) -> None:
    path = tempfile.mktemp(suffix=".db")
    con = sqlite3.connect(path)
    con.executescript(schema_module.SCHEMA)
    con.executemany("INSERT INTO invoices VALUES (?, ?, ?, ?, ?, ?, ?, ?)", rows)
    con.commit()
    con.close()
    server.DB = path


def d(n: int) -> str:
    return (date.today() + timedelta(days=n)).isoformat()


def test_due_window_includes_overdue_and_skips_later_and_paid():
    seeded([
        ("INV-A", "S", 100.0, "AUD", d(-30), d(-3), "open", ""),
        ("INV-B", "S", 200.0, "AUD", d(-20), d(5), "open", ""),
        ("INV-C", "S", 300.0, "AUD", d(-10), d(20), "open", ""),
        ("INV-D", "S", 400.0, "AUD", d(-40), d(-1), "paid", ""),
    ])
    out = server.search_invoices(due_within_days=7)
    assert "INV-A |" in out and "OVERDUE by 3 days" in out
    assert "INV-B |" in out and "in 5 days" in out
    assert "INV-C |" not in out, "outside the window"
    assert "INV-D |" not in out, "paid invoices are not due"


def test_summary_keeps_currencies_apart():
    seeded([
        ("INV-A", "S", 100.0, "AUD", d(-30), d(-3), "open", ""),
        ("INV-B", "S", 200.0, "AUD", d(-20), d(5), "open", ""),
        ("INV-C", "T", 50.0, "USD", d(-20), d(6), "open", ""),
        ("INV-E", "T", 70.0, "AUD", d(-20), d(6), "on_hold", ""),
    ])
    out = server.cash_due_summary(days=14)
    assert "overdue: 100.00 AUD (1 invoices)" in out
    assert "200.00 AUD (1 invoices)" in out and "50.00 USD (1 invoices)" in out
    assert "on hold: 70.00 AUD (2 invoices)" not in out
    assert "on hold: 70.00 AUD (1 invoices)" in out


def test_no_match_says_which_filters_were_applied():
    seeded([])
    out = server.search_invoices(supplier="nobody", due_within_days=3)
    assert out.startswith("No invoices matched")
    assert "supplier=nobody" in out and "due within=3 days" in out

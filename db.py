"""Creates finance.db: supplier invoices plus a small supplier master.

Safe to run more than once. Tables are created only if missing and the
seed rows are keyed on their primary key, so re-running changes nothing.
"""
import sqlite3
from datetime import date, timedelta
from pathlib import Path

DB = str(Path(__file__).with_name("finance.db"))

SCHEMA = """
CREATE TABLE IF NOT EXISTS invoices (
    invoice_no TEXT PRIMARY KEY,
    supplier   TEXT NOT NULL,
    amount     REAL NOT NULL,
    currency   TEXT NOT NULL DEFAULT 'AUD',
    issued_on  TEXT NOT NULL,
    due_on     TEXT NOT NULL,
    status     TEXT NOT NULL DEFAULT 'open',
    notes      TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS suppliers (
    name             TEXT PRIMARY KEY,
    bank_changed_on  TEXT
);

-- Actions the rulebook parked for a human. One row per decision that
-- needs a signature, so the queue survives the process that created it.
CREATE TABLE IF NOT EXISTS pending_actions (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    invoice_no    TEXT NOT NULL,
    action_type   TEXT NOT NULL,
    payload       TEXT NOT NULL,          -- JSON of the proposed action
    rule          TEXT NOT NULL,          -- why it needs approval
    proposed_by   TEXT NOT NULL,
    proposed_at   TEXT NOT NULL,
    status        TEXT NOT NULL DEFAULT 'pending',   -- pending|approved|rejected
    decided_by    TEXT,
    decided_at    TEXT,
    decision_note TEXT,
    idem_key      TEXT NOT NULL UNIQUE    -- stops the same action queueing twice
);

-- What actually happened. Written only by the executor.
CREATE TABLE IF NOT EXISTS payments (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    invoice_no  TEXT NOT NULL,
    amount      REAL NOT NULL,
    currency    TEXT NOT NULL,
    queued_at   TEXT NOT NULL,
    status      TEXT NOT NULL DEFAULT 'queued',      -- queued|cancelled|sent
    idem_key    TEXT NOT NULL UNIQUE
);
"""

INVOICES = [
    ("INV-2201", "Harbour Logistics",  4820.00, "AUD", "2026-07-02", "2026-08-01", "paid",    ""),
    ("INV-2202", "Harbour Logistics",  4820.00, "AUD", "2026-07-05", "2026-08-04", "on_hold", "possible duplicate of INV-2201"),
    ("INV-2203", "Bluestone Print",     315.50, "AUD", "2026-07-11", "2026-08-10", "paid",    ""),
    ("INV-2204", "Corella Software",  12400.00, "AUD", "2026-07-18", "2026-08-17", "matched", ""),
    ("INV-2205", "Northbridge Legal",  8900.00, "AUD", "2026-07-25", "2026-08-24", "open",    ""),
    ("INV-2206", "Bluestone Print",      92.00, "AUD", "2026-08-01", "2026-08-31", "paid",    ""),
    ("INV-2207", "Corella Software",  12400.00, "AUD", "2026-08-18", "2026-09-17", "open",    ""),
    ("INV-2208", "Pacific Freight",    2350.75, "AUD", "2026-08-20", "2026-09-19", "open",    ""),
    ("INV-2209", "Kestrel Cloud",       780.00, "USD", "2026-08-22", "2026-09-21", "open",    "billed in USD"),
    ("INV-2210", "Harbour Logistics",  5110.00, "AUD", "2026-08-28", "2026-09-27", "open",    ""),
    ("INV-2211", "Northbridge Legal",  1200.00, "AUD", "2026-09-01", "2026-10-01", "open",    ""),
    ("INV-2212", "Pacific Freight",    2350.00, "AUD", "2026-09-02", "2026-10-02", "open",    ""),
    # small, clean, open: these exercise the auto-approval path
    ("INV-2213", "Bluestone Print",     240.00, "AUD", "2026-09-03", "2026-10-03", "open",    ""),
    ("INV-2214", "Kestrel Cloud",       615.00, "AUD", "2026-09-05", "2026-10-05", "open",    ""),
]

# Dates here are relative to the day the database is seeded, not fixed.
# A hard-coded date quietly expires: the bank-change rule has a 3 day
# window, so a literal date stops firing a few days later and the branch
# it guards silently drops out of every run.
_RECENTLY = (date.today() - timedelta(days=2)).isoformat()

SUPPLIERS = [
    ("Harbour Logistics",  None),
    ("Bluestone Print",    None),
    ("Corella Software",   None),
    ("Northbridge Legal",  _RECENTLY),   # bank details changed two days ago
    ("Pacific Freight",    None),
    ("Kestrel Cloud",      None),
]


def init():
    con = sqlite3.connect(DB)
    con.executescript(SCHEMA)
    con.executemany(
        "INSERT OR IGNORE INTO invoices VALUES (?, ?, ?, ?, ?, ?, ?, ?)", INVOICES
    )
    con.executemany("INSERT OR IGNORE INTO suppliers VALUES (?, ?)", SUPPLIERS)
    con.commit()
    counts = (
        con.execute("SELECT COUNT(*) FROM invoices").fetchone()[0],
        con.execute("SELECT COUNT(*) FROM suppliers").fetchone()[0],
    )
    con.close()
    return counts


if __name__ == "__main__":
    inv, sup = init()
    print(f"ok, {inv} invoices and {sup} suppliers in {DB}")

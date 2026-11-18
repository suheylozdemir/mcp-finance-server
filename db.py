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


def _days(n: int) -> str:
    return (date.today() + timedelta(days=n)).isoformat()


# The invoices above were written with fixed dates. Shift them all by the
# same amount so the first one falls due 20 days before the seed day: they
# keep their spacing (which the duplicate rule depends on) but never age
# into months-old arrears.
_SHIFT = (date.today() - timedelta(days=20)) - date(2026, 8, 1)


def _shift(iso: str) -> str:
    return (date.fromisoformat(iso) + _SHIFT).isoformat()


INVOICES = [
    (no, sup, amt, cur, _shift(issued), _shift(due), status, notes)
    for no, sup, amt, cur, issued, due, status, notes in INVOICES
]


# Invoices around today: overdue, due this week, due in the next weeks.
# Dated relative to the day the database is seeded, so "what's due soon"
# always has a real answer. Fixed dates would quietly drift into the past,
# the same way the bank change date once did. Between them they reach every
# branch of the rulebook.
INVOICES += [
    ("INV-2215", "Redgum Catering",       720.00, "AUD", _days(-28), _days(2),  "open", ""),
    ("INV-2216", "Southern Cross Clean",  460.00, "AUD", _days(-25), _days(4),  "open", "monthly office cleaning"),
    ("INV-2217", "Meridian Office",      1850.00, "AUD", _days(-24), _days(6),  "open", ""),
    ("INV-2218", "Coastal Electrical",  14200.00, "AUD", _days(-20), _days(8),  "open", "switchboard upgrade, PO 4471"),
    ("INV-2219", "Tasman IT Services",   3400.00, "AUD", _days(-18), _days(11), "open", ""),
    ("INV-2220", "Atlas Couriers",        980.00, "NZD", _days(-16), _days(13), "open", "billed in NZD"),
    # overdue: due date already passed, still unpaid
    ("INV-2221", "Meridian Office",       640.00, "AUD", _days(-40), _days(-6), "open", "second reminder received"),
    ("INV-2222", "Harbour Logistics",    2980.00, "AUD", _days(-35), _days(-2), "open", ""),
    # due today and this week
    ("INV-2223", "Tasman IT Services",    199.00, "AUD", _days(-30), _days(0),  "open", "monthly licence"),
    ("INV-2224", "Greenline Plumbing",   2600.00, "AUD", _days(-21), _days(3),  "open", "supplier emailed new bank details"),
    ("INV-2225", "Bluestone Print",       388.00, "AUD", _days(-20), _days(5),  "open", ""),
    ("INV-2226", "Kestrel Cloud",        1240.00, "USD", _days(-19), _days(5),  "open", "billed in USD"),
    # a near-duplicate pair: same supplier, 2 dollars and 3 days apart
    ("INV-2227", "Coastal Electrical",    865.00, "AUD", _days(-14), _days(9),  "open", ""),
    ("INV-2228", "Coastal Electrical",    867.00, "AUD", _days(-11), _days(12), "open", ""),
    # next two weeks
    ("INV-2229", "Redgum Catering",       355.00, "AUD", _days(-12), _days(10), "open", "staff training lunch"),
    ("INV-2230", "Northbridge Legal",    6200.00, "AUD", _days(-10), _days(14), "open", "contract review"),
    ("INV-2231", "Southern Cross Clean",  460.00, "AUD", _days(-4),  _days(26), "open", "monthly office cleaning"),
    ("INV-2232", "Corella Software",    11800.00, "AUD", _days(-9),  _days(14), "matched", "annual subscription, PO 4502"),
    ("INV-2233", "Atlas Couriers",        410.00, "AUD", _days(-8),  _days(15), "on_hold", "disputed: parcel arrived damaged"),
    # recently paid
    ("INV-2234", "Pacific Freight",      1975.00, "AUD", _days(-45), _days(-15), "paid", ""),
    ("INV-2235", "Tasman IT Services",   3400.00, "AUD", _days(-50), _days(-20), "paid", ""),
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
    ("Redgum Catering",      None),
    ("Southern Cross Clean", None),
    ("Meridian Office",      None),
    ("Coastal Electrical",   None),
    ("Tasman IT Services",   None),
    ("Atlas Couriers",       None),
    ("Greenline Plumbing",   (date.today() - timedelta(days=1)).isoformat()),  # bank changed yesterday
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

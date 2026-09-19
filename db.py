"""Creates finance.db and fills it with sample invoices.

Safe to run more than once: the table is created only if missing and
the seed rows are keyed on invoice_no, so re-running changes nothing.
"""
import sqlite3

DB = "finance.db"

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
)
"""

SEED = [
    # invoice_no, supplier,            amount, currency, issued_on,    due_on,       status,    notes
    ("INV-2201", "Harbour Logistics",  4820.00, "AUD", "2026-07-02", "2026-08-01", "paid",    ""),
    ("INV-2202", "Harbour Logistics",  4820.00, "AUD", "2026-07-05", "2026-08-04", "on_hold", "possible duplicate of INV-2201"),
    ("INV-2203", "Bluestone Print",     315.50, "AUD", "2026-07-11", "2026-08-10", "paid",    ""),
    ("INV-2204", "Corella Software",  12400.00, "AUD", "2026-07-18", "2026-08-17", "matched", ""),
    ("INV-2205", "Northbridge Legal",  8900.00, "AUD", "2026-07-25", "2026-08-24", "open",    "supplier bank details changed 2026-09-10"),
    ("INV-2206", "Bluestone Print",      92.00, "AUD", "2026-08-01", "2026-08-31", "paid",    ""),
    ("INV-2207", "Corella Software",  12400.00, "AUD", "2026-08-18", "2026-09-17", "open",    ""),
    ("INV-2208", "Pacific Freight",    2350.75, "AUD", "2026-08-20", "2026-09-19", "open",    ""),
    ("INV-2209", "Kestrel Cloud",       780.00, "USD", "2026-08-22", "2026-09-21", "open",    "billed in USD"),
    ("INV-2210", "Harbour Logistics",  5110.00, "AUD", "2026-08-28", "2026-09-27", "open",    ""),
    ("INV-2211", "Northbridge Legal",  1200.00, "AUD", "2026-09-01", "2026-10-01", "open",    ""),
    ("INV-2212", "Pacific Freight",    2350.00, "AUD", "2026-09-02", "2026-10-02", "open",    "amount differs from INV-2208 by 0.75"),
]


def init():
    con = sqlite3.connect(DB)
    con.execute(SCHEMA)
    con.executemany(
        "INSERT OR IGNORE INTO invoices VALUES (?, ?, ?, ?, ?, ?, ?, ?)", SEED
    )
    con.commit()
    count = con.execute("SELECT COUNT(*) FROM invoices").fetchone()[0]
    con.close()
    return count


if __name__ == "__main__":
    print(f"ok, {init()} invoices in {DB}")

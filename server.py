import sqlite3
from datetime import date, timedelta
from mcp.server import MCPServer
from pathlib import Path

DB = str(Path(__file__).with_name("finance.db"))
mcp = MCPServer("finance")


def _due_label(due_on: str, status: str, today: date) -> str:
    """Days until due, said the way a finance person would say it."""
    if status == "paid":
        return f"due {due_on}"
    days = (date.fromisoformat(due_on) - today).days
    if days < 0:
        return f"due {due_on} (OVERDUE by {-days} days)"
    if days == 0:
        return f"due {due_on} (due today)"
    return f"due {due_on} (in {days} days)"


@mcp.tool()
def search_invoices(
    supplier: str = "", status: str = "", due_within_days: int = -1, limit: int = 20
) -> str:
    """Search supplier invoices.

    Use this to answer questions about invoices: which ones are open,
    which belong to a given supplier, or what is due soon.

    Args:
        supplier: Supplier name or part of it. Empty means any supplier.
        status: One of open, matched, paid, on_hold. Empty means any status.
        due_within_days: Only unpaid invoices due within this many days from
            today, overdue ones included. -1 means no due-date filter.
        limit: Maximum number of invoices to return.
    """
    today = date.today()
    query = (
        "SELECT invoice_no, supplier, amount, currency, due_on, status "
        "FROM invoices WHERE 1=1"
    )
    params: list = []

    if supplier:
        query += " AND supplier LIKE ?"
        params.append(f"%{supplier}%")

    if status:
        query += " AND status = ?"
        params.append(status)

    if due_within_days >= 0:
        query += " AND status != 'paid' AND due_on <= ?"
        params.append((today + timedelta(days=due_within_days)).isoformat())

    query += " ORDER BY due_on LIMIT ?"
    params.append(limit)

    con = sqlite3.connect(DB)
    rows = con.execute(query, params).fetchall()
    con.close()

    if not rows:
        window = "any" if due_within_days < 0 else f"{due_within_days} days"
        return (
            "No invoices matched "
            f"(supplier={supplier or 'any'}, status={status or 'any'}, due within={window})."
        )

    lines = [
        f"{no} | {sup} | {amt:.2f} {cur} | {_due_label(due, st, today)} | {st}"
        for no, sup, amt, cur, due, st in rows
    ]
    return f"{len(rows)} invoice(s) found:\n" + "\n".join(lines)


@mcp.tool()
def cash_due_summary(days: int = 14) -> str:
    """Summarise how much money is owed to suppliers, by currency.

    Use this for cash-flow questions: how much is overdue, how much falls
    due in the coming days, and how much is held. Totals are kept per
    currency and never converted, because an exchange rate is not
    something this tool knows.

    Args:
        days: How far ahead to look, in days from today.
    """
    today = date.today().isoformat()
    horizon = (date.today() + timedelta(days=days)).isoformat()
    buckets = {
        "overdue": ("due_on < ? AND status IN ('open', 'matched')", [today]),
        f"due in the next {days} days": (
            "due_on >= ? AND due_on <= ? AND status IN ('open', 'matched')",
            [today, horizon],
        ),
        "on hold": ("status = 'on_hold'", []),
    }

    con = sqlite3.connect(DB)
    lines = [f"Supplier payables as of {today}:"]
    for label, (where, params) in buckets.items():
        rows = con.execute(
            f"SELECT currency, COUNT(*), SUM(amount) FROM invoices WHERE {where} "
            "GROUP BY currency ORDER BY currency",
            params,
        ).fetchall()
        if not rows:
            lines.append(f"- {label}: none")
            continue
        parts = ", ".join(f"{total:,.2f} {cur} ({n} invoices)" for cur, n, total in rows)
        lines.append(f"- {label}: {parts}")
    con.close()
    return "\n".join(lines)

@mcp.tool()
def get_invoice(invoice_no: str) -> str:
    """Get the full detail of one invoice, including its notes.

    Use this after search_invoices when the user asks about a specific
    invoice, or when the notes on an invoice matter (duplicate warnings,
    supplier bank detail changes, payment holds).

    Args:
        invoice_no: The invoice number, e.g. INV-2205.
    """
    con = sqlite3.connect(DB)
    row = con.execute(
        "SELECT invoice_no, supplier, amount, currency, issued_on, "
        "due_on, status, notes FROM invoices WHERE invoice_no = ?",
        (invoice_no,),
    ).fetchone()
    con.close()

    if row is None:
        return f"No invoice found with number {invoice_no}."

    no, supplier, amount, currency, issued, due, status, notes = row
    return (
        f"Invoice:   {no}\n"
        f"Supplier:  {supplier}\n"
        f"Amount:    {amount:.2f} {currency}\n"
        f"Issued:    {issued}\n"
        f"Due:       {due}\n"
        f"Status:    {status}\n"
        f"Notes:     {notes or '(none)'}"
    )

if __name__ == "__main__":
    mcp.run(transport="stdio")

import sqlite3
from mcp.server import MCPServer
from pathlib import Path

DB = str(Path(__file__).with_name("finance.db"))
mcp = MCPServer("finance")


@mcp.tool()
def search_invoices(supplier: str = "", status: str = "", limit: int = 20) -> str:
    """Search supplier invoices.

    Use this to answer questions about invoices: which ones are open,
    which belong to a given supplier, or what is due soon.

    Args:
        supplier: Supplier name or part of it. Empty means any supplier.
        status: One of open, matched, paid, on_hold. Empty means any status.
        limit: Maximum number of invoices to return.
    """
    query = (
        "SELECT invoice_no, supplier, amount, currency, due_on, status "
        "FROM invoices WHERE 1=1"
    )
    params = []

    if supplier:
        query += " AND supplier LIKE ?"
        params.append(f"%{supplier}%")

    if status:
        query += " AND status = ?"
        params.append(status)

    query += " ORDER BY due_on LIMIT ?"
    params.append(limit)

    con = sqlite3.connect(DB)
    rows = con.execute(query, params).fetchall()
    con.close()

    if not rows:
        return (
            "No invoices matched "
            f"(supplier={supplier or 'any'}, status={status or 'any'})."
        )

    lines = [
        f"{no} | {sup} | {amt:.2f} {cur} | due {due} | {st}"
        for no, sup, amt, cur, due, st in rows
    ]
    return f"{len(rows)} invoice(s) found:\n" + "\n".join(lines)

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

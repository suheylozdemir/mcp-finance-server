# Finance MCP Server

An MCP server that exposes supplier invoice data to an LLM as callable tools.

Built against MCP protocol version `2026-07-28` with the Python SDK (`mcp` 2.2.0),
running over the stdio transport and connected to Claude Desktop.

## Why

An LLM cannot reach data that lives in a database. The usual fix is a bespoke
integration per application, which is `N x M` work: every AI app times every
internal system. MCP turns that into `N + M`: each system exposes one server,
each application speaks one protocol.

This repository is the smallest honest version of that: one server, two tools,
a real client on the other end.

## Tools

| Tool | Purpose |
|---|---|
| `search_invoices(supplier, status, limit)` | Filtered list of invoices. All parameters optional. |
| `get_invoice(invoice_no)` | Full detail of one invoice, including free-text notes. |

The seed data contains three deliberate anomalies, so the tools have something
worth finding: a suspected duplicate invoice, a supplier whose bank details
changed, and two invoices that differ by 75 cents.

## Design decisions

**Parameterised SQL, never string interpolation.** The arguments reaching these
tools are produced by a language model. Interpolating them into a query would
hand the model an execution path into the database. Every value goes through a
`?` placeholder.

**Database path resolved from `__file__`.** The server process is started by the
client, not from the project directory. A relative path would not merely fail:
SQLite would silently create an empty database elsewhere and every query would
return "not found". Silent wrong answers are worse than crashes.

**Docstrings are instructions, not documentation.** The SDK turns each function's
docstring and type hints into the tool definition the model sees. `get_invoice`
explicitly states when to prefer it over `search_invoices`, because two similar
tools with vague descriptions is how a model ends up calling the wrong one.

**Nothing is written to stdout.** Under the stdio transport, stdout carries the
JSON-RPC stream. A stray `print` corrupts the protocol. Diagnostics go to stderr.

**Empty results are successes, not errors.** A query that matches nothing returns
a sentence saying so, including the filters that were applied. An empty string
would leave the model unable to tell "no records" from "tool broken".

## Run

```bash
conda create -n mcp312 python=3.12 && conda activate mcp312
pip install "mcp[cli]"
python db.py          # creates finance.db and seeds it
mcp dev server.py     # opens MCP Inspector
```

To connect it to Claude Desktop, add to `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "finance": {
      "command": "/path/to/python",
      "args": ["/path/to/server.py"]
    }
  }
}
```

## Files

```
db.py        schema and seed data
server.py    the MCP server
finance.db   generated, not tracked
```

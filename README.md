# Finance Operations Agent

Two parts of one system:

1. **An MCP server** that exposes supplier invoice data to an LLM as callable tools.
2. **An agent** that reads that data and decides what to do about each invoice,
   inside a rulebook that can refuse it.

Built against MCP protocol version `2026-07-28` with the Python SDK (`mcp` 2.2.0).

## The decision the agent makes

```
load -> read -> propose one action -> policy gate -> execute | park for approval | reject -> audit
        (planner)                     (rules)        (executor)
```

The planner proposes. It never performs anything. A separate rulebook decides
whether the proposal is allowed, and a separate executor carries it out. Plain
function calling lets a model invoke `pay()` directly; that works right up to the
moment you need dry-run, an approval gate, idempotency or an audit trail, and
then there is nowhere to put them.

The planner is deliberately deterministic for now. It is also the baseline: when
an LLM planner replaces it, this is the number it has to beat. A model that
cannot outperform a page of if-statements is not earning its latency.

## The rulebook

Thresholds are the delegation-of-authority ladder every finance team has:

| Amount (AUD) | Outcome |
|---|---|
| under 1,000 | paid without a human |
| 1,000 to 10,000 | one approver |
| over 10,000 | two approvers |

Three hard stops apply regardless of amount, and are evaluated **before** the
thresholds, so a small invoice cannot slip past them:

| Rule | Why it exists |
|---|---|
| `supplier_bank_changed_recently` | a changed payee account is the most expensive fraud in accounts payable |
| `possible_duplicate_of:<invoice>` | same supplier, near-identical amount, close issue dates |
| `foreign_currency` | FX and bank charges make the final amount uncertain |

Every decision carries a rule name into the audit trail, so "why did this stop"
is answered with a term a finance person recognises rather than a line number.

## What the current data exercises

Running `python run_agent.py` over the seeded invoices produces 5 automatic
actions, 4 parked for approval and 2 refused. Each branch is reachable, which is
the point of the seed data.

The case worth reading is `INV-2205`: the planner proposes payment because
nothing on the invoice looks wrong, and the rulebook refuses it because the
supplier changed their bank details two days earlier. The planner is not told
about bank changes on purpose.

## The approval queue

Anything the rulebook parks is written to `pending_actions` and outlives the
process that proposed it. `approve.py` lists what is waiting and takes the
decision:

```bash
python run_agent.py --live      # queues what needs a signature
python approve.py               # shows the queue
python approve.py 1 approve alex "checked the PO"
```

Two constraints are enforced in the database rather than by convention:

**The proposer cannot be the approver.** `agent:rules-v1` proposes a payment and
is refused when it tries to decide on it. This is segregation of duties, the
control every finance framework starts with, and it is the reason an agent can
be trusted with a payment queue at all.

**An action is queued at most once.** A UNIQUE index on the idempotency key means
a second run of the agent adds nothing rather than filling the queue with copies
of a decision nobody has answered yet.

Executed payments land in `payments`, also keyed on the idempotency key, so the
double-payment guard survives a crash. It is a database constraint, not a set in
memory: two processes racing on the same invoice cannot both win, because the
second INSERT fails rather than the second check reading a stale set.

## Tools exposed over MCP

| Tool | Purpose |
|---|---|
| `search_invoices(supplier, status, limit)` | filtered list, all parameters optional |
| `get_invoice(invoice_no)` | one invoice in full, including free-text notes |

## Design decisions

**Parameterised SQL, never string interpolation.** Arguments reaching the MCP
tools are produced by a language model. Interpolating them into a query hands the
model an execution path into the database.

**Database path resolved from `__file__`.** The server process is started by the
client, not from the project directory. A relative path would not merely fail:
SQLite would create an empty database elsewhere and every query would return
"not found". Silent wrong answers are worse than crashes.

**Docstrings are instructions, not documentation.** The SDK turns each function's
docstring and type hints into the tool definition the model sees.

**Nothing is written to stdout.** Under the stdio transport, stdout carries the
JSON-RPC stream. A stray `print` corrupts the protocol. Diagnostics go to stderr.

**Empty results are successes, not errors.** A query matching nothing returns a
sentence saying so, including the filters applied, so the model can tell "no
records" from "tool broken".

**Dry-run does not consume the idempotency key.** A rehearsal that marked the
action as done would cause the real run afterwards to be skipped as a duplicate.

**The executor marks an action done only after the side effect returns.** Marking
it first turns a transient failure into an action silently skipped on retry.

## Known limitations

The duplicate rule currently flags `INV-2208` and `INV-2212`, which differ by 75
cents and 13 days. Whether that is a genuine duplicate or two legitimate freight
invoices is not something the current rule can tell. The false-alarm rate is one
of the four metrics the evaluation layer will measure; an agent that escalates
everything is safe and useless.

Approval is currently a name, not a role. Anyone who is not the proposer can sign
off any amount. Role-based limits (one approver under 10,000, two above it) are
the next piece, and `tests/test_seed_data.py` exists because the first version of
the seed data used fixed dates and the bank-change rule silently stopped firing
once they aged past the window.

## Run

```bash
conda create -n mcp312 python=3.12 && conda activate mcp312
pip install "mcp[cli]" pytest
python db.py            # creates finance.db and seeds it
python run_agent.py     # dry-run over every unpaid invoice
pytest -q               # 12 tests
mcp dev server.py       # opens MCP Inspector against the server
```

To connect the server to Claude Desktop, add to `claude_desktop_config.json`:

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

## Layout

```
db.py              schema and seed data
server.py          the MCP server
run_agent.py       runs the decision loop over every unpaid invoice
agent/domain.py    value objects, no I/O
agent/reader.py    the only module that touches the database
agent/actions.py   the actions that may be proposed
agent/policy.py    the rulebook
agent/planner.py   deterministic planner, to be replaced by an LLM
agent/executor.py  the only place a side effect happens, plus the audit trail
tests/             policy and executor tests
finance.db         generated, not tracked
```

## Roadmap

- [x] Layer 1 — agent, tools, decision loop, audit trail
- [x] Layer 2 — durable approval queue, segregation of duties, payment ledger
- [ ] Layer 2b — payment run cut-off and cancellation, role-based approval limits
- [ ] Layer 3 — labelled case set, four metrics, CI regression gate
- [ ] Layer 4 — model routing, caching, token budget
- [ ] Layer 5 — retries, queue, degradation when the model is down

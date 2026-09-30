"""Walk every unpaid invoice through the decision loop.

    load -> read -> propose -> policy gate -> execute | queue for approval | reject

Anything the rulebook parks now lands in a real queue that outlives this
process. Run approve.py afterwards to work through it.
"""
import sys
from datetime import date

from agent.executor import Audit, Executor
from agent.planner import propose
from agent.policy import Verdict, evaluate
from agent.queue import park
from agent.reader import load_case, open_invoice_numbers

DRY_RUN = "--live" not in sys.argv
TODAY = date.today()
ACTOR = "agent:rules-v1"

audit = Audit()
executor = Executor(audit, dry_run=DRY_RUN)

print(f"mode: {'DRY-RUN' if DRY_RUN else 'LIVE'}   today: {TODAY}   actor: {ACTOR}")
print("=" * 78)

tally: dict[str, int] = {}

for number in open_invoice_numbers():
    case = load_case(number)
    if case is None:
        continue

    action = propose(case, TODAY)
    audit.record(number, "proposed", action=type(action).__name__, why=action.reason)

    decision = evaluate(action, case, TODAY)
    audit.record(number, "decided", verdict=decision.verdict.value, rule=decision.rule)

    if decision.verdict is Verdict.ALLOW:
        outcome = executor.execute(action).description
    elif decision.verdict is Verdict.NEEDS_APPROVAL:
        if DRY_RUN:
            outcome = f"[dry-run] would queue for approval ({decision.rule})"
        else:
            item_id = park(action, decision.rule, ACTOR)
            if item_id is None:
                outcome = f"already in the approval queue ({decision.rule})"
            else:
                audit.record(number, "parked", item=item_id, rule=decision.rule)
                outcome = f"queued for approval as #{item_id} ({decision.rule})"
    else:
        audit.record(number, "rejected", rule=decision.rule)
        outcome = f"refused by the rulebook ({decision.rule})"

    tally[decision.verdict.value] = tally.get(decision.verdict.value, 0) + 1

    inv = case.invoice
    print(f"{inv.invoice_no}  {inv.supplier:<20} {inv.amount:>9,.2f} {inv.currency}  [{inv.status}]")
    print(f"    proposed : {type(action).__name__}")
    print(f"    verdict  : {decision.verdict.value:<9} rule={decision.rule}")
    print(f"    outcome  : {outcome}\n")

print("=" * 78)
print("verdicts:", ", ".join(f"{k}={v}" for k, v in sorted(tally.items())))
print("audit events:", len(audit.events))
if DRY_RUN:
    print("\nnothing was written. run with --live to queue approvals and payments.")

"""Walk every unpaid invoice through the decision loop and print the trace.

    load -> read -> propose -> policy gate -> execute | park | reject -> audit
"""
import sys
from datetime import date

from agent.executor import Audit, Executor
from agent.planner import propose
from agent.policy import Verdict, evaluate
from agent.reader import load_case, open_invoice_numbers

DRY_RUN = "--live" not in sys.argv
TODAY = date.today()

audit = Audit()
executor = Executor(audit, dry_run=DRY_RUN)

print(f"mode: {'DRY-RUN' if DRY_RUN else 'LIVE'}   today: {TODAY}")
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
        audit.record(number, "parked", rule=decision.rule)
        outcome = f"waiting for approval ({decision.rule})"
    else:
        audit.record(number, "rejected", rule=decision.rule)
        outcome = f"refused by the rulebook ({decision.rule})"

    tally[decision.verdict.value] = tally.get(decision.verdict.value, 0) + 1

    inv = case.invoice
    print(f"{inv.invoice_no}  {inv.supplier:<20} {inv.amount:>9,.2f} {inv.currency}  [{inv.status}]")
    print(f"    proposed : {type(action).__name__}")
    print(f"    reason   : {action.reason}")
    print(f"    verdict  : {decision.verdict.value:<9} rule={decision.rule}")
    print(f"    outcome  : {outcome}\n")

print("=" * 78)
print("verdicts:", ", ".join(f"{k}={v}" for k, v in sorted(tally.items())))
print("audit events:", len(audit.events))

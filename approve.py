"""Work through the approval queue.

    python approve.py                      list what is waiting
    python approve.py 3 approve <who>      sign off item 3
    python approve.py 3 reject  <who> ...  refuse item 3

The person named must not be the one who proposed the item. That is
checked in agent/queue.py and it will refuse rather than warn.
"""
import sys

from agent.executor import Audit, Executor
from agent.actions import SchedulePayment
from agent.queue import SelfApproval, approve, pending, reject


def show() -> None:
    items = pending()
    if not items:
        print("approval queue is empty")
        return
    print(f"{len(items)} item(s) waiting:\n")
    for item in items:
        print("  " + item.summary())
        print(f"      proposed by {item.proposed_by} at {item.proposed_at}")
    print("\napprove with:  python approve.py <id> approve <your name>")


def rebuild(item) -> SchedulePayment:
    """Turn the stored payload back into an action object.

    Only payments reach the queue today, so this stays a single case
    rather than a registry pretending to be general.
    """
    if item.action_type != "SchedulePayment":
        raise NotImplementedError(f"cannot rebuild {item.action_type} yet")
    return SchedulePayment(**item.payload)


def main() -> None:
    if len(sys.argv) < 2:
        show()
        return

    item_id, verdict, actor = int(sys.argv[1]), sys.argv[2], sys.argv[3]
    note = " ".join(sys.argv[4:])

    try:
        if verdict == "approve":
            item = approve(item_id, actor, note)
            effect = Executor(Audit(), dry_run=False).execute(rebuild(item))
            print(f"approved #{item_id} by {actor}")
            print(f"  {effect.description}")
        elif verdict == "reject":
            item = reject(item_id, actor, note)
            print(f"rejected #{item_id} by {actor}: {note or 'no reason given'}")
        else:
            print("verdict must be approve or reject")
    except SelfApproval as e:
        print(f"refused: {e}")
    except LookupError as e:
        print(f"refused: {e}")


if __name__ == "__main__":
    main()

"""The approval queue: the part of the system a person actually touches.

Two rules are enforced here rather than left to whoever calls this:

  * an action is queued at most once (the idempotency key is UNIQUE)
  * the person who proposed an action cannot be the person who approves
    it (segregation of duties, the maker-checker rule every finance
    control framework starts with)

Neither rule is worth much as a convention. Both are worth something as
a constraint the code cannot route around.
"""
from __future__ import annotations

import json
import sqlite3
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

from .actions import Action, idempotency_key

DB = str(Path(__file__).resolve().parent.parent / "finance.db")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _connect() -> sqlite3.Connection:
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    return con


class SelfApproval(Exception):
    """Raised when someone tries to approve their own proposal."""


@dataclass(frozen=True, slots=True)
class PendingItem:
    id: int
    invoice_no: str
    action_type: str
    payload: dict
    rule: str
    proposed_by: str
    proposed_at: str

    def summary(self) -> str:
        amount = self.payload.get("amount")
        money = f" {amount:,.2f} {self.payload.get('currency', '')}" if amount else ""
        return f"#{self.id} {self.invoice_no}{money} [{self.action_type}] {self.rule}"


def park(action: Action, rule: str, proposed_by: str) -> int | None:
    """Put an action in the queue. Returns the row id, or None when the
    same action is already waiting there."""
    con = _connect()
    try:
        cur = con.execute(
            """INSERT INTO pending_actions
               (invoice_no, action_type, payload, rule, proposed_by,
                proposed_at, idem_key)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                action.invoice_no,
                type(action).__name__,
                json.dumps(asdict(action)),
                rule,
                proposed_by,
                _now(),
                idempotency_key(action),
            ),
        )
        con.commit()
        return cur.lastrowid
    except sqlite3.IntegrityError:
        # UNIQUE on idem_key. The same decision was already queued, so a
        # second run of the agent adds nothing rather than duplicating it.
        return None
    finally:
        con.close()


def pending() -> list[PendingItem]:
    con = _connect()
    rows = con.execute(
        "SELECT * FROM pending_actions WHERE status = 'pending' ORDER BY id"
    ).fetchall()
    con.close()
    return [
        PendingItem(
            id=r["id"],
            invoice_no=r["invoice_no"],
            action_type=r["action_type"],
            payload=json.loads(r["payload"]),
            rule=r["rule"],
            proposed_by=r["proposed_by"],
            proposed_at=r["proposed_at"],
        )
        for r in rows
    ]


def _decide(item_id: int, verdict: str, actor: str, note: str) -> PendingItem:
    con = _connect()
    row = con.execute(
        "SELECT * FROM pending_actions WHERE id = ? AND status = 'pending'",
        (item_id,),
    ).fetchone()
    if row is None:
        con.close()
        raise LookupError(f"no pending item #{item_id}")

    if row["proposed_by"] == actor:
        con.close()
        raise SelfApproval(
            f"{actor} proposed #{item_id} and cannot also decide it"
        )

    con.execute(
        """UPDATE pending_actions
           SET status = ?, decided_by = ?, decided_at = ?, decision_note = ?
           WHERE id = ?""",
        (verdict, actor, _now(), note, item_id),
    )
    con.commit()
    con.close()
    return PendingItem(
        id=row["id"],
        invoice_no=row["invoice_no"],
        action_type=row["action_type"],
        payload=json.loads(row["payload"]),
        rule=row["rule"],
        proposed_by=row["proposed_by"],
        proposed_at=row["proposed_at"],
    )


def approve(item_id: int, actor: str, note: str = "") -> PendingItem:
    return _decide(item_id, "approved", actor, note)


def reject(item_id: int, actor: str, note: str = "") -> PendingItem:
    return _decide(item_id, "rejected", actor, note)

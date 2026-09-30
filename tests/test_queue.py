"""The approval queue. These tests run against a throwaway database so
they never touch finance.db."""
import sqlite3
import tempfile

import db as schema_module
from agent import executor as executor_module
from agent import queue as q
from agent.actions import SchedulePayment
from agent.executor import Audit, Executor

ACTION = SchedulePayment("INV-9001", 5000.0, "AUD", "test")


def fresh_db() -> str:
    """A new empty database, wired into the modules under test."""
    path = tempfile.mktemp(suffix=".db")
    con = sqlite3.connect(path)
    con.executescript(schema_module.SCHEMA)
    con.commit()
    con.close()
    q.DB = path
    executor_module.DB = path
    return path


def test_parked_action_survives_in_the_queue():
    fresh_db()
    item_id = q.park(ACTION, "doa_single_approver", "agent:rules-v1")
    assert item_id is not None
    waiting = q.pending()
    assert len(waiting) == 1
    assert waiting[0].invoice_no == "INV-9001"
    assert waiting[0].rule == "doa_single_approver"


def test_the_same_action_cannot_be_queued_twice():
    """Running the agent again must not fill the queue with copies of a
    decision a person has not answered yet."""
    fresh_db()
    assert q.park(ACTION, "doa_single_approver", "agent:rules-v1") is not None
    assert q.park(ACTION, "doa_single_approver", "agent:rules-v1") is None
    assert len(q.pending()) == 1


def test_you_cannot_approve_your_own_proposal():
    fresh_db()
    item_id = q.park(ACTION, "doa_single_approver", "suheyl")
    try:
        q.approve(item_id, "suheyl")
    except q.SelfApproval:
        pass
    else:
        raise AssertionError("self-approval was allowed")
    assert len(q.pending()) == 1, "a refused approval must leave the item waiting"


def test_someone_else_can_approve_and_it_leaves_the_queue():
    fresh_db()
    item_id = q.park(ACTION, "doa_single_approver", "agent:rules-v1")
    item = q.approve(item_id, "suheyl", "checked the PO")
    assert item.invoice_no == "INV-9001"
    assert q.pending() == []


def test_rejecting_also_clears_it_from_the_queue():
    fresh_db()
    item_id = q.park(ACTION, "doa_single_approver", "agent:rules-v1")
    q.reject(item_id, "suheyl", "wrong cost centre")
    assert q.pending() == []


def test_deciding_an_unknown_item_is_refused():
    fresh_db()
    try:
        q.approve(9999, "suheyl")
    except LookupError:
        pass
    else:
        raise AssertionError("approving a non-existent item should fail")

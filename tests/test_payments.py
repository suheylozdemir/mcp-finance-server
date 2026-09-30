"""Idempotency now lives in the database, not in a set in memory."""
import sqlite3
import tempfile

import db as schema_module
from agent import executor as executor_module
from agent.actions import SchedulePayment
from agent.executor import Audit, Executor

ACTION = SchedulePayment("INV-9002", 240.0, "AUD", "test")


def fresh_db() -> str:
    path = tempfile.mktemp(suffix=".db")
    con = sqlite3.connect(path)
    con.executescript(schema_module.SCHEMA)
    con.commit()
    con.close()
    executor_module.DB = path
    return path


def rows(path: str) -> int:
    con = sqlite3.connect(path)
    n = con.execute("SELECT COUNT(*) FROM payments").fetchone()[0]
    con.close()
    return n


def test_a_live_payment_is_written_once():
    path = fresh_db()
    ex = Executor(Audit(path=None), dry_run=False)
    assert ex.execute(ACTION).performed is True
    assert rows(path) == 1


def test_running_it_again_writes_nothing():
    path = fresh_db()
    ex = Executor(Audit(path=None), dry_run=False)
    ex.execute(ACTION)
    assert ex.execute(ACTION).performed is False
    assert rows(path) == 1


def test_a_second_executor_still_cannot_double_pay():
    """The guard has to hold across processes, not just within one run.
    A fresh Executor stands in for the second process."""
    path = fresh_db()
    Executor(Audit(path=None), dry_run=False).execute(ACTION)
    second = Executor(Audit(path=None), dry_run=False)
    assert second.execute(ACTION).performed is False
    assert rows(path) == 1


def test_dry_run_writes_no_payment_and_leaves_the_key_free():
    path = fresh_db()
    rehearsal = Executor(Audit(path=None), dry_run=True)
    assert rehearsal.execute(ACTION).performed is False
    assert rows(path) == 0
    real = Executor(Audit(path=None), dry_run=False)
    assert real.execute(ACTION).performed is True, "the rehearsal consumed the key"

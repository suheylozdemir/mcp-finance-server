"""Action identity and the audit trail.

Live-payment behaviour is covered in test_payments.py; here we care about
what counts as "the same action" and about what gets written down.
"""
import sqlite3
import tempfile

import db as schema_module
from agent import executor as executor_module
from agent.actions import SchedulePayment, idempotency_key
from agent.executor import Audit, Executor

ACTION = SchedulePayment("INV-9003", 240.0, "AUD", "test")


def fresh_db() -> str:
    path = tempfile.mktemp(suffix=".db")
    con = sqlite3.connect(path)
    con.executescript(schema_module.SCHEMA)
    con.commit()
    con.close()
    executor_module.DB = path
    return path


def test_wording_of_the_reason_does_not_change_the_action():
    a = SchedulePayment("INV-1", 240.0, "AUD", "one wording")
    b = SchedulePayment("INV-1", 240.0, "AUD", "different wording")
    assert idempotency_key(a) == idempotency_key(b)


def test_a_different_amount_is_a_different_action():
    a = SchedulePayment("INV-1", 240.0, "AUD", "x")
    b = SchedulePayment("INV-1", 241.0, "AUD", "x")
    assert idempotency_key(a) != idempotency_key(b)


def test_dry_run_describes_without_doing():
    fresh_db()
    effect = Executor(Audit(path=None), dry_run=True).execute(ACTION)
    assert effect.performed is False
    assert effect.description.startswith("[dry-run]")


def test_every_attempt_is_recorded_including_the_refused_one():
    fresh_db()
    audit = Audit(path=None)
    ex = Executor(audit, dry_run=False)
    ex.execute(ACTION)
    ex.execute(ACTION)
    assert [e.kind for e in audit.for_invoice("INV-9003")] == ["executed", "skipped"]


def test_the_audit_file_gets_one_json_line_per_event(tmp_path=None):
    import json
    from pathlib import Path

    fresh_db()
    log = Path(tempfile.mktemp(suffix=".jsonl"))
    audit = Audit(path=log)
    Executor(audit, dry_run=True).execute(ACTION)
    lines = log.read_text().strip().splitlines()
    assert len(lines) == 1
    assert json.loads(lines[0])["invoice_no"] == "INV-9003"

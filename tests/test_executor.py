from agent.actions import SchedulePayment, idempotency_key
from agent.executor import Audit, Executor

ACTION = SchedulePayment("INV-1", 240.0, "AUD", "test")


def test_live_run_happens_once_only():
    ex = Executor(Audit(), dry_run=False)
    assert ex.execute(ACTION).performed is True
    assert ex.execute(ACTION).performed is False


def test_dry_run_changes_nothing_and_stays_repeatable():
    """A rehearsal must not consume the idempotency key, otherwise the
    real run afterwards would be skipped as a duplicate."""
    ex = Executor(Audit(), dry_run=True)
    first, second = ex.execute(ACTION), ex.execute(ACTION)
    assert first.performed is False
    assert second.description.startswith("[dry-run]")


def test_wording_of_the_reason_does_not_change_the_action():
    a = SchedulePayment("INV-1", 240.0, "AUD", "one wording")
    b = SchedulePayment("INV-1", 240.0, "AUD", "different wording")
    assert idempotency_key(a) == idempotency_key(b)


def test_a_different_amount_is_a_different_action():
    a = SchedulePayment("INV-1", 240.0, "AUD", "x")
    b = SchedulePayment("INV-1", 241.0, "AUD", "x")
    assert idempotency_key(a) != idempotency_key(b)


def test_every_attempt_is_recorded():
    audit = Audit()
    ex = Executor(audit, dry_run=False)
    ex.execute(ACTION)
    ex.execute(ACTION)
    kinds = [e.kind for e in audit.for_invoice("INV-1")]
    assert kinds == ["executed", "skipped"]

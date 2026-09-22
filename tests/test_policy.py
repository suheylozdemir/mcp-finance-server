"""The rulebook is where money gets stopped, so it gets the most tests."""
from datetime import date

from agent.actions import FlagDuplicate, SchedulePayment
from agent.domain import Case, Invoice, Supplier
from agent.policy import Verdict, evaluate

TODAY = date(2026, 9, 22)


def invoice(**kw) -> Invoice:
    base = dict(
        invoice_no="INV-1", supplier="Acme", amount=500.0, currency="AUD",
        issued_on="2026-09-01", due_on="2026-10-01", status="open", notes="",
    )
    base.update(kw)
    return Invoice(**base)


def case(inv=None, bank_changed_on=None, similar=()) -> Case:
    inv = inv or invoice()
    return Case(inv, Supplier(inv.supplier, bank_changed_on), similar)


def payment(inv: Invoice) -> SchedulePayment:
    return SchedulePayment(inv.invoice_no, inv.amount, inv.currency, "test")


def test_small_clean_invoice_is_paid_without_a_human():
    inv = invoice(amount=240.0)
    d = evaluate(payment(inv), case(inv), TODAY)
    assert d.verdict is Verdict.ALLOW
    assert d.rule == "under_auto_limit"


def test_recent_bank_change_blocks_payment_whatever_the_amount():
    """The cheap invoice must be refused too. A hard stop that only
    applies above a threshold is not a hard stop."""
    inv = invoice(amount=50.0)
    d = evaluate(payment(inv), case(inv, bank_changed_on="2026-09-20"), TODAY)
    assert d.verdict is Verdict.REJECT
    assert d.rule == "supplier_bank_changed_recently"


def test_old_bank_change_does_not_block():
    inv = invoice(amount=50.0)
    d = evaluate(payment(inv), case(inv, bank_changed_on="2026-01-05"), TODAY)
    assert d.verdict is Verdict.ALLOW


def test_possible_duplicate_is_refused_not_merely_queued():
    """A suspected duplicate must never reach an approver looking like an
    ordinary payment, so this is REJECT and not NEEDS_APPROVAL."""
    inv = invoice(amount=4820.0)
    twin = invoice(invoice_no="INV-2", amount=4820.0, issued_on="2026-09-04")
    d = evaluate(payment(inv), case(inv, similar=(twin,)), TODAY)
    assert d.verdict is Verdict.REJECT
    assert d.rule.startswith("possible_duplicate_of:")


def test_amount_thresholds_pick_the_right_approval_level():
    for amount, rule in [
        (999.99, "under_auto_limit"),
        (1000.0, "doa_single_approver"),
        (10000.0, "doa_single_approver"),
        (10000.01, "doa_two_approvers"),
    ]:
        inv = invoice(amount=amount)
        assert evaluate(payment(inv), case(inv), TODAY).rule == rule, amount


def test_foreign_currency_never_goes_through_unattended():
    inv = invoice(amount=100.0, currency="USD")
    d = evaluate(payment(inv), case(inv), TODAY)
    assert d.verdict is Verdict.NEEDS_APPROVAL
    assert d.rule == "foreign_currency"


def test_flagging_a_duplicate_is_always_allowed():
    inv = invoice()
    d = evaluate(FlagDuplicate(inv.invoice_no, "INV-2", "test"), case(inv), TODAY)
    assert d.verdict is Verdict.ALLOW

"""Guards against test data quietly expiring.

The bank-change rule only fires inside a short window. When the seed used
a fixed date, the rule stopped firing a few days later and the branch it
protects vanished from every run without a single test failing. That is
the worst kind of failure: nothing breaks, the system just stops
exercising its most important control.
"""
from datetime import date

import db as schema_module
from agent.domain import Supplier
from agent.policy import BANK_CHANGE_FREEZE_DAYS


def test_a_seeded_supplier_is_inside_the_bank_change_window():
    changed = [row for row in schema_module.SUPPLIERS if row[1]]
    assert changed, "no supplier has a bank-change date, the rule is untestable"

    today = date.today()
    assert any(
        Supplier(name, on).bank_changed_within(BANK_CHANGE_FREEZE_DAYS, today)
        for name, on in changed
    ), "seed dates have aged out of the freeze window"

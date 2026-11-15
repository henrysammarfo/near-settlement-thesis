"""`python -m settlemark check` catches hand typed numbers and stale outputs."""

from settlemark.check import audit_numbers, check
from settlemark.config import load_config


def test_committed_outputs_pass_check():
    assert check(load_config()) == []


def test_audit_flags_a_hand_typed_number():
    cfg = load_config()
    bad = "Intents settled $9.99B last year."
    assert "$9.99B" in audit_numbers(cfg, bad, {"x": "$1.00B"})
    assert audit_numbers(cfg, "It settled $1.00B.", {"x": "$1.00B"}) == []

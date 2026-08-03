import uuid
from datetime import date
from decimal import Decimal

from app.ingestion.specialized import transaction_fingerprint


def test_transaction_fingerprint_is_stable() -> None:
    account_id = uuid.UUID("00000000-0000-0000-0000-000000000001")
    first = transaction_fingerprint(account_id, date(2026, 7, 1), Decimal("15.00"), "QTS grant")
    second = transaction_fingerprint(
        account_id, date(2026, 7, 1), Decimal("15.0"), "  qts   grant "
    )
    assert first == second


def test_transaction_fingerprint_changes_for_amount() -> None:
    account_id = uuid.UUID("00000000-0000-0000-0000-000000000001")
    first = transaction_fingerprint(account_id, date(2026, 7, 1), Decimal("15"), "grant")
    second = transaction_fingerprint(account_id, date(2026, 7, 1), Decimal("16"), "grant")
    assert first != second


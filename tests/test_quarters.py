from datetime import datetime, timezone

from m365_confluence.models import ChangeItem
from m365_confluence.quarters import (
    derive_quarter,
    normalize_quarter,
    quarter_from_date,
    quarter_key,
)


def test_normalize_explicit_quarter():
    assert normalize_quarter("Rolling out in Q3 2026") == "Q3 2026"
    assert normalize_quarter("GA in Q1 CY2027") == "Q1 2027"
    assert normalize_quarter("2026 Q4 release") == "Q4 2026"


def test_normalize_month_year():
    assert normalize_quarter("Available August 2026") == "Q3 2026"


def test_normalize_unknown():
    assert normalize_quarter("no date here") == ""
    assert normalize_quarter("") == ""


def test_quarter_from_date():
    assert quarter_from_date(datetime(2026, 5, 1)) == "Q2 2026"
    assert quarter_from_date(datetime(2026, 12, 31)) == "Q4 2026"


def test_derive_quarter_prefers_text_then_actby():
    text_item = ChangeItem(id="1", source="roadmap", title="Q2 2026 rollout", body="")
    assert derive_quarter(text_item) == "Q2 2026"

    date_item = ChangeItem(
        id="2",
        source="message_center",
        title="no quarter",
        body="",
        act_by=datetime(2026, 11, 5, tzinfo=timezone.utc),
    )
    assert derive_quarter(date_item) == "Q4 2026"


def test_quarter_key_orders_unknown_last():
    assert quarter_key("Q1 2026") < quarter_key("Q2 2026")
    assert quarter_key("Q4 2026") < quarter_key("Q1 2027")
    assert quarter_key("") > quarter_key("Q4 2099")

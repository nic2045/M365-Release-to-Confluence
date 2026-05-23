from datetime import datetime, timezone

from m365_confluence.filters import apply_filters
from m365_confluence.models import ChangeItem


def _item(id_, *, tags=None, act_by=None, products=None, category=""):
    return ChangeItem(
        id=id_,
        source="message_center",
        title="t",
        body="b",
        category=category,
        tags=tags or [],
        products=products or [],
        act_by=act_by,
    )


def test_no_filters_passes_all():
    items = [_item("1"), _item("2")]
    assert len(apply_filters(items)) == 2


def test_major_only():
    items = [_item("1", tags=["MajorChange"]), _item("2")]
    assert [i.id for i in apply_filters(items, major_only=True)] == ["1"]


def test_action_required():
    items = [_item("1", act_by=datetime(2026, 6, 1, tzinfo=timezone.utc)), _item("2")]
    assert [i.id for i in apply_filters(items, action_required=True)] == ["1"]


def test_product_substring_case_insensitive():
    items = [_item("1", products=["Microsoft Teams"]), _item("2", products=["Exchange"])]
    assert [i.id for i in apply_filters(items, products=["teams"])] == ["1"]


def test_category_filter():
    items = [_item("1", category="planForChange"), _item("2", category="stayInformed")]
    assert [i.id for i in apply_filters(items, categories=["planforchange"])] == ["1"]


def test_filters_combine_with_and():
    items = [
        _item("1", tags=["MajorChange"], products=["Teams"]),
        _item("2", tags=["MajorChange"], products=["Exchange"]),
    ]
    result = apply_filters(items, major_only=True, products=["teams"])
    assert [i.id for i in result] == ["1"]


def test_should_make_page_modes():
    from m365_confluence.pipeline import _should_make_page

    major = _item("1", tags=["MajorChange"])
    normal = _item("2")
    assert _should_make_page(major, "all") is True
    assert _should_make_page(normal, "all") is True
    assert _should_make_page(major, "none") is False
    assert _should_make_page(major, "major") is True
    assert _should_make_page(normal, "major") is False


def test_worldwide_only():
    from m365_confluence.filters import is_worldwide

    ww = _item("1")
    ww.cloud_instances = ["Worldwide (Standard Multi-Tenant)", "GCC"]
    gcc = _item("2")
    gcc.cloud_instances = ["GCC High", "DoD"]
    none = _item("3")  # no cloud info (e.g. Message Center) -> passes

    assert is_worldwide(ww) is True
    assert is_worldwide(gcc) is False
    assert is_worldwide(none) is True

    kept = apply_filters([ww, gcc, none], worldwide_only=True)
    assert [i.id for i in kept] == ["1", "3"]


def test_is_rollout_or_live():
    from m365_confluence.filters import is_rollout_or_live

    assert is_rollout_or_live("Rolling out") is True
    assert is_rollout_or_live("Launched") is True
    assert is_rollout_or_live("Generally Available") is True
    assert is_rollout_or_live("In development") is False
    assert is_rollout_or_live("") is False


def test_output_relevant():
    from types import SimpleNamespace

    from m365_confluence.pipeline import _output_relevant

    rolling = _item("1")
    rolling.source = "roadmap"
    rolling.status = "Rolling out"
    dev = _item("2")
    dev.source = "roadmap"
    dev.status = "In development"
    mc = _item("3")
    mc.source = "message_center"

    assert _output_relevant(rolling, None) is True  # new + live
    assert _output_relevant(dev, None) is False  # not live yet
    prev_live = SimpleNamespace(status="Launched")
    assert _output_relevant(rolling, prev_live) is False  # already live last run
    prev_dev = SimpleNamespace(status="In development")
    assert _output_relevant(rolling, prev_dev) is True  # transitioned to live
    assert _output_relevant(mc, None) is True  # message center always relevant


def test_fatal_provider_error_detection():
    from m365_confluence.pipeline import _is_fatal_provider_error

    assert _is_fatal_provider_error(Exception("Your credit balance is too low")) is True
    assert _is_fatal_provider_error(Exception("authentication_error: bad key")) is True
    assert _is_fatal_provider_error(Exception("Connection timed out")) is False

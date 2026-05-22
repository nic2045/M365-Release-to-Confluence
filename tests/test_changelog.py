from m365_confluence.changelog import ChangelogStore, render_changelog_body
from m365_confluence.confluence_macros import decision_badge, slip_badge, status_macro


def test_status_macro_contains_colour_and_title():
    out = status_macro("Green", "Active")
    assert 'ac:name="status"' in out
    assert ">Green<" in out
    assert ">Active<" in out


def test_decision_badge_colours():
    assert ">Green<" in decision_badge("Activate")
    assert ">Red<" in decision_badge("Deactivate")
    assert ">Blue<" in decision_badge("Communicate")
    assert ">Yellow<" in decision_badge("Monitor")
    assert decision_badge("") == ""


def test_slip_badge_is_red():
    assert ">Red<" in slip_badge()


def test_changelog_roundtrip_and_summary(tmp_path):
    path = tmp_path / "cl.json"
    store = ChangelogStore(path)
    entry = store.add(processed=5, new=2, changed=3, slipped=1)
    assert "+2 neu" in entry.summary
    assert "~3" in entry.summary
    assert "1 verschoben" in entry.summary
    store.save()

    reloaded = ChangelogStore(path).load()
    assert len(reloaded.entries()) == 1


def test_render_changelog_body():
    store = ChangelogStore("unused")
    store.add(processed=3, new=3, changed=0, slipped=0)
    body = render_changelog_body(store.entries())
    assert "<table>" in body
    assert "Zeitpunkt" in body
    assert "+3 neu" in body

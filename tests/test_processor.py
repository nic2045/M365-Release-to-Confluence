from m365_confluence.ai.processor import process_item
from m365_confluence.ai.prompts import parse_response
from m365_confluence.models import ChangeItem


def _item() -> ChangeItem:
    return ChangeItem(id="MC1", source="message_center", title="T", body="raw")


class _ScriptedProvider:
    """Returns queued responses in order; records how many times it was called."""

    def __init__(self, responses):
        self._responses = list(responses)
        self.calls = 0

    def complete(self, system, prompt):
        self.calls += 1
        return self._responses.pop(0)


def test_parse_tolerates_newlines_in_strings():
    raw = '{"summary": "line one\nline two", "audience": "Admins"}'
    result = parse_response(raw, _item())
    assert "line one" in result.summary
    assert result.audience == "Admins"


def test_process_item_succeeds_first_try():
    provider = _ScriptedProvider(['{"summary": "ok", "audience": "Admins"}'])
    result = process_item(provider, _item())
    assert provider.calls == 1
    assert result.summary == "ok"


def test_process_item_repairs_invalid_json():
    bad = '{"summary": "he said "hi"", "audience": "Admins"}'  # unescaped inner quotes
    good = '{"summary": "he said hi", "audience": "Admins"}'
    provider = _ScriptedProvider([bad, good])
    result = process_item(provider, _item())
    assert provider.calls == 2  # one repair round-trip
    assert result.summary == "he said hi"

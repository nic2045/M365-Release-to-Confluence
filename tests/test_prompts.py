from m365_confluence.ai.prompts import parse_response, render_storage
from m365_confluence.models import ChangeItem, ProcessedItem


def _item() -> ChangeItem:
    return ChangeItem(
        id="MC123",
        source="message_center",
        title="Original title",
        body="raw",
        url="https://example.com/x",
        status="In development",
        products=["Teams"],
    )


def test_parse_response_plain_json():
    raw = (
        '{"title": "New title", "summary": "S", "impact": "I", '
        '"audience": "Admins", "recommended_action": "Do it", '
        '"action_items": ["a", "b", ""]}'
    )
    result = parse_response(raw, _item())
    assert result.confluence_title == "New title"
    assert result.audience == "Admins"
    assert result.action_items == ["a", "b"]
    assert "<h2>Summary</h2>" in result.confluence_body


def test_parse_response_strips_code_fence():
    raw = '```json\n{"summary": "S"}\n```'
    result = parse_response(raw, _item())
    # Falls back to source title when title is absent.
    assert result.confluence_title == "Original title"
    assert result.summary == "S"


def test_render_storage_escapes_html():
    processed = ProcessedItem(
        source_item=_item(),
        summary="<script>alert(1)</script>",
        impact="ok",
        audience="Admins",
    )
    body = render_storage(processed)
    assert "<script>" not in body
    assert "&lt;script&gt;" in body

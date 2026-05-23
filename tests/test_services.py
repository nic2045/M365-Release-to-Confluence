from m365_confluence.services import service_for, services_for


def test_service_for_known():
    assert service_for("Outlook") == "Exchange Online"
    assert service_for("Exchange") == "Exchange Online"
    assert service_for("SharePoint") == "SharePoint Online"
    assert service_for("OneDrive") == "SharePoint Online"
    assert service_for("Microsoft Teams") == "Teams"
    assert service_for("Planner") == "Teams"
    assert service_for("Microsoft To Do") == "Teams"
    assert service_for("Whiteboard") == "Teams"
    assert service_for("Microsoft Purview") == "Compliance/Security"
    assert service_for("Microsoft Defender for Office 365") == "Compliance/Security"
    assert service_for("Microsoft Information Protection") == "Compliance/Security"


def test_service_for_default():
    assert service_for("Microsoft Copilot (Microsoft 365)") == "Allgemein / M365 Admin"
    assert service_for("Excel") == "Allgemein / M365 Admin"


def test_services_for_dedupes_and_defaults():
    assert services_for(["Outlook", "Exchange"]) == ["Exchange Online"]
    assert services_for(["Teams", "SharePoint"]) == ["Teams", "SharePoint Online"]
    assert services_for([]) == ["Allgemein / M365 Admin"]


def test_service_override(tmp_path, monkeypatch):
    f = tmp_path / "map.json"
    f.write_text('{"excel": "Office Apps"}', encoding="utf-8")
    monkeypatch.setenv("SERVICE_MAP_FILE", str(f))
    assert service_for("Excel") == "Office Apps"

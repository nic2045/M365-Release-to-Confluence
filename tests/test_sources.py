from m365_confluence.sources.message_center import MessageCenterSource
from m365_confluence.sources.roadmap import RoadmapSource


def test_message_center_mapping():
    raw = {
        "id": "MC123",
        "title": " New Teams feature ",
        "category": "planForChange",
        "services": ["Microsoft Teams"],
        "isMajorChange": True,
        "lastModifiedDateTime": "2026-05-01T00:00:00Z",
        "actionRequiredByDateTime": "2026-06-01T00:00:00Z",
        "body": {"content": "<p>details</p>"},
        "details": [{"name": "RoadmapIds", "value": "98765"}],
    }
    item = MessageCenterSource._map(raw)
    assert item.id == "MC123"
    assert item.source == "message_center"
    assert item.title == "New Teams feature"
    assert item.products == ["Microsoft Teams"]
    assert "MajorChange" in item.tags
    assert item.act_by is not None


def test_roadmap_mapping():
    raw = {
        "id": 98765,
        "title": "Some rollout",
        "description": "what it does",
        "status": "In development",
        "tagsContainer": {
            "products": [{"tagName": "Teams"}],
            "releasePhase": [{"tagName": "General Availability"}],
            "cloudInstances": [
                {"tagName": "Worldwide (Standard Multi-Tenant)"},
                {"tagName": "GCC"},
            ],
            "platforms": [{"tagName": "Desktop"}],
        },
        "created": "2026-03-01T00:00:00Z",
        "modified": "2026-04-01T00:00:00Z",
    }
    item = RoadmapSource._map(raw)
    assert item.id == "98765"
    assert item.source == "roadmap"
    assert item.products == ["Teams"]
    assert item.status == "In development"
    assert item.release_phases == ["General Availability"]
    assert "Worldwide (Standard Multi-Tenant)" in item.cloud_instances
    assert item.platforms == ["Desktop"]
    assert item.created is not None
    assert "General Availability" in item.tags
    assert "featureid=98765" in item.url


def test_roadmap_v2_mapping():
    raw = {
        "id": 555,
        "title": "V2 feature",
        "description": "desc",
        "status": "Rolling out",
        "products": ["Microsoft Teams"],
        "cloudInstances": ["Worldwide (Standard Multi-Tenant)", "GCC"],
        "platforms": ["Desktop", "Web"],
        "releaseRings": ["General Availability", "Targeted Release"],
        "moreInfoUrls": ["https://learn.microsoft.com/x"],
        "availabilities": [
            {"ring": "Targeted Release", "year": 2026, "month": "July"},
            {"ring": "General Availability", "year": 2026, "month": "September"},
        ],
        "created": "2026-03-01T00:00:00Z",
        "modified": "2026-04-01T00:00:00Z",
    }
    item = RoadmapSource._map(raw)
    assert item.id == "555"
    assert item.products == ["Microsoft Teams"]
    assert item.release_phases == ["General Availability", "Targeted Release"]
    assert "Worldwide (Standard Multi-Tenant)" in item.cloud_instances
    assert item.platforms == ["Desktop", "Web"]
    assert item.url == "https://learn.microsoft.com/x"
    # GA availability (Sep 2026) is authoritative -> Q3 2026
    assert item.release_date is not None
    assert item.release_date.year == 2026 and item.release_date.month == 9


def test_features_accepts_list_and_wrapped():
    from m365_confluence.sources.roadmap import _features

    assert _features([{"id": 1}]) == [{"id": 1}]
    assert _features({"value": [{"id": 2}]}) == [{"id": 2}]
    assert _features({"features": [{"id": 3}]}) == [{"id": 3}]
    assert _features({"nope": 1}) == []

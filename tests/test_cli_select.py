from m365_confluence.cli import _parse_selection


def test_parse_all():
    assert _parse_selection("all", 3) == [0, 1, 2]


def test_parse_numbers_and_ranges():
    assert _parse_selection("1,3", 5) == [0, 2]
    assert _parse_selection("2-4", 5) == [1, 2, 3]
    assert _parse_selection("1 3-4", 5) == [0, 2, 3]


def test_parse_ignores_out_of_range_and_junk():
    assert _parse_selection("0,9,abc,2", 3) == [1]


def test_parse_blank():
    assert _parse_selection("", 3) == []


def test_approval_gate_redirects_to_review(monkeypatch, tmp_path):
    import m365_confluence.cli as cli

    captured = {}

    class _Result:
        fetched = processed = published = skipped = unchanged = slipped = new = changed = 0
        dashboards = 0
        not_relevant = 0
        titles = []

    def fake_run(config, **kwargs):
        captured.update(kwargs)
        return _Result()

    def fake_load(**kwargs):
        captured["require_confluence"] = kwargs.get("require_confluence")

        class _C:
            ai = type(
                "AI",
                (),
                {
                    "provider": "anthropic",
                    "anthropic_model": "m",
                    "azure_deployment": "",
                    "local_model": "",
                },
            )()
            filters = type(
                "F",
                (),
                {
                    "products": [],
                    "categories": [],
                    "major_only": False,
                    "action_required": False,
                    "worldwide_only": False,
                    "new_rollouts_only": False,
                    "quarter": "",
                },
            )()

        return _C()

    monkeypatch.setattr(cli, "run", fake_run)
    monkeypatch.setattr(cli.Config, "load", staticmethod(fake_load))
    monkeypatch.chdir(tmp_path)

    # No --approve -> must redirect to review.json and not require Confluence
    assert cli.main(["--source", "roadmap"]) == 0
    assert captured["review_out"] == "review.json"
    assert captured["require_confluence"] is False


def test_approve_allows_publish(monkeypatch, tmp_path):
    import m365_confluence.cli as cli

    captured = {}

    class _Result:
        fetched = processed = published = skipped = unchanged = slipped = new = changed = 0
        dashboards = 0
        not_relevant = 0
        titles = []

    def fake_run(config, **kwargs):
        captured.update(kwargs)
        return _Result()

    def fake_load(**kwargs):
        captured["require_confluence"] = kwargs.get("require_confluence")

        class _C:
            ai = type(
                "AI",
                (),
                {
                    "provider": "anthropic",
                    "anthropic_model": "m",
                    "azure_deployment": "",
                    "local_model": "",
                },
            )()
            filters = type(
                "F",
                (),
                {
                    "products": [],
                    "categories": [],
                    "major_only": False,
                    "action_required": False,
                    "worldwide_only": False,
                    "new_rollouts_only": False,
                    "quarter": "",
                },
            )()

        return _C()

    monkeypatch.setattr(cli, "run", fake_run)
    monkeypatch.setattr(cli.Config, "load", staticmethod(fake_load))
    monkeypatch.chdir(tmp_path)

    assert cli.main(["--source", "roadmap", "--approve"]) == 0
    assert captured["review_out"] is None
    assert captured["require_confluence"] is True

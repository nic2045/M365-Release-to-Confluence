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

from app.catalog import SPEC
from app.domain.prepare import prepare_rows
from tests.domain_cases import CLEAN, row


def test_clean_sample_prepares():
    items, issues = prepare_rows(CLEAN)
    assert len(items) == 4
    assert issues == []


def test_blank_key_is_isolated():
    items, issues = prepare_rows([row(**{SPEC["key"]: ""})])
    assert not items
    assert issues[0]["code"] == "KEY_MISSING"


def test_bad_number_is_isolated():
    item = row(**{"stage_seq": "abc"})
    items, issues = prepare_rows([item])
    assert not items
    assert issues[0]["code"].startswith("INVALID_")


def test_domain_invalid_rows_are_isolated():
    item = row(**{'good_qty': '10', 'scrap_qty': '10', 'rework_qty': '10'})
    items, issues = prepare_rows([item])
    assert not items
    assert issues


def test_normalization_row_is_accepted():
    item = row(**{'good_qty': '９５０', 'input_qty': '1000'})
    items, issues = prepare_rows([item])
    assert len(items) == 1
    assert issues == []


def test_issue_keeps_line_and_key():
    key = CLEAN[0][SPEC["key"]]
    item = row(**{"stage_seq": "abc"})
    item["_line"] = 77
    _, issues = prepare_rows([item])
    assert issues[0]["line"] == 77
    assert issues[0]["key"] == key

from app.domain.decision import decide_rows
from tests.domain_cases import calc, run, run_profile


def test_clean_sample_has_no_blocker():
    results, _ = run_profile("clean")
    assert sum(1 for item in results if item["verdict"] == "REJECT") == 0


def test_dirty_sample_has_blocker():
    results, _ = run_profile("dirty")
    assert any(item["verdict"] == "REJECT" for item in results)


def test_each_result_has_reason():
    results, _ = run_profile("dirty")
    assert all(item.get("reason") for item in results)


def test_boundary_case_one():
    results, issues = run([{'work_order': 'Q1', 'stage_seq': '1', 'stage': '冲压', 'input_qty': '100', 'good_qty': '95', 'scrap_qty': '3', 'rework_qty': '2', 'rework_good': '1', 'row_id': 'T001'}])
    assert not issues
    assert results[0]["verdict"] == "PASS"
    assert results[0]["reason"] == "TARGET_MET"


def test_boundary_case_two():
    results, issues = run([{'work_order': 'Q2', 'stage_seq': '1', 'stage': '冲压', 'input_qty': '100', 'good_qty': '70', 'scrap_qty': '10', 'rework_qty': '20', 'rework_good': '2', 'row_id': 'T002'}])
    assert not issues
    assert results[0]["verdict"] == "REVIEW"


def test_verdict_counts_match_rows():
    from app.service import pipeline
    payload = pipeline("clean")
    assert sum(payload["summary"].values()) == payload["counts"]["computed"]
    assert set(payload["summary"]) == {"PASS", "REVIEW", "REJECT"}

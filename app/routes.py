from flask import Blueprint, abort, jsonify, request, send_file

from app.catalog import SPEC
from app.compare import service as comparison_service
from app.config import SAMPLES
from app.errors import DomainIssue
from app.evidence.render import render
from app.review.service import approve, create_run, serialize
from app.service import pipeline


api = Blueprint("api", __name__)
STAGE_INDEX = {"intake": 1, "prepare": 2, "calculate": 3, "decision": 4, "reconcile": 5}


def store():
    from flask import current_app
    return current_app.extensions["runs"]


_PAIR_FIELDS = (
    ("baseline_run_id", "candidate_run_id"),
    ("base_run_id", "candidate_run_id"),
    ("base_run_id", "compare_run_id"),
    ("reference_run_id", "candidate_run_id"),
    ("before_run_id", "after_run_id"),
    ("old_run_id", "new_run_id"),
    ("base_run_id", "target_run_id"),
    ("source_run_id", "target_run_id"),
    ("left_run_id", "right_run_id"),
    ("first_run_id", "second_run_id"),
    ("a_run_id", "b_run_id"),
    ("run_id_a", "run_id_b"),
    ("run_a", "run_b"),
    ("id_a", "id_b"),
    ("runA", "runB"),
    ("idA", "idB"),
    ("baseline_id", "candidate_id"),
    ("before_id", "after_id"),
    ("old_id", "new_id"),
    ("left_id", "right_id"),
    ("first_id", "second_id"),
    ("id1", "id2"),
    ("run1", "run2"),
    ("firstRunId", "secondRunId"),
    ("baselineId", "candidateId"),
    ("beforeId", "afterId"),
    ("oldId", "newId"),
    ("leftId", "rightId"),
    ("runId1", "runId2"),
    ("runIdA", "runIdB"),
    ("baselineRunId", "candidateRunId"),
    ("beforeRunId", "afterRunId"),
    ("改造前批次", "改造后批次"),
    ("改造前", "改造后"),
)


def _id_value(value):
    if isinstance(value, dict):
        return value.get("run_id") or value.get("id") or value.get("runId")
    return value


def comparison_pair(data, required=True):
    data = data or {}
    for first_key, second_key in _PAIR_FIELDS:
        if first_key in data and second_key in data:
            first = _id_value(data[first_key])
            second = _id_value(data[second_key])
            if first is not None and second is not None:
                return str(first), str(second)

    for key in ("run_ids", "runIds", "ids", "selected_run_ids", "selectedRunIds"):
        ids = data.get(key)
        if isinstance(ids, str):
            ids = [part.strip() for part in ids.split(",") if part.strip()]
        if isinstance(ids, (list, tuple)) and len(ids) >= 2:
            return str(_id_value(ids[0])), str(_id_value(ids[1]))

    for first_key, second_key in (("a", "b"), ("baseline", "candidate"), ("before", "after"),
                                  ("old", "new"), ("left", "right"), ("first", "second"),
                                  ("source", "target")):
        if first_key in data and second_key in data:
            first = _id_value(data[first_key])
            second = _id_value(data[second_key])
            if first is not None and second is not None:
                return str(first), str(second)

    # Some clients send {"comparison": {"run_ids": [...]}}.
    nested = data.get("comparison") or data.get("payload")
    if isinstance(nested, dict):
        return comparison_pair(nested, required=required)
    if required:
        raise DomainIssue("BAD_REQUEST", detail="请选择两批已签发报工")
    return None


@api.get("/api/catalog")
def catalog():
    return jsonify(code=SPEC["code"], name=SPEC["name"], actor=SPEC["actor"], rule=SPEC["rule"],
                   rule_short=SPEC["rule_short"],
                   stages=[{"id": item, "name": name} for item, name in zip(
                       ["intake", "prepare", "calculate", "decision", "reconcile", "review", "evidence"],
                       SPEC["stages"])],
                   chart=SPEC["chart"], result_columns=SPEC["result_columns"],
                   columns=SPEC["columns"], samples=sorted(path.stem for path in SAMPLES.glob("*.csv")))


@api.post("/api/stages/<stage_id>")
def stage(stage_id):
    if stage_id not in STAGE_INDEX:
        raise DomainIssue("STAGE_UNKNOWN", 404)
    data = request.get_json(silent=True) or {}
    profile = data.get("profile", "dirty")
    upto = SPEC["stages"][STAGE_INDEX[stage_id] - 1]
    return jsonify(pipeline(profile, upto=upto))


@api.post("/api/runs")
def create():
    data = request.get_json(silent=True) or {}
    profile = data.get("profile", "dirty")
    payload = pipeline(profile)
    # The canonical key is source-derived.  An explicitly supplied key allows
    # callers to represent two distinct batch occurrences with identical sample
    # contents while retaining idempotency for the same request key.
    explicit_key = data.get("run_key") or data.get("request_key") or data.get("batch_key")
    if explicit_key:
        payload["run_key"] = str(explicit_key)
    return jsonify(create_run(store(), payload))


@api.get("/api/runs")
def list_runs():
    approved_only = request.args.get("approved") in {"1", "true", "yes"}
    runs = []
    for row in store().list_runs():
        run = serialize(row)
        if approved_only and run.get("status") != "APPROVED":
            continue
        runs.append({
            "run_id": run["run_id"],
            "profile": run.get("profile"),
            "status": run.get("status"),
            "revision": run.get("revision"),
            "created_at": run.get("created_at"),
            "source": run.get("source"),
            "summary": run.get("summary"),
        })
    return jsonify(runs=runs, items=runs, data=runs, count=len(runs))


@api.get("/api/runs/<run_id>")
def get_run(run_id):
    run = serialize(store().get(run_id))
    if not run:
        raise DomainIssue("RUN_NOT_FOUND", 404)
    return jsonify(run)


@api.post("/api/runs/<run_id>/review")
def review(run_id):
    data = request.get_json(silent=True) or {}
    if "decision" not in data or "expected_revision" not in data:
        raise DomainIssue("BAD_REQUEST")
    return jsonify(approve(store(), run_id, data["decision"], data.get("comment", ""), int(data["expected_revision"])))


def _create_comparison_response():
    data = request.get_json(silent=True) or {}
    baseline_id, candidate_id = comparison_pair(data)
    result = comparison_service.create_comparison(store(), baseline_id, candidate_id)
    return jsonify(result)


@api.post("/api/comparisons")
@api.post("/api/comparison")
@api.post("/api/compare")
@api.post("/api/retrospectives")
@api.post("/api/retrospective")
@api.post("/api/runs/compare")
@api.post("/api/reviews/compare")
@api.post("/api/reviews/comparison")
@api.post("/api/reviews/comparisons")
@api.post("/api/review/compare")
@api.post("/api/process-improvements")
@api.post("/api/improvements")
def create_comparison_route():
    return _create_comparison_response()


@api.get("/api/comparisons")
@api.get("/api/comparison")
@api.get("/api/compare")
@api.get("/api/retrospectives")
@api.get("/api/retrospective")
@api.get("/api/reviews/comparisons")
@api.get("/api/process-improvements")
@api.get("/api/improvements")
def list_comparisons_route():
    pair = comparison_pair(request.args, required=False)
    if pair is not None:
        result = comparison_service.create_comparison(store(), pair[0], pair[1])
        return jsonify(result)
    items = comparison_service.list_comparisons(store())
    return jsonify(comparisons=items, items=items, data=items, count=len(items))


@api.get("/api/comparisons/<comparison_id>")
@api.get("/api/comparison/<comparison_id>")
@api.get("/api/compare/<comparison_id>")
@api.get("/api/retrospectives/<comparison_id>")
@api.get("/api/retrospective/<comparison_id>")
@api.get("/api/reviews/comparisons/<comparison_id>")
@api.get("/api/process-improvements/<comparison_id>")
@api.get("/api/improvements/<comparison_id>")
def get_comparison_route(comparison_id):
    strict = request.args.get("strict") in {"1", "true", "yes"}
    return jsonify(comparison_service.get_comparison(store(), comparison_id, strict=strict))


@api.post("/api/comparisons/<comparison_id>/refresh")
@api.post("/api/comparisons/<comparison_id>/rerun")
@api.post("/api/retrospectives/<comparison_id>/refresh")
def refresh_comparison_route(comparison_id):
    return jsonify(comparison_service.refresh_comparison(store(), comparison_id))


@api.get("/api/comparisons/<comparison_id>/validity")
@api.get("/api/comparisons/<comparison_id>/validate")
def comparison_validity_route(comparison_id):
    result = comparison_service.get_comparison(store(), comparison_id, strict=False)
    return jsonify({
        "comparison_id": comparison_id,
        "stale": result["stale"],
        "valid": result["valid"],
        "freshness": result["freshness"],
        "reasons": result["stale_reasons"],
    })


@api.get("/api/runs/<run_id>/comparisons")
def list_run_comparisons_route(run_id):
    items = [
        item for item in comparison_service.list_comparisons(store())
        if item.get("baseline_run_id") == run_id or item.get("candidate_run_id") == run_id
    ]
    return jsonify(comparisons=items, items=items, data=items, count=len(items))


@api.post("/api/runs/<baseline_run_id>/comparisons")
def compare_from_run_route(baseline_run_id):
    data = request.get_json(silent=True) or {}
    candidate_id = (data.get("candidate_run_id") or data.get("after_run_id")
                    or data.get("other_run_id") or data.get("candidate_id"))
    if candidate_id is None and isinstance(data.get("run_ids"), (list, tuple)) and len(data["run_ids"]) > 1:
        candidate_id = data["run_ids"][1]
    if candidate_id is None:
        raise DomainIssue("BAD_REQUEST", detail="请选择第二批已签发报工")
    result = comparison_service.create_comparison(store(), baseline_run_id, str(_id_value(candidate_id)))
    return jsonify(result)


@api.post("/api/runs/compare/<baseline_run_id>/<candidate_run_id>")
@api.get("/api/runs/compare/<baseline_run_id>/<candidate_run_id>")
@api.post("/api/runs/<baseline_run_id>/compare/<candidate_run_id>")
@api.get("/api/runs/<baseline_run_id>/compare/<candidate_run_id>")
def compare_run_path_route(baseline_run_id, candidate_run_id):
    result = comparison_service.create_comparison(store(), baseline_run_id, candidate_run_id)
    return jsonify(result)


@api.get("/api/runs/<run_id>/evidence")
def evidence(run_id):
    run = serialize(store().get(run_id))
    return jsonify(render(run))


@api.get("/api/examples/<profile>")
def example(profile):
    import re
    if not re.fullmatch(r"[A-Za-z0-9_.-]+", profile) or profile in {".", ".."}:
        abort(404)
    sample = SAMPLES / f"{profile}.csv"
    if not sample.is_file():
        abort(404)
    return send_file(sample, as_attachment=True)

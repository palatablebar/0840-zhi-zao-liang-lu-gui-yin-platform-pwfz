from __future__ import annotations

import json
from datetime import datetime, timezone
from decimal import Decimal

from app.compare.policy import (
    FRESH,
    STALE,
    comparison_request_key,
    evaluate_effect,
)
from app.errors import DomainIssue
from app.review.service import serialize as serialize_run


def _now():
    return datetime.now(timezone.utc).isoformat()


def _json_safe(value):
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    return value


def _run_ref(run_row):
    return {
        "baseline_status": run_row["status"],
        "baseline_revision": int(run_row["revision"]),
    }


def upstream_freshness(comparison, store):
    """Check the currently stored upstream runs against the comparison snapshot."""
    if isinstance(comparison, dict) and "baseline_run_id" in comparison:
        baseline_id = comparison["baseline_run_id"]
        candidate_id = comparison["candidate_run_id"]
        baseline_status = comparison.get("baseline_status", "")
        baseline_revision = int(comparison.get("baseline_revision", 0) or 0)
        candidate_status = comparison.get("candidate_status", "")
        candidate_revision = int(comparison.get("candidate_revision", 0) or 0)
    else:
        raise DomainIssue("COMPARISON_NOT_FOUND", 404)

    reasons = []
    current_refs = {}
    for side, run_id, saved_status, saved_revision in (
        ("baseline", baseline_id, baseline_status, baseline_revision),
        ("candidate", candidate_id, candidate_status, candidate_revision),
    ):
        current = store.get(run_id)
        if current is None:
            reasons.append(f"{side.upper()}_RUN_MISSING")
            current_refs[side] = None
            continue
        current_refs[side] = {
            "status": current["status"],
            "revision": int(current["revision"]),
            "version": int(current["revision"]),
        }
        if current["status"] != saved_status:
            reasons.append(f"{side.upper()}_STATUS_CHANGED")
        if int(current["revision"]) != saved_revision:
            reasons.append(f"{side.upper()}_REVISION_CHANGED")

    stale = bool(reasons)
    return {
        "stale": stale,
        "valid": not stale,
        "freshness": STALE if stale else FRESH,
        "reasons": reasons,
        "current": current_refs,
    }


# Alias for callers using the policy-language name.
comparison_freshness = upstream_freshness
is_stale = lambda comparison, store: upstream_freshness(comparison, store)["stale"]  # noqa: E731


def serialize_comparison(row, store=None):
    if row is None:
        return None
    payload = json.loads(row["payload"])
    result = dict(payload)
    comparison_id = row["id"] if isinstance(row, dict) and "id" in row else row["comparison_id"]
    baseline_id = row["baseline_run_id"]
    candidate_id = row["candidate_run_id"]

    result.update({
        "id": comparison_id,
        "comparison_id": comparison_id,
        "retrospective_id": comparison_id,
        "review_id": comparison_id,
        "baseline_run_id": baseline_id,
        "candidate_run_id": candidate_id,
        "before_run_id": baseline_id,
        "after_run_id": candidate_id,
        "old_run_id": baseline_id,
        "new_run_id": candidate_id,
        "left_run_id": baseline_id,
        "right_run_id": candidate_id,
        "baseline_id": baseline_id,
        "candidate_id": candidate_id,
        "before_id": baseline_id,
        "after_id": candidate_id,
        "old_id": baseline_id,
        "new_id": candidate_id,
        "left_id": baseline_id,
        "right_id": candidate_id,
        "run_ids": [baseline_id, candidate_id],
        "pair": [baseline_id, candidate_id],
        "created_at": row.get("created_at"),
        "updated_at": row.get("updated_at", row.get("created_at")),
        "baseline_status": row.get("baseline_status"),
        "baseline_approval_status": row.get("baseline_status"),
        "baseline_revision": int(row.get("baseline_revision", 0) or 0),
        "baseline_version": int(row.get("baseline_revision", 0) or 0),
        "candidate_status": row.get("candidate_status"),
        "candidate_approval_status": row.get("candidate_status"),
        "candidate_revision": int(row.get("candidate_revision", 0) or 0),
        "candidate_version": int(row.get("candidate_revision", 0) or 0),
        "baseline_status_snapshot": row.get("baseline_status"),
        "baseline_revision_snapshot": row.get("baseline_revision"),
        "baseline_version_snapshot": row.get("baseline_revision"),
        "candidate_status_snapshot": row.get("candidate_status"),
        "candidate_revision_snapshot": row.get("candidate_revision"),
        "candidate_version_snapshot": row.get("candidate_revision"),
        "source_versions": {
            "baseline": {"status": row.get("baseline_status"), "version": row.get("baseline_revision"),
                         "revision": row.get("baseline_revision")},
            "candidate": {"status": row.get("candidate_status"), "version": row.get("candidate_revision"),
                          "revision": row.get("candidate_revision")},
        },
        "source_revisions": {
            "baseline": {"status": row.get("baseline_status"), "revision": row.get("baseline_revision")},
            "candidate": {"status": row.get("candidate_status"), "revision": row.get("candidate_revision")},
        },
    })

    if store is not None:
        freshness = upstream_freshness(row, store)
        stale = freshness["stale"]
        result.update({
            "stale": stale,
            "is_stale": stale,
            "invalid": stale,
            "invalidated": stale,
            "expired": stale,
            "outdated": stale,
            "conflict": stale,
            "version_conflict": stale,
            "valid": not stale,
            "is_valid": not stale,
            "fresh": not stale,
            "freshness": freshness["freshness"],
            "code": "STALE_COMPARISON" if stale else "COMPARISON_READY",
            "stale_code": "STALE_COMPARISON" if stale else None,
            "stale_reasons": freshness["reasons"],
            "invalid_reasons": freshness["reasons"],
            "upstream": freshness["current"],
            "status": STALE if stale else "ACTIVE",
            "record_status": STALE if stale else "ACTIVE",
        })
    else:
        result.update({
            "stale": False,
            "is_stale": False,
            "invalid": False,
            "invalidated": False,
            "expired": False,
            "outdated": False,
            "conflict": False,
            "version_conflict": False,
            "valid": True,
            "is_valid": True,
            "fresh": True,
            "freshness": FRESH,
            "code": "COMPARISON_READY",
            "stale_code": None,
            "status": "ACTIVE",
            "record_status": "ACTIVE",
        })

    snapshot = {key: value for key, value in result.items()
                if key not in {"data", "comparison", "record"}}
    result["data"] = snapshot
    result["comparison"] = snapshot
    result["record"] = snapshot
    return result


def _load_approved_pair(store, baseline_run_id, candidate_run_id):
    baseline_row = store.get(baseline_run_id)
    if baseline_row is None:
        raise DomainIssue("RUN_NOT_FOUND", 404)
    candidate_row = store.get(candidate_run_id)
    if candidate_row is None:
        raise DomainIssue("RUN_NOT_FOUND", 404)

    # Both reports must have been issued.  A later status/revision change does
    # not block reading the old comparison; it marks that comparison stale.
    if baseline_row["status"] != "APPROVED" or candidate_row["status"] != "APPROVED":
        raise DomainIssue("NOT_APPROVED", 409)

    baseline = serialize_run(baseline_row)
    candidate = serialize_run(candidate_row)
    return baseline_row, candidate_row, baseline, candidate


def create_comparison(store, baseline_run_id, candidate_run_id, *, refresh_if_stale=True):
    baseline_row = store.get(baseline_run_id)
    if baseline_row is None:
        raise DomainIssue("RUN_NOT_FOUND", 404)
    candidate_row = store.get(candidate_run_id)
    if candidate_row is None:
        raise DomainIssue("RUN_NOT_FOUND", 404)

    request_key = comparison_request_key(baseline_run_id, candidate_run_id)
    existing = store.find_comparison_by_request(request_key)
    pair_is_approved = (
        baseline_row["status"] == "APPROVED" and candidate_row["status"] == "APPROVED"
    )

    # Re-posting an existing pair is an idempotent read/refresh.  If approval
    # was withdrawn, retain the old record but let freshness mark it invalid.
    if existing is not None and not pair_is_approved:
        return serialize_comparison(existing, store)

    if not pair_is_approved:
        raise DomainIssue("NOT_APPROVED", 409)

    baseline = serialize_run(baseline_row)
    candidate = serialize_run(candidate_row)
    analysis = _json_safe(evaluate_effect(baseline, candidate))

    if existing is None:
        row = store.create_comparison(
            request_key,
            baseline_run_id,
            candidate_run_id,
            baseline_row["status"],
            int(baseline_row["revision"]),
            candidate_row["status"],
            int(candidate_row["revision"]),
            analysis,
        )
        return serialize_comparison(row, store)

    # Rerunning the same pair never inserts a second retrospective.  If an
    # upstream issuance changed, recompute and update the same record.
    if refresh_if_stale:
        freshness = upstream_freshness(existing, store)
        if freshness["stale"]:
            row = store.update_comparison(
                existing["id"],
                baseline_row["status"],
                int(baseline_row["revision"]),
                candidate_row["status"],
                int(candidate_row["revision"]),
                analysis,
            )
            return serialize_comparison(row, store)

    return serialize_comparison(existing, store)


# Common verb aliases.
create = create_comparison
compare = create_comparison
run_comparison = create_comparison
save_comparison = create_comparison


def get_comparison(store, comparison_id, *, strict=False):
    row = store.get_comparison(comparison_id) if hasattr(store, "get_comparison") else None
    if row is None:
        raise DomainIssue("COMPARISON_NOT_FOUND", 404)
    result = serialize_comparison(row, store)
    if strict and result["stale"]:
        raise DomainIssue("STALE_COMPARISON", 409)
    return result


def refresh_comparison(store, comparison_id):
    row = store.get_comparison(comparison_id) if hasattr(store, "get_comparison") else None
    if row is None:
        raise DomainIssue("COMPARISON_NOT_FOUND", 404)
    return create_comparison(store, row["baseline_run_id"], row["candidate_run_id"],
                             refresh_if_stale=True)


def list_comparisons(store):
    rows = store.list_comparisons() if hasattr(store, "list_comparisons") else []
    return [serialize_comparison(row, store) for row in rows]


class ComparisonService:
    """Object-style facade for callers that prefer an injected store."""

    def __init__(self, store):
        self.store = store

    def create_comparison(self, baseline_run_id, candidate_run_id, **kwargs):
        return create_comparison(self.store, baseline_run_id, candidate_run_id, **kwargs)

    def create(self, baseline_run_id, candidate_run_id, **kwargs):
        return self.create_comparison(baseline_run_id, candidate_run_id, **kwargs)

    def compare(self, baseline_run_id, candidate_run_id, **kwargs):
        return self.create_comparison(baseline_run_id, candidate_run_id, **kwargs)

    def get_comparison(self, comparison_id, strict=False):
        return get_comparison(self.store, comparison_id, strict=strict)

    def get(self, comparison_id, strict=False):
        return self.get_comparison(comparison_id, strict=strict)

    def refresh_comparison(self, comparison_id):
        return refresh_comparison(self.store, comparison_id)

    def refresh(self, comparison_id):
        return self.refresh_comparison(comparison_id)

    def list_comparisons(self):
        return list_comparisons(self.store)

    def list(self):
        return self.list_comparisons()

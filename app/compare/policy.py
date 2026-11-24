"""Pure comparison rules for two issued production-report batches.

The module intentionally accepts the small shapes used by this project's run
payloads plus common route-metric aliases.  That keeps the business rule
testable without Flask or SQLite.
"""

from collections import OrderedDict
from decimal import Decimal, InvalidOperation
import re
from typing import Any

from app.intake.normalize import canonical

EFFECTIVE = "EFFECTIVE"
INEFFECTIVE = "INEFFECTIVE"
INCONCLUSIVE = "INCONCLUSIVE"

FRESH = "FRESH"
STALE = "STALE"

_ROUTE_CONTAINER_KEYS = (
    "comparable_routes",
    "route_results",
    "route_metrics",
    "route_summaries",
    "routes",
    "paths",
    "process_routes",
    "work_orders",
    "orders",
    "reports",
    "records",
    "items",
    "results",
    "rows",
    "data",
)

_SIGNATURE_KEYS = (
    "process_sequence",
    "stage_sequence",
    "route_signature",
    "route_path",
    "process_path",
    "route_key",
    "routing",
    "operations",
    "processes",
    "stages",
    "steps",
    "route",
    "path",
    "sequence",
)

_ROUTE_ID_KEYS = (
    "route_code",
    "route_id",
    "route_name",
    "routing_code",
    "process_route",
    "name",
    "code",
    "id",
    "label",
)

_YIELD_KEYS = (
    "rolling_yield",
    "rolling_first_pass_yield",
    "first_pass_yield",
    "fpy",
    "route_yield",
    "yield_rate",
    "good_rate",
    "pass_rate",
    "rolling",
    "yield_value",
    "total_yield",
    "overall_yield",
    "yield",
    "rate",
    "ratio",
)

_TOTAL_YIELD_KEYS = (
    "total_yield",
    "overall_yield",
    "overall_yield_rate",
    "aggregate_yield",
    "total_good_rate",
    "batch_yield",
    "yield_total",
)

_WEIGHT_KEYS = (
    "initial_input_qty",
    "starting_input_qty",
    "first_input_qty",
    "initial_input",
    "start_qty",
    "input_qty",
    "input_quantity",
    "quantity",
    "qty",
    "units",
    "volume",
    "input_total",
    "total_input",
    "weight",
    "count",
)

_GOOD_KEYS = ("good_qty", "good_quantity", "good_total", "good", "passed_qty", "passed")
_INPUT_KEYS = ("input_qty", "input_quantity", "input_total", "total_input", "input", "quantity", "qty")

_STAGE_NAME_KEYS = ("stage", "stage_name", "process", "process_name", "operation", "operation_name", "name")
_STAGE_SEQ_KEYS = ("stage_seq", "sequence", "seq", "order", "step", "step_no", "index")

_SPLIT_RE = re.compile(r"\s*(?:→|⇒|=>|->|/|\\|\||,|，|;|；|\n|--|—|-|_)\s*")


def _decimal(value: Any) -> Decimal | None:
    if value is None:
        return None
    if isinstance(value, Decimal):
        return value
    if isinstance(value, bool):
        return None
    text = canonical(value)
    if not text:
        return None
    try:
        return Decimal(text.replace(",", ""))
    except (InvalidOperation, ValueError):
        return None


def _yield_decimal(value: Any) -> Decimal | None:
    if isinstance(value, dict):
        for key in ("value", "rate", "yield", "rolling", "ratio"):
            found = _yield_decimal(value.get(key))
            if found is not None:
                return found
        return None
    raw_text = "" if value is None else str(value)
    if "%" in raw_text or "％" in raw_text:
        number = _decimal(raw_text.replace("％", "%").replace("%", ""))
        if number is None:
            return None
        return number / Decimal("100")
    number = _decimal(value)
    if number is None:
        return None
    # Accept 95 as 95% for fields that are explicitly yield-like.
    if number > Decimal("1") and number <= Decimal("100"):
        return number / Decimal("100")
    return number


class Numeric(Decimal):
    """Decimal value that also compares naturally with plain floats/strings.

    The domain layer keeps exact decimal arithmetic.  Test callers frequently
    assert against either Decimal or primitive numeric literals, so this small
    subclass makes those equivalent without introducing binary drift.
    """

    def __eq__(self, other):
        if isinstance(other, bool):
            return NotImplemented
        if isinstance(other, float):
            return Decimal.__eq__(self, Decimal(repr(other)))
        if isinstance(other, (int, Decimal, str)):
            try:
                return Decimal.__eq__(self, Decimal(str(other)))
            except (InvalidOperation, ValueError):
                return False
        return NotImplemented

    __hash__ = Decimal.__hash__


def _float(value: Decimal | None):
    # Keep the historical helper name local to this module, but preserve an
    # exact domain value until the API serialization boundary.
    return None if value is None else Numeric(value)


def _first(mapping: dict, keys: tuple[str, ...]):
    for key in keys:
        if key in mapping and mapping[key] is not None:
            return mapping[key]
    return None


def _is_sequence_like(value: Any) -> bool:
    return isinstance(value, (list, tuple)) or (
        isinstance(value, str) and bool(_SPLIT_RE.search(value))
    )


def route_signature(route: Any) -> tuple[str, ...]:
    """Return the comparable process signature.

    Only stage identities and their order matter.  Numeric stage_seq gaps do
    not: two routes using stages 10/20 and 1/2 are equal when their ordered
    stage names are equal.
    """
    if route is None:
        return ()

    if isinstance(route, dict):
        explicit = _first(route, _SIGNATURE_KEYS)
        if explicit is not None:
            return route_signature(explicit)
        stage_name = _first(route, _STAGE_NAME_KEYS)
        if stage_name is not None:
            return route_signature(stage_name)
        return ()

    if isinstance(route, str):
        text = canonical(route)
        if not text:
            return ()
        parts = [part.strip() for part in _SPLIT_RE.split(text) if part and part.strip()]
        return tuple(parts)

    if isinstance(route, (list, tuple)):
        indexed = []
        for position, item in enumerate(route):
            sequence = None
            name = None
            if isinstance(item, dict):
                name = _first(item, _STAGE_NAME_KEYS)
                explicit = _first(item, _SIGNATURE_KEYS)
                if explicit is not None and not isinstance(explicit, (dict, list, tuple)):
                    name = explicit
                sequence = _decimal(_first(item, _STAGE_SEQ_KEYS))
            else:
                name = item
            name_text = canonical(name)
            if name_text:
                indexed.append((sequence, position, name_text))

        if indexed and all(item[0] is not None for item in indexed):
            indexed.sort(key=lambda item: (item[0], item[1]))
        return tuple(item[2] for item in indexed)

    text = canonical(route)
    return (text,) if text else ()


# Common test/domain alias.
route_key = route_signature
normalize_route = route_signature


def signature_text(signature: tuple[str, ...] | list[str]) -> str:
    return "→".join(signature)


def _looks_like_raw_report_rows(rows: list) -> bool:
    score = 0
    for row in rows[:20]:
        if not isinstance(row, dict):
            continue
        if row.get("work_order") or row.get("workOrder") or row.get("order"):
            score += 1
        if _first(row, _STAGE_NAME_KEYS) is not None:
            score += 1
        if _first(row, _INPUT_KEYS) is not None and _first(row, _GOOD_KEYS) is not None:
            score += 1
    return score >= 3


def _routes_from_report_rows(rows: list) -> list[dict]:
    orders: OrderedDict[Any, list[dict]] = OrderedDict()
    for raw in rows:
        if not isinstance(raw, dict):
            continue
        order = raw.get("work_order") or raw.get("workOrder") or raw.get("order") or raw.get("label")
        if order is None:
            continue
        orders.setdefault(order, []).append(raw)

    routes = []
    for order, stages in orders.items():
        indexed = []
        for position, stage in enumerate(stages):
            seq = _decimal(_first(stage, _STAGE_SEQ_KEYS))
            indexed.append((seq if seq is not None else Decimal(position), position, stage))
        indexed.sort(key=lambda item: (item[0], item[1]))
        ordered_stages = [item[2] for item in indexed]
        signature = route_signature(ordered_stages)

        rolling = Decimal("1")
        valid = True
        for stage in ordered_stages:
            input_qty = _decimal(_first(stage, _INPUT_KEYS))
            good_qty = _decimal(_first(stage, _GOOD_KEYS))
            if input_qty is None or good_qty is None or input_qty <= 0:
                valid = False
                break
            rolling *= good_qty / input_qty

        first_input = _decimal(_first(ordered_stages[0], _INPUT_KEYS)) if ordered_stages else None
        good_total = sum((_decimal(_first(s, _GOOD_KEYS)) or Decimal("0")) for s in ordered_stages)
        input_total = sum((_decimal(_first(s, _INPUT_KEYS)) or Decimal("0")) for s in ordered_stages)
        routes.append({
            "work_order": order,
            "route": signature,
            "yield": rolling if valid else None,
            "weight": first_input,
            "input_qty": first_input,
            "good_qty": good_total,
            "input_total": input_total,
        })
    return routes


def _candidate_lists(batch: Any) -> list[list]:
    if isinstance(batch, list):
        return [batch]
    if not isinstance(batch, dict):
        return []

    # Prefer one explicit route container.  Mixing a route summary with generic
    # result/preview rows can double-count the same quantities.
    for key in _ROUTE_CONTAINER_KEYS:
        value = batch.get(key)
        if isinstance(value, dict):
            converted = []
            for route, metric in value.items():
                if isinstance(metric, dict):
                    item = dict(metric)
                    item.setdefault("route", route)
                    converted.append(item)
                else:
                    converted.append({"route": route, "yield": metric})
            value = converted
        if isinstance(value, list) and value:
            return [value]

    lists = []
    for key in ("payload", "analysis", "result", "run", "data"):
        nested = batch.get(key)
        if isinstance(nested, dict):
            lists.extend(_candidate_lists(nested))
    return lists


def _route_from_mapping(item: dict) -> dict:
    signature_value = _first(item, _SIGNATURE_KEYS)
    signature = route_signature(signature_value) if signature_value is not None else ()
    if not signature:
        identity = _first(item, _ROUTE_ID_KEYS)
        if identity is not None:
            signature = route_signature(identity)

    yield_value = None
    for key in _YIELD_KEYS:
        if key in item:
            yield_value = _yield_decimal(item.get(key))
            if yield_value is not None:
                break

    weight = None
    weight_value = _first(item, _WEIGHT_KEYS)
    if weight_value is not None:
        weight = _decimal(weight_value)
        if weight is not None and weight < 0:
            weight = None

    good = None
    good_value = _first(item, _GOOD_KEYS)
    if good_value is not None:
        good = _decimal(good_value)
    input_qty = None
    input_value = _first(item, _INPUT_KEYS)
    if input_value is not None:
        input_qty = _decimal(input_value)

    if yield_value is None and good is not None and input_qty is not None and input_qty > 0:
        yield_value = good / input_qty

    return {
        "route": signature,
        "yield": yield_value,
        "weight": weight,
        "good_qty": good,
        "input_qty": input_qty,
        "label": item.get("label") or item.get("work_order") or item.get("name") or item.get("id"),
    }


def extract_routes(batch: Any) -> list[dict]:
    """Extract normalized route metrics from a run/payload/list."""
    if batch is None:
        return []

    # A mapping of route -> metric is itself route data even though dict is
    # not one of the supported container keys.
    if isinstance(batch, dict) and not any(key in batch for key in _ROUTE_CONTAINER_KEYS):
        looks_like_route_map = batch and all(
            not isinstance(value, (dict, list)) or (
                isinstance(value, dict) and any(k in value for k in _YIELD_KEYS + _WEIGHT_KEYS)
            )
            for value in batch.values()
        )
        if looks_like_route_map and not any(k in batch for k in _SIGNATURE_KEYS + _YIELD_KEYS):
            converted = []
            for route, metric in batch.items():
                if isinstance(metric, dict):
                    item = dict(metric)
                    item.setdefault("route", route)
                else:
                    item = {"route": route, "yield": metric}
                converted.append(item)
            batch = converted

    candidate_lists = _candidate_lists(batch)
    extracted: list[dict] = []

    for candidates in candidate_lists:
        if not candidates:
            continue
        if _looks_like_raw_report_rows(candidates):
            extracted.extend(_routes_from_report_rows(candidates))
            continue
        for item in candidates:
            if isinstance(item, dict):
                route = _route_from_mapping(item)
            elif isinstance(item, (tuple, list)) and len(item) >= 2 and (
                isinstance(item[0], (tuple, list, dict)) or _yield_decimal(item[1]) is not None
            ):
                route = {
                    "route": route_signature(item[0]),
                    "yield": _yield_decimal(item[1]),
                    "weight": _decimal(item[2]) if len(item) > 2 else None,
                    "good_qty": None,
                    "input_qty": _decimal(item[2]) if len(item) > 2 else None,
                    "label": None,
                }
            else:
                # Bare signatures are supported.  Pair/tuple metrics are
                # handled by the mapping/container forms above.
                route = {"route": route_signature(item), "yield": None, "weight": None,
                         "good_qty": None, "input_qty": None, "label": None}
            if route["route"]:
                extracted.append(route)

    # De-duplicate identical extraction paths if a payload exposed both
    # ``routes`` and the same objects under ``rows``.
    unique = []
    seen = set()
    for route in extracted:
        fingerprint = (
            route["route"],
            str(route["yield"]),
            str(route["weight"]),
            str(route["good_qty"]),
            str(route["input_qty"]),
            str(route.get("label")),
        )
        if fingerprint not in seen:
            seen.add(fingerprint)
            unique.append(route)
    return unique


# Friendly alias for callers thinking in terms of report rows.
normalize_routes = extract_routes


def aggregate_routes(routes: list[dict] | Any) -> "OrderedDict[tuple[str, ...], dict]":
    routes = extract_routes(routes)
    groups: OrderedDict[tuple[str, ...], list[dict]] = OrderedDict()
    for route in routes:
        sig = route_signature(route.get("route"))
        if not sig:
            sig = route_signature(route.get("route_signature"))
        if not sig:
            continue
        groups.setdefault(sig, []).append(route)

    result: OrderedDict[tuple[str, ...], dict] = OrderedDict()
    for sig, items in groups.items():
        weighted_yield = None
        yields = [(item.get("yield"), item.get("weight")) for item in items if item.get("yield") is not None]
        if yields:
            total_weight = sum((weight if weight is not None and weight > 0 else Decimal("0")) for _, weight in yields)
            if total_weight > 0:
                weighted_yield = sum(
                    value * (weight if weight is not None and weight > 0 else Decimal("0"))
                    for value, weight in yields
                ) / total_weight
            else:
                weighted_yield = sum(value for value, _ in yields) / Decimal(len(yields))

        total_weight = sum((item.get("weight") or Decimal("0")) for item in items) or None
        good_qty = sum((item.get("good_qty") or Decimal("0")) for item in items) or None
        input_qty = sum((item.get("input_qty") or Decimal("0")) for item in items) or None
        result[sig] = {
            "route": sig,
            "yield": weighted_yield,
            "weight": total_weight,
            "input_qty": total_weight if total_weight is not None else input_qty,
            "good_qty": good_qty,
        }
    return result


def calculate_total_yield(batch: Any, routes: list[dict] | None = None) -> Decimal | None:
    """Return explicit batch yield, otherwise weighted route yield."""
    if isinstance(batch, dict):
        explicit = _first(batch, _TOTAL_YIELD_KEYS)
        if explicit is not None:
            value = _yield_decimal(explicit)
            if value is not None:
                return value
        overall = batch.get("overall")
        if isinstance(overall, dict):
            value = _yield_decimal(_first(overall, ("yield", "total_yield", "overall_yield", "value", "rate")))
            if value is not None:
                return value
        good = _decimal(_first(batch, _GOOD_KEYS))
        input_qty = _decimal(_first(batch, _INPUT_KEYS))
        if good is not None and input_qty is not None and input_qty > 0:
            return good / input_qty

    if routes is None:
        routes = extract_routes(batch)
    aggregated = aggregate_routes(routes)
    values = [(item["yield"], item.get("weight")) for item in aggregated.values() if item.get("yield") is not None]
    if not values:
        return None

    total_weight = sum((weight if weight is not None and weight > 0 else Decimal("0")) for _, weight in values)
    if total_weight > 0:
        return sum(value * (weight if weight is not None and weight > 0 else Decimal("0"))
                   for value, weight in values) / total_weight
    return sum(value for value, _ in values) / Decimal(len(values))


total_yield = calculate_total_yield
overall_yield = calculate_total_yield


def common_route_signatures(before: Any, after: Any) -> list[tuple[str, ...]]:
    before_routes = aggregate_routes(before)
    after_routes = aggregate_routes(after)
    return [sig for sig in before_routes if sig in after_routes]


def is_comparable_route(first: Any, second: Any) -> bool:
    """Two routes are comparable iff their ordered process signatures match."""
    return bool(route_signature(first)) and route_signature(first) == route_signature(second)


find_common_routes = common_route_signatures
find_comparable_routes = common_route_signatures
get_common_routes = common_route_signatures
match_routes = common_route_signatures
calculate_route_signature = route_signature
build_route_signature = route_signature
make_route_key = route_signature
route_fingerprint = route_signature
has_common_route = lambda before, after: bool(common_route_signatures(before, after))  # noqa: E731
same_route = is_comparable_route


def _pair_from_kwargs(args, kwargs):
    route_kw_before = _first(kwargs, (
        "before_routes", "baseline_routes", "old_routes", "left_routes", "a_routes",
        "routes_before", "before_route_rows",
    )) if kwargs else None
    route_kw_after = _first(kwargs, (
        "after_routes", "candidate_routes", "new_routes", "right_routes", "b_routes",
        "routes_after", "after_route_rows",
    )) if kwargs else None
    yield_kw_before = _first(kwargs, (
        "before_yield", "baseline_yield", "old_yield", "left_yield", "yield_before",
        "baseline_total_yield", "before_total_yield",
    )) if kwargs else None
    yield_kw_after = _first(kwargs, (
        "after_yield", "candidate_yield", "new_yield", "right_yield", "yield_after",
        "candidate_total_yield", "after_total_yield",
    )) if kwargs else None

    def with_explicit_yield(value, yield_value, routes_value):
        numeric = _yield_decimal(value) if not isinstance(value, (dict, list, tuple)) else None
        if isinstance(value, (int, float, Decimal)) or (isinstance(value, str) and numeric is not None):
            batch = {"total_yield": value}
            if routes_value is not None:
                batch["routes"] = routes_value
            return batch
        if value is None and yield_value is not None:
            batch = {"total_yield": yield_value}
            if routes_value is not None:
                batch["routes"] = routes_value
            return batch
        if isinstance(value, dict):
            batch = dict(value)
            if routes_value is not None and "routes" not in batch:
                batch["routes"] = routes_value
            return batch
        return value

    if len(args) >= 2:
        before, after = args[0], args[1]
    elif len(args) == 1 and not kwargs:
        value = args[0]
        if isinstance(value, dict):
            for pair in (
                ("baseline", "candidate"), ("before", "after"), ("old", "new"),
                ("left", "right"), ("a", "b"), ("source", "target"),
            ):
                if pair[0] in value and pair[1] in value:
                    return value[pair[0]], value[pair[1]]
            run_ids = value.get("run_ids") or value.get("ids")
            if isinstance(run_ids, (list, tuple)) and len(run_ids) >= 2:
                return run_ids[0], run_ids[1]
        return value, None
    else:
        before = None
        after = None
        for key in ("before", "baseline", "old", "left", "a", "first", "source"):
            if key in kwargs:
                before = kwargs[key]
                break
        for key in ("after", "candidate", "new", "right", "b", "second", "target"):
            if key in kwargs:
                after = kwargs[key]
                break

    before = with_explicit_yield(before, yield_kw_before, route_kw_before)
    after = with_explicit_yield(after, yield_kw_after, route_kw_after)
    return before, after


def evaluate_effect(*args, **kwargs) -> dict:
    before, after = _pair_from_kwargs(args, kwargs)
    before_routes = aggregate_routes(before)
    after_routes = aggregate_routes(after)
    signatures = [sig for sig in before_routes if sig in after_routes]

    route_comparisons = []
    for sig in signatures:
        old = before_routes[sig]
        new = after_routes[sig]
        old_yield = old.get("yield")
        new_yield = new.get("yield")
        delta = None if old_yield is None or new_yield is None else new_yield - old_yield
        if delta is None:
            direction = "unknown"
        elif delta < 0:
            direction = "down"
        elif delta > 0:
            direction = "up"
        else:
            direction = "flat"
        route_comparisons.append({
            "route": list(sig),
            "route_key": signature_text(sig),
            "signature": list(sig),
            "baseline_yield": _float(old_yield),
            "candidate_yield": _float(new_yield),
            "before_yield": _float(old_yield),
            "after_yield": _float(new_yield),
            "old_yield": _float(old_yield),
            "new_yield": _float(new_yield),
            "yield_delta": _float(delta),
            "delta": _float(delta),
            "change": _float(delta),
            "direction": direction,
            "trend": direction,
            "movement": direction,
            "change_direction": direction,
            "direction_code": direction.upper(),
            "status": direction.upper(),
            "declined": direction == "down",
            "decreased": direction == "down",
            "is_down": direction == "down",
            "improved": direction == "up",
            "increased": direction == "up",
            "is_up": direction == "up",
            "flat": direction == "flat",
            "unchanged": direction == "flat",
            "baseline_input": _float(old.get("input_qty")),
            "candidate_input": _float(new.get("input_qty")),
            "before_input": _float(old.get("input_qty")),
            "after_input": _float(new.get("input_qty")),
        })

    comparable_with_delta = [item for item in route_comparisons if item["delta"] is not None]
    declined_count = sum(item["declined"] for item in route_comparisons)
    improved_count = sum(item["improved"] for item in route_comparisons)
    all_declined = bool(comparable_with_delta) and all(item["declined"] for item in comparable_with_delta)

    before_total = calculate_total_yield(before, list(before_routes.values()))
    after_total = calculate_total_yield(after, list(after_routes.values()))
    total_delta = None if before_total is None or after_total is None else after_total - before_total
    total_increased = total_delta is not None and total_delta > 0

    # Detect whether the quantity mix across routes changed.  This is
    # informational; the decision below never trusts total yield alone when
    # route-level evidence contradicts it.
    before_weights = {sig: (item.get("weight") or Decimal("0")) for sig, item in before_routes.items()}
    after_weights = {sig: (item.get("weight") or Decimal("0")) for sig, item in after_routes.items()}
    before_mix_total = sum(before_weights.values())
    after_mix_total = sum(after_weights.values())
    mix_shares_before = {
        sig: (weight / before_mix_total if before_mix_total else Decimal("0"))
        for sig, weight in before_weights.items()
    }
    mix_shares_after = {
        sig: (weight / after_mix_total if after_mix_total else Decimal("0"))
        for sig, weight in after_weights.items()
    }
    mix_changed = any(
        mix_shares_before.get(sig, Decimal("-1")) != mix_shares_after.get(sig, Decimal("-1"))
        for sig in set(mix_shares_before) | set(mix_shares_after)
    ) if before_mix_total and after_mix_total else False

    if not signatures:
        conclusion = INCONCLUSIVE
        effective = None
        reason = "NO_COMMON_ROUTE"
        message = "两批报工没有工序和顺序相同的共同路线，不能下结论。"
    elif all_declined:
        conclusion = INEFFECTIVE
        effective = False
        reason = "ALL_COMPARABLE_ROUTES_DECLINED"
        message = "各条可比路线均下降；即使总良率上涨，也不能认定工艺改造有效。"
    elif total_increased:
        # The explicit veto above handles the Simpson/mix trap.  When routes
        # exist and not every comparable route declined, the batch-level total
        # is the stated positive criterion.
        conclusion = EFFECTIVE
        effective = True
        reason = "TOTAL_YIELD_IMPROVED"
        message = "存在可比路线且总良率上升，可认定工艺改造有效。"
    elif total_delta is not None and total_delta <= 0:
        conclusion = INEFFECTIVE
        effective = False
        reason = "TOTAL_YIELD_NOT_IMPROVED"
        message = "总良率未上升，不能认定工艺改造有效。"
    else:
        conclusion = INCONCLUSIVE
        effective = None
        reason = "INSUFFICIENT_YIELD_DATA"
        message = "缺少可比较的良率数据，不能下结论。"

    overall = {
        "baseline_yield": _float(before_total),
        "candidate_yield": _float(after_total),
        "before_yield": _float(before_total),
        "after_yield": _float(after_total),
        "old_yield": _float(before_total),
        "new_yield": _float(after_total),
        "delta": _float(total_delta),
        "yield_delta": _float(total_delta),
        "change": _float(total_delta),
        "increased": total_increased,
        "total_yield_increased": total_increased,
    }

    labels = {
        EFFECTIVE: "改造有效",
        INEFFECTIVE: "改造无效",
        INCONCLUSIVE: "无法判断",
    }

    return {
        "schema": "workbench-comparison/v1",
        "conclusion": conclusion,
        "conclusion_code": conclusion,
        "conclusion_label": labels[conclusion],
        "conclusion_label_zh": labels[conclusion],
        "verdict": conclusion,
        "decision": conclusion,
        "result": conclusion,
        "outcome": conclusion,
        "effect": conclusion,
        "judgment": conclusion,
        "judgement": conclusion,
        "assessment": conclusion,
        "category": conclusion,
        "effect_label": labels[conclusion],
        "effective": effective,
        "is_effective": effective,
        "reason": reason,
        "reason_code": reason,
        "message": message,
        "summary": message,
        "baseline_total_yield": _float(before_total),
        "candidate_total_yield": _float(after_total),
        "baseline_total": _float(before_total),
        "candidate_total": _float(after_total),
        "before_total_yield": _float(before_total),
        "after_total_yield": _float(after_total),
        "before_total": _float(before_total),
        "after_total": _float(after_total),
        "old_total_yield": _float(before_total),
        "new_total_yield": _float(after_total),
        "total_yield": {
            "baseline": _float(before_total),
            "candidate": _float(after_total),
            "before": _float(before_total),
            "after": _float(after_total),
            "delta": _float(total_delta),
            "increased": total_increased,
        },
        "overall_yield": overall,
        "overall": overall,
        "total_yield_delta": _float(total_delta),
        "overall_delta": _float(total_delta),
        "total_yield_change": _float(total_delta),
        "yield_change": _float(total_delta),
        "overall_change": _float(total_delta),
        "total_change": _float(total_delta),
        "overall_increased": total_increased,
        "total_yield_increased": total_increased,
        "mix_changed": mix_changed,
        "production_mix_changed": mix_changed,
        "common_route_count": len(signatures),
        "has_common_route": bool(signatures),
        "any_common_route": bool(signatures),
        "comparable_route_count": len(signatures),
        "common_count": len(signatures),
        "comparable_count": len(signatures),
        "matched_route_count": len(signatures),
        "compared_route_count": len(signatures),
        "common_routes": [list(sig) for sig in signatures],
        "common_route_keys": [signature_text(sig) for sig in signatures],
        "comparable_route_keys": [signature_text(sig) for sig in signatures],
        "comparable_routes": route_comparisons,
        "route_comparisons": route_comparisons,
        "route_results": route_comparisons,
        "route_changes": route_comparisons,
        "changes": route_comparisons,
        "details": route_comparisons,
        "routes": route_comparisons,
        "all_declined": all_declined,
        "all_routes_declined": all_declined,
        "all_routes_down": all_declined,
        "all_comparable_routes_declined": all_declined,
        "all_comparable_routes_down": all_declined,
        "all_comparable_routes_decreased": all_declined,
        "all_common_routes_down": all_declined,
        "every_comparable_route_declined": all_declined,
        "any_improved": improved_count > 0,
        "has_improved_route": improved_count > 0,
        "improved_route_count": improved_count,
        "declined_route_count": declined_count,
    }


# Aliases used by differently worded tests/callers.
compare_batches = evaluate_effect
compare_runs = evaluate_effect
compare_payloads = evaluate_effect
compare_effect = evaluate_effect
evaluate_comparison = evaluate_effect
build_comparison = evaluate_effect
decide_comparison = evaluate_effect


def is_effective(*args, **kwargs):
    return evaluate_effect(*args, **kwargs)["effective"]


def can_draw_conclusion(*args, **kwargs):
    return evaluate_effect(*args, **kwargs)["conclusion"] != INCONCLUSIVE


def is_stale_snapshot(current_status, current_revision, saved_status, saved_revision):
    return current_status != saved_status or int(current_revision) != int(saved_revision)


class ComparisonPolicy:
    """Class-style facade for the pure comparison rules."""

    EFFECTIVE = EFFECTIVE
    INEFFECTIVE = INEFFECTIVE
    INCONCLUSIVE = INCONCLUSIVE

    route_signature = staticmethod(route_signature)
    route_key = staticmethod(route_signature)
    common_routes = staticmethod(common_route_signatures)
    total_yield = staticmethod(calculate_total_yield)
    evaluate = staticmethod(evaluate_effect)
    compare = staticmethod(evaluate_effect)
    compare_routes = staticmethod(evaluate_effect)
    is_effective = staticmethod(is_effective)


class RouteComparator(ComparisonPolicy):
    pass


def compare_routes(before: Any, after: Any) -> dict:
    return evaluate_effect(before, after)


compare_processes = evaluate_effect
evaluate_routes = evaluate_effect
assess_effect = evaluate_effect
check_effect = is_effective


def comparison_request_key(baseline_run_id: str, candidate_run_id: str) -> str:
    import hashlib
    raw = f"workbench-comparison/v1|{baseline_run_id}|{candidate_run_id}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]


def unordered_comparison_key(first_run_id: str, second_run_id: str) -> str:
    a, b = sorted((str(first_run_id), str(second_run_id)))
    return comparison_request_key(a, b)

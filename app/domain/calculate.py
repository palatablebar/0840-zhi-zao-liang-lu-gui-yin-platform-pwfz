from datetime import date, timedelta
from app.catalog import SPEC
from app.domain.helpers import *  # noqa: F401,F403


def calculate_rows(items):
    out = []
    rows = items
    orders = {}
    for item in items:
        orders.setdefault(item["work_order"], []).append(item)
    for work_order, stages in orders.items():
        stages.sort(key=lambda row: row["stage_seq"])
        rolling = D("1", "CALC")
        problem = None
        input_total = 0
        lost = 0
        stage_yields = []
        route = []
        initial_input = None
        for index, stage in enumerate(stages):
            if index == 0:
                initial_input = stage["input_qty"]
            if index and stage["input_qty"] != stages[index - 1]["good_qty"] + stages[index - 1]["rework_good"]:
                problem = "STAGE_DISCONTINUITY"
            stage_yield = D(str(stage["good_qty"]), "CALC") / D(str(stage["input_qty"]), "CALC")
            stage_yields.append(stage_yield)
            route.append(str(stage.get("stage") or stage.get("stage_name") or stage.get("operation") or ""))
            rolling *= stage_yield
            input_total += stage["input_qty"]
            lost += stage["scrap_qty"] + stage["rework_qty"] - stage["rework_good"]
        out.append({"label": work_order, "rolling": rolling, "stage_count": len(stages),
                    "route": route, "route_signature": tuple(route), "route_key": "→".join(route),
                    "stage_yields": stage_yields, "initial_input": initial_input,
                    "input_total": input_total, "lost": lost, "problem": problem,
                    "metric": D(str(input_total), "CALC"), "limit": D("0.90", "LIMIT")})
    for item in out:
        item.setdefault("label", str(item.get(SPEC["key"], "")))
    return out

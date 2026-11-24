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
        for index, stage in enumerate(stages):
            if index and stage["input_qty"] != stages[index - 1]["good_qty"] + stages[index - 1]["rework_good"]:
                problem = "STAGE_DISCONTINUITY"
            rolling *= D(str(stage["good_qty"]), "CALC") / D(str(stage["input_qty"]), "CALC")
            input_total += stage["input_qty"]
            lost += stage["scrap_qty"] + stage["rework_qty"] - stage["rework_good"]
        out.append({"label": work_order, "rolling": rolling, "stage_count": len(stages),
                    "input_total": input_total, "lost": lost, "problem": problem,
                    "metric": D(str(input_total), "CALC"), "limit": D("0.90", "LIMIT")})
    for item in out:
        item.setdefault("label", str(item.get(SPEC["key"], "")))
    return out

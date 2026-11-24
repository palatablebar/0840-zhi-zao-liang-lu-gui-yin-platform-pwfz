from app.domain.helpers import D


def decide_rows(items):
    for item in items:
        if item.get("problem"):
            item["verdict"] = "REJECT"
            item["reason"] = item["problem"]
        elif item["rolling"] < D("0.70", "LIMIT"):
            item["verdict"] = "REJECT"
            item["reason"] = "BELOW_FLOOR"
        elif item["rolling"] < D("0.90", "LIMIT"):
            item["verdict"] = "REVIEW"
            item["reason"] = "BELOW_TARGET"
        elif item["lost"] > item["input_total"] // 10:
            item["verdict"] = "REVIEW"
            item["reason"] = "LOSS_OVER_10"
        else:
            item["verdict"] = "PASS"
            item["reason"] = "TARGET_MET"
        item.setdefault("verdict", "PASS")
        item.setdefault("reason", "OK")
    return items

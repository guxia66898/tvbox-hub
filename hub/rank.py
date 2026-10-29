"""打分、排序与汇总统计。"""
from __future__ import annotations

from tvbox_config_parser import KIND_SINGLE, KIND_STORE, KIND_URLS, normalize_url
from .probe import flatten


def score_single(node: dict) -> float | None:
    """单仓可用性得分：40 基础 + L2 通过率×30（未抽样给中性 12）+ 速度≤20 + 站点≤10。"""
    if node.get("kind") != KIND_SINGLE or node.get("status") != "ok":
        return None
    l2 = node.get("l2") if isinstance(node.get("l2"), dict) else {}
    pr = l2.get("pass_rate") if l2 else None
    l2_bonus = 30.0 * pr if pr is not None else 12.0
    total = node.get("total_ms")
    speed_bonus = min(20.0, 20.0 * 1200 / max(total, 200)) if total else 0.0
    site_bonus = min(10.0, node.get("site_count", 0) / 10.0)
    return round(40.0 + l2_bonus + speed_bonus + site_bonus, 1)


def rank_singles(nodes: list[dict]) -> list[dict]:
    """展平全部节点，返回按得分降序的可用单仓列表。"""
    scored = [(score_single(n), n) for n in flatten(nodes)]
    return [n for _, n in sorted((x for x in scored if x[0] is not None),
                                 key=lambda x: x[0], reverse=True)]


def speed_label(total_ms) -> str:
    """测速分级：快 <500ms / 中 <2s / 慢 <5s / 不可用。"""
    if total_ms is None:
        return "不可用"
    if total_ms < 500:
        return "快"
    if total_ms < 2000:
        return "中"
    if total_ms < 5000:
        return "慢"
    return "不可用"


def summary(nodes: list[dict]) -> dict:
    """统计（按 URL 去重：同一线路被多个多仓引用时只计一次）。"""
    flat = flatten(nodes)
    uniq: dict[str, dict] = {}
    for n in flat:
        key = normalize_url(n.get("url", ""))
        prev = uniq.get(key)
        if prev is None or (prev.get("status") != "ok" and n.get("status") == "ok"):
            uniq[key] = n
    rows = list(uniq.values())
    ok = [n for n in rows if n.get("status") == "ok"]
    totals = [n["total_ms"] for n in ok if n.get("total_ms") is not None]
    return {
        "lines_total": len(nodes),
        "nodes_total": len(rows),
        "available": len(ok),
        "singles_ok": sum(1 for n in ok if n.get("kind") == KIND_SINGLE),
        "multis_ok": sum(1 for n in ok if n.get("kind") in (KIND_STORE, KIND_URLS)),
        "avg_total_ms": round(sum(totals) / len(totals), 1) if totals else None,
        "l2_probed": sum(1 for n in rows if isinstance(n.get("l2"), dict)
                         and n["l2"].get("sites_sampled", 0) > 0),
    }

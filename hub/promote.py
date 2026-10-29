"""采集子线自动晋升：把连续多轮可用的多仓子线提升为显式种子。

背景：多仓配置里展开出的子线（如某聚合仓里的 48 条子仓）每轮都靠父仓"重新发现"，
一旦父仓失效，这些子线就跟着消失。本模块用长期可用性数据把它们"转正"：

- 每轮为每条可探到的叶子线路累计 `ok_streak`（连续可用轮数）/ `fail_streak`
- 连续可用达到 `promote_after` 轮 → 晋升，下一轮起作为顶层种子直接探测
- 晋升后连续失败达到 `promote_prune_fails` 轮 → 淘汰（不再作为种子）
- 状态存 `seeds/promote.json`（机器管理），与人工策展的 `lines.json` 严格隔离

与 `auto.json`（自动发现的**配置地址**）互补：promote.json 存的是**靠实测赚来的**线路。
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone

from tvbox_config_parser import KIND_SINGLE, clean_source_url, normalize_url

STATE_FILE = "promote.json"
MAX_ENTRIES = 400


def _key(url: str) -> str:
    """判重键：剥代理前缀后规范化（与 discover 一致）。"""
    return normalize_url(clean_source_url(url))


def _state_path(cfg) -> str:
    seeds_dir = os.path.dirname(getattr(cfg, "seeds_path", "seeds/lines.json"))
    return os.path.join(seeds_dir, STATE_FILE)


def load_state(cfg) -> list[dict]:
    path = _state_path(cfg)
    if not os.path.exists(path):
        return []
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return []
    entries = data.get("entries") if isinstance(data, dict) else None
    return entries if isinstance(entries, list) else []


def save_state(cfg, entries: list[dict]) -> str:
    path = _state_path(cfg)
    keep = [e for e in entries if e.get("url")]
    keep.sort(key=lambda e: (e.get("promoted", False), e.get("ok_streak", 0)), reverse=True)
    keep = keep[:MAX_ENTRIES]
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"_说明": "由 hub.promote 自动维护：连续多轮可用的采集子线在此转正；"
                            "晋升后连续失败达阈值的会被淘汰。人工种子请写 lines.json。",
                   "entries": keep}, f, ensure_ascii=False, indent=2)
    return path


def active(cfg) -> list[dict]:
    """已晋升的线路（下一轮起作为顶层种子参与探测）。"""
    return [e for e in load_state(cfg) if e.get("promoted")]


def _flatten(nodes: list[dict]) -> list[dict]:
    out: list[dict] = []
    stack = list(nodes)
    while stack:
        n = stack.pop()
        out.append(n)
        stack.extend(n.get("children") or [])
    return out


def update(cfg, nodes: list[dict], known: set[str]) -> tuple[list[dict], list[dict]]:
    """用本轮探测结果更新晋升状态。

    参数：
        nodes: 本轮顶层节点（含 children 树）
        known: 已在 lines.json / auto.json 中的判重键集合（不重复收录）

    返回 (新晋升列表, 被淘汰列表)。
    """
    after = max(1, int(getattr(cfg, "promote_after", 3)))
    prune_after = max(1, int(getattr(cfg, "promote_prune_fails", 5)))
    cap = int(getattr(cfg, "promote_max", 300))
    now = datetime.now(timezone.utc).isoformat()

    state = {_key(e.get("url", "")): e for e in load_state(cfg)}
    flat = _flatten(nodes)

    # 本轮每条线路的最终结论（同一 URL 多次出现时，任意一次可用即算可用）
    seen: dict[str, dict] = {}
    for n in flat:
        k = _key(n.get("url", ""))
        if not k:
            continue
        ok = n.get("status") == "ok"
        cur = seen.get(k)
        if cur is None:
            seen[k] = {"ok": ok, "name": n.get("name", ""), "kind": n.get("kind", ""),
                       "url": n.get("url", ""), "site_count": n.get("site_count", 0)}
        elif ok:
            cur["ok"] = True
            if not cur["name"]:
                cur["name"] = n.get("name", "")

    promoted_new: list[dict] = []
    dropped: list[dict] = []

    for k, info in seen.items():
        # 已在人工种子/自动发现清单里的，不参与晋升管理（避免重复计数与冗余条目）
        if k in known:
            state.pop(k, None)
            continue
        if not info["ok"]:
            # 只对已在册的条目记失败（新出现的失败线路不值得记录）
            e = state.get(k)
            if e:
                e["fail_streak"] = (e.get("fail_streak") or 0) + 1
            continue
        # 可用：只考虑"叶子单仓"（多仓父节点不可直接订阅）
        if info["kind"] != KIND_SINGLE:
            continue
        e = state.get(k)
        if e is None:
            state[k] = {"url": info["url"], "name": info["name"],
                        "site_count": info["site_count"], "ok_streak": 1,
                        "fail_streak": 0, "first_seen": now, "last_ok": now,
                        "promoted": False}
            continue
        e["ok_streak"] = (e.get("ok_streak") or 0) + 1
        e["fail_streak"] = 0
        e["last_ok"] = now
        if info["name"]:
            e["name"] = info["name"]
        e["site_count"] = max(e.get("site_count") or 0, info["site_count"] or 0)
        if not e.get("promoted") and e["ok_streak"] >= after:
            e["promoted"] = True
            e["promoted_at"] = now
            promoted_new.append(e)

    # 淘汰：晋升后长时间不可用
    for k in list(state):
        e = state[k]
        if e.get("promoted") and (e.get("fail_streak") or 0) >= prune_after:
            dropped.append(e)
            del state[k]

    entries = list(state.values())
    # 晋升数量上限：按连续可用轮数取前 cap 条
    promoted = [e for e in entries if e.get("promoted")]
    if len(promoted) > cap:
        promoted.sort(key=lambda e: e.get("ok_streak") or 0, reverse=True)
        for e in promoted[cap:]:
            e["promoted"] = False

    save_state(cfg, entries)
    return promoted_new, dropped

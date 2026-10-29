"""产物写出：merged/curated/tvbox 配置、report 报告、历史快照与体检面板。"""
from __future__ import annotations

import json
import os
import urllib.parse
from datetime import datetime, timezone

from tvbox_config_parser import (
    KIND_SINGLE, KIND_STORE, KIND_URLS,
    clean_source_url, encode_url, normalize_url,
)
from .probe import flatten


def _write_json(path: str, obj) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)


def _sort_key(n: dict):
    l2 = n.get("l2") if isinstance(n.get("l2"), dict) else {}
    pr = l2.get("pass_rate")
    total = n.get("total_ms")
    return (0 if pr is not None else 1, -(pr or 0), total if total is not None else 1e9)


def _entry(n: dict) -> dict:
    url = clean_source_url(n["url"])
    url = encode_url(url)
    name = n.get("name") or urllib.parse.urlsplit(url).netloc
    return {"name": name, "url": url}


def _entry_mirrored(n: dict, mirrors: list[str] | None, use_mirror: bool) -> dict:
    """导出条目：清洗 + 编码 + （可选）GitHub 镜像改写。"""
    e = _entry(n)
    if use_mirror:
        from .mirror import to_mirror
        e["url"] = encode_url(to_mirror(e["url"], mirrors))
    return e


def _dedupe(entries: list[dict], cap: int = 500) -> dict:
    seen: set[str] = set()
    out: list[dict] = []
    for e in entries:
        key = normalize_url(e["url"])
        if key in seen:
            continue
        seen.add(key)
        out.append(e)
        if len(out) >= cap:
            break
    return {"urls": out}


def _localize_urls(cfg_data: dict, cfg) -> None:
    """把单仓配置里的所有 URL 就地”电视端化“：百分号编码 + GitHub 镜像。

    实测教训（安卓盒子 import merged.json 后点不开）：
    - `.../jar/潇洒.jar` 这种中文路径不编码，客户端 HttpUrl.parse() 返回 null，
      spider jar 加载失败 → 所有 type:3 站点全部报废（表现为点播无反应）
    - `raw.githubusercontent.com` 直链在国内被阻断 → jar 拉不到
    两者叠加就是”名称能显示、内容全空白“。
    """
    from .mirror import to_mirror
    use_mirror = bool(getattr(cfg, "mirror_enabled", True))
    mirrors = getattr(cfg, "mirror_prefixes", None) or None

    def fix(u):
        if not isinstance(u, str) or not u.strip():
            return u
        # jar/spider 带 ;md5; 后缀，只处理前缀部分
        head, sep, rest = u.partition(";md5;")
        head = encode_url(clean_source_url(head))
        if use_mirror:
            head = encode_url(to_mirror(head, mirrors))
        return head + sep + rest

    if isinstance(cfg_data.get("spider"), str):
        cfg_data["spider"] = fix(cfg_data["spider"])
    for s in cfg_data.get("sites") or []:
        if not isinstance(s, dict):
            continue
        if isinstance(s.get("jar"), str):
            s["jar"] = fix(s["jar"])
        if isinstance(s.get("playUrl"), str):
            s["playUrl"] = fix(s["playUrl"])
        if isinstance(s.get("api"), str) and s["api"].startswith(("http://", "https://")):
            s["api"] = fix(s["api"])
        ext = s.get("ext")
        if isinstance(ext, str) and ext.startswith(("http://", "https://")):
            s["ext"] = fix(ext)
    for l in cfg_data.get("lives") or []:
        if not isinstance(l, dict):
            continue
        for k in ("url", "api", "jar", "epg"):
            if isinstance(l.get(k), str) and l[k].startswith(("http://", "https://")):
                l[k] = fix(l[k])
    for p in cfg_data.get("parses") or []:
        if isinstance(p, dict) and isinstance(p.get("url"), str) \
                and p["url"].startswith(("http://", "https://")):
            p["url"] = fix(p["url"])


def build_merged(nodes: list[dict], cfg=None) -> dict:
    """多仓聚合配置：全部可用单仓叶子，按 L2 通过率/测速排序。"""
    leaves = [n for n in flatten(nodes)
              if n.get("kind") == KIND_SINGLE and n.get("status") == "ok"]
    leaves.sort(key=_sort_key)
    mirrors, use = _mirror_opts(cfg)
    return _dedupe([_entry_mirrored(n, mirrors, use) for n in leaves])


def build_curated(nodes: list[dict], cfg=None) -> dict:
    """精选配置：只含种子线路中可用的单仓。"""
    leaves = [n for n in flatten(nodes)
              if n.get("kind") == KIND_SINGLE and n.get("status") == "ok" and n.get("is_seed")]
    leaves.sort(key=_sort_key)
    mirrors, use = _mirror_opts(cfg)
    return _dedupe([_entry_mirrored(n, mirrors, use) for n in leaves])


def _mirror_opts(cfg) -> tuple[list[str] | None, bool]:
    """从配置取镜像开关与列表（缺省开启）。"""
    if cfg is None:
        return None, True
    use = bool(getattr(cfg, "mirror_enabled", True))
    mirrors = getattr(cfg, "mirror_prefixes", None) or None
    return mirrors, use


def build_tvbox_config(nodes: list[dict]) -> dict | None:
    """单仓合并配置：调用 merge.merge_configs（相对路径转绝对 + 全局 spider 投票 +
    per-site jar 分配 + 站点/解析/直播去重），type:3 站点不再被丢弃。"""
    singles = [n for n in flatten(nodes) if n.get("kind") == KIND_SINGLE
               and n.get("status") == "ok" and isinstance(n.get("raw"), dict)]
    singles.sort(key=_sort_key)
    if not singles:
        return None
    sourced = [(n["url"], n["raw"]) for n in singles]
    from .merge import merge_configs
    return merge_configs(sourced)


def _public(node: dict) -> dict:
    """去掉 raw 大字段后的可写盘节点（递归）。"""
    c = {k: v for k, v in node.items() if k != "raw"}
    c["children"] = [_public(ch) for ch in (node.get("children") or [])]
    return c


def write_artifacts(nodes: list[dict], cfg, started_at: datetime, harvest_stats: dict) -> dict:
    """写全部产物并维护历史；返回各产物路径。"""
    out_dir = getattr(cfg, "out_dir", "dist")
    history_dir = getattr(cfg, "history_dir", "history")
    os.makedirs(out_dir, exist_ok=True)
    os.makedirs(history_dir, exist_ok=True)

    flat = flatten(nodes)
    totals = [n["total_ms"] for n in flat
              if n.get("status") == "ok" and n.get("total_ms") is not None]
    uniq: dict[str, dict] = {}
    for n in flat:
        key = normalize_url(n.get("url", ""))
        prev = uniq.get(key)
        if prev is None or (prev.get("status") != "ok" and n.get("status") == "ok"):
            uniq[key] = n
    rows = list(uniq.values())
    ok_rows = [n for n in rows if n.get("status") == "ok"]
    summary = {
        "lines_total": len(nodes),
        "nodes_total": len(rows),
        "available": len(ok_rows),
        "singles_ok": sum(1 for n in ok_rows if n.get("kind") == KIND_SINGLE),
        "multis_ok": sum(1 for n in ok_rows if n.get("kind") in (KIND_STORE, KIND_URLS)),
        "avg_total_ms": round(sum(totals) / len(totals), 1) if totals else None,
        "l2_probed": sum(1 for n in rows if isinstance(n.get("l2"), dict)
                         and n["l2"].get("sites_sampled", 0) > 0),
    }

    # 与上次快照做差异（口径与快照一致：单仓叶子 + 顶层多仓）
    now = datetime.now(timezone.utc)
    ts = now.strftime("%Y%m%d-%H%M%S")
    snap_lines = []
    for n in flat:
        is_leaf_single = n.get("kind") == KIND_SINGLE
        is_top_multi = n.get("kind") in (KIND_STORE, KIND_URLS) and n.get("depth") == 0
        if is_leaf_single or is_top_multi:
            l2 = n.get("l2") if isinstance(n.get("l2"), dict) else {}
            snap_lines.append({
                "url": n["url"], "name": n.get("name", ""), "kind": n.get("kind"),
                "available": n.get("status") == "ok",
                "total_ms": n.get("total_ms"), "site_count": n.get("site_count", 0),
                "l2_pass_rate": l2.get("pass_rate") if l2 else None,
            })
    available_urls = sorted({l["url"] for l in snap_lines if l["available"]})
    diff = {"newly_available": [], "newly_dead": []}
    index_path = os.path.join(history_dir, "index.json")
    index: list = []
    if os.path.exists(index_path):
        try:
            with open(index_path, encoding="utf-8") as f:
                index = json.load(f)
        except Exception:
            index = []
    prev_avail: set[str] = set()
    if index:
        try:
            with open(os.path.join(history_dir, index[0].get("file", "")), encoding="utf-8") as f:
                snap_old = json.load(f)
            prev_avail = {l["url"] for l in snap_old.get("lines", []) if l.get("available")}
        except Exception:
            prev_avail = set()
    if prev_avail:
        diff["newly_available"] = sorted(set(available_urls) - prev_avail)[:200]
        diff["newly_dead"] = sorted(prev_avail - set(available_urls))[:200]

    # 历史快照与趋势序列
    ts = now.strftime("%Y%m%d-%H%M%S")
    snap_file = f"snap-{ts}.json"
    _write_json(os.path.join(history_dir, snap_file), {"ts": now.isoformat(), "lines": snap_lines})
    index.insert(0, {"ts": now.isoformat(), "file": snap_file,
                     "available": len(available_urls), "lines_total": len(nodes)})
    _write_json(index_path, index[:60])

    series_path = os.path.join(history_dir, "history.json")
    series: list = []
    if os.path.exists(series_path):
        try:
            with open(series_path, encoding="utf-8") as f:
                series = json.load(f)
        except Exception:
            series = []
    series.append({"date": now.strftime("%m-%d %H:%M"), "available": len(available_urls),
                   "lines_total": len(nodes), "avg_total_ms": summary["avg_total_ms"]})
    _write_json(series_path, series[-60:])

    # 三个配置产物 + 报告
    p_merged = os.path.join(out_dir, "merged.json")
    _write_json(p_merged, build_merged(nodes, cfg))
    p_curated = os.path.join(out_dir, "curated.json")
    _write_json(p_curated, build_curated(nodes, cfg))
    p_tvbox = os.path.join(out_dir, "tvbox.json")
    merged_cfg = build_tvbox_config(nodes)
    if merged_cfg:
        _localize_urls(merged_cfg, cfg)
    # jar 可达性检查：给指向失效 jar 的站点打标记（type:3 站点的硬依赖）
    if merged_cfg and getattr(cfg, "jar_check_enabled", False):
        try:
            from .jarcheck import check_jars, load_cache, mark_dead_sites, save_cache
            jars = [s.get("jar") for s in (merged_cfg.get("sites") or [])
                    if isinstance(s, dict) and s.get("jar")]
            if merged_cfg.get("spider"):
                jars.append(merged_cfg["spider"])
            cached = load_cache(cfg)
            health = check_jars(jars, cfg, workers=getattr(cfg, "jar_check_workers", 12))
            cached.update(health)
            health = cached
            dead = mark_dead_sites(merged_cfg, health)
            save_cache(cfg, health)
            ok_n = sum(1 for v in health.values() if v)
            print(f"[jar] 探测 {len(health)} 个 jar：{ok_n} 可达 / {len(health) - ok_n} 失效"
                  f"（{dead} 个站点被标记 jar_dead）", flush=True)
        except Exception as e:  # noqa: BLE001
            print(f"[jar] 检查跳过（{type(e).__name__}: {e}）", flush=True)
    _write_json(p_tvbox, merged_cfg)

    duration = round((datetime.now(timezone.utc) - started_at).total_seconds(), 1)
    report = {"meta": {"generated_at": now.isoformat(), "duration_s": duration,
                       "harvest": harvest_stats, "l2_enabled": getattr(cfg, "l2_enabled", True)},
              "summary": summary, "diff": diff, "lines": [_public(n) for n in nodes]}
    p_report = os.path.join(out_dir, "report.json")
    _write_json(p_report, report)

    # 体检面板
    p_panel = os.path.join(out_dir, "index.html")
    try:
        from .panel import build_panel
        build_panel(report, series, p_panel)
    except Exception as e:  # noqa: BLE001
        print(f"[warn] 面板生成失败：{type(e).__name__}: {e}", flush=True)
        p_panel = ""

    return {"merged": p_merged, "curated": p_curated, "tvbox": p_tvbox,
            "report": p_report, "panel": p_panel,
            "snapshot": os.path.join(history_dir, snap_file)}

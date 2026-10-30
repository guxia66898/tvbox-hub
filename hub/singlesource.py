"""单源直出产物：把经过验证的**自洽单仓**直接发布，而不是混成大配置。

设计动因（2026-10-30 用户实测反馈）：
    之前发布的 tvbox.json 是 6418 个站点的「大杂烩」——258 个 jar 混装，
    靠 per-site `jar` 字段区分来源。实测结果：能导入、但能播放的没几个，
    远不如「饭太硬」这类单一作者维护的配置。

根因：
    1. per-site `jar` 不是所有客户端都支持（影视仓部分版本忽略该字段），
       一旦忽略 → 5637/6418 个 type:3 站点（88%）全部报废；
    2. 22.5% 的 jar 已失效，混装后无法定位是哪一家拖垮了整体；
    3. 不同作者的站点质量差异极大，合并把好源和死源混为一谈。

新策略：**不做大合并，直接给出若干「自洽单仓」**——
    一个配置 + 一个 jar，由同一作者维护，站点与 jar 严格配套。
    这正是「饭太硬」好用的原因，也是生态里的事实标准形态。

产物：
    best.json        综合评分最高的那一个（默认推荐）
    sources.json     全部通过验证的自洽单仓清单（含站点数/jar 可达性）
    tvbox.json       兼容旧路径：仍输出单仓，但只取**一个**最优自洽源，不再合并
"""
from __future__ import annotations

import json
import os
import urllib.parse

from tvbox_config_parser import clean_source_url, encode_url, parse_payload

from .fetch import http_fetch_sync


def resolve_jar(spider: str, base_url: str) -> str:
    """按客户端语义解析 jar：绝对原样、相对基于配置 URL、类名引用返回空。"""
    s = str(spider or "").split(";md5;")[0].strip()
    if not s:
        return ""
    if s.startswith("img+"):
        s = s[4:]
    if s.startswith(("http://", "https://")):
        return s
    if s.startswith("//"):
        return "https:" + s
    if s.startswith(("csp_", "py_", "js_")):
        return ""
    try:
        return urllib.parse.urljoin(base_url, s)
    except Exception:
        return ""


def _is_self_contained(obj: dict) -> bool:
    """自洽判定：有 spider，且 ≥90% 的 type:3 站点不带自己的 jar。"""
    spider = str(obj.get("spider") or "")
    sites = [s for s in (obj.get("sites") or []) if isinstance(s, dict)]
    t3 = [s for s in sites if s.get("type") == 3]
    if not spider or not t3:
        return False
    own = sum(1 for s in t3 if s.get("jar"))
    return (own / len(t3)) <= 0.10


def verify_source(url: str, cfg, timeout_s: float = 20.0) -> dict | None:
    """拉取并验证一个单仓：结构自洽 + jar 可达。返回描述 dict 或 None。"""
    try:
        r = http_fetch_sync(url, timeout_s=timeout_s,
                            max_bytes=getattr(cfg, "max_bytes", 4_194_304),
                            allow_private=getattr(cfg, "allow_private", False))
        if not r["ok"]:
            return None
        p = parse_payload(r["body_bytes"] or b"")
        if not p or p.kind != "single":
            return None
        obj = p.raw_obj
        if not _is_self_contained(obj):
            return None
        jar = resolve_jar(obj.get("spider"), url)
        if not jar:
            return None
        jr = http_fetch_sync(jar, timeout_s=timeout_s, max_bytes=64 * 1024,
                             allow_private=getattr(cfg, "allow_private", False))
        size = jr["size_kb"] or 0
        if not jr["ok"] or (jr["status"] or 0) >= 400 or size <= 20:
            return None
        sites = [s for s in (obj.get("sites") or []) if isinstance(s, dict)]
        t3 = [s for s in sites if s.get("type") == 3]
        return {
            "url": url,
            "name": "",
            "sites": len(sites),
            "type3": len(t3),
            "jar": jar,
            "jar_kb": round(size, 1),
            "spider_raw": str(obj.get("spider") or "")[:120],
            "total_ms": r["total_ms"],
        }
    except Exception:
        return None


def build_sources(nodes: list[dict], cfg, limit: int = 60) -> list[dict]:
    """从本轮探测结果里挑出自洽单仓并逐一验证 jar 可达性。"""
    from .probe import flatten
    singles = [n for n in flatten(nodes)
               if n.get("kind") == "single" and n.get("status") == "ok"]
    # 优先验证 L2 通过率高、站点多的
    singles.sort(key=lambda n: (
        -((n.get("l2") or {}).get("pass_rate") or 0),
        -(n.get("site_count") or 0),
    ))
    out: list[dict] = []
    seen: set[str] = set()
    for n in singles:
        if len(out) >= limit:
            break
        url = n["url"]
        key = clean_source_url(url).lower()
        if key in seen:
            continue
        seen.add(key)
        info = verify_source(url, cfg)
        if info:
            info["name"] = n.get("name") or ""
            info["l2_pass_rate"] = (n.get("l2") or {}).get("pass_rate")
            out.append(info)
    out.sort(key=lambda x: (-(x["sites"]), -(x.get("l2_pass_rate") or 0)))
    return out


def write_sources(out_dir: str, sources: list[dict]) -> dict:
    """写出 sources.json 与 best.json。"""
    os.makedirs(out_dir, exist_ok=True)
    p_src = os.path.join(out_dir, "sources.json")
    with open(p_src, "w", encoding="utf-8") as f:
        json.dump({
            "_说明": "通过验证的自洽单仓（一个配置 + 一个 jar，同作者维护）。"
                     "任选一条填入客户端即可，无需合并。",
            "count": len(sources),
            "sources": [
                {"name": s["name"] or s["url"].rsplit("/", 1)[-1],
                 "url": encode_url(clean_source_url(s["url"])),
                 "sites": s["sites"], "type3": s["type3"],
                 "jar_kb": s["jar_kb"],
                 "l2_pass_rate": s.get("l2_pass_rate")}
                for s in sources
            ],
        }, f, ensure_ascii=False, indent=2)

    p_best = os.path.join(out_dir, "best.json")
    best = sources[0] if sources else None
    with open(p_best, "w", encoding="utf-8") as f:
        json.dump({
            "_说明": "默认推荐：评分最高的单个自洽源。直接把 url 填进客户端。",
            "url": encode_url(clean_source_url(best["url"])) if best else "",
            "name": (best["name"] if best else ""),
            "sites": best["sites"] if best else 0,
            "why": "自洽单仓：settings 与 jar 由同一作者维护，站点与 jar 严格配套，"
                   "不依赖客户端的 per-site jar 支持" if best else "",
        }, f, ensure_ascii=False, indent=2)
    return {"sources": p_src, "best": p_best}

"""L1 线路递归探测（多仓展开）与 L2 站点 API 抽样验活。"""
from __future__ import annotations

import asyncio
import statistics

from tvbox_config_parser import (
    KIND_SINGLE, KIND_STORE, KIND_URLS,
    is_http_url, normalize_url, parse_payload,
)
from .fetch import http_fetch


def new_node(url: str, name: str, depth: int, parent: str, is_seed: bool, source: str) -> dict:
    """统一节点结构（键名与产物契约一致，勿改）。"""
    return {"url": url, "name": name or "", "kind": "unknown", "format": "",
            "status": "pending", "error": "", "ttfb_ms": None, "total_ms": None,
            "size_kb": None, "speed_kbps": None, "site_count": 0,
            "has_cleartext_spider": False, "children": [], "depth": depth,
            "parent_url": parent, "is_seed": is_seed, "source": source,
            "l2": None, "raw": None, "is_duplicate": False}


def flatten(nodes: list[dict]) -> list[dict]:
    """深度优先展平（保序）。"""
    out: list[dict] = []
    for n in nodes:
        out.append(n)
        out.extend(flatten(n.get("children") or []))
    return out


async def probe_lines(lines: list[dict], cfg) -> list[dict]:
    """对顶层线路做 L1 探测：抓取→解析→分类→多仓递归展开。"""
    sem = asyncio.Semaphore(cfg.concurrency)
    state = {"seen": {}, "count": 0}

    async def analyze(line: dict, depth: int, parent: str) -> dict:
        url = line["url"]
        node = new_node(url, line.get("name", ""), depth, parent,
                        line.get("is_seed", False), line.get("source", ""))
        if not is_http_url(url):
            node["status"], node["error"] = "fail", "无效地址"
            return node
        norm = normalize_url(url)
        if norm in state["seen"]:
            # 同一 URL 常被多个多仓重复引用。不能当作失败（会遗漏可用线路），
            # 而是复用已探到的结论，并标记 is_duplicate 供统计时去重。
            prev = state["seen"][norm]
            node.update(status=prev.get("status", "ok"), kind=prev.get("kind", "unknown"),
                        format=prev.get("format", ""), site_count=prev.get("site_count", 0),
                        ttfb_ms=prev.get("ttfb_ms"), total_ms=prev.get("total_ms"),
                        size_kb=prev.get("size_kb"), speed_kbps=prev.get("speed_kbps"),
                        has_cleartext_spider=prev.get("has_cleartext_spider", False),
                        error="", raw=prev.get("raw"), is_duplicate=True)
            if not node["name"]:
                node["name"] = prev.get("name", "")
            return node
        state["seen"][norm] = node
        if state["count"] >= cfg.max_nodes:
            node["status"], node["error"] = "fail", "节点数上限"
            return node
        state["count"] += 1

        async with sem:
            r = await http_fetch(url, timeout_s=cfg.timeout_s, ua=cfg.ua,
                                 max_bytes=cfg.max_bytes, allow_private=cfg.allow_private)
        node["ttfb_ms"], node["total_ms"], node["size_kb"] = r["ttfb_ms"], r["total_ms"], r["size_kb"]
        if None not in (r["ttfb_ms"], r["total_ms"], r["size_kb"]):
            node["speed_kbps"] = round(r["size_kb"] / max(r["total_ms"] - r["ttfb_ms"], 1) * 1000, 2)
        if not r["ok"]:
            node["status"], node["error"] = "fail", r["error"] or "抓取失败"
            return node
        if r["status"] is not None and r["status"] >= 400:
            node["status"], node["error"] = "fail", f"HTTP {r['status']}"
            return node

        try:
            payload = parse_payload(r["body_bytes"] or b"")
        except RuntimeError as e:
            node["status"], node["error"] = "fail", str(e)
            return node
        except Exception:
            node["status"], node["error"] = "fail", "解析异常"
            return node
        if payload is None:
            node["status"], node["error"] = "fail", "响应不是有效JSON/未识别格式"
            return node

        node.update(kind=payload.kind, format=payload.format,
                    site_count=payload.site_count,
                    has_cleartext_spider=payload.has_cleartext_spider,
                    raw=payload.raw_obj)
        if not node["name"] and payload.name:
            node["name"] = payload.name

        if payload.kind in (KIND_STORE, KIND_URLS):
            if depth >= cfg.max_depth:
                node["status"], node["error"] = "fail", "超过最大嵌套深度"
                return node
            subs = [su for su in payload.sub_entries if is_http_url(su[1])][: cfg.children_limit]
            budget = max(0, cfg.max_nodes - state["count"])
            subs = subs[:budget]
            node["children"] = list(await asyncio.gather(
                *[analyze({"name": sn, "url": su}, depth + 1, url) for sn, su in subs]))
        node["status"] = "ok"
        return node

    return list(await asyncio.gather(*[analyze(l, 0, "") for l in lines]))


async def verify_pass(nodes: list[dict], cfg) -> list[dict]:
    """复测采样：对可用叶子节点再抓 samples 次取中位数；返回展平节点列表。

    只复测叶子线路（单仓）——多仓父节点本身不是可订阅目标，替它发请求纯属浪费；
    超时跟随配置，避免慢线路被误判。
    """
    flat = flatten(nodes)
    sem = asyncio.Semaphore(cfg.concurrency)

    async def reverify(n: dict) -> None:
        if n["status"] != "ok" or n.get("kind") != KIND_SINGLE:
            return
        ttfb, total, size = [], [], []
        any_ok = False
        for _ in range(max(1, cfg.samples)):
            async with sem:
                r = await http_fetch(n["url"], timeout_s=cfg.timeout_s, ua=cfg.ua,
                                     max_bytes=cfg.max_bytes, allow_private=cfg.allow_private)
            if r["ok"]:
                any_ok = True
            if r["ttfb_ms"] is not None:
                ttfb.append(r["ttfb_ms"])
            if r["total_ms"] is not None:
                total.append(r["total_ms"])
            if r["size_kb"] is not None:
                size.append(r["size_kb"])
        if ttfb:
            n["ttfb_ms"] = round(statistics.median(ttfb), 1)
        if total:
            n["total_ms"] = round(statistics.median(total), 1)
        if size:
            n["size_kb"] = round(statistics.median(size), 2)
        if None not in (n["ttfb_ms"], n["total_ms"], n["size_kb"]):
            n["speed_kbps"] = round(n["size_kb"] / max(n["total_ms"] - n["ttfb_ms"], 1) * 1000, 2)
        if not any_ok:
            n["status"], n["error"] = "fail", "复测失败"

    await asyncio.gather(*[reverify(n) for n in flat])
    return flat


def _site_probe_url(api: str) -> str:
    a = api.strip()
    low = a.lower()
    if low.endswith((".json", ".txt", ".xml")) or "ac=" in low:
        return a
    if "?" in a:
        return a + "&ac=list"
    return a.rstrip("/") + "?ac=list"


async def probe_l2(nodes: list[dict], cfg) -> None:
    """L2 站点抽样：对可用单仓的 sites（type 0/1）并发探测 API 可用性。"""
    flat = flatten(nodes)
    targets = [n for n in flat if n["kind"] == KIND_SINGLE and n["status"] == "ok"
               and isinstance(n.get("raw"), dict)]
    sem = asyncio.Semaphore(cfg.l2_concurrency)
    ok_marks = ('"list"', '"code"', "<list", "<rss", '"vod_')

    async def probe_site(api: str) -> tuple[bool, str]:
        async with sem:
            r = await http_fetch(_site_probe_url(api), timeout_s=cfg.timeout_s,
                                 ua=cfg.ua, max_bytes=524_288, allow_private=cfg.allow_private)
        if not r["ok"]:
            return False, r["error"] or "抓取失败"
        if r["status"] is not None and r["status"] >= 400:
            return False, f"HTTP {r['status']}"
        body = r["body"] or ""
        if not body:
            return False, "空响应"
        if any(m in body for m in ok_marks):
            return True, ""
        return False, "响应异常"

    async def run_node(n: dict) -> None:
        sites = n["raw"].get("sites")
        all_sites = sites if isinstance(sites, list) else []
        cands = [s for s in all_sites
                 if isinstance(s, dict) and s.get("type") in (0, 1)
                 and isinstance(s.get("api"), str) and is_http_url(s["api"])]
        cands.sort(key=lambda s: 0 if s.get("searchable") in (1, True) else 1)
        cands = cands[: cfg.l2_max_sites]
        results = await asyncio.gather(*[probe_site(s["api"]) for s in cands]) if cands else []
        ok = sum(1 for good, _ in results if good)
        n["l2"] = {"sites_total": len(all_sites), "sites_sampled": len(cands),
                   "sites_ok": ok,
                   "pass_rate": round(ok / len(cands), 3) if cands else None,
                   "errors": [err for _, err in results if err][:3]}

    await asyncio.gather(*[run_node(n) for n in targets])

"""CLI 入口：采集 → L1/L2 探测 → 排名 → 产物。"""
from __future__ import annotations

import argparse
import asyncio
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

from tvbox_config_parser import extract_urls, normalize_url

from .config import HubConfig, load_seeds
from .fetch import http_fetch_sync
from .probe import probe_l2, probe_lines, verify_pass
from .rank import rank_singles, score_single, speed_label, summary


def _parse_args(argv=None):
    p = argparse.ArgumentParser(prog="tvbox-hub", description="TVBox/影视仓 线路中枢")
    p.add_argument("--config", help="配置 JSON（缺省用内置默认值）")
    p.add_argument("--out", help="产物目录")
    p.add_argument("--history", help="历史快照目录")
    p.add_argument("--seeds", help="种子线路文件")
    p.add_argument("--timeout", type=float, help="单请求超时秒")
    p.add_argument("--concurrency", type=int, help="L1 并发数")
    p.add_argument("--max-depth", dest="max_depth", type=int, help="多仓递归深度")
    p.add_argument("--children-limit", dest="children_limit", type=int, help="每仓子仓上限")
    p.add_argument("--max-nodes", dest="max_nodes", type=int, help="总节点上限")
    p.add_argument("--samples", type=int, help="复测采样次数")
    p.add_argument("--l2", dest="l2_enabled", action="store_true", default=None,
                   help="开启 L2 站点抽样")
    p.add_argument("--no-l2", dest="l2_enabled", action="store_false", default=None,
                   help="关闭 L2")
    p.add_argument("--l2-max-sites", dest="l2_max_sites", type=int, help="每仓 L2 抽样上限")
    p.add_argument("--l2-concurrency", dest="l2_concurrency", type=int)
    p.add_argument("--no-harvest", dest="harvest_enabled", action="store_false", default=None,
                   help="跳过聚合页采集")
    p.add_argument("--allow-private", dest="allow_private", action="store_true", default=None,
                   help="关闭 SSRF 防护（仅限本机调试，线上勿开）")
    p.add_argument("--max-pages", type=int, help="聚合页抓取上限（默认全部）")
    p.add_argument("--no-discover", dest="discover_enabled", action="store_false", default=None,
                   help="跳过自动发现新仓库")
    p.add_argument("--discover-max", dest="discover_max", type=int, help="本轮发现的候选验证上限")
    p.add_argument("--no-promote", dest="promote_enabled", action="store_false", default=None,
                   help="关闭采集子线自动晋升")
    p.add_argument("--promote-after", dest="promote_after", type=int,
                   help="连续多少轮可用后晋升为种子（默认 3）")
    p.add_argument("--no-jar-check", dest="jar_check_enabled", action="store_false", default=None,
                   help="跳过 jar 可达性检查（省 30~60 秒）")
    p.add_argument("--no-mirror", dest="mirror_enabled", action="store_false", default=None,
                   help="导出时不对 GitHub 直链套加速镜像（国内设备可能拉不到）")
    return p.parse_args(argv)


def _harvest(pages: list[str], cfg: HubConfig) -> tuple[dict, list[str]]:
    """并发抓取聚合页并抽取候选线路。"""
    page_list = pages[: cfg.max_pages] if cfg.max_pages else pages
    stats = {"pages": len(page_list), "pages_ok": 0, "extracted": 0}
    found: list[str] = []

    def work(page: str) -> list[str]:
        try:
            r = http_fetch_sync(page, timeout_s=6.0, ua=cfg.ua,
                                max_bytes=1_048_576, allow_private=cfg.allow_private)
            if r["ok"]:
                return extract_urls(r["body"], cfg.harvest_per_page)
        except Exception:
            pass
        return []

    with ThreadPoolExecutor(max_workers=4) as ex:
        for i, urls in enumerate(ex.map(work, page_list), 1):
            if urls:
                stats["pages_ok"] += 1
                stats["extracted"] += len(urls)
                found.extend(urls)
            print(f"[harvest] {i}/{stats['pages']} 页完成，累计候选 {stats['extracted']} 条",
                  file=sys.stderr, flush=True)
    return stats, found


async def _pipeline(lines: list[dict], cfg: HubConfig):
    nodes = await probe_lines(lines, cfg)
    flat = await verify_pass(nodes, cfg)
    if cfg.l2_enabled:
        await probe_l2(nodes, cfg)
    return nodes, flat


def main(argv=None) -> int:
    args = _parse_args(argv)
    overrides = {
        "seeds_path": args.seeds, "out_dir": args.out, "history_dir": args.history,
        "timeout_s": args.timeout, "concurrency": args.concurrency,
        "max_depth": args.max_depth, "children_limit": args.children_limit,
        "max_nodes": args.max_nodes, "samples": args.samples,
        "l2_enabled": args.l2_enabled, "l2_max_sites": args.l2_max_sites,
        "l2_concurrency": args.l2_concurrency, "harvest_enabled": args.harvest_enabled,
        "allow_private": args.allow_private, "max_pages": args.max_pages,
        "discover_enabled": args.discover_enabled, "discover_max": args.discover_max,
        "promote_enabled": args.promote_enabled, "promote_after": args.promote_after,
        "jar_check_enabled": args.jar_check_enabled,
        "mirror_enabled": args.mirror_enabled,
    }
    cfg = HubConfig.from_file(args.config, overrides)
    started_at = datetime.now(timezone.utc)

    try:
        base, pages = load_seeds(cfg.seeds_path)
    except FileNotFoundError as e:
        print(f"[error] {e}", flush=True)
        return 2

    lines = [{"name": n, "url": u, "is_seed": True, "source": "seed"} for n, u in base]

    # 已自动发现并验证过的来源（auto.json）也当种子参与探测
    from .discover import discover, load_auto, save_auto, update_health
    from .discover import _dedupe_key
    from .promote import active as promote_active, update as promote_update

    auto_entries = load_auto(cfg)
    if auto_entries:
        lines.extend({"name": e.get("name", ""), "url": e["url"],
                      "is_seed": True, "source": "auto"} for e in auto_entries if e.get("url"))
        print(f"[auto] 加载已发现来源 {len(auto_entries)} 条", flush=True)

    # 已晋升的采集子线：直接作为顶层种子探测（不再依赖父仓发现）
    if cfg.promote_enabled:
        promoted = promote_active(cfg)
        if promoted:
            lines.extend({"name": e.get("name", ""), "url": e["url"],
                          "is_seed": True, "source": "promoted"} for e in promoted)
            print(f"[promote] 加载已晋升子线 {len(promoted)} 条", flush=True)

    # 自动发现新仓库（实测通过才入库）
    if cfg.discover_enabled:
        print("[discover] 开始扫描索引页 / Codeberg / GitHub 搜索...", flush=True)
        known = {_dedupe_key(u) for _, u in base}
        known |= {_dedupe_key(e.get("url", "")) for e in auto_entries}
        try:
            found = discover(cfg, known)
            if found:
                save_auto(cfg, found)
                lines.extend({"name": f.get("name", ""), "url": f["url"],
                              "is_seed": True, "source": "discover"} for f in found)
            print(f"[discover] 新发现并验证通过 {len(found)} 条（已写入 auto.json）", flush=True)
        except Exception as e:  # noqa: BLE001
            print(f"[discover] 跳过（{type(e).__name__}: {e}）", flush=True)
    harvest_stats = {"pages": 0, "pages_ok": 0, "extracted": 0}
    if cfg.harvest_enabled and pages:
        print(f"[harvest] 开始抓取 {len(pages)} 个聚合页...", flush=True)
        harvest_stats, found = _harvest(pages, cfg)
        print(f"[harvest] 完成：{harvest_stats['pages_ok']}/{harvest_stats['pages']} 页成功，"
              f"抽取 {harvest_stats['extracted']} 条候选", flush=True)
        lines.extend({"name": "", "url": u, "is_seed": False, "source": "harvest"}
                     for u in found)

    seen: set[str] = set()
    deduped = []
    for l in lines:
        key = normalize_url(l["url"])
        if key in seen:
            continue
        seen.add(key)
        deduped.append(l)

    print(f"[probe] 共 {len(deduped)} 条线路"
          f"（种子 {sum(1 for l in deduped if l['is_seed'])}），开始 L1 探测"
          f"（深度 {cfg.max_depth}，并发 {cfg.concurrency}）...", flush=True)
    nodes, _flat = asyncio.run(_pipeline(deduped, cfg))

    # 用本轮结果更新 auto.json 健康计数（连续失败多的自动淘汰）
    try:
        update_health(cfg, nodes)
    except Exception as e:  # noqa: BLE001
        print(f"[auto] 健康计数更新跳过（{type(e).__name__}: {e}）", flush=True)

    # 采集子线晋升：连续多轮可用 → 转正为显式种子
    if cfg.promote_enabled:
        try:
            known = {_dedupe_key(u) for _, u in base}
            known |= {_dedupe_key(e.get("url", "")) for e in auto_entries}
            new_promoted, dropped = promote_update(cfg, nodes, known)
            if new_promoted:
                print(f"[promote] 新晋升 {len(new_promoted)} 条："
                      + ", ".join((e.get('name') or e['url'])[:18] for e in new_promoted[:5]),
                      flush=True)
            if dropped:
                print(f"[promote] 淘汰失效子线 {len(dropped)} 条", flush=True)
            if not new_promoted and not dropped:
                print("[promote] 本轮无变化", flush=True)
        except Exception as e:  # noqa: BLE001
            print(f"[promote] 晋升更新跳过（{type(e).__name__}: {e}）", flush=True)

    try:
        from .publish import write_artifacts
        paths = write_artifacts(nodes, cfg, started_at, harvest_stats)
    except Exception as e:  # noqa: BLE001
        print(f"[error] 产物写盘失败：{type(e).__name__}: {e}", flush=True)
        return 1

    s = summary(nodes)
    print(f"[done] 顶层 {s['lines_total']} | 节点 {s['nodes_total']} | 可用 {s['available']}"
          f" | 单仓 {s['singles_ok']} | 多仓 {s['multis_ok']}"
          f" | L2 抽样节点 {s['l2_probed']}", flush=True)
    top = rank_singles(nodes)[:15]
    if top:
        print("Top15 可用单仓：", flush=True)
        for n in top:
            pr = (n.get("l2") or {}).get("pass_rate") if isinstance(n.get("l2"), dict) else None
            print(f"  [{score_single(n):>5}] {speed_label(n.get('total_ms')):>3}"
                  f" {int(n.get('total_ms') or 0):>6}ms"
                  f" l2={'-' if pr is None else format(pr, '.0%')}"
                  f" {str(n.get('name') or '')[:16]:<16} {n['url'][:90]}", flush=True)
    print(f"[done] 产物：{paths}", flush=True)
    return 0

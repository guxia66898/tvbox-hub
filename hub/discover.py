"""自动发现新的接口配置来源。

四条通道（按可靠性排序）：
1. 索引页挖掘：抓 awesome 清单 / 聚合仓库 README，抽取其中的配置链接（无需授权）
2. Codeberg 公开搜索：Gitea API 无需 token，搜 tvbox 相关仓库并枚举其配置
3. GitHub 仓库搜索：需要 GITHUB_TOKEN（匿名 60 次/小时极易耗尽），无 token 自动跳过
4. jsDelivr 文件树：对上面发现/已知仓库枚举根目录配置文件（无 API 限制）

所有候选**必须先实测解析通过**才写入 seeds/auto.json；auto.json 与人工策展的
seeds/lines.json 分离，带健康计数，连续失败 >= AUTO_PRUNE_FAILS 自动淘汰。
"""
from __future__ import annotations

import json
import os
import re
import urllib.parse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

from tvbox_config_parser import (
    KIND_SINGLE, KIND_STORE, KIND_URLS,
    extract_urls, is_http_url, normalize_url, parse_payload,
)

AUTO_FILE = "auto.json"
AUTO_PRUNE_FAILS = 3          # 连续失败达到此值即淘汰
AUTO_MAX_ENTRIES = 800        # auto.json 条目上限

# 索引页：awesome 清单与聚合仓库 README（均来自已确认存在的仓库）
DEFAULT_INDEX_PAGES = [
    "https://raw.githubusercontent.com/Zhou-Li-Bin/Tvbox-QingNing/main/README.md",
    "https://raw.githubusercontent.com/laoma528/awesome-zhuiju-free/main/README.md",
    "https://raw.githubusercontent.com/youhunwl/TVAPP/main/README.md",
    "https://raw.githubusercontent.com/dongyubin/IPTV/main/README.md",
    "https://raw.githubusercontent.com/wuxierj/TVBox/main/README.md",
    "https://raw.githubusercontent.com/youhunwl/TVBox/master/README.md",
]

CODEBERG_SEARCH = "https://codeberg.org/api/v1/repos/search?q={q}&limit=20&sort=updated"
CODEBERG_CONTENTS = "https://codeberg.org/api/v1/repos/{repo}/contents?ref={branch}"
CODEBERG_RAW = "https://codeberg.org/{repo}/raw/branch/{branch}/{path}"
GITHUB_SEARCH = ("https://api.github.com/search/repositories"
                 "?q={q}&sort=updated&per_page=20")
JSDELIVR_TREE = "https://data.jsdelivr.com/v1/packages/gh/{repo}@{branch}"

DEFAULT_QUERIES = ["tvbox", "tvbox 接口", "影视仓", "tvbox config"]
_CFG_SUFFIX = (".json", ".txt")


def _fetch(url: str, timeout_s: float = 10.0, max_bytes: int = 2_000_000) -> dict:
    """薄封装（测试可 monkeypatch）。"""
    from .fetch import http_fetch_sync
    return http_fetch_sync(url, timeout_s=timeout_s, max_bytes=max_bytes)


def _get_json(url: str, timeout_s: float = 10.0):
    r = _fetch(url, timeout_s=timeout_s)
    if not r["ok"]:
        return None
    try:
        return json.loads(r["body"])
    except Exception:
        return None


def _looks_like_config(url: str) -> bool:
    low = url.lower().split("?")[0]
    return low.endswith(_CFG_SUFFIX)


def _dedupe_key(url: str) -> str:
    """判重键：剥掉 GitHub 代理前缀后再规范化，避免同源多代理形态重复入库。"""
    from tvbox_config_parser import clean_source_url
    return normalize_url(clean_source_url(url))


def _from_index_pages(cfg, known: set[str]) -> list[tuple[str, str, str]]:
    """通道 1：从索引页 README 中抽取配置链接。"""
    out: list[tuple[str, str, str]] = []
    pages = getattr(cfg, "discover_index_pages", None) or DEFAULT_INDEX_PAGES
    for page in pages:
        r = _fetch(page, timeout_s=cfg.timeout_s)
        if not r["ok"]:
            continue
        host = urllib.parse.urlsplit(page).netloc
        for u in extract_urls(r["body"], limit=80):
            if _dedupe_key(u) in known or not _looks_like_config(u):
                continue
            out.append(("", u, "index"))
    return out


def _from_codeberg(cfg, known: set[str]) -> list[tuple[str, str, str]]:
    """通道 2：Codeberg 公开搜索（Gitea API，不需要 token）。"""
    out: list[tuple[str, str, str]] = []
    seen_repo: set[str] = set()
    for q in (getattr(cfg, "discover_queries", None) or DEFAULT_QUERIES):
        data = _get_json(CODEBERG_SEARCH.format(q=urllib.parse.quote(q)))
        for repo in (data or {}).get("data", [])[:8]:
            full = repo.get("full_name") or ""
            branch = repo.get("default_branch") or "main"
            if not full or full in seen_repo:
                continue
            seen_repo.add(full)
            items = _get_json(CODEBERG_CONTENTS.format(repo=full, branch=branch))
            if not isinstance(items, list):
                continue
            picked = 0
            for it in items:
                if picked >= 2:
                    break
                name = it.get("name") or ""
                if it.get("type") != "file" or not name.lower().endswith(_CFG_SUFFIX):
                    continue
                if (it.get("size") or 0) < 2000:
                    continue
                url = CODEBERG_RAW.format(repo=full, branch=branch, path=urllib.parse.quote(name))
                if _dedupe_key(url) in known:
                    continue
                label = full.split("/")[-1]
                out.append((f"cb-{label}", url, "codeberg"))
                picked += 1
    return out


def _from_github(cfg, known: set[str], token: str) -> list[tuple[str, str, str]]:
    """通道 3：GitHub 仓库搜索（需 token）+ jsDelivr 枚举根目录配置。"""
    out: list[tuple[str, str, str]] = []
    for q in (getattr(cfg, "discover_queries", None) or DEFAULT_QUERIES):
        url = GITHUB_SEARCH.format(q=urllib.parse.quote(q))
        r = _fetch(url, timeout_s=cfg.timeout_s)
        if not r["ok"]:
            continue
        try:
            items = json.loads(r["body"]).get("items", [])
        except Exception:
            continue
        for repo in items[:5]:
            full = repo.get("full_name") or ""
            branch = repo.get("default_branch") or "main"
            if not full:
                continue
            tree = _get_json(JSDELIVR_TREE.format(repo=full, branch=branch))
            files = (tree or {}).get("files", []) if isinstance(tree, dict) else []
            picked = 0
            for f in files:
                if picked >= 2:
                    break
                name = f.get("name") or ""
                if f.get("type") != "file" or "/" in name:
                    continue
                if not name.lower().endswith(_CFG_SUFFIX) or (f.get("size") or 0) < 2000:
                    continue
                raw = f"https://raw.githubusercontent.com/{full}/{branch}/{urllib.parse.quote(name)}"
                if _dedupe_key(raw) in known:
                    continue
                out.append((f"gh-{full.split('/')[-1]}", raw, "github"))
                picked += 1
    return out


def verify_candidates(cands: list[tuple[str, str, str]], cfg) -> list[dict]:
    """并发实测：抓取 + 解析，只保留真正的配置（单仓/多仓且有内容）。"""
    uniq: dict[str, tuple[str, str, str]] = {}
    for name, url, src in cands:
        if not is_http_url(url):
            continue
        key = _dedupe_key(url)
        if key not in uniq:
            uniq[key] = (name, url, src)
    items = list(uniq.values())[: max(1, getattr(cfg, "discover_max", 40))]

    def work(item):
        name, url, src = item
        r = _fetch(url, timeout_s=cfg.timeout_s)
        if not r["ok"]:
            return None
        try:
            p = parse_payload(r["body_bytes"] or b"")
        except Exception:
            return None
        if not p or p.kind not in (KIND_SINGLE, KIND_STORE, KIND_URLS):
            return None
        if not p.sub_entries and p.site_count <= 0:
            return None
        return {"name": name or url.rsplit("/", 1)[-1], "url": url, "source": src,
                "kind": p.kind, "sites": p.site_count, "subs": len(p.sub_entries)}

    with ThreadPoolExecutor(max_workers=max(1, getattr(cfg, "discover_concurrency", 8))) as ex:
        results = [x for x in ex.map(work, items) if x]
    results.sort(key=lambda x: -(x["sites"] + x["subs"] * 5))
    return results


def discover(cfg, known: set[str]) -> list[dict]:
    """执行全部可用通道，返回**已验证**的新来源。"""
    cands: list[tuple[str, str, str]] = []
    cands += _from_index_pages(cfg, known)
    cands += _from_codeberg(cfg, known)
    token = (getattr(cfg, "github_token", "") or os.environ.get("GITHUB_TOKEN") or "").strip()
    if token:
        cands += _from_github(cfg, known, token)
    return verify_candidates(cands, cfg)


def _auto_path(cfg) -> str:
    seeds_dir = os.path.dirname(getattr(cfg, "seeds_path", "seeds/lines.json"))
    return os.path.join(seeds_dir, AUTO_FILE)


def load_auto(cfg) -> list[dict]:
    """读取 auto.json（机器管理的已发现来源）。"""
    path = _auto_path(cfg)
    if not os.path.exists(path):
        return []
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return []
    entries = data.get("entries") if isinstance(data, dict) else None
    return entries if isinstance(entries, list) else []


def _write_auto(cfg, entries: list[dict]) -> str:
    """直接写入 auto.json（不做与旧文件的合并），写入前按阈值淘汰。"""
    path = _auto_path(cfg)
    merged = [e for e in entries if (e.get("fail") or 0) < AUTO_PRUNE_FAILS]
    merged.sort(key=lambda e: (e.get("last_ok") or "", e.get("ok") or 0), reverse=True)
    merged = merged[:AUTO_MAX_ENTRIES]
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"_说明": "由 hub.discover 自动维护：发现的候选须实测解析通过才入库；"
                            "连续失败达到阈值的条目自动淘汰。人工种子请写 lines.json。",
                   "entries": merged}, f, ensure_ascii=False, indent=2)
    return path


def save_auto(cfg, entries: list[dict]) -> str:
    """写回 auto.json：与已有条目按 URL 合并，保留首次发现时间与健康计数。"""
    path = _auto_path(cfg)
    old = {_dedupe_key(e.get("url", "")): e for e in load_auto(cfg)}
    now = datetime.now(timezone.utc).isoformat()
    for e in entries:
        key = _dedupe_key(e.get("url", ""))
        if not key:
            continue
        prev = old.get(key)
        if prev:
            prev.update({k: v for k, v in e.items() if k in ("name", "kind", "sites", "subs")})
        else:
            old[key] = {**e, "first_seen": now, "last_ok": now, "ok": 1, "fail": 0}
    return _write_auto(cfg, list(old.values()))


def update_health(cfg, nodes: list[dict]) -> None:
    """用本轮探活结果更新 auto.json 的健康计数（用于淘汰死源）。"""
    entries = load_auto(cfg)
    if not entries:
        return
    verdict: dict[str, bool] = {}
    stack = list(nodes)
    while stack:
        n = stack.pop()
        stack.extend(n.get("children") or [])
        if n.get("is_duplicate"):
            # 重复引用节点不参与健康计数（其首次出现的节点已经计入）
            continue
        key = _dedupe_key(n.get("url", ""))
        ok = n.get("status") == "ok"
        verdict[key] = verdict.get(key, False) or ok
    now = datetime.now(timezone.utc).isoformat()
    for e in entries:
        key = _dedupe_key(e.get("url", ""))
        if key not in verdict:
            continue
        if verdict[key]:
            e["ok"] = (e.get("ok") or 0) + 1
            e["fail"] = 0
            e["last_ok"] = now
        else:
            e["fail"] = (e.get("fail") or 0) + 1
    _write_auto(cfg, entries)

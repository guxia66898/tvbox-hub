"""jar 可达性检查：标记指向失效 jar 的站点，供产物降噪。

背景：type:3 站点必须由客户端加载 jar 才能用。聚合后共有 270+ 个不同 jar，
抽样实测约 15% 已失效（上游删库/代理挂掉）。这些站点在客户端里必然报错，
但它们在 L1 层面"配置能下载、JSON 能解析"，因此不会被现有验活发现。

做法：并发 HEAD/GET 探测每个唯一 jar 地址，缓存结果到 dist/jar_health.json；
报告中给站点打 `jar_dead` 标记，并在面板上显示（不直接删除站点——jar 可能临时抽风，
由用户自行判断）。
"""
from __future__ import annotations

import json
import os
from concurrent.futures import ThreadPoolExecutor

from tvbox_config_parser import clean_source_url

from .fetch import http_fetch_sync

CACHE_FILE = "jar_health.json"


def _jar_url(v) -> str:
    """从 jar 字符串取可下载 URL（去 ;md5; 后缀与 img+ 前缀）。"""
    if not isinstance(v, str) or not v.strip():
        return ""
    u = v.split(";md5;")[0].strip()
    if u.startswith("img+"):
        u = u[4:]
    u = clean_source_url(u)
    return u if u.startswith(("http://", "https://")) else ""


def check_jars(jars: list[str], cfg, workers: int = 12) -> dict[str, bool]:
    """并发探测 jar 可达性；只取响应头/前 2KB，避免下载整个 jar。"""
    urls = sorted({_jar_url(j) for j in jars if _jar_url(j)})
    result: dict[str, bool] = {}

    def probe(u: str) -> tuple[str, bool]:
        try:
            r = http_fetch_sync(u, timeout_s=8.0, ua=getattr(cfg, "ua", "okhttp/4.12.0"),
                                max_bytes=2048,
                                allow_private=getattr(cfg, "allow_private", False))
            return u, bool(r["ok"] and (r["status"] or 0) < 400)
        except Exception:
            return u, False

    with ThreadPoolExecutor(max_workers=workers) as ex:
        for u, ok in ex.map(probe, urls):
            result[u] = ok
    return result


def load_cache(cfg) -> dict[str, bool]:
    path = os.path.join(getattr(cfg, "out_dir", "dist"), CACHE_FILE)
    if not os.path.exists(path):
        return {}
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return {}
    jars = data.get("jars") if isinstance(data, dict) else None
    return jars if isinstance(jars, dict) else {}


def save_cache(cfg, health: dict[str, bool]) -> str:
    path = os.path.join(getattr(cfg, "out_dir", "dist"), CACHE_FILE)
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    ok = sum(1 for v in health.values() if v)
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"summary": {"total": len(health), "ok": ok,
                               "dead": len(health) - ok},
                   "jars": health}, f, ensure_ascii=False, indent=2)
    return path


def mark_dead_sites(config: dict, health: dict[str, bool]) -> int:
    """给配置里指向失效 jar 的站点打 jar_dead 标记（原地修改），返回标记数。"""
    n = 0
    for s in config.get("sites") or []:
        if not isinstance(s, dict):
            continue
        u = _jar_url(s.get("jar"))
        if u and health.get(u) is False:
            s["jar_dead"] = True
            n += 1
    return n

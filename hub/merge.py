"""单仓配置合并引擎（算法移植自 tvbox-source-aggregator 的 merger/parser/dedup）。

关键能力：
- 相对路径转绝对（基于配置源 URL），支持 ./ ../ // 三种形态
- 全局 spider 投票制 + per-site jar 字段分配（让不同来源的 type:3 站点共存）
- 站点去重键 key|api，key 冲突自动加后缀
- parses 按 url|type 去重、lives 按 url 去重、rules 按 host 合并、hosts 按域名覆盖
- 清洗 127.0.0.1/localhost 等本地引用
"""
from __future__ import annotations

import re
import urllib.parse

_CLASS_PREFIXES = ("csp_", "py_", "js_")


def extract_spider_jar_url(spider: str | None) -> str | None:
    """从 spider 字符串提取 JAR URL：去 ';md5;' 后缀与 'img+' 前缀。"""
    if not spider or not isinstance(spider, str):
        return None
    url = spider.split(";md5;")[0].strip()
    if url.startswith("img+"):
        url = url[4:]
    if not url.startswith(("http://", "https://")):
        return None
    return url


def _is_resolvable(url) -> bool:
    if not isinstance(url, str) or not url:
        return False
    if url.startswith(("http://", "https://", "./", "../", "//")):
        return True
    return not url.startswith(_CLASS_PREFIXES)


def resolve_url(url, base_url: str):
    """相对路径转绝对；类名引用(csp_/py_/js_)与占位符保持原样。"""
    if not isinstance(url, str) or not url:
        return url
    if "{{" in url and "}}" in url:
        return url
    if url.startswith(("http://", "https://")):
        return url
    if url.startswith("//"):
        try:
            proto = urllib.parse.urlsplit(base_url).scheme or "https"
            return f"{proto}:{url}"
        except Exception:
            return "https:" + url
    if url.startswith(("csp_", "py_", "js_")):
        return url
    if url.startswith(("./", "../")):
        try:
            return urllib.parse.urljoin(base_url, url)
        except Exception:
            return url
    return url


def _resolve_ext(ext, base_url: str):
    if isinstance(ext, str):
        return resolve_url(ext, base_url) if _is_resolvable(ext) else ext
    if isinstance(ext, dict):
        out = {}
        for k, v in ext.items():
            out[k] = resolve_url(v, base_url) if isinstance(v, str) and _is_resolvable(v) else v
        return out
    return ext


def normalize_config(obj: dict, source_url: str) -> dict:
    """规范单个配置：补默认值 + 相对路径转绝对 + 类型归一化。"""
    cfg = dict(obj)
    cfg["spider"] = resolve_url(cfg.get("spider"), source_url) if cfg.get("spider") else None

    sites = []
    for s in cfg.get("sites") or []:
        if not isinstance(s, dict) or not s.get("key") or s.get("api") is None:
            continue
        s = dict(s)
        # type 归一化：源配置常见字符串 "0"/"1"/"3"，不转数字客户端可能不识别
        t = s.get("type")
        if isinstance(t, str) and t.strip().isdigit():
            s["type"] = int(t.strip())
        s["name"] = s.get("name") or s.get("key")
        s["key"] = _safe_key(s["key"])
        s.setdefault("searchable", 1)
        s.setdefault("quickSearch", 1)
        s.setdefault("filterable", 1)
        if s.get("type") in (0, 1):
            s["api"] = resolve_url(s["api"], source_url)
        elif s.get("type") == 3 and _is_resolvable(s.get("api")):
            s["api"] = resolve_url(s["api"], source_url)
        if s.get("jar"):
            s["jar"] = resolve_url(s["jar"], source_url)
        if s.get("playUrl"):
            s["playUrl"] = resolve_url(s["playUrl"], source_url)
        if s.get("ext"):
            s["ext"] = _resolve_ext(s["ext"], source_url)
        sites.append(s)
    cfg["sites"] = sites

    parses = []
    for p in cfg.get("parses") or []:
        if not isinstance(p, dict):
            continue
        p = dict(p)
        if p.get("url"):
            p["url"] = resolve_url(p["url"], source_url)
        if p.get("ext"):
            p["ext"] = _resolve_ext(p["ext"], source_url)
        parses.append(p)
    cfg["parses"] = parses

    lives = []
    for l in cfg.get("lives") or []:
        if not isinstance(l, dict):
            continue
        l = dict(l)
        for k in ("url", "api", "jar", "epg"):
            if l.get(k) and _is_resolvable(l[k]):
                l[k] = resolve_url(l[k], source_url)
        if l.get("ext"):
            l["ext"] = _resolve_ext(l["ext"], source_url)
        lives.append(l)
    cfg["lives"] = lives
    return cfg


def select_global_spider(configs: list[dict]) -> tuple[str | None, str | None]:
    """投票选全局 spider：统计各 JAR 覆盖的无 jar 字段 type:3 站点数，取最多者。"""
    counts: dict[str, int] = {}
    full: dict[str, str] = {}
    for cfg in configs:
        jar = extract_spider_jar_url(cfg.get("spider"))
        if not jar:
            continue
        n = sum(1 for s in cfg.get("sites") or []
                if s.get("type") == 3 and not s.get("jar"))
        if n > 0:
            counts[jar] = counts.get(jar, 0) + n
            full.setdefault(jar, cfg["spider"])
    if not counts:
        return None, None
    best = max(counts, key=lambda k: counts[k])
    return best, full.get(best)


def _dedupe_sites(sites: list[dict]) -> list[dict]:
    """去重键 key|api；key 冲突时加后缀 _2 并给 name 加 (2)。"""
    seen: set[str] = set()
    key_map: dict[str, str] = {}
    used: dict[str, int] = {}
    out: list[dict] = []
    for s in sites:
        dk = f"{s.get('key')}|{s.get('api')}"
        if dk in seen:
            continue
        seen.add(dk)
        key = s.get("key") or ""
        if key in key_map and key_map[key] != dk:
            n = used.get(key, 1) + 1
            used[key] = n
            s = dict(s)
            s["key"] = f"{key}_{n}"
            if s.get("name"):
                s["name"] = f"{s['name']}({n})"
        else:
            key_map[key] = dk
            used.setdefault(key, 1)
        out.append(s)
    return out


def _dedupe_parses(parses: list[dict]) -> list[dict]:
    seen: set[str] = set()
    out = []
    for p in parses:
        k = f"{p.get('url')}|{p.get('type', 0)}"
        if k in seen:
            continue
        seen.add(k)
        out.append(p)
    return out


def _dedupe_lives(lives: list[dict]) -> list[dict]:
    seen: set[str] = set()
    out = []
    for l in lives:
        u = l.get("url") or l.get("api") or ""
        if not u:
            out.append(l)
            continue
        if u in seen:
            continue
        seen.add(u)
        out.append(l)
    return out


def _merge_rules(rules: list) -> list:
    host_map: dict[str, dict] = {}
    anon = 0
    for r in rules:
        if not isinstance(r, dict):
            continue
        hk = r.get("host") or ",".join(sorted(r.get("hosts") or []))
        if not hk:
            host_map[f"__anon_{anon}"] = r
            anon += 1
            continue
        if hk in host_map:
            cur = host_map[hk]
            for f in ("rule", "filter", "regex", "script"):
                if r.get(f):
                    cur[f] = list(dict.fromkeys((cur.get(f) or []) + r[f]))
        else:
            host_map[hk] = dict(r)
    return list(host_map.values())


def _dedupe_hosts(hosts: list) -> list:
    m: dict[str, str] = {}
    for h in hosts:
        if isinstance(h, str) and "=" in h:
            m[h.split("=", 1)[0]] = h
    return list(m.values())


def _dedupe_strs(arr: list) -> list:
    return list(dict.fromkeys(x for x in arr if isinstance(x, str)))


def _is_local(v) -> bool:
    return isinstance(v, str) and ("127.0.0.1" in v or "localhost" in v)


def _valid_api(v) -> bool:
    """api 合法性：http(s) URL 或 csp_/py_/js_ 类名引用。

    实测发现上游配置存在脏数据（如 api="360"、api="" ），
    这类站点加载必失败，聚合时应剔除。
    """
    if not isinstance(v, str) or not v.strip():
        return False
    a = v.strip()
    if a.startswith(("http://", "https://")):
        host = a.split("://", 1)[-1].split("/")[0]
        return bool(host) and "." in host
    return a.startswith(_CLASS_PREFIXES)


def _safe_key(key: str) -> str:
    """规范化站点 key：TVBox 用它做 SP 存储与去重标识。

    实测上游存在带空格、全角竖线、变体选择符、括号后缀的 key（如 '戏 曲'、'短剧｜聚合'、
    'q女优嗯嗥(3)'）。这里只保留字母/数字/下划线/汉字，其余字符一律剔除；
    保证非空且不以数字开头（避免被客户端当作索引）。
    """
    k = "".join(ch for ch in str(key).strip()
                 if ch.isalnum() or ch == "_")
    return k or "site"


def clean_local_refs(cfg: dict) -> dict:
    """清洗 127.0.0.1/localhost 引用：聚合后对其他用户是死链。"""
    cfg = dict(cfg)
    cfg["sites"] = [s for s in cfg.get("sites") or []
                    if not _is_local(s.get("api")) and not _is_local(s.get("ext"))]
    cfg["lives"] = [l for l in cfg.get("lives") or [] if not _is_local(l.get("url"))]
    return cfg


def clean_empty_entries(cfg: dict) -> dict:
    cfg = dict(cfg)
    cfg["sites"] = [s for s in cfg.get("sites") or []
                    if s.get("key") and _valid_api(s.get("api"))]
    cfg["parses"] = [p for p in cfg.get("parses") or []
                     if p.get("name") and isinstance(p.get("url"), str) and p["url"].strip()]
    cfg["lives"] = [l for l in cfg.get("lives") or [] if l.get("url") or l.get("api")]
    cfg["doh"] = [d for d in cfg.get("doh") or [] if isinstance(d, dict) and d.get("name") and d.get("url")]
    return cfg


def merge_configs(sourced: list[tuple[str, dict]]) -> dict | None:
    """把多个 (来源URL, 配置dict) 合并成单个可用的 TVBox 单仓配置。"""
    if not sourced:
        return None
    configs = [normalize_config(obj, url) for url, obj in sourced]
    global_jar, global_spider_full = select_global_spider(configs)

    all_sites: list[dict] = []
    all_parses: list[dict] = []
    all_lives: list[dict] = []
    all_hosts: list[str] = []
    all_rules: list = []
    all_doh: list = []
    all_ads: list[str] = []
    all_flags: list[str] = []
    extra = {}

    for cfg in configs:
        for k in ("wallpaper", "logo", "ijk", "proxy"):
            if k not in extra and isinstance(cfg.get(k), str):
                extra[k] = cfg[k]
        for s in cfg.get("sites") or []:
            s = dict(s)
            if s.get("type") == 3 and not s.get("jar"):
                jar = extract_spider_jar_url(cfg.get("spider"))
                if jar and jar != global_jar and cfg.get("spider"):
                    s["jar"] = cfg["spider"]  # 打上原配置的 jar，实现共存
            all_sites.append(s)
        all_parses.extend(cfg.get("parses") or [])
        all_lives.extend(cfg.get("lives") or [])
        all_hosts.extend(cfg.get("hosts") or [])
        all_rules.extend(cfg.get("rules") or [])
        all_doh.extend(cfg.get("doh") or [])
        all_ads.extend(cfg.get("ads") or [])
        all_flags.extend(cfg.get("flags") or [])

    merged = {
        "sites": _dedupe_sites(all_sites),
        "parses": _dedupe_parses(all_parses),
        "lives": _dedupe_lives(all_lives),
        "hosts": _dedupe_hosts(all_hosts),
        "rules": _merge_rules(all_rules),
        "doh": [d for d in {d.get("url"): d for d in all_doh if isinstance(d, dict) and d.get("url")}.values()],
        "ads": _dedupe_strs(all_ads),
        "flags": _dedupe_strs(all_flags),
    }
    if global_spider_full:
        merged["spider"] = global_spider_full
    merged.update(extra)

    merged = clean_empty_entries(merged)
    merged = clean_local_refs(merged)
    merged = strip_proxy_prefixes(merged)
    return merged


_BLOB_RE = re.compile(
    r"^https?://github\.com/([^/]+)/([^/]+)/(?:blob|raw)/(.+)$", re.IGNORECASE)


def _github_blob_to_raw(u: str) -> str:
    """github.com/user/repo/blob/branch/path → raw.githubusercontent.com 直链。

    社区配置里常把网页地址当 jar 用，剥了代理后必须转 raw，否则下载到的是 HTML。
    """
    m = _BLOB_RE.match(u)
    if not m:
        return u
    user, repo, rest = m.groups()
    return f"https://raw.githubusercontent.com/{user}/{repo}/{rest}"


def strip_proxy_prefixes(cfg: dict) -> dict:
    """处理 jar / spider 上的 GitHub 代理前缀。

    策略：只有当被包裹的内层地址指向 raw.githubusercontent.com / gitee / gitlab
    等可直连域名时才剥离（电视端不认代理域名）；若内层本身就依赖代理中转，保留原样。
    实测发现上游还有 `agent 自建反向代理 + 裸路径` 的写法，需先补协议再判断。
    """
    from tvbox_config_parser import clean_source_url

    def _clean(u: str) -> str:
        v = _ensure_http(u)
        stripped = _ensure_http(clean_source_url(_ensure_http(v)))
        # 只对公网稳定域名执行剥离，其余保持原始代理地址（可能是唯一可用镜像）
        inner = stripped.lower()
        if any(d in inner for d in ("raw.githubusercontent.com", "github.com", "gitee.com",
                                    "gitlab.com", "jihulab.com", "codeberg.org",
                                    "jsdelivr.net", "kstore")):
            return _github_blob_to_raw(stripped)
        return v

    cfg = dict(cfg)
    if isinstance(cfg.get("spider"), str):
        cfg["spider"] = _clean(cfg["spider"])
    for s in cfg.get("sites") or []:
        if isinstance(s.get("jar"), str):
            s["jar"] = _clean(s["jar"])
    for l in cfg.get("lives") or []:
        if isinstance(l.get("jar"), str):
            l["jar"] = _clean(l["jar"])
    return cfg


def _ensure_http(u: str) -> str:
    """修复协议头：`https:/x` → `https://x`，`//x` → `https://x`，无协议 → 补 https://。"""
    u = (u or "").strip()
    if not u or u.startswith(_CLASS_PREFIXES):
        return u
    m = re.match(r"^https?:/(?!/)", u)
    if m:
        u = "https://" + u[m.end():]
    if u.startswith("//"):
        return "https:" + u
    if u.startswith(("http://", "https://")):
        return u
    return "https://" + u

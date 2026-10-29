"""通用工具：URL 规范化、有效性判断、代理前缀清洗。"""
from __future__ import annotations

import re
import urllib.parse

_PROXY_RE = re.compile(
    r"^https?://[^/]*?(gh-proxy\.com|gh-proxy\.org|ghproxy\.net|ghproxy\.com|ghproxy\.org"
    r"|ghfast\.top|gh\.proxy\.ustclug\.org|mirror\.ghproxy\.com|ghp\.ci|gh\.llkk\.cc"
    r"|github\.moeyy\.xyz|ghproxy\.cc|gh-proxy\.top|gh\.api\.cmliu\.org)/",
    re.IGNORECASE,
)
_DOUBLE_SCHEME_RE = re.compile(r"^https?://https?://", re.IGNORECASE)
# `https:/raw...`（单斜杠）这类畸形协议头
_FIX_SCHEME_RE = re.compile(r"^https?:/(?!/)", re.IGNORECASE)


def normalize_url(url: str) -> str:
    """规范化 URL 用于去重：路径部分小写，host 保持原样（中文域名不转码）。"""
    url = (url or "").strip()
    if not url:
        return url
    i = url.find("://")
    if i < 0:
        return url
    scheme = url[:i]
    rest = url[i + 3:].rstrip("/")
    slash = rest.find("/")
    if slash < 0:
        return scheme + "://" + rest
    return scheme + "://" + rest[:slash] + "/" + rest[slash + 1:].lower()


def is_http_url(url: str) -> bool:
    """判断是否为合法 http(s) URL（host 必须非空且含 '.'）。"""
    url = (url or "").strip()
    if not url:
        return False
    i = url.find("://")
    if i < 0:
        return False
    if url[:i].lower() not in ("http", "https"):
        return False
    host = url[i + 3:].split("/")[0]
    return bool(host) and "." in host


def _ensure_scheme(u: str) -> str:
    """保证 URL 带协议头。

    实测坑：`g.blfrp.cn/https://raw...` 这类代理被剥离后会剩下裸域名
    （`raw.githubusercontent.com/...`），安卓端 HttpUrl.parse() 直接返回 null，
    表现为条目能显示但点开空白。
    """
    if not u:
        return u
    if u.startswith(("http://", "https://")):
        return u
    if u.startswith("//"):
        return "https:" + u
    # 形如 host/path 且 host 含点 → 补 https
    head = u.split("/", 1)[0]
    if "." in head and " " not in head:
        return "https://" + u
    return u


def clean_source_url(url: str) -> str:
    """剥离 GitHub 加速代理前缀并修正双重/残缺协议，供影视仓直接加载。"""
    u = (url or "").strip()
    if not u:
        return u
    u = _PROXY_RE.sub("", u)
    u = _DOUBLE_SCHEME_RE.sub("https://", u)
    u = _FIX_SCHEME_RE.sub("https://", u)
    u = _ensure_scheme(u)
    return u


def encode_url(url: str) -> str:
    """把 URL 编码成电视端 OkHttp 一定能解析的形式。

    实测教训：中文路径（如 `.../潇洒.txt`）直接写进 JSON，安卓端
    `HttpUrl.parse()` 会返回 null，表现为「名称能显示但内容永远拉不下来」。
    所以必须做两层编码：

    - host：中文域名 -> IDNA（punycode），如「肥猫.com」-> `xn--...`
    - path / query：百分号编码（保留 URL 元字符）

    已编码的 `%XX` 不会被二次编码（因为 `%` 在 safe 集合中）。
    """
    u = (url or "").strip()
    if not u or "://" not in u:
        return u
    scheme, rest = u.split("://", 1)
    # 拆出 host 与尾部（path + query + fragment）
    cut = len(rest)
    for ch in "/?#":
        i = rest.find(ch)
        if 0 <= i < cut:
            cut = i
    host, tail = rest[:cut], rest[cut:]

    # host 里的中文域名转 IDNA；含端口时分别处理
    try:
        if host and any(ord(c) > 127 for c in host):
            if ":" in host:
                h, port = host.rsplit(":", 1)
                host = h.encode("idna").decode("ascii") + ":" + port
            else:
                host = host.encode("idna").decode("ascii")
    except Exception:
        pass  # IDNA 失败就保留原样，别把整条 URL 弄坏

    # path/query 百分号编码，保留 URL 元字符与已有的 %XX
    tail = urllib.parse.quote(tail, safe="/%:@&?=+.,~*_'-!$()[]#;")
    return f"{scheme}://{host}{tail}"

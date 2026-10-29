"""通用工具：URL 规范化、有效性判断、代理前缀清洗。"""
from __future__ import annotations

import re

_PROXY_RE = re.compile(
    r"^https?://[^/]*?(gh-proxy\.com|gh-proxy\.org|ghproxy\.net|ghproxy\.com|ghproxy\.org"
    r"|ghfast\.top|gh\.proxy\.ustclug\.org|mirror\.ghproxy\.com|ghp\.ci|gh\.llkk\.cc"
    r"|github\.moeyy\.xyz|ghproxy\.cc|gh-proxy\.top|gh\.api\.cmliu\.org)/",
    re.IGNORECASE,
)
_DOUBLE_SCHEME_RE = re.compile(r"^https?://https?://", re.IGNORECASE)


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


def clean_source_url(url: str) -> str:
    """剥离 GitHub 加速代理前缀并修正双重协议，供影视仓直接加载。"""
    u = (url or "").strip()
    if not u:
        return u
    u = _PROXY_RE.sub("", u)
    u = _DOUBLE_SCHEME_RE.sub("https://", u)
    return u

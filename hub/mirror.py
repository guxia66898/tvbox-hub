"""GitHub 直链的镜像改写：让国内电视盒子能真的拉到 raw.githubusercontent.com 的内容。

实测背景（2026-10-29，本机 + 电视端反馈）：
- `raw.githubusercontent.com` 在多数家宽/盒子上被 DNS 污染或 TCP 阻断，
  而 `merged.json` 里有 67 条子仓是它的直链 → 客户端点开必定空白。
- 实测可用的加速前缀（按稳定性排序，均为「前缀 + 完整原始 URL」形态）：
    gh-proxy.com    1497ms  OK
    gh.llkk.cc      1390ms  OK
    gh-proxy.org    1101ms  OK
    ghproxy.net    10938ms  OK（慢，作兜底）
  不可用：ghfast.top（超时）、ghp.ci / github.moeyy.xyz / kkgithub（TLS 断连）、
          ghproxy.cc（证书错误）。

策略：只改写 raw.githubusercontent.com 直链，其它域名原样保留；
可用镜像列表可通过配置覆盖（mirrors 顺序即优先级）。
"""
from __future__ import annotations

import urllib.parse

# 默认镜像前缀（前缀 + 完整原始 URL），按实测稳定性排序
DEFAULT_MIRRORS = [
    "https://gh-proxy.com/",
    "https://gh.llkk.cc/",
    "https://gh-proxy.org/",
    "https://ghproxy.net/",
]

# 只对这些域名做改写（其余保持原样，避免绕坏本身可达的源）
MIRROR_TARGET_HOSTS = ("raw.githubusercontent.com", "raw.github.com", "github.com")

# 已经是代理形态的，不再二次套娃
_KNOWN_PROXY_HOSTS = (
    "gh-proxy.com", "gh-proxy.org", "ghproxy.net", "ghproxy.com", "ghproxy.org",
    "ghfast.top", "ghp.ci", "gh.llkk.cc", "github.moeyy.xyz", "ghproxy.cc",
    "gh-proxy.top", "gh.api.cmliu.org", "ghproxy.net", "g.blfrp.cn",
    "ghproxy.cc", "raw.kkgithub.com", "cdn.jsdelivr.net",
)


def _host(url: str) -> str:
    try:
        return (urllib.parse.urlsplit(url).hostname or "").lower()
    except Exception:
        return ""


def should_mirror(url: str) -> bool:
    """是否值得套镜像：GitHub 直链、且当前没走代理。"""
    if not url or not url.startswith(("http://", "https://")):
        return False
    h = _host(url)
    if not h:
        return False
    if any(p in h for p in _KNOWN_PROXY_HOSTS):
        return False
    return any(h == t or h.endswith("." + t) for t in MIRROR_TARGET_HOSTS)


def to_mirror(url: str, mirrors: list[str] | None = None, index: int = 0) -> str:
    """把 GitHub 直链改成第 index 个镜像形态；不适用时原样返回。"""
    if not should_mirror(url):
        return url
    pool = mirrors or DEFAULT_MIRRORS
    if not pool:
        return url
    prefix = pool[index % len(pool)]
    if not prefix.endswith("/"):
        prefix += "/"
    return prefix + url


def apply_mirrors(urls: list[str], mirrors: list[str] | None = None) -> list[str]:
    """批量改写（同一 index，便于保持一致）。"""
    return [to_mirror(u, mirrors) for u in urls]

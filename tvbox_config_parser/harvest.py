"""聚合页 URL 抽取：正则 + 关键词过滤（移植自影视仓接口助手 v1.0）。"""
from __future__ import annotations

import re

_URL_RE = re.compile(r"https?://[^\s\"'<>()\[\]]+")
_TRAIL_PUNCT = re.compile(r"[.,;:，。；：、\)\]\"}>]+$")
_SKIP_SUFFIX = re.compile(r"\.(png|jpe?g|gif|webp|svg|ico|css|js|woff2?|ttf|eot|mp4|mp3|zip)$", re.IGNORECASE)

SKIP_KW = [
    "github.com/", "gitlab.com/", "gitee.com/", "zhihu.com", "bilibili", "baidu.com",
    "google.com", "bing.com", "youtube", "douyin", "weibo", "taobao", "jd.com",
    "xiaomi.com", "360.cn", "sohu", "163.com", "sina.com", "cloudflare",
    "jsdelivr.net", "unpkg.com", "gravatar", "w3.org", "mozilla.org", "jquery",
    "bootstrap", "miit.gov.cn", "flowus.cn", "allflow.cn", "staticfile.org", "cdn.staticfile",
]
LINE_KW = [
    "/tv", "/box", "/api", ".json", ".txt", "/dc", "kstore", "jundie", "catvod",
    "tvbox", "yingm", "liucn", "nxog", "tspider", "/dm/", "dcang", "仓库", "线路", "接口", "配置",
]


def extract_urls(html: str, limit: int = 60) -> list[str]:
    """从聚合页 HTML 中抽取疑似线路/接口 URL：过滤静态资源、大站与页面链接，
    只保留含线路关键词的候选，按出现顺序去重，上限 limit 条。"""
    out: list[str] = []
    for m in _URL_RE.findall(html or ""):
        u = _TRAIL_PUNCT.sub("", m)
        low = u.lower()
        if not u.startswith("http"):
            continue
        if _SKIP_SUFFIX.search(low):
            continue
        if any(k in low for k in SKIP_KW):
            continue
        if ".html" in low or "/app/" in low or "/soft" in low or "/zt" in low:
            continue
        if not any(k in low for k in LINE_KW):
            continue
        if u not in out:
            out.append(u)
        if len(out) >= limit:
            break
    return out

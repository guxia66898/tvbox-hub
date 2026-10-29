# -*- coding: utf-8 -*-
"""体检线上产物：URL 是否可被电视端 OkHttp 解析 + 子仓可达性。

用法：python tools/check_export.py [dist 目录或 base URL]
默认检查本地 dist/；传 URL 前缀（如 https://user.github.io/repo/dist/）可查线上。
"""
import json
import os
import sys
import urllib.parse
import urllib.request
from collections import Counter
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _paths import dist  # noqa: E402


def load(target: str, name: str):
    if target.startswith("http"):
        url = target.rstrip("/") + "/" + name
        req = urllib.request.Request(url, headers={"User-Agent": "okhttp/4.12.0"})
        with urllib.request.urlopen(req, timeout=40) as r:
            return json.loads(r.read().decode("utf-8"))
    with open(os.path.join(target, name), encoding="utf-8") as f:
        return json.load(f)


def non_ascii(s: str) -> bool:
    return any(ord(c) > 127 for c in s)


def check_url_shape(u: str) -> list[str]:
    """模拟安卓 OkHttp 的严格解析：返回问题列表（空 = 可解析）。"""
    errs = []
    if not u.startswith(("http://", "https://")):
        errs.append("协议头异常")
    if non_ascii(u):
        errs.append("含非 ASCII 字符（未百分号编码）")
    sp = urllib.parse.urlsplit(u)
    if not sp.hostname:
        errs.append("无 host")
    return errs


def main():
    target = sys.argv[1] if len(sys.argv) > 1 else dist()
    print(f"检查目标: {target}\n")

    merged = load(target, "merged.json")
    urls = merged.get("urls", [])
    bad = [(u["url"], check_url_shape(u["url"])) for u in urls]
    bad = [(u, e) for u, e in bad if e]

    print("=" * 70)
    print(f"1) merged.json — {len(urls)} 条子仓")
    print("=" * 70)
    print(f"  URL 形状问题: {len(bad)} 条")
    for u, e in bad[:8]:
        print(f"    {','.join(e):24} {u[:76]}")

    hosts = Counter(urllib.parse.urlsplit(u["url"]).hostname or "?" for u in urls)
    direct = sum(n for h, n in hosts.items() if h == "raw.githubusercontent.com")
    proxied = sum(n for h, n in hosts.items() if "gh-proxy" in h or "ghproxy" in h
                  or "gh.llkk" in h)
    print(f"  raw.githubusercontent 直链: {direct} 条（国内常不通）")
    print(f"  已套加速镜像: {proxied} 条")

    print()
    print("=" * 70)
    print("2) tvbox.json — 单仓配置")
    print("=" * 70)
    t = load(target, "tvbox.json")
    sites = t.get("sites") or []
    spider = t.get("spider") or ""
    print(f"  站点 {len(sites)} | parses {len(t.get('parses') or [])} "
          f"| lives {len(t.get('lives') or [])}")
    print(f"  spider: {str(spider)[:76]}")
    if spider:
        e = check_url_shape(str(spider).split(";md5;")[0])
        print(f"  spider 合法性: {'OK' if not e else '错误 -> ' + ','.join(e)}")

    jars = [s.get("jar") for s in sites if isinstance(s, dict) and s.get("jar")]
    bad_jars = [j for j in set(jars) if check_url_shape(str(j).split(";md5;")[0])]
    print(f"  jar 引用 {len(jars)} 次 / 唯一 {len(set(jars))} 个 | 形状异常 {len(bad_jars)} 个")
    for j in bad_jars[:5]:
        print(f"    {str(j)[:80]}")

    bad_apis = [s["api"] for s in sites
                if isinstance(s, dict) and isinstance(s.get("api"), str)
                and s["api"].startswith(("http://", "https://"))
                and check_url_shape(s["api"])]
    print(f"  含非 ASCII 的站点 api: {len(bad_apis)} 个")

    print()
    print("=" * 70)
    print("3) 子仓实际可达性（抽样 40 条）")
    print("=" * 70)
    sample = urls[:40]

    def probe(item):
        try:
            req = urllib.request.Request(item["url"], headers={"User-Agent": "okhttp/4.12.0"})
            with urllib.request.urlopen(req, timeout=15) as r:
                body = r.read(512)
            return item["url"], body.lstrip().startswith((b"{", b"[")), r.status
        except Exception as e:
            return item["url"], False, type(e).__name__

    with ThreadPoolExecutor(max_workers=12) as ex:
        rows = list(ex.map(probe, sample))
    ok = sum(1 for _, good, _ in rows if good)
    print(f"  可解析为配置: {ok}/{len(rows)}")
    for u, good, extra in rows:
        if not good:
            print(f"    FAIL({extra}) {u[:72]}")

    print()
    if bad or bad_jars:
        print("结论：存在 URL 形状问题，电视端可能点不开。请检查 encode_url / mirror 配置。")
        return 1
    print("结论：URL 形状全部合法。若电视端仍点不开，检查网络能否访问各子仓域名。")
    return 0


if __name__ == "__main__":
    sys.exit(main())

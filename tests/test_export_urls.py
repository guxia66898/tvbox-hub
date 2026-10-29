# -*- coding: utf-8 -*-
"""导出层编码/镜像回归测试（针对电视端点不开的真实缺陷）。"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from hub.mirror import should_mirror, to_mirror  # noqa: E402
from hub.publish import _localize_urls, build_merged  # noqa: E402
from tvbox_config_parser import clean_source_url, encode_url  # noqa: E402


def node(url, name="", kind="single", ok=True, is_seed=True, raw=None):
    return {"url": url, "name": name, "kind": kind, "format": "plain_json",
            "status": "ok" if ok else "fail", "error": "", "ttfb_ms": 100.0,
            "total_ms": 200.0, "size_kb": 10.0, "speed_kbps": 50.0, "site_count": 10,
            "has_cleartext_spider": False, "children": [], "depth": 0,
            "parent_url": "", "is_seed": is_seed, "source": "seed", "l2": None,
            "raw": raw, "is_duplicate": False}


class Cfg:
    mirror_enabled = True
    mirror_prefixes = None


def main():
    # 1) 中文路径必须被编码（这是「名称能显示但内容拉不下来」的根因）
    u = "https://raw.githubusercontent.com/youhunwl/TVBox/master/潇洒.txt"
    e = encode_url(clean_source_url(u))
    assert "%E6%BD%87%E6%B4%92" in e, e
    assert not any(ord(c) > 127 for c in e), "编码后不应残留非 ASCII"
    print("  OK  中文路径已百分号编码")

    # 2) 中文域名转 IDNA
    d = encode_url(clean_source_url("http://www.饭太硬.com/tv"))
    assert "xn--" in d and not any(ord(c) > 127 for c in d), d
    print("  OK  中文域名已转 IDNA")

    # 3) GitHub 直链套镜像；代理形态与普通站点不动
    assert should_mirror(u)
    assert not should_mirror("https://gh-proxy.com/https://raw.githubusercontent.com/a/b.json")
    assert not should_mirror("https://www.ls660.com/TV/x.json")
    m = to_mirror(u)
    assert m.startswith("https://gh-proxy.com/https://raw.githubusercontent.com/"), m
    print("  OK  镜像只作用于 GitHub 直链")

    # 4) merged 导出：URL 全部可被 OkHttp 解析（无非 ASCII、协议完整）
    nodes = [node(u, "潇洒"), node("http://www.饭太硬.com/tv", "饭太硬"),
             node("https:/raw.githubusercontent.com/a/b/c.json", "畸形")]
    merged = build_merged(nodes, Cfg())
    for item in merged["urls"]:
        assert item["url"].startswith(("http://", "https://")), item
        assert not any(ord(c) > 127 for c in item["url"]), item
    print(f"  OK  merged 导出 {len(merged['urls'])} 条全部 URL 合法")

    # 5) tvbox.json 的 spider / jar 也要被处理（否则 type:3 全废）
    conf = {
        "spider": "https://raw.githubusercontent.com/youhunwl/TVBox/master/jar/潇洒.jar;md5;abc123",
        "sites": [
            {"key": "a", "type": 3, "api": "csp_A",
             "jar": "https://raw.githubusercontent.com/youhunwl/TVBox/master/jar/潇洒.jar"},
            {"key": "b", "type": 0, "api": "https://www.ls660.com/api.php/provide/vod/"},
            {"key": "c", "type": 3, "api": "csp_C",
             "jar": "https://gh-proxy.com/https://raw.githubusercontent.com/x/y/main/j.jar"},
        ],
        "lives": [{"name": "L", "url": "https://raw.githubusercontent.com/a/b/main/live.txt"}],
        "parses": [{"name": "p", "type": 0, "url": "https://raw.githubusercontent.com/a/b/p.json"}],
    }
    _localize_urls(conf, Cfg())

    assert "%E6%BD%87%E6%B4%92.jar" in conf["spider"], conf["spider"]
    assert conf["spider"].startswith("https://gh-proxy.com/"), conf["spider"]
    assert conf["spider"].endswith(";md5;abc123"), "md5 后缀不能被破坏"
    print("  OK  spider 已编码+镜像，md5 后缀保留")

    jars = [s["jar"] for s in conf["sites"] if s.get("jar")]
    assert all(not any(ord(c) > 127 for c in j) for j in jars), jars
    assert jars[0].startswith("https://gh-proxy.com/")
    assert jars[1].startswith("https://gh-proxy.com/"), "已代理的不应二次套娃"
    assert conf["sites"][1]["api"] == "https://www.ls660.com/api.php/provide/vod/"
    print("  OK  站点 jar 已处理，普通 api 不受影响")

    assert not any(ord(c) > 127 for c in conf["lives"][0]["url"])
    assert conf["lives"][0]["url"].startswith("https://gh-proxy.com/")
    print("  OK  lives 已处理")

    # 6) 关闭镜像时不改写
    class NoMirror:
        mirror_enabled = False
        mirror_prefixes = None

    conf2 = {"spider": "https://raw.githubusercontent.com/a/b/main/x.jar",
             "sites": [], "lives": [], "parses": []}
    _localize_urls(conf2, NoMirror())
    assert conf2["spider"] == "https://raw.githubusercontent.com/a/b/main/x.jar"
    print("  OK  --no-mirror 时保持原始直链")

    print("\nEXPORT LOCALIZE ALL PASS")


if __name__ == "__main__":
    main()

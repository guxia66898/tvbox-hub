# -*- coding: utf-8 -*-
"""合并引擎离线测试：相对路径/spider 投票/per-site jar/key 冲突/本地地址清洗。"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from hub.merge import merge_configs  # noqa: E402


def main():
    a = ("https://a.example/tvbox/a.json", {
        "spider": "./jar/a.jar;md5;abc",
        "sites": [
            {"key": "cspA", "name": "A仓-爬虫A", "type": 3, "api": "csp_AAA"},
            {"key": "cmsA", "name": "A仓-CMS", "type": 0, "api": "./api.php/provide/vod/"},
            {"key": "localA", "name": "本地站", "type": 0, "api": "http://127.0.0.1:9978/proxy"},
        ],
        "parses": [{"name": "p1", "type": 0, "url": "https://p.example/1"}],
        "lives": [{"name": "L1", "url": "./live/a.txt"}],
        "ads": ["mimg.0c1q0l.cn"],
    })
    b = ("https://b.example/cfg/b.json", {
        "spider": "https://cdn.b.example/jar/b.jar",
        "sites": [
            {"key": "cspB", "name": "B仓-爬虫B", "type": 3, "api": "csp_BBB"},
            {"key": "cmsA", "name": "同名不同源", "type": 0, "api": "https://b.example/api/vod"},
            {"key": "cspJ", "name": "B仓-自带jar", "type": 3, "api": "csp_JJJ",
             "jar": "https://cdn.b.example/jar/x.jar"},
        ],
        "parses": [{"name": "p1改名", "type": 0, "url": "https://p.example/1"}],
        "lives": [{"name": "L1重复绝对地址", "url": "https://a.example/tvbox/live/a.txt"}],
    })

    merged = merge_configs([a, b])
    keys = [s["key"] for s in merged["sites"]]

    # 1) 相对路径转绝对
    assert merged["spider"] == "https://a.example/tvbox/jar/a.jar;md5;abc", merged["spider"]
    assert "https://a.example/tvbox/api.php/provide/vod/" in [s["api"] for s in merged["sites"]]
    assert merged["lives"][0]["url"] == "https://a.example/tvbox/live/a.txt", merged["lives"][0]

    # 2) 本地引用被清洗
    assert "localA" not in keys

    # 3) type:3 站点保留 + 非全局 jar 的站点打上 per-site jar
    assert "cspA" in keys and "cspB" in keys and "cspJ" in keys, keys
    by_key = {s["key"]: s for s in merged["sites"]}
    # 投票：A 仓无 jar 的 type3 = 1，B 仓 = 1 → 平手取先出现(a)；b 仓 cspB 应打上 b 的 jar
    assert by_key["cspB"].get("jar") == "https://cdn.b.example/jar/b.jar", by_key["cspB"]
    assert "jar" not in by_key["cspA"]
    assert by_key["cspJ"]["jar"] == "https://cdn.b.example/jar/x.jar"

    # 4) key 冲突加后缀
    assert "cmsA_2" in keys, keys
    assert by_key["cmsA_2"]["name"].endswith("(2)")

    # 5) parses 按 url|type 去重（同名不同 url 才保留）
    assert len(merged["parses"]) == 1

    # 6) lives 去重（相对路径已解析成同一绝对地址）
    assert len(merged["lives"]) == 1

    # 7) ads 去重
    assert merged["ads"] == ["mimg.0c1q0l.cn"]

    # 8) 脏数据清洗：api 不是 URL/类名（如段标题 api="360"）、空 api 均剔除
    dirty = ("https://d.example/x.json", {
        "spider": "x.jar",
        "sites": [
            {"key": "hdr", "name": "🤖以下为推荐资源🤖", "type": 3, "api": "360"},
            {"key": "empty", "name": "空api", "type": 0, "api": ""},
            {"key": "ok1", "name": "正常站", "type": 0, "api": "https://d.example/api"},
            {"key": "cls", "name": "类名引用", "type": 3, "api": "csp_Valid"},
        ]})
    m2 = merge_configs([dirty])
    keys2 = [s["key"] for s in m2["sites"]]
    assert "hdr" not in keys2 and "empty" not in keys2, keys2
    assert "ok1" in keys2 and "cls" in keys2, keys2

    # 9) key 空白清理（TVBox 用作存储键）
    spaced = ("https://e.example/x.json", {
        "spider": "x.jar",
        "sites": [{"key": "戏 曲", "name": "戏曲", "type": 0, "api": "https://e.example/a"}]})
    m3 = merge_configs([spaced])
    assert m3["sites"][0]["key"] == "戏曲", m3["sites"][0]["key"]

    # 10) 代理前缀：内层可直连则剥离，否则保留原代理地址
    proxied = ("https://f.example/x.json", {
        "spider": "x.jar",
        "sites": [
            {"key": "p1", "name": "GitHub代理", "type": 3, "api": "csp_A",
             "jar": "https://gh-proxy.org/https://raw.githubusercontent.com/a/b/main/x.jar"},
            {"key": "p2", "name": "私有代理", "type": 3, "api": "csp_B",
             "jar": "https://myproxy.example/jar/spider.jar"},
        ]})
    m4 = merge_configs([proxied])
    by4 = {s["key"]: s for s in m4["sites"]}
    assert by4["p1"]["jar"] == "https://raw.githubusercontent.com/a/b/main/x.jar", by4["p1"]["jar"]
    assert by4["p2"]["jar"] == "https://myproxy.example/jar/spider.jar", by4["p2"]["jar"]

    # 11) 代理包裹的 github.com/blob 地址 → raw 直链（否则下载到 HTML）
    blobbed = ("https://g.example/x.json", {
        "spider": "x.jar",
        "sites": [{"key": "b1", "name": "blob", "type": 3, "api": "csp_A",
                   "jar": "https://gh-proxy.com/https://github.com/u/r/blob/main/jar/s.jar"}]})
    m5 = merge_configs([blobbed])
    assert m5["sites"][0]["jar"] == "https://raw.githubusercontent.com/u/r/main/jar/s.jar", \
        m5["sites"][0]["jar"]

    print("MERGE ALL PASS")


if __name__ == "__main__":
    main()

# -*- coding: utf-8 -*-
"""单源直出与相对路径 jar 解析的回归测试（离线）。"""
import json
import os
import shutil
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from hub import singlesource as SS  # noqa: E402
from hub.config import HubConfig  # noqa: E402

# 自洽：298 个 type:3 站点，全部不带 jar（靠全局 spider）
SELF_CFG = {
    "spider": "./jar/pg.jar;md5;abc",
    "sites": [{"key": f"k{i}", "name": f"站{i}", "type": 3, "api": f"csp_{i}"}
              for i in range(50)] + [{"key": "c", "name": "CMS", "type": 0,
                                      "api": "https://a.example/api"}],
}
# 非自洽：站点各自带 jar
MIXED_CFG = {
    "spider": "./jar/a.jar",
    "sites": [{"key": f"x{i}", "name": f"x{i}", "type": 3, "api": f"csp_{i}",
               "jar": f"https://cdn.example/j{i}.jar"} for i in range(10)],
}


def fake_fetch(url, **kw):
    """按 URL 返回预置响应：配置 JSON 或 jar 二进制。"""
    base = {"ok": True, "status": 200, "ttfb_ms": 20.0, "total_ms": 40.0,
            "final_url": url, "error": ""}
    if url.endswith(".jar"):
        body = b"PK\x03\x04" + b"\x00" * 40000   # 假装 40KB jar
        return {**base, "body": "", "body_bytes": body, "size_kb": len(body) / 1024}
    if "self" in url:
        body = json.dumps(SELF_CFG).encode()
    elif "mixed" in url:
        body = json.dumps(MIXED_CFG).encode()
    else:
        return {**base, "ok": False, "status": 404, "error": "HTTP 404",
                "body": "", "body_bytes": None, "size_kb": None,
                "ttfb_ms": None, "total_ms": None}
    return {**base, "body": body.decode(), "body_bytes": body, "size_kb": len(body) / 1024}


def main():
    SS.http_fetch_sync = fake_fetch

    # 1) 相对路径 jar 必须按配置 URL 解析（这是关键修正）
    got = SS.resolve_jar("./jar/pg.jar;md5;abc",
                         "https://raw.githubusercontent.com/u/r/main/js.json")
    assert got == "https://raw.githubusercontent.com/u/r/main/jar/pg.jar", got
    print("  OK  相对路径 jar 按配置 URL 解析", got[-40:])

    # 2) 绝对地址与类名引用
    assert SS.resolve_jar("https://cdn.x/a.jar", "https://a/b.json") == "https://cdn.x/a.jar"
    assert SS.resolve_jar("csp_Douban", "https://a/b.json") == ""
    assert SS.resolve_jar("js_drpy", "https://a/b.json") == ""
    print("  OK  绝对地址原样，类名引用返回空")

    # 3) 自洽判定
    assert SS._is_self_contained(SELF_CFG) is True
    assert SS._is_self_contained(MIXED_CFG) is False
    print("  OK  自洽判定：单 jar 配置通过，多 jar 混装拒绝")

    cfg = HubConfig(allow_private=False, max_bytes=4_194_304)

    # 4) verify_source：自洽 + jar 可达 → 通过
    info = SS.verify_source("https://raw.githubusercontent.com/u/r/main/self.json", cfg)
    assert info and info["jar_kb"] > 20, info
    assert info["sites"] == 51 and info["type3"] == 50, info
    print(f"  OK  自洽源验证通过：{info['sites']} 站点 / jar {info['jar_kb']}KB")

    # 5) 非自洽源被拒
    assert SS.verify_source("https://raw.githubusercontent.com/u/r/main/mixed.json", cfg) is None
    print("  OK  多 jar 混装源被拒绝")

    # 6) 404 源被拒
    assert SS.verify_source("https://raw.githubusercontent.com/u/r/main/nope.json", cfg) is None
    print("  OK  拉取失败源被拒绝")

    # 7) 产物写出
    work = tempfile.mkdtemp()
    try:
        sources = [{"url": "https://raw.githubusercontent.com/u/r/main/self.json",
                    "name": "测试源", "sites": 51, "type3": 50, "jar": "x",
                    "jar_kb": 40.0, "l2_pass_rate": 0.9}]
        paths = SS.write_sources(work, sources)
        best = json.load(open(paths["best"], encoding="utf-8"))
        src = json.load(open(paths["sources"], encoding="utf-8"))
        assert best["url"].startswith("https://"), best
        assert best["sites"] == 51
        assert src["count"] == 1 and len(src["sources"]) == 1
        assert src["sources"][0]["name"] == "测试源"
        print("  OK  best.json / sources.json 写出正确")
    finally:
        shutil.rmtree(work, ignore_errors=True)

    print("\nSINGLESOURCE ALL PASS")


if __name__ == "__main__":
    main()

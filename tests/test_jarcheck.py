# -*- coding: utf-8 -*-
"""jar 可达性检查测试（离线，打桩网络）。"""
import json
import os
import shutil
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from hub import jarcheck as J  # noqa: E402
from hub.config import HubConfig  # noqa: E402


def main():
    # 1) URL 提取：去 ;md5; 后缀、img+ 前缀、代理前缀
    assert J._jar_url("https://a/b.jar;md5;abcd") == "https://a/b.jar"
    assert J._jar_url("img+https://a/b.jar") == "https://a/b.jar"
    assert J._jar_url("https://ghproxy.net/https://raw.githubusercontent.com/u/r/main/x.jar") \
        == "https://raw.githubusercontent.com/u/r/main/x.jar"
    assert J._jar_url("csp_XXX") == ""
    assert J._jar_url("") == ""
    assert J._jar_url(None) == ""

    # 2) 探测与缓存
    J.http_fetch_sync = lambda u, **kw: {
        "ok": "good" in u, "status": 200 if "good" in u else 404,
        "body": "", "body_bytes": b"", "ttfb_ms": 1.0, "total_ms": 2.0,
        "size_kb": 0.1, "final_url": u, "error": ""}
    work = tempfile.mkdtemp()
    try:
        cfg = HubConfig(out_dir=work, jar_check_enabled=True, jar_check_workers=4)
        jars = ["https://good/1.jar", "https://bad/2.jar", "https://good/1.jar;md5;x"]
        health = J.check_jars(jars, cfg)
        assert health == {"https://good/1.jar": True, "https://bad/2.jar": False}, health

        path = J.save_cache(cfg, health)
        assert os.path.exists(path)
        cache = J.load_cache(cfg)
        assert cache == health
        summary = json.load(open(path, encoding="utf-8"))["summary"]
        assert summary == {"total": 2, "ok": 1, "dead": 1}, summary

        # 3) 标记
        cfg_data = {"sites": [
            {"key": "a", "jar": "https://good/1.jar"},
            {"key": "b", "jar": "https://bad/2.jar"},
            {"key": "c", "jar": "https://bad/2.jar;md5;y"},
            {"key": "d"},
        ]}
        n = J.mark_dead_sites(cfg_data, health)
        assert n == 2, n
        flags = {s["key"]: s.get("jar_dead") for s in cfg_data["sites"]}
        assert flags == {"a": None, "b": True, "c": True, "d": None}, flags

        # 4) 探测异常时按不可用处理（不抛异常）
        def boom(u, **kw):
            raise OSError("network down")
        J.http_fetch_sync = boom
        assert J.check_jars(["https://x/1.jar"], cfg) == {"https://x/1.jar": False}
        print("JARCHECK ALL PASS")
    finally:
        shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    main()

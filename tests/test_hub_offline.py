# -*- coding: utf-8 -*-
"""hub 产物/面板离线冒烟：合成节点 → write_artifacts → 校验文件与面板。"""
import json
import os
import shutil
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from hub.config import HubConfig
from hub.publish import write_artifacts


def node(url, name, kind, status, **kw):
    n = {"url": url, "name": name, "kind": kind, "format": kw.get("format", "plain_json"),
         "status": status, "error": kw.get("error", ""), "ttfb_ms": kw.get("ttfb_ms"),
         "total_ms": kw.get("total_ms"), "size_kb": kw.get("size_kb"),
         "speed_kbps": kw.get("speed_kbps"), "site_count": kw.get("site_count", 0),
         "has_cleartext_spider": kw.get("has_cleartext_spider", False),
         "children": kw.get("children", []), "depth": kw.get("depth", 0),
         "parent_url": kw.get("parent_url", ""), "is_seed": kw.get("is_seed", True),
         "source": kw.get("source", "seed"), "l2": kw.get("l2"), "raw": kw.get("raw")}
    return n


def main():
    cfg = HubConfig(out_dir="dist-test", history_dir="history-test")
    shutil.rmtree("dist-test", ignore_errors=True)
    shutil.rmtree("history-test", ignore_errors=True)

    leaf_a = node("http://a.example/tv.json", "站点A", "single", "ok",
                  total_ms=350.0, site_count=10,
                  l2={"sites_total": 12, "sites_sampled": 8, "sites_ok": 7, "pass_rate": 0.875, "errors": []},
                  raw={"spider": "x.jar", "sites": [{"key": "a", "name": "A", "type": 0, "api": "http://a.example/api.php/provide/vod"}],
                       "parses": [{"name": "p1", "type": 0, "url": "http://p/1"}]})
    leaf_b = node("http://b.example/tv.json", "站点B", "single", "ok",
                  total_ms=900.0, site_count=3, is_seed=False, source="harvest",
                  l2={"sites_total": 5, "sites_sampled": 5, "sites_ok": 1, "pass_rate": 0.2, "errors": ["超时"]},
                  raw={"sites": [{"key": "b", "name": "B", "type": 1, "api": "http://b.example/api.php/provide/vod"}]},
                  children=[])
    leaf_dead = node("http://c.example/tv.json", "站点C", "single", "fail", error="超时")
    leaf_d = node("http://d.example/tv.json", "站点D", "single", "ok",
                  total_ms=700.0, site_count=2,
                  raw={"sites": [{"key": "d", "name": "D", "type": 0, "api": "http://d.example/api/vod"}]})
    multi = node("http://m.example/dc.json", "多仓M", "multi_storehouse", "ok",
                 children=[leaf_b, leaf_d], total_ms=120.0)

    nodes = [leaf_a, leaf_dead, multi]
    started = datetime.now(timezone.utc)
    paths = write_artifacts(nodes, cfg, started, {"pages": 3, "pages_ok": 1, "extracted": 5})

    for key in ("merged", "curated", "tvbox", "report", "snapshot"):
        assert paths.get(key) and os.path.exists(paths[key]), f"{key} 缺失: {paths}"
    assert os.path.exists(paths["panel"]), "面板缺失"

    merged = json.load(open(paths["merged"], encoding="utf-8"))
    assert [u["url"] for u in merged["urls"]] == ["http://a.example/tv.json", "http://b.example/tv.json", "http://d.example/tv.json"]
    curated = json.load(open(paths["curated"], encoding="utf-8"))
    assert [u["url"] for u in curated["urls"]] == ["http://a.example/tv.json", "http://d.example/tv.json"]  # b 非种子
    tvbox = json.load(open(paths["tvbox"], encoding="utf-8"))
    assert tvbox["sites"][0]["key"] == "a" and tvbox["sites"][1]["key"] == "b" and tvbox["sites"][2]["key"] == "d"
    assert tvbox["parses"][0]["name"] == "p1"
    report = json.load(open(paths["report"], encoding="utf-8"))
    assert report["summary"]["available"] == 4 and report["summary"]["singles_ok"] == 3
    assert report["lines"][2]["children"][0]["l2"]["pass_rate"] == 0.2
    html = open(paths["panel"], encoding="utf-8").read()
    assert "TVBox 线路中枢 · 体检面板" in html and "const DATA = {" in html
    assert "</script>" in html and "cdjango" not in html  # 转义未被破坏

    # 第二轮：无变化 → diff 应为空；再伪造 a 失效 → newly_dead
    paths2 = write_artifacts([leaf_a, leaf_dead, multi], cfg, datetime.now(timezone.utc),
                             {"pages": 0, "pages_ok": 0, "extracted": 0})
    r2 = json.load(open(paths2["report"], encoding="utf-8"))
    assert r2["diff"] == {"newly_available": [], "newly_dead": []}, r2["diff"]
    changed = node("http://a.example/tv.json", "站点A", "single", "fail", error="HTTP 404")
    paths3 = write_artifacts([changed, leaf_dead, multi], cfg, datetime.now(timezone.utc),
                             {"pages": 0, "pages_ok": 0, "extracted": 0})
    r3 = json.load(open(paths3["report"], encoding="utf-8"))
    assert r3["diff"]["newly_dead"] == ["http://a.example/tv.json"], r3["diff"]
    assert r3["diff"]["newly_available"] == []

    shutil.rmtree("dist-test", ignore_errors=True)
    shutil.rmtree("history-test", ignore_errors=True)
    print("HUB SMOKE ALL PASS")


if __name__ == "__main__":
    main()

# -*- coding: utf-8 -*-
"""采集子线自动晋升测试（完全离线）。"""
import json
import os
import shutil
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from hub import promote as P  # noqa: E402
from hub.config import HubConfig  # noqa: E402


def leaf(url, ok=True, name="", sites=10, kind="single"):
    return {"url": url, "name": name, "kind": kind, "status": "ok" if ok else "fail",
            "site_count": sites, "children": [], "is_duplicate": False}


def multi(url, children):
    return {"url": url, "name": "多仓", "kind": "multi_urls", "status": "ok",
            "site_count": 0, "children": children, "is_duplicate": False}


def main():
    work = tempfile.mkdtemp()
    try:
        seeds = os.path.join(work, "seeds")
        os.makedirs(seeds)
        cfg = HubConfig(seeds_path=os.path.join(seeds, "lines.json"),
                        promote_enabled=True, promote_after=3, promote_prune_fails=3)

        # 第一轮：子线可 2 次，第 3 次才晋升
        nodes = [multi("http://m/1.json", [leaf("http://a/1.json", name="子线A"),
                                           leaf("http://b/1.json", ok=False, name="子线B")])]
        P.update(cfg, nodes, known=set())
        st = {e["url"]: e for e in P.load_state(cfg)}
        assert st["http://a/1.json"]["ok_streak"] == 1 and not st["http://a/1.json"]["promoted"]
        assert not P.active(cfg)

        # 第 2 轮
        P.update(cfg, nodes, known=set())
        st = {e["url"]: e for e in P.load_state(cfg)}
        assert st["http://a/1.json"]["ok_streak"] == 2 and not st["http://a/1.json"]["promoted"]

        # 第 3 轮 → 晋升
        new, dropped = P.update(cfg, nodes, known=set())
        st = {e["url"]: e for e in P.load_state(cfg)}
        assert st["http://a/1.json"]["promoted"], "连续 3 轮可用应晋升"
        assert [e["url"] for e in new] == ["http://a/1.json"], new
        assert not dropped
        assert [e["url"] for e in P.active(cfg)] == ["http://a/1.json"]

        # 已晋升的后续轮次不重复报告为"新晋升"
        new2, _ = P.update(cfg, nodes, known=set())
        assert new2 == [], new2

        # 失败累计（连 3 轮）→ 淘汰
        fail_nodes = [multi("http://m/1.json", [leaf("http://a/1.json", ok=False)])]
        for i in range(3):
            _, dropped = P.update(cfg, fail_nodes, known=set())
        assert dropped and dropped[0]["url"] == "http://a/1.json", dropped
        assert not P.active(cfg), "淘汰后不应再作为种子"

        # 多仓父节点不会被晋升（不可直接订阅）
        P.update(cfg, [multi("http://m/2.json", [])], known=set())
        assert all(not e["promoted"] for e in P.load_state(cfg))

        # 已在人工种子表中的线路不会被重复收录
        P.update(cfg, [multi("http://m/3.json", [leaf("http://seed/1.json")])], known=set())
        before = len(P.load_state(cfg))
        P.update(cfg, [multi("http://m/3.json", [leaf("http://seed/1.json")])],
                 known={P._key("http://seed/1.json")})
        assert P._key("http://seed/1.json") not in {P._key(e["url"]) for e in P.load_state(cfg)}

        # 代理形态不同视为同一线路
        P.update(cfg, [multi("http://m/4.json",
                             [leaf("https://ghproxy.net/https://raw.githusercontent.com/x.json")])],
                 known=set())
        n1 = len(P.load_state(cfg))
        P.update(cfg, [multi("http://m/4.json",
                             [leaf("https://raw.githusercontent.com/x.json")])], known=set())
        n2 = len(P.load_state(cfg))
        assert n1 == n2, f"代理形态未归一: {n1} -> {n2}"

        # 状态文件可重复读取
        assert isinstance(json.load(open(P._state_path(cfg), encoding="utf-8"))["entries"], list)
        print("PROMOTE ALL PASS")
    finally:
        shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    main()

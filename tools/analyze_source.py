# -*- coding: utf-8 -*-
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _paths import dist, history, seeds, p  # noqa: E402

"""分析「新线路从哪来」：对比历史快照 URL 集合 + 拆解本轮节点的来源层级。"""
import glob
import json
import os
from collections import Counter

HIST = os.path.join(p('history'))
snaps = sorted(glob.glob(os.path.join(HIST, "snap-*.json")))
print(f"历史快照 {len(snaps)} 份\n")

prev = None
for p in snaps:
    d = json.load(open(p, encoding="utf-8"))
    urls = {l["url"] for l in d.get("lines", [])}
    name = os.path.basename(p).replace("snap-", "").replace(".json", "")
    if prev is None:
        print(f"{name}: {len(urls)} 条（基线）")
    else:
        new = urls - prev
        gone = prev - urls
        print(f"{name}: {len(urls)} 条 | 首次出现 {len(new)} | 消失 {len(gone)}")
        for u in list(new)[:4]:
            print(f"    + {u[:95]}")
    prev = urls

print("\n===== 本轮节点来源拆解 =====")
r = json.load(open(dist("report.json"), encoding="utf-8"))


def walk(ns, depth=0):
    for n in ns:
        yield n, depth
        yield from walk(n.get("children") or [], depth + 1)


flat = list(walk(r["lines"]))
src = Counter(n.get("source") or "?" for n, _ in flat)
dep = Counter(d for _, d in flat)
print("按 source:", dict(src))
print("按深度:", dict(dep), "（深度0=种子/采集顶层，深度>0=多仓展开出的子线）")

# 哪些顶层是多仓、各展开多少
print("\n多仓展开明细（前 12）：")
multis = [(n, d) for n, d in flat if n.get("kind") in ("multi_storehouse", "multi_urls")]
expanded = [(n.get("name") or n["url"], len(n.get("children") or []),
             sum(1 for c in (n.get("children") or []) if c.get("status") == "ok"))
            for n, _ in multis]
expanded.sort(key=lambda x: -x[1])
for name, total, ok in expanded[:12]:
    print(f"  {name[:34]:<34} 展开 {total:>3} 子线，其中可用 {ok}")

# 检查：这些子线里有多少不在种子表里
seeds = json.load(open(seeds("lines.json"), encoding="utf-8"))
seed_urls = {u for _, u in seeds["base_lines"]}
child_urls = {n["url"] for n, d in flat if d > 0}
print(f"\n多仓展开出的子线 {len(child_urls)} 条，其中不在种子表里的：{len(child_urls - seed_urls)} 条")

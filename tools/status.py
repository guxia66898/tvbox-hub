# -*- coding: utf-8 -*-
"""汇总晋升与 jar 检查状态。"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _paths import dist, seeds  # noqa: E402

d = json.load(open(seeds("promote.json"), encoding="utf-8"))
e = d["entries"]
p = [x for x in e if x.get("promoted")]
print(f"promote.json: 共 {len(e)} 条，已晋升 {len(p)} 条")
print("  晋升样本:", [x.get("name", "")[:16] for x in p[:5]])
print("  待晋升（ok_streak>=1 未满 3）:", sum(1 for x in e if not x.get("promoted")))

hs = json.load(open(dist("jar_health.json"), encoding="utf-8"))["summary"]
print(f"jar_health: 共 {hs['total']} 个，可达 {hs['ok']}，失效 {hs['dead']} "
      f"（失效率 {hs['dead'] / hs['total'] * 100:.1f}%）")

t = json.load(open(dist("tvbox.json"), encoding="utf-8"))
sites = t.get("sites") or []
dead = sum(1 for x in sites if x.get("jar_dead"))
print(f"tvbox.json: 站点 {len(sites)}，jar_dead 标记 {dead} "
      f"（占 {dead / len(sites) * 100:.1f}%）")

r = json.load(open(dist("report.json"), encoding="utf-8"))
print(f"report: 顶层 {r['summary']['lines_total']}，节点 {r['summary']['nodes_total']}，"
      f"可用 {r['summary']['available']}，L2 抽样 {r['summary']['l2_probed']}")

# -*- coding: utf-8 -*-
"""评估「相似名称合并」的收益空间：当前产物里到底有多少重复站点。"""
import json
import sys

sys.path.insert(0, __import__("os").path.dirname(__import__("os").path.abspath(__file__)))
from _paths import dist  # noqa: E402

t = json.load(open(dist("tvbox.json"), encoding="utf-8"))
sites = [s for s in (t.get("sites") or []) if isinstance(s, dict)]
print(f"合并后站点总数: {len(sites)}")


def norm(s: str) -> str:
    import re
    s = (s or "").lower()
    s = re.sub(r"[【】\[\]()（）《》「」『』<>\s\-_·•,.，。]", "", s)
    return re.sub(r"\d+", "", s)


# 1) 名称完全相同的组
from collections import defaultdict
byname = defaultdict(list)
for s in sites:
    byname[norm(s.get("name") or s.get("key"))].append(s)
dupe_groups = {k: v for k, v in byname.items() if len(v) > 1 and k}
total_dupe = sum(len(v) - 1 for v in dupe_groups.values())
print(f"名称（归一化后）完全相同的组: {len(dupe_groups)} 个，可减少 {total_dupe} 个站点")

# 2) api 域名相同但名称不同的组（同一站点的不同壳）
bydomain = defaultdict(list)
for s in sites:
    api = str(s.get("api") or "")
    if api.startswith("http"):
        host = api.split("://", 1)[-1].split("/")[0]
        bydomain[host].append(s)
dom_groups = {k: v for k, v in bydomain.items() if len(v) > 1}
dom_dupe = sum(len(v) - 1 for v in dom_groups.values())
print(f"同一 API 域名下多站点: {len(dom_groups)} 个域，可减少 {dom_dupe} 个站点")

print("\n名称重复最多的组（前 8）：")
for k, v in sorted(dupe_groups.items(), key=lambda x: -len(x[1]))[:8]:
    names = {s.get("name") for s in v}
    apis = {str(s.get("api"))[:38] for s in v}
    print(f"  [{len(v)} 个] {k[:24]!r} | 名称种类 {len(names)} | api 种类 {len(apis)}")

print("\n同一域名下最多站点（前 6）：")
for k, v in sorted(dom_groups.items(), key=lambda x: -len(x[1]))[:6]:
    print(f"  [{len(v)} 个] {k} | {[s.get('name') for s in v][:4]}")

# -*- coding: utf-8 -*-
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _paths import dist, history, seeds, p  # noqa: E402

"""对比新旧 tvbox.json 合并效果。"""
import json
import sys
from collections import Counter

OLD = dist("tvbox.before-merge.json")
NEW = dist("tvbox.json")


def stat(path, tag):
    c = json.load(open(path, encoding="utf-8"))
    sites = [s for s in (c.get("sites") or []) if isinstance(s, dict)]
    types = Counter(s.get("type") for s in sites)
    jarred = sum(1 for s in sites if s.get("jar"))
    print(f"{tag}")
    print(f"  站点总数 {len(sites)} | 类型分布 {dict(types)} | 带 per-site jar 的站点 {jarred}")
    print(f"  parses {len(c.get('parses') or [])} | lives {len(c.get('lives') or [])} "
          f"| hosts {len(c.get('hosts') or [])} | rules {len(c.get('rules') or [])} "
          f"| doh {len(c.get('doh') or [])} | ads {len(c.get('ads') or [])}")
    print(f"  spider = {str(c.get('spider'))[:90]}")
    return c


old = stat(OLD, "旧版（仅 type 0/1 合并，type:3 全部丢弃）：")
new = stat(NEW, "新版（完整合并引擎，type:3 共存）：")

old_keys = {s.get("key") for s in (old.get("sites") or []) if isinstance(s, dict)}
new_keys = {s.get("key") for s in (new.get("sites") or []) if isinstance(s, dict)}
print(f"\n净增站点 key：{len(new_keys - old_keys)} 个（旧 {len(old_keys)} → 新 {len(new_keys)}）")
sample = [s for s in (new.get("sites") or []) if isinstance(s, dict) and s.get("jar")][:5]
print("带 per-site jar 的站点示例：")
for s in sample:
    print(f"  {s.get('key')} | {s.get('name')} | type={s.get('type')} | jar={str(s.get('jar'))[:60]}")

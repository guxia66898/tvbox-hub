# -*- coding: utf-8 -*-
"""合并 discovered.json + 多仓缓存 到 seeds/lines.json（normalize_url 语义去重）。"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tvbox_config_parser import clean_source_url, normalize_url  # noqa: E402

SEEDS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "lines.json")
DISC = os.path.join(os.path.dirname(os.path.abspath(__file__)), "discovered.json")
CACHE = os.path.join(os.environ.get("TEMP", ""), "tvbox_valid.json")

data = json.load(open(SEEDS, encoding="utf-8"))
base = data["base_lines"]
seen = {normalize_url(clean_source_url(u)) for _, u in base}

added = []
for name, u in json.load(open(DISC, encoding="utf-8")).get("entries", []):
    key = normalize_url(clean_source_url(u))
    if key not in seen:
        seen.add(key)
        base.append([str(name), str(u)])
        added.append(name)

cache = json.load(open(CACHE, encoding="utf-8")) if os.path.exists(CACHE) else []
for item in cache:
    if not isinstance(item, dict):
        continue
    if item.get("kind") not in ("multi_storehouse", "multi_urls"):
        continue
    u = item.get("url")
    if not u:
        continue
    key = normalize_url(clean_source_url(u))
    if key in seen:
        continue
    seen.add(key)
    host = key.split("://", 1)[-1].split("/")[0]
    name = f"多仓-{host}"
    base.append([name, u])
    added.append(name)

json.dump(data, open(SEEDS, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
print(f"种子总数: {len(base)} | 本次新增: {len(added)}")
for n in added:
    print("  +", n)

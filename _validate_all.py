# -*- coding: utf-8 -*-
"""校验所有产物为合法 JSON，无冲突标记残留。"""
import io
import json
import os
import sys

sys.path.insert(0, ".")
sys.path.insert(0, "tools")
from _paths import dist  # noqa: E402

FILES = ["best.json", "sources.json", "merged.json", "curated.json",
         "report.json", "jar_health.json"]

ok_all = True
for f in FILES:
    p = dist(f)
    if not os.path.exists(p):
        print(f"  MISS {f}")
        ok_all = False
        continue
    raw = io.open(p, encoding="utf-8", newline="").read()
    markers = [m for m in ("<<<<<<<", "=======", ">>>>>>>") if m in raw]
    try:
        d = json.loads(raw)
        extra = ""
        if f == "sources.json":
            extra = f" | {d.get('count')} 源"
        elif f == "merged.json":
            extra = f" | {len(d.get('urls', []))} 条"
        elif f == "curated.json":
            extra = f" | {len(d.get('urls', []))} 条"
        elif f == "report.json":
            extra = f" | 可用 {d['summary']['available']}"
        print(f"  OK   {f:16} {len(raw)//1024:>5}KB{extra}"
              + (f"  ⚠ 冲突标记 {markers}" if markers else ""))
        if markers:
            ok_all = False
    except Exception as e:
        print(f"  FAIL {f:16} {str(e)[:60]}")
        ok_all = False

# HTML 面板
p = dist("index.html")
html = io.open(p, encoding="utf-8", newline="").read()
print(f"  {'OK  ' if 'const DATA =' in html else 'FAIL'} index.html       {len(html)//1024:>5}KB")

print()
print("全部合格" if ok_all else "有问题需修复")

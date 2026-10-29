# -*- coding: utf-8 -*-
"""面板产物完整性检查（不依赖浏览器）。"""
import json
import re
import sys

sys.path.insert(0, __import__("os").path.dirname(__import__("os").path.abspath(__file__)))
from _paths import dist  # noqa: E402

html = open(dist("index.html"), encoding="utf-8").read()
checks = {
    "标题": "TVBox 线路中枢 · 体检面板" in html,
    "内嵌数据": "const DATA = {" in html,
    "行数上限常量": "MAX_ROWS" in html,
    "汇总卡片容器": 'id="cards"' in html,
    "趋势图容器": 'id="trend"' in html,
    "差异区容器": 'id="diff"' in html,
    "表格容器": 'id="rows"' in html,
    "筛选-关键字": 'id="kw"' in html,
    "筛选-类型": 'id="fKind"' in html,
    "筛选-状态": 'id="fStatus"' in html,
    "无外链资源": len(re.findall(r'(?:src|href)="https?://', html)) == 0,
    "转义处理": 'replace(/[&<>"]/g' in html,
}
for k, v in checks.items():
    print(f"  {'OK ' if v else 'FAIL'} {k}")
assert all(checks.values()), [k for k, v in checks.items() if not v]

# 内嵌数据可解析
m = re.search(r"const DATA = (\{.*?\});\n", html, re.S)
assert m, "无法提取内嵌 DATA"
# 去掉 JS 转义后解析
raw = m.group(1).replace("<\\/", "</")
data = json.loads(raw)
r = data["report"]
print(f"\n内嵌 report: lines {len(r['lines'])} 顶层 | summary available {r['summary']['available']}"
      f" | history {len(data.get('history', []))} 点")
print(f"差异: 新增 {len(r['diff']['newly_available'])} / 失效 {len(r['diff']['newly_dead'])}")
print(f"页面大小: {len(html)//1024} KB")
print("PANEL CHECK ALL PASS")

# -*- coding: utf-8 -*-
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _paths import dist, history, seeds, p  # noqa: E402

"""纰漏审计：用真实产物检查可交付质量。"""
import json
import os
import re
import sys
from collections import Counter


print("=" * 60)
print("1. tvbox.json 是否真能被 TVBox 解析（结构合法性）")
print("=" * 60)
t = json.load(open(dist("tvbox.json"), encoding="utf-8"))
sites = t.get("sites") or []
bad_key = [s for s in sites if not isinstance(s.get("key"), str) or " " in s.get("key", "")]
bad_type = [s for s in sites if not isinstance(s.get("type"), int)]
no_api = [s for s in sites if not s.get("api")]
print(f"站点 {len(sites)} | key 非字符串或含空格 {len(bad_key)} | type 非整数 {len(bad_type)} | 无 api {len(no_api)}")

# key 是否含特殊字符（TVBox 用作 SP 存储 key，可能有隐患）
odd = [s["key"] for s in sites if re.search(r"[^\w\u4e00-\u9fff\-\.]", s.get("key", ""))]
print(f"key 含特殊字符（TVBox 用作存储键可能有隐患）: {len(odd)} 例 {odd[:5]}")

print()
print("=" * 60)
print("2. 站点 api 格式检查")
print("=" * 60)
apis = [s.get("api", "") for s in sites]
no_scheme = [a for a in apis if not str(a).startswith(("http://", "https://", "csp_", "py_", "js_"))]
print(f"api 无有效 scheme: {len(no_scheme)} 例 {no_scheme[:5]}")
weird = [a for a in apis if str(a).startswith("https:/") and not str(a).startswith("https://")]
print(f"api 协议头残缺: {len(weird)} 例 {weird[:3]}")

print()
print("=" * 60)
print("3. jar 地址质量")
print("=" * 60)
jars = [s.get("jar") for s in sites if s.get("jar")]
uniq_jars = set(jars)
bad_jar = [j for j in uniq_jars if not str(j).split(";md5;")[0].startswith(("http://", "https://"))]
print(f"jar 引用 {len(jars)} 次 / 唯一 {len(uniq_jars)} 个 | 协议头不合法 {len(bad_jar)} 例 {bad_jar[:3]}")
proxy_jar = [j for j in uniq_jars if any(p in str(j) for p in ("gh-proxy", "ghproxy", "ghfast", "ghp.ci", "gh.llkk", "moeyy"))]
print(f"仍含代理前缀的 jar: {len(proxy_jar)} 个（会尝试剥离）")
for j in proxy_jar[:3]:
    print(f"   {str(j)[:100]}")

print()
print("=" * 60)
print("4. 产物之间的数据一致性")
print("=" * 60)
m = json.load(open(dist("merged.json"), encoding="utf-8"))
c = json.load(open(dist("curated.json"), encoding="utf-8"))
r = json.load(open(dist("report.json"), encoding="utf-8"))
print(f"merged {len(m['urls'])} | curated {len(c['urls'])} | report available {r['summary']['available']}")
from tvbox_config_parser import clean_source_url as _cs, normalize_url as _nu
cur_urls = {_nu(_cs(u["url"])) for u in c["urls"]}
mer_urls = {_nu(_cs(u["url"])) for u in m["urls"]}
print(f"curated 是否为 merged 子集: {cur_urls <= mer_urls}")
print(f"both 空 name: {sum(1 for u in m['urls'] if not u.get('name'))} / {len(m['urls'])}")
print(f"merged 内重复 URL: {len(m['urls']) - len(mer_urls)}")

print()
print("=" * 60)
print("5. 面板自包含性（有没有外链依赖）")
print("=" * 60)
html = open(dist("index.html"), encoding="utf-8").read()
ext = re.findall(r'(?:src|href)="(https?://[^"]+)"', html)
print(f"外部资源引用: {len(ext)} 例 {ext[:3]}")
print(f"文件大小: {len(html)//1024} KB | 内嵌 DATA: {'const DATA =' in html}")

print()
print("=" * 60)
print("6. 历史快照完整性")
print("=" * 60)
idx = json.load(open(history("index.json"), encoding="utf-8"))
print(f"index 条目 {len(idx)} | 最新 {idx[0]['ts'][:19]} available={idx[0]['available']}")
missing = [e["file"] for e in idx if not os.path.exists(os.path.join("history", e["file"]))]
print(f"快照文件缺失: {len(missing)} {missing[:3]}")
series = json.load(open(history("history.json"), encoding="utf-8"))
print(f"趋势序列 {len(series)} 点")

print()
print("=" * 60)
print("7. seeds 一致性")
print("=" * 60)
seeds_data = json.load(open(seeds("lines.json"), encoding="utf-8"))
from tvbox_config_parser import normalize_url, clean_source_url
keys = [normalize_url(clean_source_url(u)) for _, u in seeds_data["base_lines"]]
dup = [k for k, v in Counter(keys).items() if v > 1]
print(f"种子 {len(keys)} 条 | 重复 {len(dup)} {dup[:3]}")
auto = json.load(open(seeds("auto.json"), encoding="utf-8")) if os.path.exists(seeds("auto.json")) else {"entries": []}
auto_keys = {normalize_url(clean_source_url(e["url"])) for e in auto["entries"]}
print(f"auto.json {len(auto['entries'])} 条 | 与种子表重叠: {len(auto_keys & set(keys))}")

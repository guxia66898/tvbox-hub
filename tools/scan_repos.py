# -*- coding: utf-8 -*-
"""jsDelivr 文件树扫描（@main/@master 回退）。输出候选种子 raw URL。"""
import json
import urllib.request

REPOS = [
    ("qist/tvbox", "OK影视·tvbox"),
    ("2hacc/TVBox", "TVBox网络接口"),
    ("noimank/tvbox", "自用tvbox源·影视仓多仓"),
    ("Dong-learn9/TVBox-zyjk", "TVBox自用接口"),
    ("Zhou-Li-Bin/Tvbox-QingNing", "青柠聚合"),
    ("cluntop/tvbox", "cluntop接口"),
    ("kimwang1978/tvbox", "自用影视仓·TVBOX"),
    ("wuxierj/TVBox", "接口大全"),
    ("niubihu1/tvbox", "牛虎旗舰聚合"),
    ("qirenzhidao/tvbox18", "tvbox影视tv宝盒"),
    ("hackyjso/TVbox", "TVbox配置"),
    ("youhunwl/TVBox", "接口私有化备份"),
]

def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "tvbox-hub-seeds"})
    return json.load(urllib.request.urlopen(req, timeout=25))

for repo, label in REPOS:
    tree = None
    used = None
    for br in ("main", "master", "HEAD"):
        try:
            data = get(f"https://data.jsdelivr.com/v1/packages/gh/{repo}@{br}")
            tree = data.get("files", [])
            used = br
            break
        except Exception:
            continue
    if tree is None:
        print(f"{repo} [{label}] ERR unreachable")
        continue
    root = [f for f in tree if "/" not in f.get("name", "") and f.get("type") == "file"
            and f["name"].lower().endswith((".json", ".txt")) and f.get("size", 0) > 1500
            and not f["name"].startswith(("_", "."))]
    root.sort(key=lambda x: -x["size"])
    for f in root[:2]:
        print(f"SEED|{label}|{repo}|{used}|{f['name']}|{f['size']}")
    if not root:
        subs = [f["name"] for f in tree if f.get("type") == "directory"][:6]
        print(f"NOTE|{repo}@{used}|根目录无大json，子目录: {subs}")

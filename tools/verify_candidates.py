# -*- coding: utf-8 -*-
"""候选种子实测：抓取+解析，输出可直接写入 seeds 的验证结果。"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from hub.fetch import http_fetch_sync  # noqa: E402
from tvbox_config_parser import parse_payload  # noqa: E402

CANDS = [
    ("2hacc-oktv", "https://raw.githubusercontent.com/2hacc/TVBox/main/oktv.json"),
    ("noimank-多仓", "https://raw.githubusercontent.com/noimank/tvbox/main/tvboxmuti.json"),
    ("Dong-learn9-1", "https://raw.githubusercontent.com/Dong-learn9/TVBox-zyjk/main/tvbox1.json"),
    ("Dong-learn9-2", "https://raw.githubusercontent.com/Dong-learn9/TVBox-zyjk/main/tvbox2.json"),
    ("hackyjso-jzy", "https://raw.githubusercontent.com/hackyjso/TVbox/main/jzy.txt"),
    ("youhunwl-毒盒", "https://raw.githubusercontent.com/youhunwl/TVBox/master/毒盒.txt"),
    ("youhunwl-摸鱼", "https://raw.githubusercontent.com/youhunwl/TVBox/master/摸鱼.txt"),
    ("juhe-subhub聚合", "https://ofind.cn/juhe-subhub/merged.json"),
]

for name, u in CANDS:
    r = http_fetch_sync(u, timeout_s=10)
    p = parse_payload(r["body_bytes"]) if r["ok"] else None
    if p:
        size = r["size_kb"]
        print(f"{name}: {p.kind} 子线{len(p.sub_entries)} 站点{p.site_count} {size:.0f}KB")
    else:
        print(f"{name}: 不可用 {r['error'][:40]}")

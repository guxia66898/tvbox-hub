# -*- coding: utf-8 -*-
"""自动发现模块离线测试（monkeypatch 网络层，零外网依赖）。"""
import json
import os
import shutil
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from hub import discover as D  # noqa: E402
from hub.config import HubConfig  # noqa: E402

REAL_CFG = json.dumps({"spider": "x.jar",
                       "sites": [{"key": "a", "name": "A", "type": 0, "api": "http://a/api"}]})
MULTI_CFG = json.dumps({"urls": [{"name": "s1", "url": "http://s1/1.json"},
                                {"name": "s2", "url": "http://s2/2.json"}]})
JUNK = "<html>not a config</html>"

INDEX_BODY = """
some text https://example.com/tvbox/ok.json and https://example.com/img/banner.png
and https://example.com/other/page.html  and https://raw.githubusercontent.com/x/y/main/a.json
"""


def fake_fetch(url, timeout_s=10.0, max_bytes=2_000_000):
    """按 URL 返回预置响应。"""
    def ok(body, size_kb=None):
        b = body.encode() if isinstance(body, str) else body
        return {"ok": True, "status": 200, "body": b.decode("utf-8", "replace"),
                "body_bytes": b, "ttfb_ms": 10.0, "total_ms": 20.0,
                "size_kb": len(b) / 1024, "final_url": url, "error": ""}

    if "README.md" in url:
        return ok(INDEX_BODY)
    if "codeberg.org/api/v1/repos/search" in url:
        return ok(json.dumps({"data": [
            {"full_name": "someone/tvbox-config", "default_branch": "main"},
            {"full_name": "broken/empty", "default_branch": "main"}]}))
    if "codeberg.org/api/v1/repos/someone/tvbox-config/contents" in url:
        return ok(json.dumps([
            {"name": "main.json", "type": "file", "size": 5000},
            {"name": "readme.md", "type": "file", "size": 100}]))
    if "broken/empty/contents" in url:
        return ok(json.dumps([{"name": "x.json", "type": "file", "size": 10}]))
    # 候选配置本体
    if url.endswith("ok.json") or url.endswith("a.json") or "main.json" in url:
        return ok(REAL_CFG)
    if url.endswith("multi.json"):
        return ok(MULTI_CFG)
    if url.endswith("junk.json"):
        return ok(JUNK)
    return {"ok": False, "status": None, "body": "", "body_bytes": None,
            "ttfb_ms": None, "total_ms": None, "size_kb": None, "final_url": url,
            "error": "HTTP 404"}


def main():
    D._fetch = fake_fetch  # 打桩

    work = tempfile.mkdtemp()
    try:
        seeds = os.path.join(work, "seeds")
        os.makedirs(seeds)
        cfg = HubConfig(seeds_path=os.path.join(seeds, "lines.json"),
                        discover_max=20, discover_concurrency=4)

        # 1) 全通道发现：索引页 + codeberg
        found = D.discover(cfg, known=set())
        urls = {f["url"] for f in found}
        assert "https://example.com/tvbox/ok.json" in urls, urls
        assert any("codeberg.org/someone/tvbox-config/raw" in u for u in urls), urls
        assert not any(u.endswith(".png") for u in urls)
        # 解析通过才入库
        assert all(f["kind"] in ("single", "multi_urls", "multi_storehouse") for f in found)
        # 按内容量排序（多仓权重更高）
        print("发现的条目:", [(f["name"][:22], f["kind"], f["sites"], f["subs"]) for f in found])

        # 2) 已知 URL 应被过滤
        known = {D.normalize_url("https://example.com/tvbox/ok.json")}
        found2 = D.discover(cfg, known=known)
        assert not any("ok.json" in f["url"] for f in found2), "已知来源未被过滤"

        # 3) 无效/不可解析的候选被丢弃
        assert not any(f["url"].endswith("junk.json") for f in found2)

        # 4) auto.json 写入与合并
        path = D.save_auto(cfg, found)
        assert os.path.exists(path)
        entries = D.load_auto(cfg)
        assert len(entries) == len({D.normalize_url(f["url"]) for f in found})
        assert all("first_seen" in e and e["ok"] == 1 and e["fail"] == 0 for e in entries)

        # 5) 健康计数：连续失败 3 次要淘汰
        target = entries[0]["url"]
        for _ in range(3):
            D.update_health(cfg, [{"url": target, "status": "fail", "error": "超时",
                                   "children": []}])
        left = {e["url"] for e in D.load_auto(cfg)}
        assert target not in left, "死源未被淘汰"

        # 6) 成功探活会重置 fail 并累计 ok
        other = [e for e in D.load_auto(cfg) if e["url"] != target][0]["url"]
        D.update_health(cfg, [{"url": other, "status": "ok", "error": "", "children": []}])
        e2 = {e["url"]: e for e in D.load_auto(cfg)}[other]
        assert e2["fail"] == 0 and e2["ok"] >= 1

        # 7) 重复通道候选去重（同一 URL 只进一次）
        assert len([e for e in entries if e["url"].endswith("ok.json")]) == 1

        # 8) 无 token 时不走 GitHub 通道（不应报错）
        cfg2 = HubConfig(seeds_path=cfg.seeds_path, github_token="")
        os.environ.pop("GITHUB_TOKEN", None)
        D.discover(cfg2, known=set())
        print("DISCOVER ALL PASS")
    finally:
        shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    main()

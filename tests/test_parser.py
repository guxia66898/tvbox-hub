# -*- coding: utf-8 -*-
"""tvbox_config_parser 离线自测：python tests/test_parser.py → ALL PASS"""
import base64
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tvbox_config_parser import (  # noqa: E402
    KIND_SINGLE, KIND_STORE, KIND_URLS,
    clean_source_url, decrypt_catvod_aes_hex, extract_urls,
    normalize_url, parse_payload,
)

PNG_1X1 = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==")


def _pad(b: bytes) -> bytes:
    p = 16 - len(b) % 16
    return b + bytes([p]) * p


def _enc2423(plaintext: str, key_str: str, iv_str: str) -> str:
    """构造 2423 测试向量：字节流 = $# + key + #$ + 密文原始字节 + IV ASCII，整体再 hex。"""
    from Crypto.Cipher import AES
    key = (key_str + "0" * 16)[:16].encode("utf-8")
    iv = (iv_str + "0" * 16)[:16].encode("utf-8")
    cipher = AES.new(key, AES.MODE_CBC, iv).encrypt(_pad(plaintext.encode("utf-8")))
    stream = (b"$#" + key_str.encode("utf-8") + b"#$"
              + cipher + iv_str.encode("utf-8"))
    return stream.hex().upper()


def test_relaxed_json():
    raw = ("\ufeff// 顶部注释\n/* 块注释 */{\n"
           "  \"name\": \"测试仓\", // 行注释\n"
           "  \"spider\": \"https://x/y.jar;md5;1\",\n"
           "  \"sites\": [{\"key\":\"a\",\"name\":\"A\",\"type\":0,\"api\":\"https://a/api\"},],\n"
           "}\n")
    p = parse_payload(raw.encode("utf-8"))
    assert p is not None and p.kind == KIND_SINGLE and p.format == "json_relaxed"
    assert p.raw_obj["name"] == "测试仓" and p.site_count == 1
    # 字符串内不误伤
    raw2 = '{"spider": "", "sites": [], "lives": [], "parses": []}'
    p2 = parse_payload(raw2.encode())
    assert p2 is not None and p2.kind == "unknown"  # 单仓键全空 → unknown


def test_single():
    raw = json.dumps({"spider": "./jar/x.jar", "sites": [
        {"key": str(i), "name": str(i), "type": 0, "api": "https://h/api"} for i in range(3)]})
    p = parse_payload(raw.encode())
    assert p and p.kind == KIND_SINGLE and p.site_count == 3 and p.format == "plain_json"


def test_multi_urls():
    raw = json.dumps({"urls": [{"name": "a", "url": "http://a/1.json"},
                               {"name": "b", "url": "http://b/2.json"}]})
    p = parse_payload(raw.encode())
    assert p and p.kind == KIND_URLS and p.sub_entries == [("a", "http://a/1.json"), ("b", "http://b/2.json")]


def test_store():
    raw = json.dumps({"storeHouse": [{"sourceName": "a", "sourceUrl": "http://a/1.json"}]})
    p = parse_payload(raw.encode())
    assert p and p.kind == KIND_STORE and len(p.sub_entries) == 1


def test_aes_2423():
    plain = json.dumps({"spider": "x.jar", "sites": [{"key": "k", "name": "n", "type": 0, "api": "http://h/api"}]},
                       ensure_ascii=False)
    hexfile = _enc2423(plain, "abc1234567", "1737735574000")  # 13 位时间戳 IV
    out = decrypt_catvod_aes_hex(hexfile)
    assert out is not None and json.loads(out) == json.loads(plain)
    p = parse_payload(hexfile.encode())
    assert p is not None and p.format == "aes_hex" and p.kind == KIND_SINGLE
    hexfile16 = _enc2423(plain, "0123456789abcdef", "0123456789abcdef")  # 完整 16 字节 IV
    assert decrypt_catvod_aes_hex(hexfile16) is not None
    assert decrypt_catvod_aes_hex("2423zzzz-not-hex-zzzzzzzzzzzzzzzzzzzz") is None


def test_stego():
    cfg = json.dumps({"urls": [{"name": "s", "url": "http://s/1.json"}]}).encode()
    raw = PNG_1X1 + b"**" + base64.b64encode(cfg)
    p = parse_payload(raw)
    assert p is not None and p.format == "image_stego" and p.kind == KIND_URLS


def test_base64():
    cfg = json.dumps({"spider": "a.jar", "sites": [{"key": "k", "name": "n", "type": 1, "api": "http://h/x"}]})
    p = parse_payload(base64.b64encode(cfg.encode()))
    assert p is not None and p.format == "base64_json" and p.kind == KIND_SINGLE


def test_utils():
    assert clean_source_url("https://ghproxy.net/https://raw.githubusercontent.com/a/b/main/c.json") \
        == "https://raw.githubusercontent.com/a/b/main/c.json"
    assert clean_source_url("https://https://raw.githubusercontent.com/a/b/main/c.json") \
        == "https://raw.githubusercontent.com/a/b/main/c.json"
    assert normalize_url("http://肥猫.com/") == "http://肥猫.com"
    assert normalize_url("https://Host.COM/Path/X") == "https://Host.COM/path/x"  # 路径全小写（与 v1.0 一致）


def test_harvest():
    html = ('<a href="https://x.com/tvbox/a.json">cfg</a>'
            '<img src="https://x.com/banner.png">'
            '<a href="https://github.com/some/repo">repo</a>'
            '<a href="https://x.com/app/52116.html">page</a>'
            '<a href="https://y.cn/api.php/provide/vod">api</a>')
    urls = extract_urls(html)
    assert "https://x.com/tvbox/a.json" in urls and "https://y.cn/api.php/provide/vod" in urls
    assert all(".png" not in u and "github.com" not in u and "/app/" not in u for u in urls)


def main():
    test_relaxed_json()
    test_single()
    test_multi_urls()
    test_store()
    test_aes_2423()
    test_stego()
    test_base64()
    test_utils()
    test_harvest()
    print("ALL PASS")


if __name__ == "__main__":
    main()

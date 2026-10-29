"""TVBox/影视仓 配置解析与分类：明文/带注释 JSON、图片隐写、2423 AES、纯 Base64。

注释剥离状态机与隐写提取方案参考 yz8023/ysc-helper-android（无 LICENSE 文件），
Python 侧为独立重写。详见项目根 NOTICE。
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field

from .crypto import decrypt_catvod_aes_hex
from .stego import decode_pure_base64, decode_stego_after_double_star

KIND_SINGLE = "single"
KIND_STORE = "multi_storehouse"
KIND_URLS = "multi_urls"
KIND_UNKNOWN = "unknown"

FORMAT_PLAIN_JSON = "plain_json"
FORMAT_JSON_RELAXED = "json_relaxed"
FORMAT_IMAGE_STEGO = "image_stego"
FORMAT_AES_HEX = "aes_hex"
FORMAT_BASE64_JSON = "base64_json"

_SINGLE_KEYS = ("spider", "sites", "lives", "parses")


@dataclass
class ParsedPayload:
    kind: str
    format: str
    name: str
    site_count: int
    has_cleartext_spider: bool
    sub_entries: list = field(default_factory=list)
    raw_obj: dict = field(default_factory=dict)


def _has_content(v) -> bool:
    """单仓判定：键值非 None、非空串、非空列表。"""
    return v is not None and v != "" and v != []


def strip_comments_and_trailing_commas(text: str) -> str:
    """词法状态机：剔除 // 与 /* */ 注释及字符串外的尾随逗号，不误伤字符串内容。"""
    # 第一遍：剔除注释
    sb: list[str] = []
    i, n = 0, len(text)
    in_string = False
    escaped = False
    while i < n:
        c = text[i]
        if in_string:
            sb.append(c)
            if escaped:
                escaped = False
            elif c == "\\":
                escaped = True
            elif c == '"':
                in_string = False
            i += 1
            continue
        if c == '"':
            in_string = True
            sb.append(c)
            i += 1
            continue
        if c == "/" and i + 1 < n and text[i + 1] == "/":
            i += 2
            while i < n and text[i] not in ("\n", "\r"):
                i += 1
            continue
        if c == "/" and i + 1 < n and text[i + 1] == "*":
            i += 2
            while i + 1 < n and not (text[i] == "*" and text[i + 1] == "/"):
                i += 1
            i += 2
            continue
        sb.append(c)
        i += 1

    # 第二遍：安全消除字符串外的尾随逗号
    clean = "".join(sb)
    out: list[str] = []
    in_string = False
    escaped = False
    i, m = 0, len(clean)
    while i < m:
        c = clean[i]
        if in_string:
            out.append(c)
            if escaped:
                escaped = False
            elif c == "\\":
                escaped = True
            elif c == '"':
                in_string = False
            i += 1
            continue
        if c == '"':
            in_string = True
            out.append(c)
            i += 1
            continue
        if c == ",":
            j = i + 1
            while j < m and clean[j].isspace():
                j += 1
            if j < m and clean[j] in ("}", "]"):
                i += 1
                continue
        out.append(c)
        i += 1
    return "".join(out)


def parse_json_relaxed(text: str) -> dict | None:
    """宽松解析：先直接 json.loads，失败则剥离注释/尾逗号后从第一个 '{' 解析。"""
    t = (text or "").lstrip("\ufeff").strip()
    try:
        obj = json.loads(t)
        return obj if isinstance(obj, dict) else None
    except Exception:
        pass
    stripped = strip_comments_and_trailing_commas(t)
    idx = stripped.find("{")
    if idx < 0:
        return None
    try:
        obj = json.loads(stripped[idx:])
        return obj if isinstance(obj, dict) else None
    except Exception:
        return None


def classify(obj: dict, fmt: str) -> ParsedPayload:
    """按 storeHouse / urls / 单仓键序判定类型，抽取子仓与统计信息。"""
    sub: list[tuple[str, str]] = []
    sh = obj.get("storeHouse")
    sh_is_store = isinstance(sh, list) and bool(sh) and any(
        isinstance(x, dict) and x.get("sourceUrl") for x in sh)
    if isinstance(sh, list):
        for item in sh:
            if isinstance(item, dict):
                url = item.get("sourceUrl")
                if url and str(url).strip():
                    sub.append((str(item.get("sourceName") or ""), str(url)))

    urls = obj.get("urls")
    urls_is_multi = isinstance(urls, list) and bool(urls) and any(
        isinstance(x, dict) and x.get("url") for x in urls)
    if isinstance(urls, list):
        for item in urls:
            if isinstance(item, dict):
                url = item.get("url")
                if url and str(url).strip():
                    sub.append((str(item.get("name") or ""), str(url)))

    if sh_is_store:
        kind = KIND_STORE
    elif urls_is_multi:
        kind = KIND_URLS
    elif any(_has_content(obj.get(k)) for k in _SINGLE_KEYS):
        kind = KIND_SINGLE
    else:
        kind = KIND_UNKNOWN

    sites = obj.get("sites")
    name = obj.get("name")
    spider = obj.get("spider")
    return ParsedPayload(
        kind=kind,
        format=fmt,
        name=str(name) if isinstance(name, str) else "",
        site_count=len(sites) if isinstance(sites, list) else 0,
        has_cleartext_spider=isinstance(spider, str) and spider.strip().startswith("http://"),
        sub_entries=sub,
        raw_obj=obj,
    )


def parse_payload(raw_bytes: bytes) -> "ParsedPayload | None":
    """全生态配置解码入口：依次尝试明文 JSON → 带注释 JSON → 图片隐写 → 2423 AES → Base64。

    确认为 2423 格式但缺 pycryptodome 时抛 RuntimeError（调用方可捕获提示）。
    """
    if not raw_bytes:
        return None
    raw_text = raw_bytes.decode("utf-8", "replace").lstrip("\ufeff").strip()

    # 1) 明文标准 JSON 快速通道
    if raw_text.startswith("{"):
        try:
            obj = json.loads(raw_text)
        except Exception:
            obj = None
        if isinstance(obj, dict):
            return classify(obj, FORMAT_PLAIN_JSON)

    # 2) 带注释/尾逗号 JSON
    if "{" in raw_text:
        stripped = strip_comments_and_trailing_commas(raw_text)
        idx = stripped.find("{")
        if idx >= 0:
            candidate = stripped[idx:]
            try:
                obj = json.loads(candidate)
            except Exception:
                obj = None
            if isinstance(obj, dict):
                fmt = FORMAT_PLAIN_JSON if candidate == raw_text else FORMAT_JSON_RELAXED
                return classify(obj, fmt)

    # 3) 图片伪装隐写协议
    decoded = decode_stego_after_double_star(raw_bytes)
    if decoded:
        obj = parse_json_relaxed(decoded)
        if isinstance(obj, dict):
            return classify(obj, FORMAT_IMAGE_STEGO)

    # 4) CatVod 2423 加密配置
    if raw_text.lower().startswith("2423"):
        dec = decrypt_catvod_aes_hex(raw_text)
        if dec:
            obj = parse_json_relaxed(dec)
            if isinstance(obj, dict):
                return classify(obj, FORMAT_AES_HEX)

    # 5) 纯 Base64 编码 JSON
    decoded = decode_pure_base64(raw_text)
    if decoded:
        obj = parse_json_relaxed(decoded)
        if isinstance(obj, dict):
            return classify(obj, FORMAT_BASE64_JSON)

    return None

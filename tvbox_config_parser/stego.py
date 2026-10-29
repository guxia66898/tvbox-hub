"""图片伪装协议与纯 Base64 配置提取。"""
from __future__ import annotations

import base64


def decode_pure_base64(text: str) -> str | None:
    """解码纯 Base64 编码的 JSON 配置体；非 Base64 内容返回 None。"""
    t = (text or "").strip().replace("\n", "").replace("\r", "")
    if len(t) < 16 or t.startswith("{") or t.startswith("<"):
        return None
    try:
        raw = base64.b64decode(t, validate=True)
    except Exception:
        try:
            raw = base64.urlsafe_b64decode(t + "=" * (-len(t) % 4))
        except Exception:
            return None
    return raw.decode("utf-8", "ignore")


def decode_stego_after_double_star(data: bytes) -> str | None:
    """图片伪装接口：二进制流末尾 '**' 标记后的 Base64 配置体。

    从后向前找最后一个 '**'，避免前半段 PNG/JPG 二进制偶然出现 '**'。
    """
    if not data:
        return None
    pos = -1
    for i in range(len(data) - 2, -1, -1):
        if data[i] == 0x2A and data[i + 1] == 0x2A:
            pos = i + 2
            break
    if pos < 0 or pos >= len(data):
        return None
    tail = data[pos:].decode("ascii", "ignore").strip()
    tail = tail.replace("\n", "").replace("\r", "")
    if len(tail) < 8:
        return None
    return decode_pure_base64(tail)

"""CatVod 2423（$#key#$cipher+iv）AES-128-CBC Hex 加密配置解密。

文件本身是字节流的 hex 编码：$# + key + #$ + cipherHex + ivStr。
- "2423" 即 "$#" 的字节 hex（0x24 0x23），"2324" 即 "#$"。
- IV 兼容两种形态：13 位时间戳字符串（补 '0' 到 16 字节）与完整 16 字节。
- key 为字符串字节，右侧补 '0' 到 16 字节（超长截断）。
"""
from __future__ import annotations


def hex_to_bytes(hexs: str) -> bytes:
    """严格 hex 转字节：长度必须为偶数且全部为 hex 字符。"""
    s = (hexs or "").strip()
    if len(s) % 2 != 0:
        raise ValueError("hex 长度为奇数")
    return bytes.fromhex(s)


def decrypt_catvod_aes_hex(text: str) -> str | None:
    """解密 2423 加密配置；格式不符/密钥错/解密失败返回 None。

    当确认输入是 2423 格式但缺少 pycryptodome 时抛出 RuntimeError。
    """
    try:
        clean = (text or "").strip().lower()
        if not clean.startswith("2423") or len(clean) < 40:
            return None
        key_end = clean.find("2324", 4)
        if key_end < 4:
            return None
        key_str = hex_to_bytes(clean[4:key_end]).decode("utf-8", "ignore")
        key = (key_str + "0" * 16)[:16].encode("utf-8")

        rem = len(clean) - (key_end + 4)
        # AES-CBC 密文必为 16 字节(32 hex)整数倍：
        # 余数 26 → 标准 13 位时间戳 IV（13 字节=26 hex）；余数 0 → 完整 16 字节 IV
        if rem > 26 and rem % 32 == 26:
            iv_hex_len = 26
        elif rem > 32 and rem % 32 == 0:
            iv_hex_len = 32
        else:
            return None
        iv_str = hex_to_bytes(clean[-iv_hex_len:]).decode("utf-8", "ignore")
        iv = (iv_str + "0" * 16)[:16].encode("utf-8")

        cipher_bytes = hex_to_bytes(clean[key_end + 4: len(clean) - iv_hex_len])
        if not cipher_bytes or len(cipher_bytes) % 16 != 0:
            return None

        try:
            from Crypto.Cipher import AES
        except ImportError as e:
            raise RuntimeError("AES(2423) 解密需要 pycryptodome：pip install pycryptodome") from e
        pt = AES.new(key, AES.MODE_CBC, iv).decrypt(cipher_bytes)
        if pt:
            pad = pt[-1]
            if 1 <= pad <= 16 and pt[-pad:] == bytes([pad]) * pad:
                pt = pt[:-pad]
        return pt.decode("utf-8", "ignore")
    except RuntimeError:
        raise
    except Exception:
        return None

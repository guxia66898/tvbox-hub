"""tvbox-config-parser：TVBox/影视仓 全生态配置解析库。

支持：明文 JSON、带注释/尾逗号 JSON、图片隐写（** + Base64）、
CatVod 2423（$#key#$cipher+iv）AES-128-CBC Hex、纯 Base64。
"""
from .crypto import decrypt_catvod_aes_hex, hex_to_bytes
from .harvest import LINE_KW, SKIP_KW, extract_urls
from .parser import (
    FORMAT_AES_HEX,
    FORMAT_BASE64_JSON,
    FORMAT_IMAGE_STEGO,
    FORMAT_JSON_RELAXED,
    FORMAT_PLAIN_JSON,
    KIND_SINGLE,
    KIND_STORE,
    KIND_UNKNOWN,
    KIND_URLS,
    ParsedPayload,
    classify,
    parse_json_relaxed,
    parse_payload,
    strip_comments_and_trailing_commas,
)
from .stego import decode_pure_base64, decode_stego_after_double_star
from .utils import clean_source_url, encode_url, is_http_url, normalize_url

__all__ = [
    "ParsedPayload", "parse_payload", "parse_json_relaxed", "classify",
    "strip_comments_and_trailing_commas",
    "decrypt_catvod_aes_hex", "hex_to_bytes",
    "decode_stego_after_double_star", "decode_pure_base64",
    "extract_urls", "SKIP_KW", "LINE_KW",
    "normalize_url", "is_http_url", "clean_source_url", "encode_url",
    "KIND_SINGLE", "KIND_STORE", "KIND_URLS", "KIND_UNKNOWN",
    "FORMAT_PLAIN_JSON", "FORMAT_JSON_RELAXED", "FORMAT_IMAGE_STEGO",
    "FORMAT_AES_HEX", "FORMAT_BASE64_JSON",
]

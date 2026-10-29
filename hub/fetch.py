"""HTTP 抓取：SSRF 防护、中文域名 IDNA、gzip 解压、TTFB 计时。"""
from __future__ import annotations

import asyncio
import gzip
import ipaddress
import socket
import time
import urllib.error
import urllib.parse
import urllib.request

_DEFAULT_UA = "okhttp/4.12.0"
_SAFE = "/%:@&?=+.,~*_'-!$()[]"
_CGNAT = ipaddress.ip_network("100.64.0.0/10")


def prepare_url(url: str) -> str:
    """中文域名 IDNA 编码 + 路径/查询重编码（失败原样返回）。"""
    try:
        sp = urllib.parse.urlsplit(url.strip())
        host = sp.hostname or ""
        if any(ord(c) > 127 for c in host):
            host = host.encode("idna").decode("ascii")
        netloc = f"{host}:{sp.port}" if sp.port else host
        path = urllib.parse.quote(sp.path, safe=_SAFE)
        query = urllib.parse.quote(sp.query, safe=_SAFE + "&=")
        return urllib.parse.urlunsplit((sp.scheme, netloc, path, query, ""))
    except Exception:
        return url


def validate_public_host(url: str, allow_private: bool = False) -> None:
    """SSRF 防护：解析 DNS 并拦截私网/回环/链路本地/CGNAT/保留地址。"""
    if allow_private:
        return
    host = (urllib.parse.urlsplit(url).hostname or "").strip()
    if not host:
        raise ValueError(f"无效主机：{url}")
    for info in socket.getaddrinfo(host, None):
        ip = ipaddress.ip_address(info[4][0])
        v4 = ip.ipv4_mapped if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped else ip
        if (v4.is_private or v4.is_loopback or v4.is_link_local or v4.is_multicast
                or v4.is_reserved or v4.is_unspecified or (isinstance(v4, ipaddress.IPv4Address) and v4 in _CGNAT)):
            raise ValueError(f"SSRF 防护：拦截内网/保留地址 {ip}")


def http_fetch_sync(url: str, timeout_s: float = 8.0, ua: str = _DEFAULT_UA,
                    max_bytes: int = 4_194_304, allow_private: bool = False) -> dict:
    """同步抓取，返回固定结构的指标 dict（不抛异常）。"""
    result = {"ok": False, "status": None, "body": "", "body_bytes": None,
              "ttfb_ms": None, "total_ms": None, "size_kb": None,
              "final_url": url, "error": ""}
    try:
        prepared = prepare_url(url)
        validate_public_host(prepared, allow_private)
    except ValueError as e:
        result["error"] = str(e)
        return result
    except (socket.gaierror, OSError) as e:
        result["error"] = ("DNS 解析失败：" + str(getattr(e, "reason", e)))[:120]
        return result
    req = urllib.request.Request(prepared, headers={
        "User-Agent": ua, "Accept": "*/*", "Accept-Encoding": "gzip", "Connection": "close"})
    t0 = time.perf_counter()
    try:
        resp = urllib.request.urlopen(req, timeout=timeout_s)
    except urllib.error.HTTPError as e:
        result["status"] = e.code
        result["total_ms"] = round((time.perf_counter() - t0) * 1000, 1)
        result["error"] = f"HTTP {e.code}"
        return result
    except (socket.timeout, TimeoutError):
        result["error"] = "超时"
        return result
    except urllib.error.URLError as e:
        result["error"] = str(getattr(e, "reason", e))[:120]
        return result
    except Exception as e:  # noqa: BLE001
        result["error"] = (type(e).__name__ + ":" + str(e))[:120]
        return result
    try:
        ttfb = (time.perf_counter() - t0) * 1000
        data = resp.read(max_bytes + 1)
        total = (time.perf_counter() - t0) * 1000
        if len(data) > max_bytes:
            data = data[:max_bytes]
        enc = (resp.headers.get("Content-Encoding") or "").lower()
        if enc == "gzip" or data[:2] == b"\x1f\x8b":
            try:
                data = gzip.decompress(data)
            except Exception:
                pass
        result.update(
            ok=True, status=getattr(resp, "status", None),
            body=data.decode("utf-8", "replace"), body_bytes=data,
            ttfb_ms=round(ttfb, 1), total_ms=round(total, 1),
            size_kb=round(len(data) / 1024, 2), final_url=resp.geturl())
    except Exception as e:  # noqa: BLE001
        result["error"] = (type(e).__name__ + ":" + str(e))[:120]
    finally:
        try:
            resp.close()
        except Exception:
            pass
    return result


async def http_fetch(url: str, **kw) -> dict:
    """线程池异步包装，避免阻塞事件循环。"""
    return await asyncio.to_thread(http_fetch_sync, url, **kw)

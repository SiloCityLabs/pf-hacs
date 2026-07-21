"""Local TOTP + QR PNG generation (no Planet Fitness API calls)."""

from __future__ import annotations

import base64
import hashlib
import hmac
import io
import struct
import time

import segno

from .const import TOTP_DIGITS, TOTP_STEP_SECONDS


def _b32encode_utf8(text: str) -> str:
    """Match OtpNet Base32Encoding.ToString(UTF8 bytes) — no padding."""
    alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZ234567"
    data = text.encode("utf-8")
    bits = 0
    value = 0
    out: list[str] = []
    for byte in data:
        value = (value << 8) | byte
        bits += 8
        while bits >= 5:
            out.append(alphabet[(value >> (bits - 5)) & 31])
            bits -= 5
    if bits:
        out.append(alphabet[(value << (5 - bits)) & 31])
    return "".join(out)


def _b32decode(text: str) -> bytes:
    pad = (-len(text)) % 8
    return base64.b32decode(text.upper() + "=" * pad)


def totp_code(device_id: str, for_time: int | None = None) -> str:
    """Compute the 6-digit TOTP used by the Planet Fitness app keytag."""
    if for_time is None:
        for_time = int(time.time())
    # App: Base32Encoding.ToBytes(Base32Encoding.ToString(UTF8(deviceId)))
    secret = _b32decode(_b32encode_utf8(device_id))
    counter = for_time // TOTP_STEP_SECONDS
    msg = struct.pack(">Q", counter)
    digest = hmac.new(secret, msg, hashlib.sha1).digest()
    offset = digest[-1] & 0x0F
    code = struct.unpack(">I", digest[offset : offset + 4])[0] & 0x7FFFFFFF
    return str(code % (10**TOTP_DIGITS)).zfill(TOTP_DIGITS)


def qr_payload(account_id: str, device_id: str, for_time: int | None = None) -> str:
    """New-format keytag payload: ``{AccountId}:{TOTP}``."""
    return f"{account_id}:{totp_code(device_id, for_time=for_time)}"


def seconds_remaining(for_time: int | None = None) -> int:
    if for_time is None:
        for_time = int(time.time())
    return TOTP_STEP_SECONDS - (for_time % TOTP_STEP_SECONDS)


def qr_png_bytes(payload: str, *, scale: int = 8) -> bytes:
    """Render payload as a PNG QR code."""
    qr = segno.make(payload, error="h")
    buf = io.BytesIO()
    qr.save(buf, kind="png", scale=scale, border=2)
    return buf.getvalue()

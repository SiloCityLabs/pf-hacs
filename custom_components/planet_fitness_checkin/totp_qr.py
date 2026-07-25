"""Local QR payload + PNG generation (no Planet Fitness API calls).

Formats reverse-engineered from PFMobile:

* **NewGen** (`NewGenUser == true`): ``{AccountId}:{TOTP}``
  TOTP secret = UTF-8 bytes of ``personalization.deviceId`` (SHA-1, 30s, 6 digits).

* **Legacy**: ``{AbcBarcode}`` from membership, optionally extended like the app:

  ``ExtendQrCodeIfNeeded`` → append ``/mobile`` (QRCodeSuffix.Mobile) when channel
  source is shown, then ``/{MMddyyyy-HHmmss}`` (UTC) when EnableQrCodeSuffix is on.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import io
import struct
import time
from datetime import datetime, timezone

import segno

from .const import (
    LEGACY_CHANNEL_SUFFIX,
    LEGACY_TIMESTAMP_FORMAT,
    QR_FORMAT_AUTO,
    QR_FORMAT_LEGACY_MOBILE,
    QR_FORMAT_LEGACY_PLAIN,
    QR_FORMAT_NEWGEN,
    TOTP_DIGITS,
    TOTP_STEP_SECONDS,
)


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
    secret = _b32decode(_b32encode_utf8(device_id))
    counter = for_time // TOTP_STEP_SECONDS
    msg = struct.pack(">Q", counter)
    digest = hmac.new(secret, msg, hashlib.sha1).digest()
    offset = digest[-1] & 0x0F
    code = struct.unpack(">I", digest[offset : offset + 4])[0] & 0x7FFFFFFF
    return str(code % (10**TOTP_DIGITS)).zfill(TOTP_DIGITS)


def legacy_timestamp(for_time: int | None = None) -> str:
    """App CompactDateTime: MMddyyyy-HHmmss in UTC."""
    if for_time is None:
        for_time = int(time.time())
    return datetime.fromtimestamp(for_time, tz=timezone.utc).strftime(
        LEGACY_TIMESTAMP_FORMAT
    )


def resolve_format(preferred: str, *, new_gen_user: bool) -> str:
    """Map auto/explicit preference to a concrete generator format."""
    if preferred == QR_FORMAT_AUTO:
        return QR_FORMAT_NEWGEN if new_gen_user else QR_FORMAT_LEGACY_MOBILE
    if preferred in (
        QR_FORMAT_NEWGEN,
        QR_FORMAT_LEGACY_MOBILE,
        QR_FORMAT_LEGACY_PLAIN,
    ):
        return preferred
    return QR_FORMAT_NEWGEN if new_gen_user else QR_FORMAT_LEGACY_MOBILE


def qr_payload(
    *,
    account_id: str,
    device_id: str | None,
    abc_barcode: str | None,
    new_gen_user: bool,
    qr_format: str = QR_FORMAT_AUTO,
    for_time: int | None = None,
) -> tuple[str, str]:
    """Return ``(payload, resolved_format)``."""
    resolved = resolve_format(qr_format, new_gen_user=new_gen_user)
    if for_time is None:
        for_time = int(time.time())

    if resolved == QR_FORMAT_NEWGEN:
        if not device_id:
            raise ValueError("NewGen QR requires device_id")
        return f"{account_id}:{totp_code(device_id, for_time=for_time)}", resolved

    barcode = (abc_barcode or "").strip()
    if not barcode:
        raise ValueError("Legacy QR requires abc_barcode (membership barcode)")

    if resolved == QR_FORMAT_LEGACY_PLAIN:
        return barcode, resolved

    # legacy_mobile — KeytagService.ExtendQrCodeIfNeeded(showSource=True) + timestamp
    return (
        f"{barcode}{LEGACY_CHANNEL_SUFFIX}/{legacy_timestamp(for_time)}",
        resolved,
    )


def seconds_remaining(resolved_format: str, for_time: int | None = None) -> int:
    if for_time is None:
        for_time = int(time.time())
    if resolved_format == QR_FORMAT_NEWGEN:
        return TOTP_STEP_SECONDS - (for_time % TOTP_STEP_SECONDS)
    # Legacy timestamp includes seconds — value changes every second
    return 1


def qr_png_bytes(payload: str, *, scale: int = 8) -> bytes:
    """Render payload as a PNG QR code."""
    qr = segno.make(payload, error="h")
    buf = io.BytesIO()
    qr.save(buf, kind="png", scale=scale, border=2)
    return buf.getvalue()

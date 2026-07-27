"""Coordinator for Black Card guests (list, unlock/lock, guest keytag QR).

The guest list is polled every few minutes; the QR payload is re-rendered on
every tick because the legacy keytag embeds a UTC timestamp.

A guest's barcode is only returned by the unlock endpoint, exactly like the
official app, which calls unlock whenever a guest row is opened.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from datetime import timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import PlanetFitnessApi, PlanetFitnessApiError, PlanetFitnessTokenExpired
from .const import (
    CONF_QR_FORMAT,
    DOMAIN,
    GUEST_POLL_SECONDS,
    GUEST_TICK_SECONDS,
    QR_FORMAT_LEGACY_MOBILE,
    QR_FORMAT_LEGACY_PLAIN,
)
from .totp_qr import qr_payload, qr_png_bytes

_LOGGER = logging.getLogger(__name__)


@dataclass
class Guest:
    """One Black Card guest and their (optional) keytag."""

    key: str
    user_id: str
    account_id: str | None
    first_name: str
    last_name: str
    unlocked: bool
    barcode: str | None = None
    payload: str | None = None
    resolved_format: str | None = None
    # Set after PF returns CannotLockAndUnlockPilotGuest (no revoke API).
    pilot_lock_blocked: bool = False
    png: bytes | None = field(default=None, repr=False)

    @property
    def full_name(self) -> str:
        name = f"{self.first_name} {self.last_name}".strip()
        return name or self.user_id

    @property
    def target_id(self) -> str:
        """The app posts accountId when present, else the pfx user id."""
        return self.account_id or self.user_id


def _guest_from_api(raw: dict[str, Any]) -> Guest | None:
    user_id = str(raw.get("userId") or "").strip()
    account_id = (str(raw.get("accountId")).strip() if raw.get("accountId") else None)
    key = user_id or account_id
    if not key:
        return None
    return Guest(
        key=key,
        user_id=user_id or key,
        account_id=account_id,
        first_name=str(raw.get("givenName") or "").strip(),
        last_name=str(raw.get("familyName") or "").strip(),
        unlocked=bool(raw.get("accessClub")),
    )


class PlanetFitnessGuestCoordinator(DataUpdateCoordinator[dict[str, Guest]]):
    """Keeps guest state and renders each unlocked guest's keytag QR."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        api: PlanetFitnessApi | None = None,
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_guests",
            update_interval=timedelta(seconds=GUEST_TICK_SECONDS),
        )
        self.entry = entry
        self.api = api or PlanetFitnessApi(hass, entry)
        self.supported = True
        self._guests: dict[str, Guest] = {}
        self._last_poll: float | None = None
        self._unsupported_logged = False

    @property
    def qr_format(self) -> str:
        """Guest keytags are always legacy barcodes; honour the plain override."""
        preferred = self.entry.options.get(
            CONF_QR_FORMAT, self.entry.data.get(CONF_QR_FORMAT)
        )
        if preferred == QR_FORMAT_LEGACY_PLAIN:
            return QR_FORMAT_LEGACY_PLAIN
        return QR_FORMAT_LEGACY_MOBILE

    def guest(self, key: str) -> Guest | None:
        return (self.data or {}).get(key)

    async def async_set_access(self, key: str, unlock: bool) -> None:
        """Unlock/lock a guest, caching the barcode the API hands back.

        Unified Club Pass pilot guests reject lock/unlock
        (``CannotLockAndUnlockPilotGuest``). Treat that as a no-op — PF keeps
        their club access as-is and there is no alternate disable API.
        """
        guest = self._guests.get(key)
        if guest is None:
            raise PlanetFitnessApiError(f"Unknown guest {key}")
        try:
            result = await self.api.async_set_guest_access(
                guest.target_id, unlock=unlock
            )
        except PlanetFitnessApiError as err:
            if err.is_pilot_guest_lock:
                _LOGGER.info(
                    "Planet Fitness does not allow %s for pilot guest %s; "
                    "leaving club access unchanged",
                    "unlock" if unlock else "lock",
                    guest.full_name,
                )
                guest.pilot_lock_blocked = True
                await self.async_request_refresh()
                return
            raise
        guest.unlocked = unlock
        guest.pilot_lock_blocked = False
        barcode = result.get("barcode") if isinstance(result, dict) else None
        if unlock and barcode:
            guest.barcode = str(barcode)
        elif not unlock:
            guest.barcode = None
        await self.async_request_refresh()

    async def async_poll_now(self) -> None:
        """Force the next tick to re-read the guest list."""
        self._last_poll = None
        await self.async_request_refresh()

    async def _async_update_data(self) -> dict[str, Guest]:
        if not self.supported:
            return {}

        now = time.monotonic()
        if self._last_poll is None or now - self._last_poll >= GUEST_POLL_SECONDS:
            await self._async_poll_guest_list()
            self._last_poll = now

        await self._async_render_keytags()
        return dict(self._guests)

    async def _async_poll_guest_list(self) -> None:
        try:
            raw_guests = await self.api.async_get_guests()
        except PlanetFitnessTokenExpired as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except PlanetFitnessApiError as err:
            if err.status in (403, 404):
                self.supported = False
                self._guests = {}
                if not self._unsupported_logged:
                    _LOGGER.info("Black Card guests unavailable for this account: %s", err)
                    self._unsupported_logged = True
                return
            raise UpdateFailed(str(err)) from err

        seen: dict[str, Guest] = {}
        for raw in raw_guests:
            guest = _guest_from_api(raw)
            if guest is None:
                continue
            existing = self._guests.get(guest.key)
            if existing is not None:
                # Keep the cached barcode/PNG so the QR survives a list refresh
                guest.barcode = existing.barcode
                guest.payload = existing.payload
                guest.resolved_format = existing.resolved_format
                guest.png = existing.png
                guest.pilot_lock_blocked = existing.pilot_lock_blocked
            if not guest.unlocked:
                guest.barcode = None
            seen[guest.key] = guest

        self._guests = seen
        await self._async_backfill_barcodes()

    async def _async_backfill_barcodes(self) -> None:
        """Fetch keytags for already-unlocked guests (the app does this on tap)."""
        for guest in self._guests.values():
            if not guest.unlocked or guest.barcode:
                continue
            try:
                result = await self.api.async_set_guest_access(
                    guest.target_id, unlock=True
                )
            except PlanetFitnessApiError as err:
                _LOGGER.debug("Could not load keytag for guest %s: %s", guest.key, err)
                continue
            barcode = result.get("barcode") if isinstance(result, dict) else None
            if barcode:
                guest.barcode = str(barcode)

    async def _async_render_keytags(self) -> None:
        now = int(time.time())
        for guest in self._guests.values():
            if not guest.barcode:
                guest.payload = None
                guest.resolved_format = None
                guest.png = None
                continue
            payload, resolved = qr_payload(
                account_id=guest.target_id,
                device_id=None,
                abc_barcode=guest.barcode,
                new_gen_user=False,
                qr_format=self.qr_format,
                for_time=now,
            )
            if payload != guest.payload or guest.png is None:
                guest.png = await self.hass.async_add_executor_job(qr_png_bytes, payload)
            guest.payload = payload
            guest.resolved_format = resolved

"""Coordinator — regenerates QR locally (no Planet Fitness API polling)."""

from __future__ import annotations

import logging
import time
from datetime import timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    ATTR_PAYLOAD,
    ATTR_QR_FORMAT,
    ATTR_RESOLVED_FORMAT,
    ATTR_SECONDS_REMAINING,
    CONF_ABC_BARCODE,
    CONF_ACCOUNT_ID,
    CONF_DEVICE_ID,
    CONF_EMAIL,
    CONF_NEW_GEN_USER,
    CONF_QR_FORMAT,
    DOMAIN,
    QR_FORMAT_AUTO,
    UPDATE_INTERVAL_SECONDS,
)
from .totp_qr import qr_payload, qr_png_bytes, seconds_remaining

_LOGGER = logging.getLogger(__name__)


class PlanetFitnessCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Holds account metadata and the current QR payload / PNG.

    After setup, updates are pure local math. Planet Fitness APIs are not called.
    """

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=UPDATE_INTERVAL_SECONDS),
        )
        self.entry = entry
        self._forced = False
        self._last_payload: str | None = None
        self._png: bytes | None = None

    @property
    def email(self) -> str:
        return self.entry.data[CONF_EMAIL]

    @property
    def account_id(self) -> str:
        return self.entry.data[CONF_ACCOUNT_ID]

    @property
    def device_id(self) -> str | None:
        return self.entry.data.get(CONF_DEVICE_ID)

    @property
    def abc_barcode(self) -> str | None:
        # Options override takes precedence (manual fix for older installs)
        opts = self.entry.options
        if opts.get(CONF_ABC_BARCODE):
            return opts[CONF_ABC_BARCODE]
        return self.entry.data.get(CONF_ABC_BARCODE)

    @property
    def new_gen_user(self) -> bool:
        if CONF_NEW_GEN_USER in self.entry.data:
            return bool(self.entry.data[CONF_NEW_GEN_USER])
        # Pre-1.1.0 entries only stored TOTP fields — keep NewGen behavior
        return True

    @property
    def qr_format(self) -> str:
        return self.entry.options.get(
            CONF_QR_FORMAT,
            self.entry.data.get(CONF_QR_FORMAT, QR_FORMAT_AUTO),
        )

    @property
    def png_image(self) -> bytes | None:
        return self._png

    def request_refresh_now(self) -> None:
        """Mark the next update as a forced refresh (e.g. button press)."""
        self._forced = True
        self._last_payload = None

    async def _async_update_data(self) -> dict[str, Any]:
        now = int(time.time())
        try:
            payload, resolved = qr_payload(
                account_id=self.account_id,
                device_id=self.device_id,
                abc_barcode=self.abc_barcode,
                new_gen_user=self.new_gen_user,
                qr_format=self.qr_format,
                for_time=now,
            )
        except ValueError as err:
            raise UpdateFailed(str(err)) from err

        remaining = seconds_remaining(resolved, for_time=now)

        if self._forced or self._last_payload != payload or self._png is None:
            self._png = await self.hass.async_add_executor_job(qr_png_bytes, payload)
            self._last_payload = payload
            self._forced = False
            _LOGGER.debug("Regenerated QR PNG (%s)", resolved)

        return {
            CONF_EMAIL: self.email,
            CONF_ACCOUNT_ID: self.account_id,
            CONF_DEVICE_ID: self.device_id,
            CONF_ABC_BARCODE: self.abc_barcode,
            ATTR_QR_FORMAT: self.qr_format,
            ATTR_RESOLVED_FORMAT: resolved,
            ATTR_PAYLOAD: payload,
            ATTR_SECONDS_REMAINING: remaining,
        }

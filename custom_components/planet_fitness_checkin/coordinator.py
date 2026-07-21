"""Coordinator — regenerates TOTP/QR locally (no Planet Fitness API polling)."""

from __future__ import annotations

import logging
import time
from datetime import timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import (
    ATTR_PAYLOAD,
    ATTR_SECONDS_REMAINING,
    CONF_ACCOUNT_ID,
    CONF_DEVICE_ID,
    CONF_EMAIL,
    DOMAIN,
    UPDATE_INTERVAL_SECONDS,
)
from .totp_qr import qr_payload, qr_png_bytes, seconds_remaining

_LOGGER = logging.getLogger(__name__)


class PlanetFitnessCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Holds account metadata and the current QR payload / PNG.

    After setup, updates are pure local math (TOTP). Press the Refresh button
    (or wait for the periodic tick) to rotate the payload/image. Planet Fitness
    APIs are not called during updates.
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
        self._last_window: int | None = None
        self._png: bytes | None = None

    @property
    def email(self) -> str:
        return self.entry.data[CONF_EMAIL]

    @property
    def account_id(self) -> str:
        return self.entry.data[CONF_ACCOUNT_ID]

    @property
    def device_id(self) -> str:
        return self.entry.data[CONF_DEVICE_ID]

    @property
    def png_image(self) -> bytes | None:
        return self._png

    def request_refresh_now(self) -> None:
        """Mark the next update as a forced refresh (e.g. button press)."""
        self._forced = True
        self._last_window = None

    async def _async_update_data(self) -> dict[str, Any]:
        now = int(time.time())
        window = now // 30
        payload = qr_payload(self.account_id, self.device_id, for_time=now)
        remaining = seconds_remaining(for_time=now)

        # Rebuild PNG when TOTP window changes or user forced a refresh
        if self._forced or self._last_window != window or self._png is None:
            self._png = await self.hass.async_add_executor_job(qr_png_bytes, payload)
            self._last_window = window
            self._forced = False
            _LOGGER.debug("Regenerated QR PNG for window %s", window)

        return {
            CONF_EMAIL: self.email,
            CONF_ACCOUNT_ID: self.account_id,
            CONF_DEVICE_ID: self.device_id,
            ATTR_PAYLOAD: payload,
            ATTR_SECONDS_REMAINING: remaining,
        }

"""Authenticated Planet Fitness mobile API client.

Endpoints mirror ``PF.Models.DTO.PFX.MobileService`` in the official app:

* ``GET  /black-card/guest``                 → ``BffBlackCardGuest[]``
* ``PUT  /black-card/guest/{userId}/unlock`` → ``{prospectId, userId, barcode}``
* ``PUT  /black-card/guest/{userId}/lock``   → same shape
* ``GET  /view/checkins?from&to&pfxMembershipId`` → ``{checkinCount, checkins}``
* ``GET  /user-details?``                    → profile (membership id backfill)

The unlock response is the only place a guest keytag barcode is exposed, which
is why the app calls it every time a guest row is tapped.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import date
from typing import Any
from urllib.parse import urlencode

import aiohttp
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
    API_BASE,
    API_USER_AGENT,
    AUTH_BASE,
    CLIENT_ID,
    CONF_ACCESS_TOKEN,
    CONF_REFRESH_TOKEN,
)

_LOGGER = logging.getLogger(__name__)


class PlanetFitnessApiError(Exception):
    """Non-auth API failure."""

    def __init__(self, message: str, status: int | None = None) -> None:
        super().__init__(message)
        self.status = status


class PlanetFitnessTokenExpired(PlanetFitnessApiError):
    """Stored tokens are gone or no longer accepted — reauth required."""


class PlanetFitnessApi:
    """Thin API wrapper that keeps the stored Auth0 tokens fresh."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self._hass = hass
        self._entry = entry
        self._session = async_get_clientsession(hass)
        self._refresh_lock = asyncio.Lock()

    @property
    def has_tokens(self) -> bool:
        """Entries created before tokens were persisted can't call the API."""
        return bool(self._entry.data.get(CONF_REFRESH_TOKEN)) or bool(
            self._entry.data.get(CONF_ACCESS_TOKEN)
        )

    async def async_get_guests(self) -> list[dict[str, Any]]:
        """Return the Black Card guest list."""
        data = await self._async_request("GET", "/black-card/guest")
        if isinstance(data, dict):
            data = data.get("result", data.get("guests", []))
        if not isinstance(data, list):
            raise PlanetFitnessApiError(f"Unexpected guest list payload: {type(data)}")
        return [guest for guest in data if isinstance(guest, dict)]

    async def async_set_guest_access(
        self, user_id: str, *, unlock: bool
    ) -> dict[str, Any]:
        """Unlock/lock a guest and return ``{prospectId, userId, barcode}``."""
        action = "unlock" if unlock else "lock"
        data = await self._async_request(
            "PUT", f"/black-card/guest/{user_id}/{action}", body=b""
        )
        if isinstance(data, dict):
            return data.get("result", data) if "result" in data else data
        return {}

    async def async_get_checkins(
        self,
        *,
        membership_id: str,
        from_date: date,
        to_date: date,
        prospect_id: str | None = None,
    ) -> dict[str, Any]:
        """Return ``{checkinCount, checkins:[{dateTime, clubName}, ...]}``."""
        params: dict[str, str] = {
            "from": from_date.isoformat(),
            "to": to_date.isoformat(),
            "pfxMembershipId": membership_id,
        }
        if prospect_id:
            params["pfxProspectId"] = prospect_id
        data = await self._async_request(
            "GET", f"/view/checkins?{urlencode(params)}"
        )
        if isinstance(data, dict):
            return data.get("result", data) if "result" in data else data
        raise PlanetFitnessApiError(f"Unexpected check-in payload: {type(data)}")

    async def async_get_user_details(self) -> dict[str, Any]:
        """Fetch ``/user-details`` (used to backfill membership id on older entries)."""
        data = await self._async_request("GET", "/user-details?")
        if isinstance(data, dict):
            return data.get("result", data) if "result" in data else data
        raise PlanetFitnessApiError(f"Unexpected profile payload: {type(data)}")

    async def _async_request(
        self, method: str, path: str, *, body: bytes | None = None, retry: bool = True
    ) -> Any:
        token = self._entry.data.get(CONF_ACCESS_TOKEN)
        if not token:
            token = await self._async_refresh_tokens()

        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/json, */*",
            "User-Agent": API_USER_AGENT,
        }
        if body is not None:
            # The app sends an empty body with Content-Type "*/*" on lock/unlock
            headers["Content-Type"] = "*/*"

        try:
            async with self._session.request(
                method, f"{API_BASE}{path}", headers=headers, data=body
            ) as resp:
                text = await resp.text()
                if resp.status == 401 and retry:
                    await self._async_refresh_tokens()
                    return await self._async_request(
                        method, path, body=body, retry=False
                    )
                if resp.status >= 400:
                    raise PlanetFitnessApiError(
                        f"{method} {path} failed ({resp.status}): {text[:200]}",
                        status=resp.status,
                    )
                if not text:
                    return None
                try:
                    return await resp.json(content_type=None)
                except (ValueError, aiohttp.ContentTypeError):
                    return text
        except (aiohttp.ClientError, TimeoutError, OSError) as err:
            raise PlanetFitnessApiError(f"{method} {path} network error: {err}") from err

    async def _async_refresh_tokens(self) -> str:
        """Exchange the refresh token for a new access token and persist both."""
        async with self._refresh_lock:
            refresh_token = self._entry.data.get(CONF_REFRESH_TOKEN)
            if not refresh_token:
                raise PlanetFitnessTokenExpired(
                    "No refresh token stored — re-add the integration to enable "
                    "guests and check-in history"
                )
            try:
                async with self._session.post(
                    f"{AUTH_BASE}/oauth/token",
                    data={
                        "grant_type": "refresh_token",
                        "client_id": CLIENT_ID,
                        "refresh_token": refresh_token,
                    },
                    headers={"Accept": "application/json"},
                ) as resp:
                    text = await resp.text()
                    if resp.status != 200:
                        raise PlanetFitnessTokenExpired(
                            f"Token refresh failed ({resp.status}): {text[:200]}"
                        )
                    payload = await resp.json(content_type=None)
            except (aiohttp.ClientError, TimeoutError, OSError) as err:
                raise PlanetFitnessApiError(
                    f"Token refresh network error: {err}"
                ) from err

            access_token = payload.get("access_token")
            if not access_token:
                raise PlanetFitnessTokenExpired("Token refresh returned no access_token")

            data = {**self._entry.data, CONF_ACCESS_TOKEN: access_token}
            # Auth0 rotates refresh tokens when rotation is enabled
            if payload.get("refresh_token"):
                data[CONF_REFRESH_TOKEN] = payload["refresh_token"]
            self._hass.config_entries.async_update_entry(self._entry, data=data)
            _LOGGER.debug("Refreshed Planet Fitness access token")
            return access_token

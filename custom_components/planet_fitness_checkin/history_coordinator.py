"""Coordinator for check-in history (My Journey / ``/view/checkins``)."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .api import PlanetFitnessApi, PlanetFitnessApiError, PlanetFitnessTokenExpired
from .const import (
    ATTR_CHECKINS,
    ATTR_LAST_CLUB,
    ATTR_WINDOW_DAYS,
    CHECKIN_ATTR_LIMIT,
    CHECKIN_HISTORY_DAYS,
    CHECKIN_POLL_SECONDS,
    CONF_PFX_MEMBERSHIP_ID,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


def _parse_checkin_dt(value: Any) -> datetime | None:
    """Parse a check-in ``dateTime`` from the PF My Journey API.

    The API returns ISO strings with a ``Z`` / ``+00:00`` suffix, but the
    wall-clock values match club-local time (e.g. ~20:00 weekday / ~17:00
    Sunday Eastern), not true UTC. Treating the suffix as real UTC shifts
    times by the local offset (wrong by 4–5 hours in EST/EDT).

    Strip any claimed offset and attach Home Assistant's configured timezone,
    then callers can ``as_utc`` for timestamp entities.
    """
    if value is None:
        return None
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str) and value:
        parsed = dt_util.parse_datetime(value)
        if parsed is None:
            return None
    else:
        return None

    if parsed.tzinfo is not None:
        parsed = parsed.replace(tzinfo=None)
    return dt_util.as_local(parsed)


def _extract_membership_id(profile: dict[str, Any]) -> str | None:
    memberships = profile.get("memberships")
    if isinstance(memberships, list):
        for membership in memberships:
            if not isinstance(membership, dict):
                continue
            for key, value in membership.items():
                if key.lower() == "pfxmembershipid" and value:
                    return str(value)
    for key in ("pfxMembershipId", "pfx_membership_id"):
        if profile.get(key):
            return str(profile[key])
    user = profile.get("user")
    if isinstance(user, dict):
        membership = user.get("membership")
        if isinstance(membership, dict) and membership.get("pfxMembershipId"):
            return str(membership["pfxMembershipId"])
    return None


class PlanetFitnessHistoryCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Polls check-in history for the member's digital membership."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        api: PlanetFitnessApi,
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_history",
            update_interval=timedelta(seconds=CHECKIN_POLL_SECONDS),
        )
        self.entry = entry
        self.api = api

    async def async_poll_now(self) -> None:
        await self.async_request_refresh()

    async def _async_update_data(self) -> dict[str, Any]:
        try:
            membership_id = await self._async_membership_id()
            if not membership_id:
                raise UpdateFailed(
                    "No pfxMembershipId on this account — check-in history unavailable"
                )
            today = dt_util.now().date()
            raw = await self.api.async_get_checkins(
                membership_id=membership_id,
                from_date=today - timedelta(days=CHECKIN_HISTORY_DAYS),
                to_date=today,
            )
        except PlanetFitnessTokenExpired as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except PlanetFitnessApiError as err:
            raise UpdateFailed(str(err)) from err

        checkins_raw = raw.get("checkins") or raw.get("Checkins") or []
        if not isinstance(checkins_raw, list):
            checkins_raw = []

        parsed: list[dict[str, Any]] = []
        for item in checkins_raw:
            if not isinstance(item, dict):
                continue
            when = _parse_checkin_dt(item.get("dateTime") or item.get("DateTime"))
            club = item.get("clubName") or item.get("ClubName") or None
            if when is None:
                continue
            parsed.append(
                {
                    "date_time": when.isoformat(),
                    "club_name": str(club) if club else None,
                    "_dt": when,
                }
            )

        parsed.sort(key=lambda row: row["_dt"], reverse=True)
        count = raw.get("checkinCount")
        if count is None:
            count = raw.get("CheckinCount")
        if count is None:
            count = len(parsed)
        else:
            try:
                count = int(count)
            except (TypeError, ValueError):
                count = len(parsed)

        last = parsed[0] if parsed else None
        recent = [
            {"date_time": row["date_time"], "club_name": row["club_name"]}
            for row in parsed[:CHECKIN_ATTR_LIMIT]
        ]

        return {
            "checkin_count": count,
            "last_checkin": last["_dt"] if last else None,
            ATTR_LAST_CLUB: last["club_name"] if last else None,
            ATTR_CHECKINS: recent,
            ATTR_WINDOW_DAYS: CHECKIN_HISTORY_DAYS,
        }

    async def _async_membership_id(self) -> str | None:
        existing = self.entry.data.get(CONF_PFX_MEMBERSHIP_ID)
        if existing:
            return str(existing)
        profile = await self.api.async_get_user_details()
        membership_id = _extract_membership_id(profile)
        if membership_id:
            data = {**self.entry.data, CONF_PFX_MEMBERSHIP_ID: membership_id}
            self.hass.config_entries.async_update_entry(self.entry, data=data)
            _LOGGER.info("Backfilled pfx_membership_id for check-in history")
        return membership_id

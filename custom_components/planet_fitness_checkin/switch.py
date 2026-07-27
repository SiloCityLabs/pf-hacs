"""Switch to unlock (approve) or lock a Black Card guest's club access."""

from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .api import PlanetFitnessApiError
from .const import ATTR_USER_ID, DOMAIN
from .coordinator import PlanetFitnessRuntime
from .entity import GuestEntity, async_track_guests
from .guest_coordinator import Guest


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    runtime: PlanetFitnessRuntime = hass.data[DOMAIN][entry.entry_id]
    if runtime.guests is None:
        return

    guests = runtime.guests
    entry.async_on_unload(
        async_track_guests(
            guests,
            async_add_entities,
            lambda guest: [PlanetFitnessGuestAccessSwitch(guests, entry, guest)],
        )
    )


class PlanetFitnessGuestAccessSwitch(GuestEntity, SwitchEntity):
    """On = guest is unlocked for club access."""

    _attr_translation_key = "guest_access"

    def __init__(self, coordinator, entry: ConfigEntry, guest: Guest) -> None:
        super().__init__(coordinator, entry, guest, "access")

    @property
    def is_on(self) -> bool | None:
        guest = self.guest
        return None if guest is None else guest.unlocked

    @property
    def icon(self) -> str:
        return "mdi:lock-open-variant" if self.is_on else "mdi:lock"

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        guest = self.guest
        if guest is None:
            return None
        attrs: dict[str, Any] = {ATTR_USER_ID: guest.user_id}
        if guest.pilot_lock_blocked:
            attrs["lock_supported"] = False
            attrs["note"] = (
                "Planet Fitness does not allow locking this guest "
                "(Unified Club Pass pilot)."
            )
        return attrs

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self._async_set(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self._async_set(False)

    async def _async_set(self, unlock: bool) -> None:
        try:
            await self.coordinator.async_set_access(self._guest_key, unlock)
        except PlanetFitnessApiError as err:
            raise HomeAssistantError(
                f"Planet Fitness guest update failed: {err}"
            ) from err
"""Planet Fitness Check-In Home Assistant integration."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .api import PlanetFitnessApi
from .const import DOMAIN
from .coordinator import PlanetFitnessCoordinator, PlanetFitnessRuntime
from .guest_coordinator import PlanetFitnessGuestCoordinator
from .history_coordinator import PlanetFitnessHistoryCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [
    Platform.SENSOR,
    Platform.IMAGE,
    Platform.BUTTON,
    Platform.SWITCH,
]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Planet Fitness Check-In from a config entry."""
    coordinator = PlanetFitnessCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()

    runtime = PlanetFitnessRuntime(coordinator=coordinator)
    api = PlanetFitnessApi(hass, entry)

    if api.has_tokens:
        guests = PlanetFitnessGuestCoordinator(hass, entry, api)
        history = PlanetFitnessHistoryCoordinator(hass, entry, api)
        runtime.guests = guests
        runtime.history = history
        # Guest / history failures must not take the keytag down
        try:
            await guests.async_refresh()
        except Exception as err:  # noqa: BLE001
            _LOGGER.warning("Black Card guests unavailable: %s", err)
        try:
            await history.async_refresh()
        except Exception as err:  # noqa: BLE001
            _LOGGER.warning("Check-in history unavailable: %s", err)
    else:
        _LOGGER.info(
            "No stored tokens for %s — re-add the integration to enable Black Card "
            "guests and check-in history",
            entry.title,
        )

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = runtime

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    return True


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload when options (QR format / barcode) change.

    Entry data also changes when a refreshed access token is stored, which must
    not trigger a reload.
    """
    runtime: PlanetFitnessRuntime | None = hass.data.get(DOMAIN, {}).get(entry.entry_id)
    if runtime is not None and runtime.coordinator.options_unchanged(entry):
        return
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)
    return unload_ok

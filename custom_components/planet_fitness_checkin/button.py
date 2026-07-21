"""Button to force-regenerate the QR (local only — no API call)."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER, MODEL
from .coordinator import PlanetFitnessCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: PlanetFitnessCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([PlanetFitnessRefreshButton(coordinator, entry)])


class PlanetFitnessRefreshButton(
    CoordinatorEntity[PlanetFitnessCoordinator], ButtonEntity
):
    """Force a QR / payload refresh without contacting Planet Fitness."""

    _attr_has_entity_name = True
    _attr_translation_key = "refresh_qr"
    _attr_icon = "mdi:qrcode-plus"

    def __init__(
        self, coordinator: PlanetFitnessCoordinator, entry: ConfigEntry
    ) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_refresh_qr"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": f"PF Check-In ({coordinator.email})",
            "manufacturer": MANUFACTURER,
            "model": MODEL,
        }

    async def async_press(self) -> None:
        self.coordinator.request_refresh_now()
        await self.coordinator.async_request_refresh()

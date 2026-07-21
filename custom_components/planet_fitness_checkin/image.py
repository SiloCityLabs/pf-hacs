"""Image entity exposing the check-in QR PNG for dashboards."""

from __future__ import annotations

from homeassistant.components.image import ImageEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from .const import ATTR_PAYLOAD, DOMAIN, MANUFACTURER, MODEL
from .coordinator import PlanetFitnessCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: PlanetFitnessCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([PlanetFitnessQrImage(hass, coordinator, entry)])


class PlanetFitnessQrImage(CoordinatorEntity[PlanetFitnessCoordinator], ImageEntity):
    """QR code image regenerated locally when the TOTP window changes."""

    _attr_has_entity_name = True
    _attr_translation_key = "qr_image"
    _attr_content_type = "image/png"

    def __init__(
        self,
        hass: HomeAssistant,
        coordinator: PlanetFitnessCoordinator,
        entry: ConfigEntry,
    ) -> None:
        CoordinatorEntity.__init__(self, coordinator)
        ImageEntity.__init__(self, hass)
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_qr_image"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": f"PF Check-In ({coordinator.email})",
            "manufacturer": MANUFACTURER,
            "model": MODEL,
        }
        self._attr_image_last_updated = dt_util.utcnow()

    @callback
    def _handle_coordinator_update(self) -> None:
        self._attr_image_last_updated = dt_util.utcnow()
        self.async_write_ha_state()

    async def async_image(self) -> bytes | None:
        """Return PNG bytes for the current QR payload."""
        return self.coordinator.png_image

    @property
    def extra_state_attributes(self):
        if not self.coordinator.data:
            return None
        return {
            ATTR_PAYLOAD: self.coordinator.data.get(ATTR_PAYLOAD),
        }

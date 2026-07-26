"""Image entities exposing the check-in and guest QR PNGs for dashboards."""

from __future__ import annotations

from homeassistant.components.image import ImageEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from .const import ATTR_PAYLOAD, DOMAIN
from .coordinator import PlanetFitnessCoordinator, PlanetFitnessRuntime
from .entity import GuestEntity, async_track_guests, keytag_device_info
from .guest_coordinator import Guest, PlanetFitnessGuestCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    runtime: PlanetFitnessRuntime = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([PlanetFitnessQrImage(hass, runtime.coordinator, entry)])

    if runtime.guests is None:
        return

    guests = runtime.guests
    entry.async_on_unload(
        async_track_guests(
            guests,
            async_add_entities,
            lambda guest: [PlanetFitnessGuestQrImage(hass, guests, entry, guest)],
        )
    )


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
        self._attr_device_info = keytag_device_info(entry, coordinator.email)
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


class PlanetFitnessGuestQrImage(GuestEntity, ImageEntity):
    """Guest keytag QR — only rendered while the guest is unlocked."""

    _attr_translation_key = "guest_qr_image"
    _attr_content_type = "image/png"

    def __init__(
        self,
        hass: HomeAssistant,
        coordinator: PlanetFitnessGuestCoordinator,
        entry: ConfigEntry,
        guest: Guest,
    ) -> None:
        GuestEntity.__init__(self, coordinator, entry, guest, "qr_image")
        ImageEntity.__init__(self, hass)
        self._attr_image_last_updated = dt_util.utcnow()

    @callback
    def _handle_coordinator_update(self) -> None:
        self._attr_image_last_updated = dt_util.utcnow()
        self.async_write_ha_state()

    @property
    def available(self) -> bool:
        guest = self.guest
        return super().available and guest is not None and guest.png is not None

    async def async_image(self) -> bytes | None:
        guest = self.guest
        return None if guest is None else guest.png

    @property
    def extra_state_attributes(self):
        guest = self.guest
        if guest is None:
            return None
        return {ATTR_PAYLOAD: guest.payload}

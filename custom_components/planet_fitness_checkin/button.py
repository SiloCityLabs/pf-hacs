"""Buttons: regenerate the QR, refresh guests, refresh check-in history."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import PlanetFitnessCoordinator, PlanetFitnessRuntime
from .entity import keytag_device_info
from .guest_coordinator import PlanetFitnessGuestCoordinator
from .history_coordinator import PlanetFitnessHistoryCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    runtime: PlanetFitnessRuntime = hass.data[DOMAIN][entry.entry_id]
    entities: list[ButtonEntity] = [
        PlanetFitnessRefreshButton(runtime.coordinator, entry)
    ]
    if runtime.guests is not None:
        entities.append(
            PlanetFitnessRefreshGuestsButton(
                runtime.guests, entry, runtime.coordinator.email
            )
        )
    if runtime.history is not None:
        entities.append(
            PlanetFitnessRefreshHistoryButton(
                runtime.history, entry, runtime.coordinator.email
            )
        )
    async_add_entities(entities)


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
        self._attr_device_info = keytag_device_info(entry, coordinator.email)

    async def async_press(self) -> None:
        self.coordinator.request_refresh_now()
        await self.coordinator.async_request_refresh()


class PlanetFitnessRefreshGuestsButton(
    CoordinatorEntity[PlanetFitnessGuestCoordinator], ButtonEntity
):
    """Re-read the Black Card guest list from the API."""

    _attr_has_entity_name = True
    _attr_translation_key = "refresh_guests"
    _attr_icon = "mdi:account-multiple-check"

    def __init__(
        self,
        coordinator: PlanetFitnessGuestCoordinator,
        entry: ConfigEntry,
        email: str,
    ) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_refresh_guests"
        self._attr_device_info = keytag_device_info(entry, email)

    async def async_press(self) -> None:
        await self.coordinator.async_poll_now()


class PlanetFitnessRefreshHistoryButton(
    CoordinatorEntity[PlanetFitnessHistoryCoordinator], ButtonEntity
):
    """Re-read check-in history from the API."""

    _attr_has_entity_name = True
    _attr_translation_key = "refresh_checkins"
    _attr_icon = "mdi:history"

    def __init__(
        self,
        coordinator: PlanetFitnessHistoryCoordinator,
        entry: ConfigEntry,
        email: str,
    ) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_refresh_checkins"
        self._attr_device_info = keytag_device_info(entry, email)

    async def async_press(self) -> None:
        await self.coordinator.async_poll_now()

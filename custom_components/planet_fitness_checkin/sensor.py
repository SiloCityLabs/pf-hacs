"""Sensors for email, account id, device id, and QR payload."""

from __future__ import annotations

from homeassistant.components.sensor import SensorEntity, SensorEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    ATTR_PAYLOAD,
    ATTR_SECONDS_REMAINING,
    CONF_ACCOUNT_ID,
    CONF_DEVICE_ID,
    CONF_EMAIL,
    DOMAIN,
    MANUFACTURER,
)
from .coordinator import PlanetFitnessCoordinator

SENSORS: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key=CONF_EMAIL,
        translation_key="email",
        icon="mdi:email",
    ),
    SensorEntityDescription(
        key=CONF_ACCOUNT_ID,
        translation_key="account_id",
        icon="mdi:card-account-details",
    ),
    SensorEntityDescription(
        key=CONF_DEVICE_ID,
        translation_key="device_id",
        icon="mdi:cellphone-key",
    ),
    SensorEntityDescription(
        key=ATTR_PAYLOAD,
        translation_key="qr_payload",
        icon="mdi:qrcode",
    ),
    SensorEntityDescription(
        key=ATTR_SECONDS_REMAINING,
        translation_key="seconds_remaining",
        icon="mdi:timer-sand",
        native_unit_of_measurement="s",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: PlanetFitnessCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        PlanetFitnessSensor(coordinator, entry, description) for description in SENSORS
    )


class PlanetFitnessSensor(CoordinatorEntity[PlanetFitnessCoordinator], SensorEntity):
    """One Planet Fitness check-in sensor."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: PlanetFitnessCoordinator,
        entry: ConfigEntry,
        description: SensorEntityDescription,
    ) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{entry.entry_id}_{description.key}"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": f"Planet Fitness ({coordinator.email})",
            "manufacturer": MANUFACTURER,
            "model": "Digital Keytag",
        }

    @property
    def native_value(self):
        if not self.coordinator.data:
            return None
        return self.coordinator.data.get(self.entity_description.key)

    @property
    def extra_state_attributes(self):
        if self.entity_description.key != ATTR_PAYLOAD or not self.coordinator.data:
            return None
        return {
            ATTR_SECONDS_REMAINING: self.coordinator.data.get(ATTR_SECONDS_REMAINING),
            CONF_ACCOUNT_ID: self.coordinator.account_id,
        }

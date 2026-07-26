"""Sensors for email, account id, device id, QR payload, guests, and history."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    ATTR_BARCODE,
    ATTR_CHECKINS,
    ATTR_GUESTS,
    ATTR_LAST_CLUB,
    ATTR_PAYLOAD,
    ATTR_QR_FORMAT,
    ATTR_RESOLVED_FORMAT,
    ATTR_SECONDS_REMAINING,
    ATTR_UNLOCKED_COUNT,
    ATTR_USER_ID,
    ATTR_WINDOW_DAYS,
    CONF_ABC_BARCODE,
    CONF_ACCOUNT_ID,
    CONF_DEVICE_ID,
    CONF_EMAIL,
    DOMAIN,
)
from .coordinator import PlanetFitnessCoordinator, PlanetFitnessRuntime
from .entity import GuestEntity, async_track_guests, keytag_device_info
from .guest_coordinator import Guest, PlanetFitnessGuestCoordinator
from .history_coordinator import PlanetFitnessHistoryCoordinator

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
        key=CONF_ABC_BARCODE,
        translation_key="abc_barcode",
        icon="mdi:barcode",
    ),
    SensorEntityDescription(
        key=ATTR_RESOLVED_FORMAT,
        translation_key="qr_format",
        icon="mdi:file-code-outline",
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
    runtime: PlanetFitnessRuntime = hass.data[DOMAIN][entry.entry_id]
    entities: list[SensorEntity] = [
        PlanetFitnessSensor(runtime.coordinator, entry, description)
        for description in SENSORS
    ]

    if runtime.guests is not None:
        guests = runtime.guests
        entities.append(
            PlanetFitnessGuestCountSensor(guests, entry, runtime.coordinator)
        )
        entry.async_on_unload(
            async_track_guests(
                guests,
                async_add_entities,
                lambda guest: [PlanetFitnessGuestPayloadSensor(guests, entry, guest)],
            )
        )

    if runtime.history is not None:
        history = runtime.history
        email = runtime.coordinator.email
        entities.extend(
            [
                PlanetFitnessCheckinCountSensor(history, entry, email),
                PlanetFitnessLastCheckinSensor(history, entry, email),
            ]
        )

    async_add_entities(entities)


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
        self._attr_device_info = keytag_device_info(entry, coordinator.email)

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
            ATTR_QR_FORMAT: self.coordinator.data.get(ATTR_QR_FORMAT),
            ATTR_RESOLVED_FORMAT: self.coordinator.data.get(ATTR_RESOLVED_FORMAT),
        }


class PlanetFitnessGuestCountSensor(
    CoordinatorEntity[PlanetFitnessGuestCoordinator], SensorEntity
):
    """How many Black Card guests are on the account."""

    _attr_has_entity_name = True
    _attr_translation_key = "guest_count"
    _attr_icon = "mdi:account-multiple"

    def __init__(
        self,
        coordinator: PlanetFitnessGuestCoordinator,
        entry: ConfigEntry,
        keytag_coordinator: PlanetFitnessCoordinator,
    ) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_guest_count"
        self._attr_device_info = keytag_device_info(entry, keytag_coordinator.email)

    @property
    def native_value(self) -> int:
        return len(self.coordinator.data or {})

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        guests = list((self.coordinator.data or {}).values())
        return {
            ATTR_UNLOCKED_COUNT: sum(1 for guest in guests if guest.unlocked),
            ATTR_GUESTS: [
                {"name": guest.full_name, "unlocked": guest.unlocked}
                for guest in guests
            ],
        }


class PlanetFitnessGuestPayloadSensor(GuestEntity, SensorEntity):
    """The guest keytag string encoded in their QR."""

    _attr_translation_key = "guest_payload"
    _attr_icon = "mdi:qrcode"

    def __init__(
        self,
        coordinator: PlanetFitnessGuestCoordinator,
        entry: ConfigEntry,
        guest: Guest,
    ) -> None:
        super().__init__(coordinator, entry, guest, "payload")

    @property
    def native_value(self) -> str | None:
        guest = self.guest
        return None if guest is None else guest.payload

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        guest = self.guest
        if guest is None:
            return None
        return {
            ATTR_BARCODE: guest.barcode,
            ATTR_RESOLVED_FORMAT: guest.resolved_format,
            ATTR_USER_ID: guest.user_id,
        }


class PlanetFitnessCheckinCountSensor(
    CoordinatorEntity[PlanetFitnessHistoryCoordinator], SensorEntity
):
    """Number of club check-ins in the rolling history window."""

    _attr_has_entity_name = True
    _attr_translation_key = "checkin_count"
    _attr_icon = "mdi:counter"
    _attr_state_class = SensorStateClass.TOTAL

    def __init__(
        self,
        coordinator: PlanetFitnessHistoryCoordinator,
        entry: ConfigEntry,
        email: str,
    ) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_checkin_count"
        self._attr_device_info = keytag_device_info(entry, email)

    @property
    def native_value(self) -> int | None:
        if not self.coordinator.data:
            return None
        return self.coordinator.data.get("checkin_count")

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        data = self.coordinator.data
        if not data:
            return None
        return {
            ATTR_WINDOW_DAYS: data.get(ATTR_WINDOW_DAYS),
            ATTR_CHECKINS: data.get(ATTR_CHECKINS),
        }


class PlanetFitnessLastCheckinSensor(
    CoordinatorEntity[PlanetFitnessHistoryCoordinator], SensorEntity
):
    """Timestamp of the most recent club check-in."""

    _attr_has_entity_name = True
    _attr_translation_key = "last_checkin"
    _attr_icon = "mdi:calendar-clock"
    _attr_device_class = SensorDeviceClass.TIMESTAMP

    def __init__(
        self,
        coordinator: PlanetFitnessHistoryCoordinator,
        entry: ConfigEntry,
        email: str,
    ) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_last_checkin"
        self._attr_device_info = keytag_device_info(entry, email)

    @property
    def native_value(self) -> datetime | None:
        if not self.coordinator.data:
            return None
        value = self.coordinator.data.get("last_checkin")
        return value if isinstance(value, datetime) else None

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        data = self.coordinator.data
        if not data:
            return None
        return {ATTR_LAST_CLUB: data.get(ATTR_LAST_CLUB)}

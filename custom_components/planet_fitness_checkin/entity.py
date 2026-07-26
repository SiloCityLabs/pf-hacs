"""Shared device info and dynamic guest-entity plumbing."""

from __future__ import annotations

from collections.abc import Callable, Iterable

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER
from .guest_coordinator import Guest, PlanetFitnessGuestCoordinator


def keytag_device_info(entry: ConfigEntry, email: str) -> DeviceInfo:
    """The member's own check-in device."""
    return DeviceInfo(
        identifiers={(DOMAIN, entry.entry_id)},
        name=f"Planet Fitness ({email})",
        manufacturer=MANUFACTURER,
        model="Digital Keytag",
    )


def guest_device_info(entry: ConfigEntry, guest: Guest) -> DeviceInfo:
    """One device per Black Card guest, linked to the member device."""
    return DeviceInfo(
        identifiers={(DOMAIN, f"{entry.entry_id}_guest_{guest.key}")},
        name=f"Planet Fitness Guest ({guest.full_name})",
        manufacturer=MANUFACTURER,
        model="Black Card Guest Pass",
        via_device=(DOMAIN, entry.entry_id),
    )


class GuestEntity(CoordinatorEntity[PlanetFitnessGuestCoordinator]):
    """Base entity bound to a single guest key."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: PlanetFitnessGuestCoordinator,
        entry: ConfigEntry,
        guest: Guest,
        suffix: str,
    ) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._guest_key = guest.key
        self._attr_unique_id = f"{entry.entry_id}_guest_{guest.key}_{suffix}"
        self._attr_device_info = guest_device_info(entry, guest)

    @property
    def guest(self) -> Guest | None:
        return self.coordinator.guest(self._guest_key)

    @property
    def available(self) -> bool:
        return super().available and self.guest is not None


@callback
def async_track_guests(
    coordinator: PlanetFitnessGuestCoordinator,
    async_add_entities: AddEntitiesCallback,
    factory: Callable[[Guest], Iterable[Entity]],
) -> Callable[[], None]:
    """Create entities for guests as they appear, including after setup."""
    known: set[str] = set()

    @callback
    def _sync() -> None:
        new_entities: list[Entity] = []
        for key, guest in (coordinator.data or {}).items():
            if key in known:
                continue
            known.add(key)
            new_entities.extend(factory(guest))
        if new_entities:
            async_add_entities(new_entities)

    _sync()
    return coordinator.async_add_listener(_sync)

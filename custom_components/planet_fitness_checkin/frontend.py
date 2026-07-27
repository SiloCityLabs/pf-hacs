"""Lovelace card assets + websocket helpers for the check-in picker card."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import voluptuous as vol
from homeassistant.components import websocket_api
from homeassistant.components.frontend import add_extra_js_url
from homeassistant.components.http import StaticPathConfig
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er

from .const import DOMAIN
from .manifest_version import VERSION

_LOGGER = logging.getLogger(__name__)

_FRONTEND_URL = f"/{DOMAIN}_static"
_CARD_PATH = f"{_FRONTEND_URL}/pf-checkin-card.js"
_CARD_JS = f"{_CARD_PATH}?v={VERSION}"
_STATIC_DIR = Path(__file__).parent / "www"

_FRONTEND_REGISTERED = f"{DOMAIN}_frontend_registered"


async def async_setup_frontend(hass: HomeAssistant) -> None:
    """Serve the card JS and register it as a Lovelace resource.

    ``add_extra_js_url`` alone races the dashboard on cold start / Companion
    app refresh ("Custom element doesn't exist"). Lovelace resources are what
    HACS cards use and load reliably before the view renders.
    """
    if hass.data.get(_FRONTEND_REGISTERED):
        # Still keep the resource URL cache-bust in sync on reload
        await _async_ensure_lovelace_resource(hass)
        return

    await hass.http.async_register_static_paths(
        [
            StaticPathConfig(_FRONTEND_URL, str(_STATIC_DIR), cache_headers=False),
        ]
    )
    # Keep as a fallback for YAML-mode / non-Lovelace panels
    add_extra_js_url(hass, _CARD_JS)
    await _async_ensure_lovelace_resource(hass)
    websocket_api.async_register_command(hass, websocket_list_people)
    hass.data[_FRONTEND_REGISTERED] = True
    _LOGGER.info("Registered Planet Fitness check-in card at %s", _CARD_JS)


async def _async_ensure_lovelace_resource(hass: HomeAssistant) -> None:
    """Idempotently register / update the dashboard resource entry."""
    try:
        lovelace = hass.data.get("lovelace")
        if lovelace is None:
            _LOGGER.debug("Lovelace not ready; skipping resource registration")
            return
        resources = getattr(lovelace, "resources", None)
        if resources is None and isinstance(lovelace, dict):
            resources = lovelace.get("resources")
        if resources is None:
            _LOGGER.debug("Lovelace resources API unavailable (YAML mode?)")
            return

        # Storage mode needs an explicit load before async_items works
        if hasattr(resources, "async_get_info"):
            await resources.async_get_info()
        elif hasattr(resources, "async_load") and not getattr(
            resources, "loaded", True
        ):
            await resources.async_load()

        items = list(resources.async_items()) if hasattr(resources, "async_items") else []
        existing = next(
            (item for item in items if _CARD_PATH in item.get("url", "")),
            None,
        )
        if existing is None:
            await resources.async_create_item({"res_type": "module", "url": _CARD_JS})
            _LOGGER.info("Added Lovelace resource %s", _CARD_JS)
            return

        if existing.get("url") != _CARD_JS:
            await resources.async_update_item(
                existing["id"], {"res_type": "module", "url": _CARD_JS}
            )
            _LOGGER.info("Updated Lovelace resource → %s", _CARD_JS)
    except Exception:  # noqa: BLE001
        _LOGGER.exception("Could not register Lovelace resource for check-in card")


@websocket_api.websocket_command(
    {
        vol.Required("type"): f"{DOMAIN}/people",
        vol.Required("entity_id"): str,
    }
)
@callback
def websocket_list_people(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Return member + guest QR targets for a member check-in image entity."""
    entity_id = msg["entity_id"]
    ent_reg = er.async_get(hass)
    entry = ent_reg.async_get(entity_id)
    if entry is None or entry.config_entry_id is None:
        connection.send_error(msg["id"], "not_found", f"Unknown entity {entity_id}")
        return

    config_entry_id = entry.config_entry_id
    runtime = hass.data.get(DOMAIN, {}).get(config_entry_id)
    member_name = "Me"
    if runtime is not None:
        member_name = runtime.coordinator.email.split("@")[0]

    # Collect every entity belonging to this config entry
    by_unique: dict[str, er.RegistryEntry] = {}
    for reg_entry in er.async_entries_for_config_entry(ent_reg, config_entry_id):
        if reg_entry.unique_id:
            by_unique[reg_entry.unique_id] = reg_entry

    member_qr = by_unique.get(f"{config_entry_id}_qr_image")
    if member_qr is None:
        # Fall back to the entity the card was configured with
        member_qr = entry

    people: list[dict[str, Any]] = [
        {
            "kind": "member",
            "name": member_name,
            "label": "My keytag",
            "qr_entity": member_qr.entity_id,
            "access_entity": None,
            "unlocked": True,
        }
    ]

    guests_runtime = runtime.guests if runtime is not None else None
    guest_map = (guests_runtime.data or {}) if guests_runtime is not None else {}

    # unique_id: {entry_id}_guest_{key}_access / _qr_image
    prefix = f"{config_entry_id}_guest_"
    guest_keys: set[str] = set()
    for unique_id in by_unique:
        if not unique_id.startswith(prefix):
            continue
        rest = unique_id[len(prefix) :]
        for suffix in ("_access", "_qr_image", "_payload"):
            if rest.endswith(suffix):
                guest_keys.add(rest[: -len(suffix)])
                break

    for key in sorted(
        guest_keys,
        key=lambda k: (guest_map[k].full_name.lower() if k in guest_map else k),
    ):
        access = by_unique.get(f"{prefix}{key}_access")
        qr = by_unique.get(f"{prefix}{key}_qr_image")
        guest = guest_map.get(key)
        name = guest.full_name if guest is not None else key
        unlocked = bool(guest.unlocked) if guest is not None else False
        if access is not None:
            state = hass.states.get(access.entity_id)
            if state is not None:
                unlocked = state.state == "on"
        people.append(
            {
                "kind": "guest",
                "name": name,
                "label": "Guest pass",
                "qr_entity": qr.entity_id if qr is not None else None,
                "access_entity": access.entity_id if access is not None else None,
                "unlocked": unlocked,
            }
        )

    # Device title for the dialog header
    title = "Planet Fitness"
    if entry.device_id:
        device = dr.async_get(hass).async_get(entry.device_id)
        if device is not None:
            title = device.name_by_user or device.name or title

    connection.send_result(
        msg["id"],
        {
            "title": title,
            "config_entry_id": config_entry_id,
            "people": people,
        },
    )

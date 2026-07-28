"""Lovelace card assets + websocket helpers for the check-in picker card."""

from __future__ import annotations

import logging
import shutil
from pathlib import Path
from typing import Any

import voluptuous as vol
from aiohttp import web
from homeassistant.components import websocket_api
from homeassistant.components.frontend import add_extra_js_url
from homeassistant.components.http import HomeAssistantView, StaticPathConfig
from homeassistant.const import EVENT_HOMEASSISTANT_STARTED
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er

from .const import DOMAIN
from .manifest_version import VERSION

_LOGGER = logging.getLogger(__name__)

# HACS serves www/community via /hacsfiles/ — most reliable on Companion.
_HACS_SLUG = "pf-checkin-card"
_HACSFILES_CARD_PATH = f"/hacsfiles/{_HACS_SLUG}/pf-checkin-card.js"
_HACSFILES_CARD_JS = f"{_HACSFILES_CARD_PATH}?v={VERSION}"

# Integration view: UTF-8 charset + no-cache (Companion-safe fallback).
_FRONTEND_URL = f"/{DOMAIN}_static"
_CARD_PATH = f"{_FRONTEND_URL}/pf-checkin-card.js"
_CARD_JS = f"{_CARD_PATH}?v={VERSION}"
_STATIC_DIR = Path(__file__).parent / "www"

# Also mirror under /local for direct access / non-HACS installs.
_LOCAL_DIR_NAME = "planet_fitness_checkin"
_LOCAL_CARD_PATH = f"/local/{_LOCAL_DIR_NAME}/pf-checkin-card.js"
_LOCAL_CARD_JS = f"{_LOCAL_CARD_PATH}?v={VERSION}"

_FRONTEND_REGISTERED = f"{DOMAIN}_frontend_registered"

# Prefer HACS endpoint, then no-cache view, then /local.
_PREFERRED_RESOURCES = (
    (_HACSFILES_CARD_PATH, _HACSFILES_CARD_JS),
    (_CARD_PATH, _CARD_JS),
    (_LOCAL_CARD_PATH, _LOCAL_CARD_JS),
)


class PfCheckinCardView(HomeAssistantView):
    """Serve the card JS with an explicit UTF-8 charset (Companion WebView safe)."""

    url = _CARD_PATH
    name = f"{DOMAIN}:card_js"
    requires_auth = False
    cors_allowed = True

    async def get(self, request: web.Request) -> web.Response:
        path = _STATIC_DIR / "pf-checkin-card.js"
        body = await request.app["hass"].async_add_executor_job(
            path.read_text, "utf-8"
        )
        return web.Response(
            text=body,
            content_type="text/javascript",
            charset="utf-8",
            headers={
                "Cache-Control": "no-cache, must-revalidate",
            },
        )


async def async_setup_frontend(hass: HomeAssistant) -> None:
    """Install card files and register Lovelace resources."""
    await _async_install_card_files(hass)
    await _async_ensure_lovelace_resource(hass)

    if hass.data.get(_FRONTEND_REGISTERED):
        return

    await hass.http.async_register_static_paths(
        [
            StaticPathConfig(
                f"{_FRONTEND_URL}/assets",
                str(_STATIC_DIR / "assets"),
                cache_headers=False,
            ),
        ]
    )
    hass.http.register_view(PfCheckinCardView)

    # Extra modules load with the frontend shell (helps Companion races).
    add_extra_js_url(hass, _HACSFILES_CARD_JS)
    add_extra_js_url(hass, _CARD_JS)
    websocket_api.async_register_command(hass, websocket_list_people)

    async def _on_started(_event: Any) -> None:
        await _async_install_card_files(hass)
        await _async_ensure_lovelace_resource(hass)

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STARTED, _on_started)
    hass.data[_FRONTEND_REGISTERED] = True
    _LOGGER.info(
        "Registered Planet Fitness check-in card at %s (fallback %s)",
        _HACSFILES_CARD_JS,
        _CARD_JS,
    )


async def _async_install_card_files(hass: HomeAssistant) -> None:
    """Copy card + icon into www/community (hacsfiles) and www/local mirror."""

    def _copy() -> None:
        src_js = _STATIC_DIR / "pf-checkin-card.js"
        src_assets = _STATIC_DIR / "assets"
        body = src_js.read_text(encoding="utf-8")

        targets = [
            Path(hass.config.path("www")) / "community" / _HACS_SLUG,
            Path(hass.config.path("www")) / _LOCAL_DIR_NAME,
        ]
        for dest in targets:
            dest.mkdir(parents=True, exist_ok=True)
            (dest / "pf-checkin-card.js").write_text(body, encoding="utf-8")
            if src_assets.is_dir():
                dest_assets = dest / "assets"
                dest_assets.mkdir(exist_ok=True)
                for file in src_assets.iterdir():
                    if file.is_file():
                        shutil.copy2(file, dest_assets / file.name)

    await hass.async_add_executor_job(_copy)


async def _async_ensure_lovelace_resource(hass: HomeAssistant) -> None:
    """Keep a single Lovelace module resource on the preferred URL."""
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

        if hasattr(resources, "async_get_info"):
            await resources.async_get_info()
        elif hasattr(resources, "async_load") and not getattr(
            resources, "loaded", True
        ):
            await resources.async_load()

        items = (
            list(resources.async_items()) if hasattr(resources, "async_items") else []
        )

        preferred_path, preferred_url = _PREFERRED_RESOURCES[0]
        related = [
            item
            for item in items
            if any(path in item.get("url", "") for path, _ in _PREFERRED_RESOURCES)
        ]

        if not related:
            await resources.async_create_item(
                {"res_type": "module", "url": preferred_url}
            )
            _LOGGER.info("Added Lovelace resource %s", preferred_url)
            return

        primary = related[0]
        if preferred_path not in primary.get("url", "") or primary.get(
            "url"
        ) != preferred_url:
            await resources.async_update_item(
                primary["id"], {"res_type": "module", "url": preferred_url}
            )
            _LOGGER.info("Updated Lovelace resource -> %s", preferred_url)

        for extra in related[1:]:
            await resources.async_delete_item(extra["id"])
            _LOGGER.info("Removed duplicate Lovelace resource %s", extra.get("url"))
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

    by_unique: dict[str, er.RegistryEntry] = {}
    for reg_entry in er.async_entries_for_config_entry(ent_reg, config_entry_id):
        if reg_entry.unique_id:
            by_unique[reg_entry.unique_id] = reg_entry

    member_qr = by_unique.get(f"{config_entry_id}_qr_image")
    if member_qr is None:
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

"""Config flow: email → wait for emailed code → store account/device ids.

Options: select QR format (auto / NewGen TOTP / legacy mobile / legacy plain)
and optionally override the legacy AbcBarcode.
"""

from __future__ import annotations

import logging
from typing import Any

import aiohttp
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
import homeassistant.helpers.config_validation as cv

from .auth import (
    AuthSession,
    PlanetFitnessAuthError,
    close_auth_session,
    complete_email_login,
    start_email_login,
)
from .const import (
    CONF_ABC_BARCODE,
    CONF_ACCESS_TOKEN,
    CONF_ACCOUNT_ID,
    CONF_DEVICE_ID,
    CONF_EMAIL,
    CONF_NEW_GEN_USER,
    CONF_QR_FORMAT,
    CONF_REFRESH_TOKEN,
    DOMAIN,
    QR_FORMAT_AUTO,
    QR_FORMATS,
)

_LOGGER = logging.getLogger(__name__)

STEP_USER = vol.Schema({vol.Required(CONF_EMAIL): cv.string})
STEP_CODE = vol.Schema({vol.Required("code"): cv.string})

QR_FORMAT_LABELS = {
    QR_FORMAT_AUTO: "Auto (detect from NewGenUser flag)",
    "newgen_totp": "NewGen — {AccountId}:{TOTP}",
    "legacy_mobile": "Legacy — {AbcBarcode}/mobile/{timestamp}",
    "legacy_plain": "Legacy — {AbcBarcode} only",
}


class PlanetFitnessCheckinConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Planet Fitness Check-In."""

    VERSION = 1

    def __init__(self) -> None:
        self._email: str | None = None
        self._auth: AuthSession | None = None

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: config_entries.ConfigEntry):
        return PlanetFitnessOptionsFlow()

    async def async_step_user(self, user_input: dict[str, Any] | None = None):
        """Ask for membership email and trigger Auth0 email code."""
        errors: dict[str, str] = {}

        if user_input is not None:
            email = user_input[CONF_EMAIL].strip().lower()
            await close_auth_session(self._auth)
            self._auth = None
            try:
                self._auth = await start_email_login(email)
                self._email = email
            except PlanetFitnessAuthError as err:
                _LOGGER.warning("Login start failed: %s", err)
                errors["base"] = err.code
            except (aiohttp.ClientError, TimeoutError, OSError) as err:
                _LOGGER.warning("Network error starting login: %s", err)
                errors["base"] = "cannot_connect"
            else:
                return await self.async_step_code()

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER,
            errors=errors,
            description_placeholders={
                "help": "Use the same email as the Planet Fitness mobile app."
            },
        )

    async def async_step_code(self, user_input: dict[str, Any] | None = None):
        """Wait for the emailed 6-digit code, then finish setup."""
        errors: dict[str, str] = {}

        if user_input is not None and self._auth is not None and self._email is not None:
            auth = self._auth
            self._auth = None  # complete_email_login closes the session
            try:
                result = await complete_email_login(auth, user_input["code"])
            except PlanetFitnessAuthError as err:
                _LOGGER.warning("Login complete failed: %s", err)
                errors["base"] = err.code
                try:
                    self._auth = await start_email_login(self._email)
                except Exception as start_err:  # noqa: BLE001
                    _LOGGER.warning("Could not restart login challenge: %s", start_err)
                    self._auth = None
            except (aiohttp.ClientError, TimeoutError, OSError) as err:
                _LOGGER.warning("Network error completing login: %s", err)
                errors["base"] = "cannot_connect"
                try:
                    self._auth = await start_email_login(self._email)
                except Exception:  # noqa: BLE001
                    self._auth = None
            else:
                await self.async_set_unique_id(result.account_id.lower())
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=f"Planet Fitness ({result.email})",
                    data={
                        CONF_EMAIL: result.email,
                        CONF_ACCOUNT_ID: result.account_id,
                        CONF_DEVICE_ID: result.device_id,
                        CONF_ABC_BARCODE: result.abc_barcode,
                        CONF_NEW_GEN_USER: result.new_gen_user,
                        CONF_QR_FORMAT: QR_FORMAT_AUTO,
                        CONF_ACCESS_TOKEN: result.access_token,
                        CONF_REFRESH_TOKEN: result.refresh_token,
                    },
                )

        if self._auth is None and self._email is not None and not errors:
            return await self.async_step_user({CONF_EMAIL: self._email})

        return self.async_show_form(
            step_id="code",
            data_schema=STEP_CODE,
            errors=errors,
            description_placeholders={"email": self._email or ""},
        )

    async def async_step_reauth(self, entry_data: dict[str, Any]):
        """Re-authenticate with a fresh email code."""
        self._email = entry_data.get(CONF_EMAIL)
        return await self.async_step_user(
            {CONF_EMAIL: self._email} if self._email else None
        )


class PlanetFitnessOptionsFlow(config_entries.OptionsFlow):
    """Configure QR format and optional legacy barcode override."""

    async def async_step_init(self, user_input: dict[str, Any] | None = None):
        entry = self.config_entry
        if user_input is not None:
            data = {
                CONF_QR_FORMAT: user_input[CONF_QR_FORMAT],
            }
            barcode = (user_input.get(CONF_ABC_BARCODE) or "").strip()
            if barcode:
                data[CONF_ABC_BARCODE] = barcode
            return self.async_create_entry(title="", data=data)

        current_format = entry.options.get(
            CONF_QR_FORMAT,
            entry.data.get(CONF_QR_FORMAT, QR_FORMAT_AUTO),
        )
        current_barcode = entry.options.get(
            CONF_ABC_BARCODE,
            entry.data.get(CONF_ABC_BARCODE) or "",
        )
        detected = (
            "NewGen (TOTP)"
            if entry.data.get(CONF_NEW_GEN_USER)
            else "Legacy (AbcBarcode)"
        )

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_QR_FORMAT, default=current_format): vol.In(
                        {fmt: QR_FORMAT_LABELS[fmt] for fmt in QR_FORMATS}
                    ),
                    vol.Optional(CONF_ABC_BARCODE, default=current_barcode): cv.string,
                }
            ),
            description_placeholders={"detected": detected},
        )

"""Configuration flow and option editing for the ZTE router."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.config_entries import ConfigFlowResult, OptionsFlowWithReload
from homeassistant.const import CONF_HOST, CONF_PASSWORD
from homeassistant.core import callback

from .api import ZTEAuthError, ZTEConnectionError, ZTEError, ZTERouterClient
from .const import (
    CONF_AWAY_SECONDS,
    CONF_TRACKED_DEVICES,
    DEFAULT_AWAY_SECONDS,
    DEFAULT_HOST,
    DOMAIN,
    parse_tracked_devices,
    safe_host,
)

_LOGGER = logging.getLogger(__name__)


class ZTEPresenceConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Set up one ZTE router using the password-only LOGIN endpoint."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Validate the credentials by reading the device list once."""
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                host = safe_host(user_input[CONF_HOST])
                client = ZTERouterClient(host, user_input[CONF_PASSWORD])
                try:
                    await client.async_get_clients()
                finally:
                    await client.async_close()
            except ValueError:
                errors["base"] = "invalid_host"
            except ZTEAuthError:
                errors["base"] = "invalid_auth"
            except ZTEError:
                errors["base"] = "cannot_connect"
            else:
                await self.async_set_unique_id(f"zte_mc888a_{host}")
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=f"ZTE MC888A Ultra ({host})",
                    data={CONF_HOST: host, CONF_PASSWORD: user_input[CONF_PASSWORD]},
                )

        schema = vol.Schema(
            {
                vol.Required(CONF_HOST, default=DEFAULT_HOST): str,
                vol.Required(CONF_PASSWORD): str,
            }
        )
        return self.async_show_form(
            step_id="user", data_schema=schema, errors=errors
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Create the options flow."""
        return ZTEPresenceOptionsFlow()


class ZTEPresenceOptionsFlow(OptionsFlowWithReload):
    """Allow selecting trusted phones and the away debounce."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Change tracked MACs without touching router credentials."""
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                parsed = parse_tracked_devices(
                    user_input.get(CONF_TRACKED_DEVICES, "")
                )
            except ValueError:
                errors["base"] = "invalid_macs"
            else:
                if not parsed:
                    errors["base"] = "no_devices"
                else:
                    return self.async_create_entry(title="", data=user_input)

        default_options = self.config_entry.options
        schema = vol.Schema(
            {
                vol.Optional(
                    CONF_TRACKED_DEVICES,
                    default=default_options.get(CONF_TRACKED_DEVICES, ""),
                ): str,
                vol.Optional(
                    CONF_AWAY_SECONDS,
                    default=default_options.get(
                        CONF_AWAY_SECONDS, DEFAULT_AWAY_SECONDS
                    ),
                ): vol.All(vol.Coerce(int), vol.Range(min=60, max=3600)),
            }
        )

        available = []
        coordinator = getattr(self.config_entry, "runtime_data", None)
        if coordinator is not None and coordinator.data:
            available = [
                f"{device.mac} | {device.ip or '-'} | "
                f"{device.hostname or '-'}"
                for device in coordinator.data.values()
            ]
        return self.async_show_form(
            step_id="init",
            data_schema=schema,
            errors=errors,
            description_placeholders={
                "detected_clients": "\n".join(sorted(available)) or "None available",
            },
        )

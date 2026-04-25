from __future__ import annotations

from datetime import UTC, datetime

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult

from .const import (
    CONF_CSRF_TOKEN,
    CONF_MAX_RECORDS,
    CONF_PASSWORD,
    CONF_SCAN_INTERVAL,
    CONF_USERNAME,
    DEFAULT_MAX_RECORDS,
    DEFAULT_SCAN_INTERVAL_MINUTES,
    DEFAULT_TITLE,
    DOMAIN,
    MIN_SCAN_INTERVAL_MINUTES,
)
from .movemove_client import MoveMoveClient, MoveMoveCredentials, MoveMoveError


class MoveMoveConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input: dict | None = None) -> FlowResult:
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                await self.hass.async_add_executor_job(self._validate_input, user_input)
            except MoveMoveError as err:
                if "Invalid Login" in str(err):
                    errors["base"] = "invalid_auth"
                else:
                    errors["base"] = "cannot_connect"
            except Exception:
                errors["base"] = "unknown"
            else:
                await self.async_set_unique_id(user_input[CONF_USERNAME])
                self._abort_if_unique_id_configured()
                return self.async_create_entry(title=DEFAULT_TITLE, data=user_input)

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_USERNAME): str,
                    vol.Required(CONF_PASSWORD): str,
                    vol.Optional(CONF_CSRF_TOKEN, description={"suggested_value": ""}): str,
                    vol.Optional(CONF_MAX_RECORDS, default=DEFAULT_MAX_RECORDS): vol.All(vol.Coerce(int), vol.Range(min=1, max=500)),
                    vol.Optional(CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL_MINUTES): vol.All(vol.Coerce(int), vol.Range(min=MIN_SCAN_INTERVAL_MINUTES, max=1440)),
                }
            ),
            errors=errors,
        )

    def _validate_input(self, user_input: dict) -> None:
        now = datetime.now(UTC)
        client = MoveMoveClient(
            MoveMoveCredentials(
                username=user_input[CONF_USERNAME],
                password=user_input[CONF_PASSWORD],
                csrf_token=user_input.get(CONF_CSRF_TOKEN),
            )
        )
        client.login()
        client.fetch_month_data(now.year, now.month, max_records=user_input.get(CONF_MAX_RECORDS, DEFAULT_MAX_RECORDS))

    @staticmethod
    def async_get_options_flow(config_entry: config_entries.ConfigEntry):
        return MoveMoveOptionsFlowHandler(config_entry)


class MoveMoveOptionsFlowHandler(config_entries.OptionsFlow):
    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        self.config_entry = config_entry

    async def async_step_init(self, user_input: dict | None = None) -> FlowResult:
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_MAX_RECORDS,
                        default=self.config_entry.options.get(
                            CONF_MAX_RECORDS,
                            self.config_entry.data.get(CONF_MAX_RECORDS, DEFAULT_MAX_RECORDS),
                        ),
                    ): vol.All(vol.Coerce(int), vol.Range(min=1, max=500)),
                    vol.Optional(
                        CONF_SCAN_INTERVAL,
                        default=self.config_entry.options.get(
                            CONF_SCAN_INTERVAL,
                            self.config_entry.data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL_MINUTES),
                        ),
                    ): vol.All(vol.Coerce(int), vol.Range(min=MIN_SCAN_INTERVAL_MINUTES, max=1440)),
                }
            ),
        )

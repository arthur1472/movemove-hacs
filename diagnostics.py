from __future__ import annotations

from copy import deepcopy

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import CONF_CSRF_TOKEN, CONF_PASSWORD, CONF_USERNAME, DOMAIN

TO_REDACT = {CONF_USERNAME, CONF_PASSWORD, CONF_CSRF_TOKEN, "cardNumber", "licensePlate"}


async def async_get_config_entry_diagnostics(hass: HomeAssistant, entry: ConfigEntry) -> dict:
    coordinator = hass.data[DOMAIN][entry.entry_id]
    payload = {
        "entry": dict(entry.data),
        "options": dict(entry.options),
        "data": deepcopy(coordinator.data),
    }
    return async_redact_data(payload, TO_REDACT)

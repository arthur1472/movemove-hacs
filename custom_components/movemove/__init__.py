from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, ServiceCall

from .const import CONF_CSRF_TOKEN, CONF_MAX_RECORDS, CONF_SCAN_INTERVAL, DOMAIN, PLATFORMS
from .coordinator import MoveMoveDataUpdateCoordinator


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    async def handle_refresh(call: ServiceCall) -> None:
        for coordinator in hass.data.get(DOMAIN, {}).values():
            await coordinator.async_request_refresh()

    hass.services.async_register(DOMAIN, "refresh", handle_refresh)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    coordinator = MoveMoveDataUpdateCoordinator(
        hass,
        entry_id=entry.entry_id,
        username=entry.data["username"],
        password=entry.data["password"],
        csrf_token=entry.data.get(CONF_CSRF_TOKEN),
        max_records=entry.options.get(CONF_MAX_RECORDS, entry.data.get(CONF_MAX_RECORDS, 100)),
        scan_interval_minutes=entry.options.get(CONF_SCAN_INTERVAL, entry.data.get(CONF_SCAN_INTERVAL, 360)),
    )
    await coordinator.async_initialize()
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    await coordinator.async_config_entry_first_refresh()

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)
    return unload_ok

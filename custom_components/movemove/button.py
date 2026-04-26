from __future__ import annotations

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import MoveMoveDataUpdateCoordinator


REFRESH_BUTTON = ButtonEntityDescription(
    key="refresh_data",
    translation_key="refresh_data",
    name="Refresh data",
    icon="mdi:refresh",
    entity_category=EntityCategory.DIAGNOSTIC,
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: MoveMoveDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([MoveMoveRefreshButton(coordinator, entry)])


class MoveMoveRefreshButton(CoordinatorEntity[MoveMoveDataUpdateCoordinator], ButtonEntity):
    entity_description = REFRESH_BUTTON

    def __init__(self, coordinator: MoveMoveDataUpdateCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_{REFRESH_BUTTON.key}"
        self._attr_has_entity_name = True
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name="MoveMove",
            manufacturer="MoveMove",
            model="OnTheMove API",
            configuration_url="https://outsystems.mtc.nl/OnTheMove/",
        )

    async def async_press(self) -> None:
        await self.coordinator.async_request_refresh()

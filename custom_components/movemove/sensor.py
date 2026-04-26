from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import SensorEntity, SensorEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CURRENCY_EURO, EntityCategory, UnitOfVolume
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import ATTR_CURRENT_PERIOD, ATTR_DIAGNOSTICS, ATTR_LATEST_TRANSACTION, ATTR_SUMMARY, ATTR_TRANSACTIONS, DOMAIN
from .coordinator import MoveMoveDataUpdateCoordinator


@dataclass(frozen=True, kw_only=True)
class MoveMoveSensorDescription(SensorEntityDescription):
    value_key: str


SENSORS: tuple[MoveMoveSensorDescription, ...] = (
    MoveMoveSensorDescription(
        key="last_fuel_distance_since_previous",
        translation_key="last_fuel_distance_since_previous",
        name="MoveMove kilometers since last refuel",
        native_unit_of_measurement="km",
        value_key="last_fuel_distance_since_previous",
        icon="mdi:map-marker-distance",
    ),
    MoveMoveSensorDescription(
        key="last_fuel_location",
        translation_key="last_fuel_location",
        name="MoveMove last refuel location",
        value_key="last_fuel_location",
        icon="mdi:map-marker",
    ),
    MoveMoveSensorDescription(
        key="last_fuel_liters_per_100km",
        translation_key="last_fuel_liters_per_100km",
        name="MoveMove last refuel liters per 100km",
        native_unit_of_measurement="L/100km",
        value_key="last_fuel_liters_per_100km",
        icon="mdi:car-speed-limiter",
    ),
    MoveMoveSensorDescription(
        key="last_fresh_update_age_minutes",
        translation_key="last_fresh_update_age_minutes",
        name="MoveMove last fresh update age",
        native_unit_of_measurement="min",
        value_key="last_fresh_update_age_minutes",
        icon="mdi:timer-outline",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    MoveMoveSensorDescription(
        key="latest_transaction_amount",
        translation_key="latest_transaction_amount",
        name="MoveMove latest transaction amount",
        native_unit_of_measurement=CURRENCY_EURO,
        value_key="latest_transaction_amount",
        icon="mdi:cash-fast",
    ),
    MoveMoveSensorDescription(
        key="latest_transaction_liters",
        translation_key="latest_transaction_liters",
        name="MoveMove latest transaction liters",
        native_unit_of_measurement=UnitOfVolume.LITERS,
        value_key="latest_transaction_liters",
        icon="mdi:fuel",
    ),
    MoveMoveSensorDescription(
        key="total_amount",
        translation_key="total_amount",
        name="MoveMove total amount",
        native_unit_of_measurement=CURRENCY_EURO,
        value_key="totalAmountEur",
        icon="mdi:currency-eur",
    ),
    MoveMoveSensorDescription(
        key="fuel_amount",
        translation_key="fuel_amount",
        name="MoveMove fuel amount",
        native_unit_of_measurement=CURRENCY_EURO,
        value_key="fuelAmountEur",
        icon="mdi:gas-station",
    ),
    MoveMoveSensorDescription(
        key="fuel_liters",
        translation_key="fuel_liters",
        name="MoveMove fuel liters",
        native_unit_of_measurement=UnitOfVolume.LITERS,
        value_key="fuelLiters",
        icon="mdi:fuel",
    ),
    MoveMoveSensorDescription(
        key="average_liters_per_100km",
        translation_key="average_liters_per_100km",
        name="MoveMove average liters per 100km",
        native_unit_of_measurement="L/100km",
        value_key="averageLitersPer100Km",
        icon="mdi:car-speed-limiter",
    ),
    MoveMoveSensorDescription(
        key="transaction_count",
        translation_key="transaction_count",
        name="MoveMove transaction count",
        value_key="transactionCount",
        icon="mdi:format-list-numbered",
    ),
    MoveMoveSensorDescription(
        key="fuel_transaction_count",
        translation_key="fuel_transaction_count",
        name="MoveMove fuel transaction count",
        value_key="fuelTransactionCount",
        icon="mdi:counter",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: MoveMoveDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(MoveMoveSensor(coordinator, entry, description) for description in SENSORS)


class MoveMoveSensor(CoordinatorEntity[MoveMoveDataUpdateCoordinator], SensorEntity):
    entity_description: MoveMoveSensorDescription

    def __init__(
        self,
        coordinator: MoveMoveDataUpdateCoordinator,
        entry: ConfigEntry,
        description: MoveMoveSensorDescription,
    ) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{entry.entry_id}_{description.key}"
        self._attr_has_entity_name = True
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name="MoveMove",
            manufacturer="MoveMove",
            model="OnTheMove API",
            configuration_url="https://outsystems.mtc.nl/OnTheMove/",
        )

    @property
    def native_value(self) -> Any:
        latest_fuel = self.coordinator.data.get("latestFuelTransaction") or {}
        if self.entity_description.value_key == "latest_transaction_amount":
            latest = self.coordinator.data.get("latestTransaction") or {}
            return latest.get("amountEur")
        if self.entity_description.value_key == "latest_transaction_liters":
            latest = self.coordinator.data.get("latestTransaction") or {}
            return latest.get("liters")
        if self.entity_description.value_key == "last_fuel_distance_since_previous":
            return latest_fuel.get("distanceSincePreviousFuelKm")
        if self.entity_description.value_key == "last_fuel_location":
            return latest_fuel.get("location")
        if self.entity_description.value_key == "last_fuel_liters_per_100km":
            return latest_fuel.get("litersPer100Km")
        if self.entity_description.value_key == "last_fresh_update_age_minutes":
            return self.coordinator.data.get("diagnostics", {}).get("lastSuccessfulUpdateAgeMinutes")
        return self.coordinator.data.get("summary", {}).get(self.entity_description.value_key)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        attrs = {
            ATTR_SUMMARY: self.coordinator.data.get("summary", {}),
            ATTR_CURRENT_PERIOD: self.coordinator.data.get("currentPeriod", {}),
            ATTR_LATEST_TRANSACTION: self.coordinator.data.get("latestTransaction"),
            "latest_fuel_transaction": self.coordinator.data.get("latestFuelTransaction"),
            ATTR_DIAGNOSTICS: self.coordinator.data.get("diagnostics", {}),
        }
        latest = self.coordinator.data.get("latestTransaction") or {}
        if self.entity_description.key in {"latest_transaction_amount", "latest_transaction_liters"}:
            attrs.update(
                {
                    "latest_transaction_date": latest.get("date"),
                    "latest_transaction_type": latest.get("type"),
                    "latest_transaction_location": latest.get("location"),
                    "latest_transaction_product": latest.get("product"),
                }
            )
        if self.entity_description.key == "transaction_count":
            attrs[ATTR_TRANSACTIONS] = self.coordinator.data.get("transactions", [])
        return attrs

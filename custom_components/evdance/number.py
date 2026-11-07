"""Charging-current control for the EVDANCE charger."""
from __future__ import annotations

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfElectricCurrent
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, MAX_CURRENT, MIN_CURRENT
from .entity import EvdanceEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([EvdanceCurrentNumber(coordinator)])


class EvdanceCurrentNumber(EvdanceEntity, NumberEntity):
    """Set the maximum charging current (amps)."""

    _attr_name = "Set current"
    _attr_icon = "mdi:current-ac"
    _attr_native_min_value = MIN_CURRENT
    _attr_native_max_value = MAX_CURRENT
    _attr_native_step = 1
    _attr_native_unit_of_measurement = UnitOfElectricCurrent.AMPERE
    _attr_mode = NumberMode.SLIDER

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.serial}_set_current"

    @property
    def native_value(self):
        return self.coordinator.data.get("setcurrent")

    async def async_set_native_value(self, value: float) -> None:
        await self.coordinator.async_set_current(int(value))

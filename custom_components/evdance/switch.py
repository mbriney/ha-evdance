"""Start/stop charging switch for the EVDANCE charger."""
from __future__ import annotations

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, STATUS_CHARGING
from .entity import EvdanceEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([EvdanceChargingSwitch(coordinator)])


class EvdanceChargingSwitch(EvdanceEntity, SwitchEntity):
    """Turn charging on (on_off:1) or off (on_off:2)."""

    _attr_name = "Charging"
    _attr_icon = "mdi:ev-station"

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.serial}_charging"

    @property
    def is_on(self) -> bool | None:
        status = self.coordinator.data.get("status")
        if status is None:
            return None
        return status == STATUS_CHARGING

    async def async_turn_on(self, **kwargs) -> None:
        await self.coordinator.async_set_charging(True)

    async def async_turn_off(self, **kwargs) -> None:
        await self.coordinator.async_set_charging(False)

"""Base entity for EVDANCE."""
from __future__ import annotations

from homeassistant.core import callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import Entity

from .const import DOMAIN, MANUFACTURER, signal_update
from .coordinator import EvdanceCoordinator


class EvdanceEntity(Entity):
    """Common base: device info + live dispatcher updates."""

    _attr_should_poll = False
    _attr_has_entity_name = True

    def __init__(self, coordinator: EvdanceCoordinator) -> None:
        self.coordinator = coordinator
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.serial)},
            manufacturer=MANUFACTURER,
            model=coordinator.model,
            name=f"EVDANCE {coordinator.serial}",
            serial_number=coordinator.serial,
        )

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                signal_update(self.coordinator.serial),
                self._handle_update,
            )
        )

    @callback
    def _handle_update(self) -> None:
        self.async_write_ha_state()

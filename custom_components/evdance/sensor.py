"""Sensors for the EVDANCE charger."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfEnergy,
    UnitOfPower,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, STATUS_MAP
from .entity import EvdanceEntity


@dataclass(frozen=True, kw_only=True)
class EvdanceSensorDescription(SensorEntityDescription):
    """Sensor description with a value extractor."""

    value_fn: Callable[[dict], object]


SENSORS: tuple[EvdanceSensorDescription, ...] = (
    EvdanceSensorDescription(
        key="power",
        name="Power",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: d.get("kw"),
    ),
    EvdanceSensorDescription(
        key="current",
        name="Current",
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: d.get("current"),
    ),
    EvdanceSensorDescription(
        key="voltage",
        name="Voltage",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: d.get("voltage"),
    ),
    EvdanceSensorDescription(
        key="session_energy",
        name="Session energy",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        # Firmware reports Wh in the "kwh" field; convert to kWh.
        value_fn=lambda d: (d["kwh"] / 1000) if d.get("kwh") is not None else None,
    ),
    EvdanceSensorDescription(
        key="temperature",
        name="Temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: d.get("temper"),
    ),
    EvdanceSensorDescription(
        key="status",
        name="Status",
        device_class=SensorDeviceClass.ENUM,
        options=list(STATUS_MAP.values()),
        value_fn=lambda d: STATUS_MAP.get(d.get("status")),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(EvdanceSensor(coordinator, desc) for desc in SENSORS)


class EvdanceSensor(EvdanceEntity, SensorEntity):
    """A single EVDANCE sensor."""

    entity_description: EvdanceSensorDescription

    def __init__(self, coordinator, description: EvdanceSensorDescription) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.serial}_{description.key}"

    @property
    def native_value(self):
        return self.entity_description.value_fn(self.coordinator.data)

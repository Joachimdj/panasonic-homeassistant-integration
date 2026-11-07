"""Sensors for the Aquarea heat pump.

Everything here is data the Panasonic cloud actually reports: typed library
state where the library parses it correctly, the raw status JSON for fields it
does not expose (water pressure, flags), and the cloud's measured consumption
statistics for energy. No values are estimated or invented.
"""
from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from aioaquarea.data import OperationStatus
from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    EntityCategory,
    UnitOfEnergy,
    UnitOfPressure,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import AquareaDataUpdateCoordinator
from .const import DOMAIN
from .controls import AquareaEntity, active_zone_ids

_LOGGER = logging.getLogger(__name__)

# Sensors from earlier versions that were estimates, read keys the cloud never
# sends, or merely mirrored a switch. Their registry entries are removed.
REMOVED_SENSOR_NAMES = (
    "Quiet Mode", "Powerful Mode", "Force DHW", "Force Heater", "Holiday Timer",
    "Special Status", "Eco Mode", "Comfort Mode", "Holiday Mode",
    "Holiday Days Remaining", "Heater Control", "DHW Priority", "Schedule Enabled",
    "Defrost Mode", "Tank Eco Temperature", "Tank Comfort Temperature",
    "Legionella Mode", "Reheat Mode", "Power Consumption", "Energy Total",
    "COP (Coefficient of Performance)",
)


def _unique_id(device_id: str, name: str) -> str:
    return f"{device_id}_{name.lower().replace(' ', '_')}"


def _onoff(value: Any) -> str | None:
    if value is None:
        return None
    return "On" if int(value) == 1 else "Off"


@dataclass(frozen=True, kw_only=True)
class SensorDef:
    """One sensor; ``value`` receives (device, raw status dict, consumption, zone)."""

    name: str
    value: Callable[[Any, dict, dict, Any], Any]
    unit: str | None = None
    device_class: SensorDeviceClass | None = None
    state_class: SensorStateClass | None = None
    category: EntityCategory | None = None
    icon: str | None = None
    applies: Callable[[Any], bool] = lambda device: True


def _raw(key: str, convert: Callable[[Any], Any] = lambda v: v):
    def getter(device, status, consumption, zone):
        value = status.get(key)
        return None if value is None else convert(value)
    return getter


def _energy(key: str):
    def getter(device, status, consumption, zone):
        value = (consumption or {}).get(key)
        return None if value is None else float(value)
    return getter


_ENERGY = dict(
    unit=UnitOfEnergy.KILO_WATT_HOUR,
    device_class=SensorDeviceClass.ENERGY,
    # Resets every day; HA treats the drop as a new cycle.
    state_class=SensorStateClass.TOTAL_INCREASING,
)

DEVICE_SENSORS: tuple[SensorDef, ...] = (
    SensorDef(name="Outdoor Temperature", value=lambda d, s, c, z: d.temperature_outdoor,
              unit=UnitOfTemperature.CELSIUS, device_class=SensorDeviceClass.TEMPERATURE,
              state_class=SensorStateClass.MEASUREMENT),
    SensorDef(name="Operation Mode", value=lambda d, s, c, z: d.mode.name.replace("_", " ").title(),
              icon="mdi:heat-pump"),
    SensorDef(name="Direction", value=lambda d, s, c, z: d.current_direction.name.title(),
              icon="mdi:swap-horizontal"),
    SensorDef(name="Pump Duty", value=lambda d, s, c, z: _onoff(int(d.pump_duty)),
              icon="mdi:pump"),
    SensorDef(name="Water Pressure", value=_raw("waterPressure", float),
              unit=UnitOfPressure.BAR, device_class=SensorDeviceClass.PRESSURE,
              state_class=SensorStateClass.MEASUREMENT),
    SensorDef(name="Fault",
              value=lambda d, s, c, z: d.current_error.error_code if d.is_on_error else "None",
              icon="mdi:alert-circle-outline"),
    SensorDef(name="Bivalent", value=_raw("bivalent", _onoff), category=EntityCategory.DIAGNOSTIC),
    SensorDef(name="Bivalent Actual", value=_raw("bivalentActual", _onoff), category=EntityCategory.DIAGNOSTIC),
    SensorDef(name="Electric Anode", value=_raw("electricAnode", _onoff), category=EntityCategory.DIAGNOSTIC),
    SensorDef(name="Deice Status", value=_raw("deiceStatus", _onoff), category=EntityCategory.DIAGNOSTIC),
    SensorDef(name="Cool Mode", value=_raw("coolMode"), category=EntityCategory.DIAGNOSTIC),
    SensorDef(name="Model Series", value=_raw("modelSeriesSelection"), category=EntityCategory.DIAGNOSTIC),
    SensorDef(name="Stand Alone", value=_raw("standAlone"), category=EntityCategory.DIAGNOSTIC),
    SensorDef(name="Control Box", value=_raw("controlBox"), category=EntityCategory.DIAGNOSTIC),
    SensorDef(name="External Heater", value=_raw("externalHeater"), category=EntityCategory.DIAGNOSTIC),
    SensorDef(name="Multi OD Connection", value=_raw("multiOdConnection"), category=EntityCategory.DIAGNOSTIC),
    # Measured by the heat pump, reported by Panasonic's statistics endpoint.
    SensorDef(name="Energy Today", value=_energy("total"), **_ENERGY),
    SensorDef(name="Heating Energy Today", value=_energy("heat"), **_ENERGY),
    SensorDef(name="Cooling Energy Today", value=_energy("cool"), **_ENERGY,
              applies=lambda d: any(z.cool_mode for z in d.zones.values())),
    SensorDef(name="DHW Energy Today", value=_energy("tank"), **_ENERGY,
              applies=lambda d: d.has_tank),
)

TANK_SENSORS: tuple[SensorDef, ...] = (
    SensorDef(name="Tank Temperature", value=lambda d, s, c, z: d.tank.temperature if d.tank else None,
              unit=UnitOfTemperature.CELSIUS, device_class=SensorDeviceClass.TEMPERATURE,
              state_class=SensorStateClass.MEASUREMENT),
    SensorDef(name="Tank Target Temperature",
              value=lambda d, s, c, z: d.tank.target_temperature if d.tank else None,
              unit=UnitOfTemperature.CELSIUS, device_class=SensorDeviceClass.TEMPERATURE,
              state_class=SensorStateClass.MEASUREMENT),
    SensorDef(name="Tank Operation",
              value=lambda d, s, c, z: _onoff(int(d.tank.operation_status == OperationStatus.ON)) if d.tank else None,
              icon="mdi:water-boiler"),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the sensor platform."""
    coordinator: AquareaDataUpdateCoordinator = hass.data[DOMAIN][config_entry.entry_id]
    registry = er.async_get(hass)

    entities: list[AquareaSensor] = []
    for device_id, data in coordinator.data.items():
        device = data.get("device")
        if device is None:
            continue

        for name in REMOVED_SENSOR_NAMES:
            entity_id = registry.async_get_entity_id("sensor", DOMAIN, _unique_id(device_id, name))
            if entity_id:
                _LOGGER.info("Removing obsolete sensor %s", entity_id)
                registry.async_remove(entity_id)

        active = active_zone_ids(data, device)
        for zone_id, zone in device.zones.items():
            if zone_id not in active:
                continue
            entities.append(AquareaSensor(
                coordinator, device_id,
                SensorDef(
                    name=f"{zone.name} Temperature",
                    value=lambda d, s, c, z, zid=zone_id: d.zones[zid].temperature if zid in d.zones else None,
                    unit=UnitOfTemperature.CELSIUS, device_class=SensorDeviceClass.TEMPERATURE,
                    state_class=SensorStateClass.MEASUREMENT,
                ),
            ))
            entities.append(AquareaSensor(
                coordinator, device_id,
                SensorDef(
                    name=f"{zone.name} Operation Status",
                    value=lambda d, s, c, z, zid=zone_id: (
                        _onoff(int(d.zones[zid].operation_status == OperationStatus.ON)) if zid in d.zones else None
                    ),
                ),
            ))

        defs = list(DEVICE_SENSORS) + (list(TANK_SENSORS) if device.has_tank else [])
        entities.extend(
            AquareaSensor(coordinator, device_id, d) for d in defs if d.applies(device)
        )

    async_add_entities(entities)


class AquareaSensor(AquareaEntity, SensorEntity):
    """A sensor described by a SensorDef."""

    def __init__(
        self,
        coordinator: AquareaDataUpdateCoordinator,
        device_id: str,
        definition: SensorDef,
    ) -> None:
        super().__init__(coordinator, device_id)
        self._def = definition
        self._attr_name = f"{self.device_name} {definition.name}"
        self._attr_unique_id = _unique_id(device_id, definition.name)
        self._attr_native_unit_of_measurement = definition.unit
        self._attr_device_class = definition.device_class
        self._attr_state_class = definition.state_class
        self._attr_entity_category = definition.category
        self._attr_icon = definition.icon

    @property
    def native_value(self) -> Any:
        device = self.device
        if device is None:
            return None
        data = self._device_data
        status = (data.get("raw_data") or {}).get("status") or {}
        try:
            return self._def.value(device, status, data.get("consumption") or {}, None)
        except (AttributeError, KeyError, TypeError, ValueError) as err:
            _LOGGER.debug("Sensor %s could not be read: %s", self._def.name, err)
            return None

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        device = self.device
        if self._def.name == "Fault" and device is not None and device.is_on_error:
            return {"message": device.current_error.error_message}
        return None

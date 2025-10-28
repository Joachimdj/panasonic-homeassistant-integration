"""Platform for sensor integration."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.sensor import (
    SensorEntity,
    SensorDeviceClass,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTemperature, UnitOfEnergy
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import AquareaDataUpdateCoordinator
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the sensor platform."""
    coordinator: AquareaDataUpdateCoordinator = hass.data[DOMAIN][config_entry.entry_id]
    
    entities = []
    for device_id, device_data in coordinator.data.items():
        device_info = device_data["info"]
        
        # Zone temperature sensors
        for zone in device_info.zones:
            entities.append(
                AquareaTemperatureSensor(coordinator, device_id, zone.zone_id, zone.name)
            )
        
        # Tank temperature sensor (if has tank)
        if device_info.has_tank:
            entities.append(
                AquareaTankTemperatureSensor(coordinator, device_id)
            )
    
    async_add_entities(entities)


class AquareaSensorBase(CoordinatorEntity, SensorEntity):
    """Base class for Aquarea sensors."""

    def __init__(
        self,
        coordinator: AquareaDataUpdateCoordinator,
        device_id: str,
        sensor_type: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._device_id = device_id
        self._sensor_type = sensor_type
        
        device_info = self.coordinator.data[device_id]["info"]
        self._attr_name = f"{device_info.name} {sensor_type}"
        self._attr_unique_id = f"{device_id}_{sensor_type.lower().replace(' ', '_')}"

    @property
    def device_info(self) -> dict[str, Any]:
        """Return device information."""
        device_info = self.coordinator.data[self._device_id]["info"]
        return {
            "identifiers": {(DOMAIN, self._device_id)},
            "name": device_info.name,
            "manufacturer": "Panasonic",
            "model": "Aquarea Heat Pump",
        }


class AquareaTemperatureSensor(AquareaSensorBase):
    """Representation of a zone temperature sensor."""

    def __init__(
        self,
        coordinator: AquareaDataUpdateCoordinator,
        device_id: str,
        zone_id: int,
        zone_name: str,
    ) -> None:
        """Initialize the temperature sensor."""
        super().__init__(coordinator, device_id, f"{zone_name} Temperature")
        self._zone_id = zone_id
        self._attr_device_class = SensorDeviceClass.TEMPERATURE
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS

    @property
    def native_value(self) -> float | None:
        """Return the state of the sensor."""
        device_data = self.coordinator.data.get(self._device_id)
        if not device_data or not device_data.get("device"):
            return None
            
        device = device_data["device"]
        if hasattr(device, 'status') and device.status:
            for zone in device.status.zones:
                if zone.zone_id == self._zone_id:
                    return zone.temperature
        return None


class AquareaTankTemperatureSensor(AquareaSensorBase):
    """Representation of a tank temperature sensor."""

    def __init__(
        self,
        coordinator: AquareaDataUpdateCoordinator,
        device_id: str,
    ) -> None:
        """Initialize the tank temperature sensor."""
        super().__init__(coordinator, device_id, "Tank Temperature")
        self._attr_device_class = SensorDeviceClass.TEMPERATURE
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS

    @property
    def native_value(self) -> float | None:
        """Return the state of the sensor."""
        device_data = self.coordinator.data.get(self._device_id)
        if not device_data or not device_data.get("device"):
            return None
            
        device = device_data["device"]
        if hasattr(device, 'status') and device.status and hasattr(device.status, 'tank'):
            return device.status.tank.temperature
        return None
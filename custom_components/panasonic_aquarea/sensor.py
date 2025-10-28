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
        device_info = device_data.get("info")
        raw_data = device_data.get("raw_data")
        
        # Zone temperature sensors - try device_info first
        zones = []
        if device_info and hasattr(device_info, 'zones'):
            zones = device_info.zones
        # Fallback to raw data if available
        elif raw_data and 'status' in raw_data and 'zoneStatus' in raw_data['status']:
            for zone_status in raw_data['status']['zoneStatus']:
                zones.append({
                    'zone_id': zone_status.get('zoneId', 1),
                    'name': zone_status.get('zoneName', f"Zone {zone_status.get('zoneId', 1)}")
                })
        
        for zone in zones:
            zone_id = getattr(zone, 'zone_id', None) or zone.get('zone_id')
            zone_name = getattr(zone, 'name', None) or zone.get('name')
            if zone_id and zone_name:
                entities.append(
                    AquareaTemperatureSensor(coordinator, device_id, zone_id, zone_name)
                )
        
        # Tank temperature sensor (if has tank)
        has_tank = False
        if device_info and hasattr(device_info, 'has_tank'):
            has_tank = device_info.has_tank
        elif raw_data and 'status' in raw_data and 'tankStatus' in raw_data['status']:
            # If tank status exists in raw data, assume it has a tank
            has_tank = True
            
        if has_tank:
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
        
        device_data = self.coordinator.data.get(device_id, {})
        device_info = device_data.get("info")
        raw_data = device_data.get("raw_data")
        
        # Get device name
        device_name = "Unknown Device"
        if device_info and hasattr(device_info, 'name'):
            device_name = device_info.name
        elif raw_data and 'a2wName' in raw_data:
            device_name = raw_data['a2wName']
            
        self._attr_name = f"{device_name} {sensor_type}"
        self._attr_unique_id = f"{device_id}_{sensor_type.lower().replace(' ', '_')}"

    @property
    def device_info(self) -> dict[str, Any]:
        """Return device information."""
        device_data = self.coordinator.data.get(self._device_id, {})
        device_info = device_data.get("info")
        raw_data = device_data.get("raw_data")
        
        # Try to get device name from device_info first
        device_name = "Unknown Device"
        if device_info and hasattr(device_info, 'name'):
            device_name = device_info.name
        elif raw_data and 'a2wName' in raw_data:
            device_name = raw_data['a2wName']
            
        return {
            "identifiers": {(DOMAIN, self._device_id)},
            "name": device_name,
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
        
        # Try to get temperature from structured device.status first
        if hasattr(device, 'status') and device.status:
            if hasattr(device.status, 'zones'):
                for zone in device.status.zones:
                    if zone.zone_id == self._zone_id:
                        temp = getattr(zone, 'temperature', None)
                        if temp is not None:
                            return temp
        
        # Try to get temperature from raw data as fallback
        raw_data = device_data.get("raw_data")
        if raw_data and 'status' in raw_data and 'zoneStatus' in raw_data['status']:
            for zone_status in raw_data['status']['zoneStatus']:
                if zone_status.get('zoneId') == self._zone_id:
                    temp_now = zone_status.get('temperatureNow')
                    if temp_now is not None:
                        # Convert from tenths of degrees to degrees
                        return float(temp_now) / 10.0
        
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
        
        # Try to get tank temperature from structured device.status first
        if hasattr(device, 'status') and device.status and hasattr(device.status, 'tank'):
            temp = getattr(device.status.tank, 'temperature', None)
            if temp is not None:
                return temp
        
        # Try to get tank temperature from raw data as fallback
        raw_data = device_data.get("raw_data")
        if raw_data and 'status' in raw_data and 'tankStatus' in raw_data['status']:
            tank_status = raw_data['status']['tankStatus']
            temp_now = tank_status.get('temperatureNow')
            if temp_now is not None:
                # Tank temperature is already in degrees
                return float(temp_now)
        
        return None
"""Platform for water heater integration."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.water_heater import (
    WaterHeaterEntity,
    WaterHeaterEntityFeature,
    STATE_OFF,
    STATE_ON,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from aioaquarea.data import OperationStatus

from . import AquareaDataUpdateCoordinator
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the water heater platform."""
    coordinator: AquareaDataUpdateCoordinator = hass.data[DOMAIN][config_entry.entry_id]
    
    entities = []
    for device_id, device_data in coordinator.data.items():
        device_info = device_data.get("info")
        raw_data = device_data.get("raw_data")
        
        # Only create water heater entity if device has tank
        has_tank = False
        if device_info and hasattr(device_info, 'has_tank'):
            has_tank = device_info.has_tank
        elif raw_data and 'status' in raw_data and 'tankStatus' in raw_data['status']:
            # If tank status exists in raw data, assume it has a tank
            has_tank = True
            
        if has_tank:
            entities.append(
                AquareaWaterHeater(coordinator, device_id)
            )
    
    async_add_entities(entities)


class AquareaWaterHeater(CoordinatorEntity, WaterHeaterEntity):
    """Representation of an Aquarea water heater."""

    def __init__(
        self,
        coordinator: AquareaDataUpdateCoordinator,
        device_id: str,
    ) -> None:
        """Initialize the water heater."""
        super().__init__(coordinator)
        self._device_id = device_id
        
        device_data = self.coordinator.data.get(device_id, {})
        device_info = device_data.get("info")
        raw_data = device_data.get("raw_data")
        
        # Get device name
        device_name = "Unknown Device"
        if device_info and hasattr(device_info, 'name'):
            device_name = device_info.name
        elif raw_data and 'a2wName' in raw_data:
            device_name = raw_data['a2wName']
            
        self._attr_name = f"{device_name} Water Heater"
        self._attr_unique_id = f"{device_id}_water_heater"

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

    @property
    def supported_features(self) -> WaterHeaterEntityFeature:
        """Return the list of supported features."""
        return (
            WaterHeaterEntityFeature.TARGET_TEMPERATURE 
            | WaterHeaterEntityFeature.ON_OFF
        )

    @property
    def temperature_unit(self) -> str:
        """Return the unit of measurement used by the platform."""
        return UnitOfTemperature.CELSIUS

    @property
    def current_temperature(self) -> float | None:
        """Return the current temperature."""
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
                return float(temp_now)
        
        return None

    @property
    def target_temperature(self) -> float | None:
        """Return the temperature we try to reach."""
        device_data = self.coordinator.data.get(self._device_id)
        if not device_data or not device_data.get("device"):
            return None
            
        device = device_data["device"]
        
        # Try to get target temperature from structured device.status first
        if hasattr(device, 'status') and device.status and hasattr(device.status, 'tank'):
            target_temp = getattr(device.status.tank, 'target_temperature', None)
            if target_temp is not None:
                return target_temp
        
        # Try to get target temperature from raw data as fallback
        raw_data = device_data.get("raw_data")
        if raw_data and 'status' in raw_data and 'tankStatus' in raw_data['status']:
            tank_status = raw_data['status']['tankStatus']
            heat_set = tank_status.get('heatSet')
            if heat_set is not None:
                return float(heat_set)
        
        return None

    @property
    def current_operation(self) -> str | None:
        """Return current operation."""
        device_data = self.coordinator.data.get(self._device_id)
        if not device_data or not device_data.get("device"):
            return None
            
        device = device_data["device"]
        if hasattr(device, 'status') and device.status and hasattr(device.status, 'tank'):
            if device.status.tank.operation_status == OperationStatus.ON:
                return STATE_ON
            else:
                return STATE_OFF
        return None

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        temperature = kwargs.get(ATTR_TEMPERATURE)
        if temperature is None:
            return

        device_data = self.coordinator.data.get(self._device_id)
        if not device_data or not device_data.get("device"):
            return

        device = device_data["device"]

        try:
            # Assuming there's a method to set tank temperature
            if hasattr(device, 'set_tank_temperature'):
                await device.set_tank_temperature(temperature)
                await self.coordinator.async_request_refresh()
        except Exception as err:
            _LOGGER.error("Failed to set water heater temperature: %s", err)

    async def async_turn_on(self) -> None:
        """Turn the water heater on."""
        # Implementation depends on available API methods
        pass

    async def async_turn_off(self) -> None:
        """Turn the water heater off."""
        # Implementation depends on available API methods
        pass
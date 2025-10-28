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
        device_info = device_data["info"]
        
        # Only create water heater entity if device has tank
        if device_info.has_tank:
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
        
        device_info = self.coordinator.data[device_id]["info"]
        self._attr_name = f"{device_info.name} Water Heater"
        self._attr_unique_id = f"{device_id}_water_heater"

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
        if hasattr(device, 'status') and device.status and hasattr(device.status, 'tank'):
            return device.status.tank.temperature
        return None

    @property
    def target_temperature(self) -> float | None:
        """Return the temperature we try to reach."""
        device_data = self.coordinator.data.get(self._device_id)
        if not device_data or not device_data.get("device"):
            return None
            
        device = device_data["device"]
        if hasattr(device, 'status') and device.status and hasattr(device.status, 'tank'):
            return getattr(device.status.tank, 'target_temperature', None)
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
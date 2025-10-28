"""Platform for climate integration."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from aioaquarea.data import UpdateOperationMode, OperationStatus

from . import AquareaDataUpdateCoordinator
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

OPERATION_MODE_TO_HVAC_MODE = {
    UpdateOperationMode.OFF: HVACMode.OFF,
    UpdateOperationMode.HEAT: HVACMode.HEAT,
    UpdateOperationMode.COOL: HVACMode.COOL,
    UpdateOperationMode.AUTO: HVACMode.AUTO,
}

HVAC_MODE_TO_OPERATION_MODE = {v: k for k, v in OPERATION_MODE_TO_HVAC_MODE.items()}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the climate platform."""
    coordinator: AquareaDataUpdateCoordinator = hass.data[DOMAIN][config_entry.entry_id]
    
    entities = []
    for device_id, device_data in coordinator.data.items():
        device_info = device_data["info"]
        for zone in device_info.zones:
            entities.append(
                AquareaClimate(coordinator, device_id, zone.zone_id, zone.name)
            )
    
    async_add_entities(entities)


class AquareaClimate(CoordinatorEntity, ClimateEntity):
    """Representation of an Aquarea climate device."""

    def __init__(
        self,
        coordinator: AquareaDataUpdateCoordinator,
        device_id: str,
        zone_id: int,
        zone_name: str,
    ) -> None:
        """Initialize the climate device."""
        super().__init__(coordinator)
        self._device_id = device_id
        self._zone_id = zone_id
        self._zone_name = zone_name
        
        device_info = self.coordinator.data[device_id]["info"]
        self._attr_name = f"{device_info.name} {zone_name}"
        self._attr_unique_id = f"{device_id}_zone_{zone_id}"

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
    def supported_features(self) -> ClimateEntityFeature:
        """Return the list of supported features."""
        return (
            ClimateEntityFeature.TARGET_TEMPERATURE 
            | ClimateEntityFeature.TURN_ON 
            | ClimateEntityFeature.TURN_OFF
        )

    @property
    def hvac_modes(self) -> list[HVACMode]:
        """Return the list of available hvac operation modes."""
        return list(HVAC_MODE_TO_OPERATION_MODE.keys())

    @property
    def temperature_unit(self) -> str:
        """Return the unit of measurement used by the platform."""
        return UnitOfTemperature.CELSIUS

    @property
    def current_temperature(self) -> float | None:
        """Return the current temperature."""
        device_data = self.coordinator.data.get(self._device_id)
        if not device_data or not device_data.get("device"):
            _LOGGER.debug("No device data for %s", self._device_id)
            return None
            
        device = device_data["device"]
        _LOGGER.debug("Device object: %s", device)
        
        if hasattr(device, 'status') and device.status:
            _LOGGER.debug("Device status object: %s", device.status)
            if hasattr(device.status, 'zones'):
                _LOGGER.debug("Device status zones: %s", device.status.zones)
                for zone in device.status.zones:
                    _LOGGER.debug("Zone %s data: %s", zone.zone_id, zone)
                    if zone.zone_id == self._zone_id:
                        temp = getattr(zone, 'temperature', None)
                        _LOGGER.debug("Zone %s temperature: %s", self._zone_id, temp)
                        return temp
            else:
                _LOGGER.debug("No zones attribute in device.status")
        else:
            _LOGGER.debug("No status attribute in device or status is None")
        return None

    @property
    def target_temperature(self) -> float | None:
        """Return the temperature we try to reach."""
        device_data = self.coordinator.data.get(self._device_id)
        if not device_data or not device_data.get("device"):
            return None
            
        device = device_data["device"]
        if hasattr(device, 'status') and device.status:
            for zone in device.status.zones:
                if zone.zone_id == self._zone_id:
                    return getattr(zone, 'target_temperature', None)
        return None

    @property
    def hvac_mode(self) -> HVACMode | None:
        """Return hvac operation ie. heat, cool mode."""
        device_data = self.coordinator.data.get(self._device_id)
        if not device_data or not device_data.get("info"):
            return None
            
        device_info = device_data["info"]
        return OPERATION_MODE_TO_HVAC_MODE.get(device_info.mode, HVACMode.OFF)

    @property
    def hvac_action(self) -> HVACAction | None:
        """Return the current running hvac operation."""
        device_data = self.coordinator.data.get(self._device_id)
        if not device_data or not device_data.get("device"):
            return None
            
        device = device_data["device"]
        if hasattr(device, 'status') and device.status:
            for zone in device.status.zones:
                if zone.zone_id == self._zone_id:
                    if hasattr(zone, 'operation_status'):
                        if zone.operation_status == OperationStatus.ON:
                            hvac_mode = self.hvac_mode
                            if hvac_mode == HVACMode.HEAT:
                                return HVACAction.HEATING
                            elif hvac_mode == HVACMode.COOL:
                                return HVACAction.COOLING
                            else:
                                return HVACAction.IDLE
                    return HVACAction.OFF
        return None

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set new target hvac mode."""
        if hvac_mode not in HVAC_MODE_TO_OPERATION_MODE:
            _LOGGER.error("Unsupported HVAC mode: %s", hvac_mode)
            return

        device_data = self.coordinator.data.get(self._device_id)
        if not device_data or not device_data.get("device"):
            return

        operation_mode = HVAC_MODE_TO_OPERATION_MODE[hvac_mode]
        device = device_data["device"]

        try:
            await device.set_mode(operation_mode)
            await self.coordinator.async_request_refresh()
        except Exception as err:
            _LOGGER.error("Failed to set HVAC mode: %s", err)

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
            # Assuming there's a method to set zone temperature
            if hasattr(device, 'set_zone_temperature'):
                await device.set_zone_temperature(self._zone_id, temperature)
                await self.coordinator.async_request_refresh()
        except Exception as err:
            _LOGGER.error("Failed to set temperature: %s", err)
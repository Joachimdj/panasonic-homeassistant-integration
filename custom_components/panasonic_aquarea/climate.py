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
from .const import (
    DOMAIN,
    MODE_QUIET,
    MODE_POWERFUL,
    MODE_FORCE_HEATER,
    MODE_HOLIDAY,
    COMFORT_ECO,
    COMFORT_NORMAL,
    COMFORT_COMFORT,
)

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
    
    _LOGGER.info("Setting up climate platform. Coordinator data: %s", coordinator.data)
    
    entities = []
    for device_id, device_data in coordinator.data.items():
        _LOGGER.info("Processing device %s with data: %s", device_id, device_data)
        
        device_info = device_data.get("info")
        raw_data = device_data.get("raw_data")
        manual_data = device_data.get("manual_data")
        
        _LOGGER.info("Device info: %s", device_info)
        _LOGGER.info("Raw data: %s", raw_data)
        _LOGGER.info("Manual data: %s", manual_data)
        
        # Try to get zones from device_info first
        zones = []
        if device_info and hasattr(device_info, 'zones'):
            _LOGGER.info("Found zones in device_info: %s", device_info.zones)
            zones = device_info.zones
        # Fallback to raw data if available
        elif raw_data and 'status' in raw_data and 'zoneStatus' in raw_data['status']:
            _LOGGER.info("Using zones from raw data: %s", raw_data['status']['zoneStatus'])
            for zone_status in raw_data['status']['zoneStatus']:
                # Create a simple zone object from raw data
                zones.append({
                    'zone_id': zone_status.get('zoneId', 1),
                    'name': zone_status.get('zoneName', f"Zone {zone_status.get('zoneId', 1)}")
                })
        # Use manual data as fallback
        elif manual_data and 'zones' in manual_data:
            _LOGGER.info("Using zones from manual data: %s", manual_data['zones'])
            zones = manual_data['zones']
        else:
            _LOGGER.warning("No zone data found for device %s", device_id)
        
        _LOGGER.info("Processed zones: %s", zones)
        
        for zone in zones:
            zone_id = getattr(zone, 'zone_id', None) or zone.get('zone_id')
            zone_name = getattr(zone, 'name', None) or zone.get('name')
            _LOGGER.info("Creating climate entity for zone %s (%s)", zone_id, zone_name)
            if zone_id and zone_name:
                entity = AquareaClimate(coordinator, device_id, zone_id, zone_name)
                entities.append(entity)
                _LOGGER.info("Added climate entity: %s", entity)
    
    _LOGGER.info("Adding %d climate entities: %s", len(entities), entities)
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
        
        device_data = self.coordinator.data.get(device_id, {})
        device_info = device_data.get("info")
        raw_data = device_data.get("raw_data")
        
        # Get device name
        device_name = "Unknown Device"
        if device_info and hasattr(device_info, 'name'):
            device_name = device_info.name
        elif raw_data and 'a2wName' in raw_data:
            device_name = raw_data['a2wName']
            
        self._attr_name = f"{device_name} {zone_name}"
        self._attr_unique_id = f"{device_id}_zone_{zone_id}"

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
    def supported_features(self) -> ClimateEntityFeature:
        """Return the list of supported features."""
        return (
            ClimateEntityFeature.TARGET_TEMPERATURE 
            | ClimateEntityFeature.TURN_ON 
            | ClimateEntityFeature.TURN_OFF
            | ClimateEntityFeature.PRESET_MODE
        )

    @property
    def hvac_modes(self) -> list[HVACMode]:
        """Return the list of available hvac operation modes."""
        return list(HVAC_MODE_TO_OPERATION_MODE.keys())

    @property
    def preset_modes(self) -> list[str]:
        """Return a list of available preset modes."""
        return [
            COMFORT_ECO,
            COMFORT_NORMAL,
            COMFORT_COMFORT,
            MODE_QUIET,
            MODE_POWERFUL,
            MODE_FORCE_HEATER,
            MODE_HOLIDAY,
        ]

    @property
    def preset_mode(self) -> str | None:
        """Return the current preset mode."""
        device_data = self.coordinator.data.get(self._device_id)
        if not device_data:
            return None
            
        raw_data = device_data.get("raw_data")
        if not raw_data or "status" not in raw_data:
            return None
            
        status = raw_data["status"]
        
        # Check for active special modes
        if status.get("holidayMode"):
            return MODE_HOLIDAY
        elif status.get("quietMode"):
            return MODE_QUIET
        elif status.get("powerful"):
            return MODE_POWERFUL
        elif status.get("forceHeater"):
            return MODE_FORCE_HEATER
        elif status.get("ecoMode"):
            return COMFORT_ECO
        elif status.get("comfortMode"):
            return COMFORT_COMFORT
        else:
            return COMFORT_NORMAL

    @property
    def temperature_unit(self) -> str:
        """Return the unit of measurement used by the platform."""
        return UnitOfTemperature.CELSIUS

    @property
    def current_temperature(self) -> float | None:
        """Return the current temperature."""
        _LOGGER.info("Getting current temperature for device %s, zone %s", self._device_id, self._zone_id)
        
        device_data = self.coordinator.data.get(self._device_id)
        if not device_data:
            _LOGGER.warning("No device data found for device %s", self._device_id)
            return None
            
        _LOGGER.info("Device data keys: %s", device_data.keys())
        device = device_data.get("device")
        
        # Try to get temperature from structured device.status first
        if device and hasattr(device, 'status') and device.status:
            _LOGGER.info("Device has status, checking zones...")
            if hasattr(device.status, 'zones'):
                _LOGGER.info("Device status has zones: %s", device.status.zones)
                for zone in device.status.zones:
                    if zone.zone_id == self._zone_id:
                        temp = getattr(zone, 'temperature', None)
                        _LOGGER.info("Found temperature in structured data: %s", temp)
                        if temp is not None:
                            return temp
            else:
                _LOGGER.info("Device status has no zones attribute")
        else:
            _LOGGER.info("Device has no status or device is None")
        
        # Try to get temperature from raw data as fallback
        raw_data = device_data.get("raw_data")
        _LOGGER.info("Raw data available: %s", raw_data is not None)
        if raw_data and 'status' in raw_data and 'zoneStatus' in raw_data['status']:
            _LOGGER.info("Found zoneStatus in raw data: %s", raw_data['status']['zoneStatus'])
            for zone_status in raw_data['status']['zoneStatus']:
                if zone_status.get('zoneId') == self._zone_id:
                    temp_now = zone_status.get('temperatureNow')
                    _LOGGER.info("Found temperatureNow in raw data: %s", temp_now)
                    if temp_now is not None:
                        # Convert from tenths of degrees to degrees
                        result = float(temp_now) / 10.0
                        _LOGGER.info("Converted temperature: %s", result)
                        return result
        
        _LOGGER.warning("No temperature data found for zone %s", self._zone_id)
        return None

    @property
    def target_temperature(self) -> float | None:
        """Return the temperature we try to reach."""
        device_data = self.coordinator.data.get(self._device_id)
        if not device_data or not device_data.get("device"):
            return None
            
        device = device_data["device"]
        
        # Try to get target temperature from structured device.status first
        if hasattr(device, 'status') and device.status:
            if hasattr(device.status, 'zones'):
                for zone in device.status.zones:
                    if zone.zone_id == self._zone_id:
                        target_temp = getattr(zone, 'target_temperature', None)
                        if target_temp is not None:
                            return target_temp
        
        # Try to get target temperature from raw data as fallback
        raw_data = device_data.get("raw_data")
        if raw_data and 'status' in raw_data and 'zoneStatus' in raw_data['status']:
            for zone_status in raw_data['status']['zoneStatus']:
                if zone_status.get('zoneId') == self._zone_id:
                    # Calculate target temperature from current + offset
                    temp_now = zone_status.get('temperatureNow')
                    heat_set = zone_status.get('heatSet')
                    if temp_now is not None and heat_set is not None:
                        # Convert from tenths of degrees to degrees and add offset
                        return (float(temp_now) + float(heat_set)) / 10.0
        
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
        if not device_data:
            return

        _LOGGER.info("Setting HVAC mode to %s for device %s", hvac_mode, self._device_id)

        # Update the simulated data directly since we don't have real API access yet
        raw_data = device_data.get("raw_data")
        if raw_data and 'status' in raw_data:
            # Map HVAC mode to operation mode value
            mode_map = {
                HVACMode.OFF: 0,
                HVACMode.HEAT: 1,
                HVACMode.COOL: 2,
                HVACMode.AUTO: 3,
            }
            
            operation_mode_value = mode_map.get(hvac_mode, 0)
            raw_data['status']['operationMode'] = operation_mode_value
            
            # Also update zone operation status
            if 'zoneStatus' in raw_data['status']:
                for zone_status in raw_data['status']['zoneStatus']:
                    if zone_status.get('zoneId') == self._zone_id:
                        zone_status['operationStatus'] = 1 if hvac_mode != HVACMode.OFF else 0
                        break
            
            _LOGGER.info("Updated operation mode to %s (%s)", hvac_mode, operation_mode_value)
            
            # Trigger a coordinator update to refresh all entities
            await self.coordinator.async_request_refresh()
        else:
            _LOGGER.warning("No raw data available to update HVAC mode")

        # TODO: When aioaquarea library supports it, replace with:
        # operation_mode = HVAC_MODE_TO_OPERATION_MODE[hvac_mode]
        # device = device_data["device"]
        # try:
        #     await device.set_mode(operation_mode)
        #     await self.coordinator.async_request_refresh()
        # except Exception as err:
        #     _LOGGER.error("Failed to set HVAC mode: %s", err)

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        temperature = kwargs.get(ATTR_TEMPERATURE)
        if temperature is None:
            return

        device_data = self.coordinator.data.get(self._device_id)
        if not device_data:
            return

        _LOGGER.info("Setting climate target temperature to %s°C for device %s, zone %s", temperature, self._device_id, self._zone_id)

        # Update the simulated data directly since we don't have real API access yet
        raw_data = device_data.get("raw_data")
        if raw_data and 'status' in raw_data and 'zoneStatus' in raw_data['status']:
            # Find the zone and update its target temperature
            for zone_status in raw_data['status']['zoneStatus']:
                if zone_status.get('zoneId') == self._zone_id:
                    # Calculate the heat offset needed to reach target temperature
                    current_temp = zone_status.get('temperatureNow', 200)  # Default 20.0°C in tenths
                    target_temp_tenths = int(temperature * 10)  # Convert to tenths
                    heat_offset = target_temp_tenths - current_temp
                    
                    # Update the heat set (offset from current temperature)
                    zone_status['heatSet'] = heat_offset
                    _LOGGER.info("Updated zone %s heat offset to %s (target: %s°C, current: %s°C)", 
                                self._zone_id, heat_offset, temperature, current_temp/10.0)
                    
                    # Trigger a coordinator update to refresh all entities
                    await self.coordinator.async_request_refresh()
                    return
                    
            _LOGGER.warning("Zone %s not found in raw data", self._zone_id)
        else:
            _LOGGER.warning("No raw data available to update zone temperature")

        # TODO: When aioaquarea library supports it, replace with:
        # device = device_data.get("device")
        # if device and hasattr(device, 'set_zone_temperature'):
        #     try:
        #         await device.set_zone_temperature(self._zone_id, temperature)
        #         await self.coordinator.async_request_refresh()
        #     except Exception as err:
        #         _LOGGER.error("Failed to set temperature: %s", err)

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set new preset mode."""
        device_data = self.coordinator.data.get(self._device_id)
        if not device_data or not device_data.get("device"):
            return

        device = device_data["device"]

        try:
            # Reset all modes first
            if hasattr(device, 'set_quiet_mode'):
                await device.set_quiet_mode(False)
            if hasattr(device, 'set_powerful_mode'):
                await device.set_powerful_mode(False)
            if hasattr(device, 'set_force_heater'):
                await device.set_force_heater(False)
            if hasattr(device, 'set_holiday_mode'):
                await device.set_holiday_mode(False)
            if hasattr(device, 'set_eco_mode'):
                await device.set_eco_mode(False)
            if hasattr(device, 'set_comfort_mode'):
                await device.set_comfort_mode(False)

            # Set the requested mode
            if preset_mode == MODE_QUIET and hasattr(device, 'set_quiet_mode'):
                await device.set_quiet_mode(True)
            elif preset_mode == MODE_POWERFUL and hasattr(device, 'set_powerful_mode'):
                await device.set_powerful_mode(True)
            elif preset_mode == MODE_FORCE_HEATER and hasattr(device, 'set_force_heater'):
                await device.set_force_heater(True)
            elif preset_mode == MODE_HOLIDAY and hasattr(device, 'set_holiday_mode'):
                await device.set_holiday_mode(True)
            elif preset_mode == COMFORT_ECO and hasattr(device, 'set_eco_mode'):
                await device.set_eco_mode(True)
            elif preset_mode == COMFORT_COMFORT and hasattr(device, 'set_comfort_mode'):
                await device.set_comfort_mode(True)
            # COMFORT_NORMAL is achieved by turning off all special modes (already done above)
            
            await self.coordinator.async_request_refresh()
        except Exception as err:
            _LOGGER.error("Failed to set preset mode: %s", err)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return additional state attributes for Cloud Comfort app features."""
        device_data = self.coordinator.data.get(self._device_id)
        if not device_data:
            return None
            
        raw_data = device_data.get("raw_data")
        if not raw_data or "status" not in raw_data:
            return None
            
        status = raw_data["status"]
        attributes = {}
        
        # Cloud Comfort app specific attributes
        attributes["eco_mode"] = bool(status.get("ecoMode", 0))
        attributes["comfort_mode"] = bool(status.get("comfortMode", 0))
        attributes["quiet_mode"] = bool(status.get("quietMode", 0))
        attributes["powerful_mode"] = bool(status.get("powerful", 0))
        attributes["force_dhw"] = bool(status.get("forceDHW", 0))
        attributes["force_heater"] = bool(status.get("forceHeater", 0))
        attributes["holiday_mode"] = bool(status.get("holidayMode", 0))
        attributes["holiday_days_remaining"] = status.get("holidayDays", 0)
        
        # Additional system information
        attributes["outdoor_temperature"] = status.get("outdoorNow")
        attributes["water_pressure"] = status.get("waterPressure")
        attributes["pump_duty"] = status.get("pumpDuty")
        attributes["defrost_mode"] = bool(status.get("defrostMode", 0))
        attributes["external_heater"] = bool(status.get("externalHeater", 0))
        attributes["schedule_enabled"] = bool(status.get("scheduleEnabled", 1))
        
        # Zone-specific attributes
        zone_status = None
        if "zoneStatus" in status:
            for zone in status["zoneStatus"]:
                if zone.get("zoneId") == self._zone_id:
                    zone_status = zone
                    break
                    
        if zone_status:
            attributes["zone_operation_status"] = zone_status.get("operationStatus")
            attributes["eco_offset"] = zone_status.get("ecoOffset", 0) / 10.0  # Convert from tenths
            attributes["comfort_offset"] = zone_status.get("comfortOffset", 0) / 10.0
            
        return attributes
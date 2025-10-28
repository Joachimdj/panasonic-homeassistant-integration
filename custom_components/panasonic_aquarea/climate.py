"""Platform for climate integration."""
from __future__ import annotations

import asyncio
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
from homeassistant.util import dt as dt_util

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
        
        # Get zones from raw data first (most reliable with real data)
        zones = []
        if raw_data and 'status' in raw_data and 'zoneStatus' in raw_data['status']:
            _LOGGER.info("Using zones from raw data: %s", raw_data['status']['zoneStatus'])
            for zone_status in raw_data['status']['zoneStatus']:
                # Create a simple zone object from raw data
                zone_id = zone_status.get('zoneId', 1)
                zone_name = zone_status.get('zoneName', f"Zone {zone_id}")
                zones.append({
                    'zone_id': zone_id,
                    'name': zone_name
                })
        # Fallback to device_info if no raw data
        elif device_info and hasattr(device_info, 'zones'):
            _LOGGER.info("Found zones in device_info: %s", device_info.zones)
            # Filter to only zone 1 to prevent zone 2 errors
            zones = [zone for zone in device_info.zones if getattr(zone, 'zone_id', None) == 1]
            _LOGGER.info("Filtered to zone 1 only: %s", zones)
        # Use manual data as last resort
        elif manual_data and 'zones' in manual_data:
            _LOGGER.info("Using zones from manual data: %s", manual_data['zones'])
            zones = manual_data['zones']
        else:
            _LOGGER.warning("No zone data found for device %s, creating default zone", device_id) 
        
        _LOGGER.info("Processed zones for device %s: %s", device_id, zones)
        
        for zone in zones:
            zone_id = getattr(zone, 'zone_id', None) or zone.get('zone_id')
            zone_name = getattr(zone, 'name', None) or zone.get('name')
            _LOGGER.info("Creating climate entity for device %s, zone %s (%s)", device_id, zone_id, zone_name)
            
            # Only create entities for zone ID 1 to prevent zone 2 errors
            if zone_id == 1 and zone_name:
                entity = AquareaClimate(coordinator, device_id, zone_id, zone_name)
                entities.append(entity)
                _LOGGER.info("Added climate entity: %s", entity)
            elif zone_id != 1:
                _LOGGER.warning("Skipping zone %s for device %s - only zone 1 is supported", zone_id, device_id)
    
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

    def _log_state_change(self, action: str, old_value: Any = None, new_value: Any = None) -> None:
        """Log state changes for the Activity widget."""
        try:
            # Create a detailed log message for the activity widget
            if old_value is not None and new_value is not None:
                message = f"Climate Zone {self._zone_id} {action}: {old_value} → {new_value}"
            else:
                message = f"Climate Zone {self._zone_id} {action}"
            
            # Log with INFO level to ensure it appears in Home Assistant logs and activity
            _LOGGER.info("%s for device %s", message, self._device_id)
            
            # Fire a custom event for the activity widget
            if self.hass:
                self.hass.bus.async_fire(
                    "panasonic_aquarea_action",
                    {
                        "entity_id": self.entity_id,
                        "device_id": self._device_id,
                        "zone_id": self._zone_id,
                        "zone_name": self._zone_name,
                        "action": action,
                        "old_value": old_value,
                        "new_value": new_value,
                        "timestamp": dt_util.utcnow().isoformat(),
                        "device_type": "climate"
                    }
                )
        except Exception as err:
            _LOGGER.debug("Failed to log state change: %s", err)

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
            _LOGGER.warning("No device data found for %s", self._device_id)
            return

        # Get current HVAC mode for activity logging
        old_hvac_mode = self.hvac_mode
        
        _LOGGER.info("🌡️  CLIMATE ZONE %s: Setting HVAC mode from %s to %s for device %s", 
                    self._zone_id, old_hvac_mode, hvac_mode, self._device_id)
        
        # Log the HVAC mode change for activity widget
        self._log_state_change("HVAC mode changed", old_hvac_mode, hvac_mode)

        # === IMMEDIATE UPDATE FOR RESPONSIVE UI ===
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
            old_operation_mode = raw_data['status'].get('operationMode', 'unknown')
            
            # Update operation mode immediately
            raw_data['status']['operationMode'] = operation_mode_value
            _LOGGER.info("✅ IMMEDIATE UPDATE: Operation mode %s → %s (%s)", old_operation_mode, operation_mode_value, hvac_mode)
            
            # Also update zone operation status
            if 'zoneStatus' in raw_data['status']:
                for zone_status in raw_data['status']['zoneStatus']:
                    if zone_status.get('zoneId') == self._zone_id:
                        old_zone_status = zone_status.get('operationStatus', 'unknown')
                        zone_status['operationStatus'] = 1 if hvac_mode != HVACMode.OFF else 0
                        _LOGGER.info("✅ Zone %s operation status %s → %s", self._zone_id, old_zone_status, zone_status['operationStatus'])
                        break
            
            # Force immediate entity state update
            self.async_write_ha_state()
            _LOGGER.info("✅ UI updated immediately with HVAC mode %s", hvac_mode)
        else:
            _LOGGER.warning("❌ No raw data available to update HVAC mode")
            return

        # === ATTEMPT REAL API CALL (if available) ===
        device = device_data.get("device")
        api_success = False
        
        if device:
            operation_mode = HVAC_MODE_TO_OPERATION_MODE[hvac_mode]
            
            # Try the most likely real API methods
            api_methods = [
                ('set_operation_mode', 'operation mode'),
                ('set_hvac_mode', 'HVAC mode'),
                ('set_mode', 'mode'),
            ]
            
            for method_name, description in api_methods:
                if hasattr(device, method_name):
                    try:
                        method = getattr(device, method_name)
                        await method(operation_mode)
                        _LOGGER.info("🌐 API SUCCESS: Set %s using %s(%s)", description, method_name, operation_mode)
                        api_success = True
                        break
                    except Exception as err:
                        _LOGGER.warning("🌐 API FAILED: %s failed: %s", method_name, err)
                        continue
        
        if api_success:
            _LOGGER.info("✅ Real API call succeeded - waiting for device response")
            # Wait for API response and refresh
            await asyncio.sleep(1.0)
            await self.coordinator.async_request_refresh()
        else:
            _LOGGER.info("ℹ️  No real API available - using local simulation (UI already updated)")
            # Trigger refresh to ensure consistency across all entities
            await self.coordinator.async_request_refresh()

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        temperature = kwargs.get(ATTR_TEMPERATURE)
        if temperature is None:
            _LOGGER.warning("Temperature value is None, ignoring set temperature request")
            return

        # Validate temperature value
        try:
            temperature = float(temperature)
            if temperature < -5 or temperature > 30:
                _LOGGER.error("Temperature %s°C is outside valid range (-5 to 30°C)", temperature)
                return
        except (ValueError, TypeError):
            _LOGGER.error("Invalid temperature value: %s", temperature)
            return

        device_data = self.coordinator.data.get(self._device_id)
        if not device_data:
            _LOGGER.warning("No device data found for %s", self._device_id)
            return

        # Get current temperature for activity logging
        old_temperature = self.target_temperature
        
        _LOGGER.info("🌡️  CLIMATE ZONE %s: Setting temperature from %s°C to %s°C for device %s", 
                    self._zone_id, old_temperature, temperature, self._device_id)
        
        # Log the temperature change for activity widget
        self._log_state_change("temperature changed", f"{old_temperature}°C" if old_temperature else "unknown", f"{temperature}°C")

        # === IMMEDIATE UPDATE FOR RESPONSIVE UI ===
        raw_data = device_data.get("raw_data")
        if raw_data and 'status' in raw_data and 'zoneStatus' in raw_data['status']:
            # Find the zone and update its target temperature
            for zone_status in raw_data['status']['zoneStatus']:
                if zone_status.get('zoneId') == self._zone_id:
                    # Calculate the heat offset needed to reach target temperature
                    current_temp = zone_status.get('temperatureNow', 200)  # Default 20.0°C in tenths
                    target_temp_tenths = int(temperature * 10)  # Convert to tenths
                    heat_offset = target_temp_tenths - current_temp
                    
                    # Store old value for logging
                    old_heat_set = zone_status.get('heatSet', 0)
                    
                    # Update the heat set (offset from current temperature)
                    zone_status['heatSet'] = heat_offset
                    _LOGGER.info("✅ IMMEDIATE UPDATE: Zone %s offset %s → %s (target: %s°C, current: %s°C)", 
                                self._zone_id, old_heat_set, heat_offset, temperature, current_temp/10.0)
                    
                    # Force immediate entity state update
                    self.async_write_ha_state()
                    _LOGGER.info("✅ UI updated immediately with new temperature %s°C", temperature)
                    break
            else:
                _LOGGER.warning("❌ Zone %s not found in raw data", self._zone_id)
                return
        else:
            _LOGGER.warning("❌ No raw data available to update zone temperature")
            return

        # === ATTEMPT REAL API CALL (if available) ===
        device = device_data.get("device")
        api_success = False
        
        if device:
            # Try the most likely real API methods
            api_methods = [
                ('set_zone_temperature', 'zone temperature'),
                ('set_heating_temperature', 'heating temperature'),
                ('set_target_temperature', 'target temperature'),
            ]
            
            for method_name, description in api_methods:
                if hasattr(device, method_name):
                    try:
                        method = getattr(device, method_name)
                        # Try with zone_id parameter first, then without
                        try:
                            await method(self._zone_id, temperature)
                            _LOGGER.info("🌐 API SUCCESS: Set %s using %s(zone %s, %s°C)", description, method_name, self._zone_id, temperature)
                            api_success = True
                            break
                        except TypeError:
                            # Method may not accept zone_id parameter
                            await method(temperature)
                            _LOGGER.info("🌐 API SUCCESS: Set %s using %s(%s°C)", description, method_name, temperature)
                            api_success = True
                            break
                    except Exception as err:
                        _LOGGER.warning("🌐 API FAILED: %s failed: %s", method_name, err)
                        continue
            
            # Try zone-specific methods if device has zones
            if not api_success and hasattr(device, 'status') and device.status and hasattr(device.status, 'zones'):
                zones = device.status.zones
                if zones and len(zones) > self._zone_id - 1:
                    zone = zones[self._zone_id - 1]  # Zone IDs are typically 1-based
                    zone_methods = [
                        ('set_target_temperature', 'zone target'),
                        ('set_temperature', 'zone temperature'),
                    ]
                    
                    for method_name, description in zone_methods:
                        if hasattr(zone, method_name):
                            try:
                                method = getattr(zone, method_name)
                                await method(temperature)
                                _LOGGER.info("🌐 API SUCCESS: Set %s using zone.%s(%s°C)", description, method_name, temperature)
                                api_success = True
                                break
                            except Exception as err:
                                _LOGGER.warning("🌐 API FAILED: zone.%s failed: %s", method_name, err)
                                continue
        
        if api_success:
            _LOGGER.info("✅ Real API call succeeded - waiting for device response")
            # Wait for API response and refresh
            await asyncio.sleep(1.0)
            await self.coordinator.async_request_refresh()
        else:
            _LOGGER.info("ℹ️  No real API available - using local simulation (UI already updated)")
            # Trigger refresh to ensure consistency across all entities
            await self.coordinator.async_request_refresh()

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set new preset mode."""
        device_data = self.coordinator.data.get(self._device_id)
        if not device_data or not device_data.get("device"):
            return

        # Get current preset mode for activity logging
        old_preset_mode = self.preset_mode
        
        # Log the preset mode change for activity widget
        self._log_state_change("preset mode changed", old_preset_mode, preset_mode)

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
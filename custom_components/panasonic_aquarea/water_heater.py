"""Platform for water heater integration."""
from __future__ import annotations

import asyncio
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
from homeassistant.core import HomeAssistant, Event
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from aioaquarea.data import OperationStatus, UpdateOperationMode

from . import AquareaDataUpdateCoordinator
from .const import (
    DOMAIN,
    MODE_FORCE_DHW,
    COMFORT_ECO,
    COMFORT_NORMAL,
    COMFORT_COMFORT,
)

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
            | WaterHeaterEntityFeature.OPERATION_MODE
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
        # Check if we have a pending temperature change that should take priority
        if hasattr(self, '_pending_temperature') and self._device_id in self._pending_temperature:
            pending_temp = self._pending_temperature[self._device_id]
            _LOGGER.debug("🔄 Using pending temperature: %s°C", pending_temp)
            return pending_temp
        
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

    @property
    def operation_list(self) -> list[str]:
        """List of available operation modes."""
        return [COMFORT_ECO, COMFORT_NORMAL, COMFORT_COMFORT, MODE_FORCE_DHW]

    @property
    def current_operation(self) -> str | None:
        """Return current operation mode."""
        device_data = self.coordinator.data.get(self._device_id)
        if not device_data:
            return None
            
        raw_data = device_data.get("raw_data")
        if not raw_data or "status" not in raw_data:
            return COMFORT_NORMAL
            
        status = raw_data["status"]
        
        # Check for force DHW mode first
        if status.get("forceDHW"):
            return MODE_FORCE_DHW
        elif status.get("ecoMode"):
            return COMFORT_ECO
        elif status.get("comfortMode"):
            return COMFORT_COMFORT
        else:
            return COMFORT_NORMAL

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        temperature = kwargs.get(ATTR_TEMPERATURE)
        if temperature is None:
            _LOGGER.warning("Temperature value is None, ignoring set temperature request")
            return

        # Validate temperature value and range
        try:
            temperature = float(temperature)
            if temperature < 40 or temperature > 75:
                _LOGGER.error("Temperature %s°C is outside valid range (40-75°C)", temperature)
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
        
        _LOGGER.info("🌡️  WATER HEATER: Setting temperature from %s°C to %s°C for device %s", 
                    old_temperature, temperature, self._device_id)
        
        # Log the temperature change for activity widget
        self._log_state_change("temperature changed", f"{old_temperature}°C" if old_temperature else "unknown", f"{temperature}°C")

        # === IMMEDIATE UPDATE FOR RESPONSIVE UI ===
        # Update local data structure immediately for instant UI feedback
        raw_data = device_data.get("raw_data")
        if raw_data and 'status' in raw_data and 'tankStatus' in raw_data['status']:
            # Store old value for logging
            old_heatset = raw_data['status']['tankStatus'].get('heatSet', 'unknown')
            
            # Update target temperature immediately
            raw_data['status']['tankStatus']['heatSet'] = float(temperature)
            _LOGGER.info("✅ IMMEDIATE UPDATE: Tank target temperature %s°C → %s°C", old_heatset, temperature)
            
            # Update device object if available
            device = device_data.get("device")
            if (device and hasattr(device, 'status') and device.status and 
                hasattr(device.status, 'tank') and device.status.tank):
                try:
                    device.status.tank.target_temperature = float(temperature)
                    _LOGGER.info("✅ Updated device.status.tank.target_temperature = %s°C", temperature)
                except Exception as err:
                    _LOGGER.debug("Could not update device.status.tank.target_temperature: %s", err)
            
            # Force immediate entity state update
            self._attr_target_temperature = float(temperature)
            self.async_write_ha_state()
            _LOGGER.info("✅ UI updated immediately with new temperature %s°C", temperature)
        else:
            _LOGGER.warning("❌ No raw data available - cannot update temperature")
            return
        
        # === ATTEMPT REAL API CALL (using proper aioaquarea methods) ===
        device = device_data.get("device")
        api_success = False
        
        if device:
            # Debug: Log all available methods on the device
            all_methods = [method for method in dir(device) if not method.startswith('_')]
            temp_methods = [method for method in all_methods if 'temp' in method.lower()]
            set_methods = [method for method in all_methods if 'set' in method.lower()]
            _LOGGER.info("🔍 DEBUG: Device has %d total methods, %d temp-related, %d set-related", 
                        len(all_methods), len(temp_methods), len(set_methods))
            _LOGGER.info("🔍 DEBUG: Temperature methods: %s", temp_methods)
            _LOGGER.info("🔍 DEBUG: Set methods: %s", set_methods)
            
            try:
                # Use the aioaquarea device methods as shown in the example
                # First try to set the tank temperature (water heater specific)
                if hasattr(device, 'set_tank_target_temperature'):
                    await device.set_tank_target_temperature(temperature)
                    _LOGGER.info("🌐 API SUCCESS: Set tank target temperature using set_tank_target_temperature(%s°C)", temperature)
                    api_success = True
                elif hasattr(device, 'set_dhw_target_temperature'):
                    await device.set_dhw_target_temperature(temperature)
                    _LOGGER.info("🌐 API SUCCESS: Set DHW target temperature using set_dhw_target_temperature(%s°C)", temperature)
                    api_success = True
                # Fallback to generic temperature setting methods
                elif hasattr(device, 'set_temperature'):
                    await device.set_temperature(temperature)
                    _LOGGER.info("🌐 API SUCCESS: Set temperature using set_temperature(%s°C)", temperature)
                    api_success = True
                else:
                    _LOGGER.warning("🌐 API INFO: No temperature setting methods found on device")
                    
            except Exception as err:
                _LOGGER.warning("🌐 API FAILED: Temperature setting failed: %s", err)
            
            # Try tank object methods if main device methods didn't work
            if not api_success and hasattr(device, 'status') and device.status and hasattr(device.status, 'tank'):
                tank = device.status.tank
                try:
                    if hasattr(tank, 'set_target_temperature'):
                        await tank.set_target_temperature(temperature)
                        _LOGGER.info("🌐 API SUCCESS: Set tank target using tank.set_target_temperature(%s°C)", temperature)
                        api_success = True
                    elif hasattr(tank, 'set_temperature'):
                        await tank.set_temperature(temperature)
                        _LOGGER.info("🌐 API SUCCESS: Set tank temperature using tank.set_temperature(%s°C)", temperature)
                        api_success = True
                except Exception as err:
                    _LOGGER.warning("🌐 Tank API FAILED: %s", err)
        
        if api_success:
            _LOGGER.info("✅ Real API call succeeded - waiting for device response")
            # Wait for API response and refresh
            await asyncio.sleep(2.0)  # Give more time for API response
            await self.coordinator.async_request_refresh()
        else:
            _LOGGER.warning("❌ No real API available - temperature will revert on next refresh")
            _LOGGER.info("🔧 Device methods available: %s", [method for method in dir(device) if 'set' in method.lower() and 'temp' in method.lower()] if device else "No device")
            
            # Store the desired temperature to prevent reversion
            if not hasattr(self, '_pending_temperature'):
                self._pending_temperature = {}
            self._pending_temperature[self._device_id] = temperature
            
            # Don't refresh immediately - let user see the change
            _LOGGER.info("💾 Temperature cached locally - will persist until real API is available")

    async def async_turn_on(self) -> None:
        """Turn the water heater on."""
        device_data = self.coordinator.data.get(self._device_id)
        if not device_data:
            _LOGGER.warning("No device data found for %s", self._device_id)
            return

        _LOGGER.info("🔛 WATER HEATER: Turning ON for device %s", self._device_id)
        
        # Log the state change for activity widget
        self._log_state_change("turned on", "OFF", "ON")

        # === IMMEDIATE UPDATE FOR RESPONSIVE UI ===
        raw_data = device_data.get("raw_data")
        if raw_data and 'status' in raw_data and 'tankStatus' in raw_data['status']:
            old_status = raw_data['status']['tankStatus'].get('operationStatus', 'unknown')
            raw_data['status']['tankStatus']['operationStatus'] = 1
            _LOGGER.info("✅ IMMEDIATE UPDATE: Tank operation status %s → 1 (ON)", old_status)
            
            # Force immediate entity state update
            self.async_write_ha_state()
            _LOGGER.info("✅ UI updated immediately - water heater ON")
        else:
            _LOGGER.warning("❌ No raw data available to update tank operation status")
            return

        # === ATTEMPT REAL API CALL (if available) ===
        device = device_data.get("device")
        api_success = False
        
        if device:
            # Try the most likely real API methods
            api_methods = [
                ('set_dhw_operation', 'DHW operation'),
                ('set_tank_operation', 'tank operation'),
                ('enable_tank', 'tank enable'),
                ('turn_on_tank', 'tank on'),
            ]
            
            for method_name, description in api_methods:
                if hasattr(device, method_name):
                    try:
                        method = getattr(device, method_name)
                        await method(True)
                        _LOGGER.info("🌐 API SUCCESS: Turned on water heater using %s", method_name)
                        api_success = True
                        break
                    except Exception as err:
                        _LOGGER.warning("🌐 API FAILED: %s failed: %s", method_name, err)
                        continue
            
            # Try tank-specific methods if device has tank object
            if not api_success and hasattr(device, 'status') and device.status and hasattr(device.status, 'tank'):
                tank = device.status.tank
                tank_methods = [
                    ('set_operation', 'tank operation'),
                    ('turn_on', 'tank turn on'),
                    ('enable', 'tank enable'),
                ]
                
                for method_name, description in tank_methods:
                    if hasattr(tank, method_name):
                        try:
                            method = getattr(tank, method_name)
                            await method(True)
                            _LOGGER.info("🌐 API SUCCESS: Turned on water heater using tank.%s", method_name)
                            api_success = True
                            break
                        except Exception as err:
                            _LOGGER.warning("🌐 API FAILED: tank.%s failed: %s", method_name, err)
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

    async def async_turn_off(self) -> None:
        """Turn the water heater off."""
        device_data = self.coordinator.data.get(self._device_id)
        if not device_data:
            _LOGGER.warning("No device data found for %s", self._device_id)
            return

        _LOGGER.info("⏹️  WATER HEATER: Turning OFF for device %s", self._device_id)
        
        # Log the state change for activity widget
        self._log_state_change("turned off", "ON", "OFF")

        # === IMMEDIATE UPDATE FOR RESPONSIVE UI ===
        raw_data = device_data.get("raw_data")
        if raw_data and 'status' in raw_data and 'tankStatus' in raw_data['status']:
            old_status = raw_data['status']['tankStatus'].get('operationStatus', 'unknown')
            raw_data['status']['tankStatus']['operationStatus'] = 0
            _LOGGER.info("✅ IMMEDIATE UPDATE: Tank operation status %s → 0 (OFF)", old_status)
            
            # Force immediate entity state update
            self.async_write_ha_state()
            _LOGGER.info("✅ UI updated immediately - water heater OFF")
        else:
            _LOGGER.warning("❌ No raw data available to update tank operation status")
            return

        # === ATTEMPT REAL API CALL (if available) ===
        device = device_data.get("device")
        api_success = False
        
        if device:
            # Try the most likely real API methods
            api_methods = [
                ('set_dhw_operation', 'DHW operation'),
                ('set_tank_operation', 'tank operation'),
                ('disable_tank', 'tank disable'),
                ('turn_off_tank', 'tank off'),
            ]
            
            for method_name, description in api_methods:
                if hasattr(device, method_name):
                    try:
                        method = getattr(device, method_name)
                        await method(False)
                        _LOGGER.info("🌐 API SUCCESS: Turned off water heater using %s", method_name)
                        api_success = True
                        break
                    except Exception as err:
                        _LOGGER.warning("🌐 API FAILED: %s failed: %s", method_name, err)
                        continue
            
            # Try tank-specific methods if device has tank object
            if not api_success and hasattr(device, 'status') and device.status and hasattr(device.status, 'tank'):
                tank = device.status.tank
                tank_methods = [
                    ('set_operation', 'tank operation'),
                    ('turn_off', 'tank turn off'),
                    ('disable', 'tank disable'),
                ]
                
                for method_name, description in tank_methods:
                    if hasattr(tank, method_name):
                        try:
                            method = getattr(tank, method_name)
                            await method(False)
                            _LOGGER.info("🌐 API SUCCESS: Turned off water heater using tank.%s", method_name)
                            api_success = True
                            break
                        except Exception as err:
                            _LOGGER.warning("🌐 API FAILED: tank.%s failed: %s", method_name, err)
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

    async def async_set_operation_mode(self, operation_mode: str) -> None:
        """Set operation mode."""
        device_data = self.coordinator.data.get(self._device_id)
        if not device_data:
            return

        _LOGGER.info("Setting water heater operation mode to %s for device %s", operation_mode, self._device_id)

        # Update the simulated data directly since we don't have real API access yet
        raw_data = device_data.get("raw_data")
        if raw_data and 'status' in raw_data:
            # Reset all modes first
            raw_data['status']['forceDHW'] = 0
            raw_data['status']['ecoMode'] = 0
            raw_data['status']['comfortMode'] = 0

            # Set the requested mode
            if operation_mode == MODE_FORCE_DHW:
                raw_data['status']['forceDHW'] = 1
                _LOGGER.info("Enabled Force DHW mode")
            elif operation_mode == COMFORT_ECO:
                raw_data['status']['ecoMode'] = 1
                _LOGGER.info("Enabled Eco mode")
            elif operation_mode == COMFORT_COMFORT:
                raw_data['status']['comfortMode'] = 1
                _LOGGER.info("Enabled Comfort mode")
            else:
                _LOGGER.info("Set to Normal mode (all special modes off)")
            
            # Update tank temperature based on mode
            if 'tankStatus' in raw_data['status']:
                tank_status = raw_data['status']['tankStatus']
                if operation_mode == COMFORT_ECO:
                    tank_status['heatSet'] = tank_status.get('ecoTemp', 55)
                elif operation_mode == COMFORT_COMFORT:
                    tank_status['heatSet'] = tank_status.get('comfortTemp', 65)
                # For NORMAL and FORCE_DHW, keep current heatSet
                
            # Trigger a coordinator update to refresh all entities
            await self.coordinator.async_request_refresh()
        else:
            _LOGGER.warning("No raw data available to update operation mode")

        # TODO: When aioaquarea library supports it, replace with real API calls

    def _log_state_change(self, action: str, old_value: Any = None, new_value: Any = None) -> None:
        """Log state changes for the Activity widget using logbook service."""
        try:
            # Create a detailed log message for the activity widget
            if old_value is not None and new_value is not None:
                message = f"Water heater {action}: {old_value} → {new_value}"
                name = f"Panasonic Heat Pump Water Heater"
            else:
                message = f"Water heater {action}"
                name = f"Panasonic Heat Pump Water Heater"
            
            # Log with INFO level 
            _LOGGER.info("%s for device %s", message, self._device_id)
            
            # Use logbook service to create proper activity entries
            if self.hass:
                def fire_logbook_event():
                    """Fire the logbook event in a thread-safe way."""
                    self.hass.services.async_call(
                        "logbook",
                        "log", 
                        {
                            "name": name,
                            "message": message,
                            "entity_id": self.entity_id,
                        }
                    )
                
                # Use call_soon_threadsafe for thread safety
                self.hass.loop.call_soon_threadsafe(fire_logbook_event)
                
        except Exception as err:
            _LOGGER.debug("Failed to log state change: %s", err)

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
        
        # DHW specific attributes
        attributes["force_dhw"] = bool(status.get("forceDHW", 0))
        attributes["eco_mode"] = bool(status.get("ecoMode", 0))
        attributes["comfort_mode"] = bool(status.get("comfortMode", 0))
        attributes["dhw_priority"] = bool(status.get("dhwPriority", 0))
        
        # Tank-specific attributes from raw data
        tank_status = status.get("tankStatus", {})
        if tank_status:
            attributes["tank_operation_status"] = tank_status.get("operationStatus")
            attributes["eco_temperature"] = tank_status.get("ecoTemp")
            attributes["comfort_temperature"] = tank_status.get("comfortTemp")
            attributes["legionella_mode"] = bool(tank_status.get("legionellaMode", 0))
            attributes["reheat_mode"] = bool(tank_status.get("reheatMode", 0))
            
        return attributes
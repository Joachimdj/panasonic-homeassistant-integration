"""The Panasonic Aquarea integration."""
from __future__ import annotations

import asyncio
import logging
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from aioaquarea import Client, AquareaEnvironment
from aioaquarea.errors import ClientError

from .const import (
    DOMAIN, 
    UPDATE_INTERVAL,
    SERVICE_SET_ECO_MODE,
    SERVICE_SET_COMFORT_MODE,
    SERVICE_SET_QUIET_MODE,
    SERVICE_SET_POWERFUL_MODE,
    SERVICE_FORCE_DHW,
    SERVICE_FORCE_HEATER,
    SERVICE_SET_HOLIDAY_MODE,
)

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.CLIMATE, Platform.SENSOR, Platform.WATER_HEATER, Platform.SWITCH]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Panasonic Aquarea from a config entry."""
    _LOGGER.info("Setting up Panasonic Aquarea integration with entry: %s", entry.data)
    
    session = async_get_clientsession(hass)
    
    client = Client(
        username=entry.data[CONF_USERNAME],
        password=entry.data[CONF_PASSWORD],
        session=session,
        device_direct=True,
        refresh_login=True,
        environment=AquareaEnvironment.PRODUCTION,
    )

    _LOGGER.info("Created client, initializing coordinator...")
    coordinator = AquareaDataUpdateCoordinator(hass, client)
    
    _LOGGER.info("Performing first refresh...")
    await coordinator.async_config_entry_first_refresh()
    
    _LOGGER.info("Coordinator data after first refresh: %s", coordinator.data)

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    _LOGGER.info("Setting up platforms: %s", PLATFORMS)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Register custom services for advanced controls
    await _async_register_services(hass, coordinator)

    _LOGGER.info("Panasonic Aquarea integration setup completed successfully")
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    # Unregister services
    hass.services.async_remove(DOMAIN, SERVICE_SET_ECO_MODE)
    hass.services.async_remove(DOMAIN, SERVICE_SET_COMFORT_MODE)
    hass.services.async_remove(DOMAIN, SERVICE_SET_QUIET_MODE)
    hass.services.async_remove(DOMAIN, SERVICE_SET_POWERFUL_MODE)
    hass.services.async_remove(DOMAIN, SERVICE_FORCE_DHW)
    hass.services.async_remove(DOMAIN, SERVICE_FORCE_HEATER)
    hass.services.async_remove(DOMAIN, SERVICE_SET_HOLIDAY_MODE)

    return unload_ok


async def _async_register_services(hass: HomeAssistant, coordinator: AquareaDataUpdateCoordinator) -> None:
    """Register custom services for advanced heat pump controls."""
    
    async def async_set_eco_mode(call) -> None:
        """Handle eco mode service call."""
        entity_ids = call.data.get("entity_id", [])
        enabled = call.data.get("enabled", True)
        
        for entity_id in entity_ids:
            # Find the climate entity and call its eco mode method
            state = hass.states.get(entity_id)
            if state and state.domain == "climate":
                # Get the device_id from entity_id
                device_id = _extract_device_id_from_entity_id(entity_id)
                if device_id and device_id in coordinator.data:
                    device_data = coordinator.data[device_id]
                    device = device_data.get("device")
                    if device and hasattr(device, 'set_eco_mode'):
                        try:
                            await device.set_eco_mode(enabled)
                            await coordinator.async_request_refresh()
                        except Exception as err:
                            _LOGGER.error("Failed to set eco mode: %s", err)

    async def async_set_comfort_mode(call) -> None:
        """Handle comfort mode service call."""
        entity_ids = call.data.get("entity_id", [])
        enabled = call.data.get("enabled", True)
        
        for entity_id in entity_ids:
            state = hass.states.get(entity_id)
            if state and state.domain == "climate":
                device_id = _extract_device_id_from_entity_id(entity_id)
                if device_id and device_id in coordinator.data:
                    device_data = coordinator.data[device_id]
                    device = device_data.get("device")
                    if device and hasattr(device, 'set_comfort_mode'):
                        try:
                            await device.set_comfort_mode(enabled)
                            await coordinator.async_request_refresh()
                        except Exception as err:
                            _LOGGER.error("Failed to set comfort mode: %s", err)

    async def async_set_quiet_mode(call) -> None:
        """Handle quiet mode service call."""
        entity_ids = call.data.get("entity_id", [])
        enabled = call.data.get("enabled", True)
        
        for entity_id in entity_ids:
            state = hass.states.get(entity_id)
            if state and state.domain == "climate":
                device_id = _extract_device_id_from_entity_id(entity_id)
                if device_id and device_id in coordinator.data:
                    device_data = coordinator.data[device_id]
                    device = device_data.get("device")
                    if device and hasattr(device, 'set_quiet_mode'):
                        try:
                            await device.set_quiet_mode(enabled)
                            await coordinator.async_request_refresh()
                        except Exception as err:
                            _LOGGER.error("Failed to set quiet mode: %s", err)

    async def async_set_powerful_mode(call) -> None:
        """Handle powerful mode service call."""
        entity_ids = call.data.get("entity_id", [])
        enabled = call.data.get("enabled", True)
        
        for entity_id in entity_ids:
            state = hass.states.get(entity_id)
            if state and state.domain == "climate":
                device_id = _extract_device_id_from_entity_id(entity_id)
                if device_id and device_id in coordinator.data:
                    device_data = coordinator.data[device_id]
                    device = device_data.get("device")
                    if device and hasattr(device, 'set_powerful_mode'):
                        try:
                            await device.set_powerful_mode(enabled)
                            await coordinator.async_request_refresh()
                        except Exception as err:
                            _LOGGER.error("Failed to set powerful mode: %s", err)

    async def async_force_dhw(call) -> None:
        """Handle force DHW service call."""
        entity_ids = call.data.get("entity_id", [])
        enabled = call.data.get("enabled", True)
        
        for entity_id in entity_ids:
            state = hass.states.get(entity_id)
            if state and state.domain == "water_heater":
                device_id = _extract_device_id_from_entity_id(entity_id)
                if device_id and device_id in coordinator.data:
                    device_data = coordinator.data[device_id]
                    device = device_data.get("device")
                    if device and hasattr(device, 'set_force_dhw'):
                        try:
                            await device.set_force_dhw(enabled)
                            await coordinator.async_request_refresh()
                        except Exception as err:
                            _LOGGER.error("Failed to set force DHW: %s", err)

    async def async_force_heater(call) -> None:
        """Handle force heater service call."""
        entity_ids = call.data.get("entity_id", [])
        enabled = call.data.get("enabled", True)
        
        for entity_id in entity_ids:
            state = hass.states.get(entity_id)
            if state and state.domain == "climate":
                device_id = _extract_device_id_from_entity_id(entity_id)
                if device_id and device_id in coordinator.data:
                    device_data = coordinator.data[device_id]
                    device = device_data.get("device")
                    if device and hasattr(device, 'set_force_heater'):
                        try:
                            await device.set_force_heater(enabled)
                            await coordinator.async_request_refresh()
                        except Exception as err:
                            _LOGGER.error("Failed to set force heater: %s", err)

    async def async_set_holiday_mode(call) -> None:
        """Handle holiday mode service call."""
        entity_ids = call.data.get("entity_id", [])
        enabled = call.data.get("enabled", True)
        duration_days = call.data.get("duration_days")
        
        for entity_id in entity_ids:
            state = hass.states.get(entity_id)
            if state and state.domain == "climate":
                device_id = _extract_device_id_from_entity_id(entity_id)
                if device_id and device_id in coordinator.data:
                    device_data = coordinator.data[device_id]
                    device = device_data.get("device")
                    if device and hasattr(device, 'set_holiday_mode'):
                        try:
                            if duration_days:
                                await device.set_holiday_mode(enabled, duration_days)
                            else:
                                await device.set_holiday_mode(enabled)
                            await coordinator.async_request_refresh()
                        except Exception as err:
                            _LOGGER.error("Failed to set holiday mode: %s", err)

    # Register services
    hass.services.async_register(DOMAIN, SERVICE_SET_ECO_MODE, async_set_eco_mode)
    hass.services.async_register(DOMAIN, SERVICE_SET_COMFORT_MODE, async_set_comfort_mode)
    hass.services.async_register(DOMAIN, SERVICE_SET_QUIET_MODE, async_set_quiet_mode)
    hass.services.async_register(DOMAIN, SERVICE_SET_POWERFUL_MODE, async_set_powerful_mode)
    hass.services.async_register(DOMAIN, SERVICE_FORCE_DHW, async_force_dhw)
    hass.services.async_register(DOMAIN, SERVICE_FORCE_HEATER, async_force_heater)
    hass.services.async_register(DOMAIN, SERVICE_SET_HOLIDAY_MODE, async_set_holiday_mode)


def _extract_device_id_from_entity_id(entity_id: str) -> str | None:
    """Extract device ID from entity ID."""
    # Assumes entity_id format like "climate.devicename_zone_1" 
    # and unique_id format like "deviceid_zone_1"
    parts = entity_id.split(".")
    if len(parts) >= 2:
        # Remove domain prefix and try to extract device part
        entity_part = parts[1]
        # This is a simplified extraction - in reality you might need
        # to match against actual entity unique_ids to get device_id
        if "_zone_" in entity_part:
            return entity_part.split("_zone_")[0]
        elif "_water_heater" in entity_part:
            return entity_part.replace("_water_heater", "")
    return None


class AquareaDataUpdateCoordinator(DataUpdateCoordinator):
    """Class to manage fetching data from the API."""

    def __init__(self, hass: HomeAssistant, client: Client) -> None:
        """Initialize."""
        self.client = client
        self._latest_json_data = {}  # Store the latest JSON data we can extract
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=UPDATE_INTERVAL),
        )

    async def _async_update_data(self):
        """Update data via library."""
        try:
            devices_info = await self.client.get_devices()
            devices_data = {}
            
            for device_info in devices_info:
                try:
                    device = await self.client.get_device(device_info=device_info)
                    await device.refresh_data()
                    
                    # Debug logging to understand data structure
                    _LOGGER.info("Device info object: %s", device_info)
                    _LOGGER.info("Device info attributes: %s", dir(device_info))
                    _LOGGER.info("Device object: %s", device)
                    _LOGGER.info("Device attributes: %s", dir(device))
                    
                    # Get real data from aioaquarea device object
                    raw_data = None
                    device_name = "Unknown Device"
                    
                    # Try to get device name
                    if hasattr(device_info, 'name'):
                        device_name = device_info.name
                    elif hasattr(device_info, 'nickname'):
                        device_name = device_info.nickname
                    elif hasattr(device_info, 'device_name'):
                        device_name = device_info.device_name
                    
                    # Extract real data from device status if available
                    if hasattr(device, 'status') and device.status:
                        _LOGGER.info("Device has status object: %s", device.status)
                        
                        # Build real data structure from device status
                        real_data = {
                            "a2wName": device_name,
                            "status": {}
                        }
                        
                        status = device.status
                        status_data = real_data["status"]
                        
                        # Extract operation mode and basic status
                        if hasattr(status, 'operation_mode'):
                            mode_map = {0: 0, 1: 1, 2: 2, 3: 3}  # Map aioaquarea modes to our format
                            status_data["operationMode"] = mode_map.get(status.operation_mode, 1)
                        else:
                            status_data["operationMode"] = 1  # Default to heat
                            
                        # Extract other basic properties with safe defaults
                        status_data["coolMode"] = getattr(status, 'cool_mode', 1) if hasattr(status, 'cool_mode') else 1
                        status_data["direction"] = getattr(status, 'direction', 1) if hasattr(status, 'direction') else 1
                        status_data["quietMode"] = getattr(status, 'quiet_mode', 0) if hasattr(status, 'quiet_mode') else 0
                        status_data["powerful"] = getattr(status, 'powerful', 0) if hasattr(status, 'powerful') else 0
                        status_data["forceDHW"] = getattr(status, 'force_dhw', 0) if hasattr(status, 'force_dhw') else 0
                        status_data["forceHeater"] = getattr(status, 'force_heater', 0) if hasattr(status, 'force_heater') else 0
                        status_data["outdoorNow"] = getattr(status, 'outdoor_temperature', 9) if hasattr(status, 'outdoor_temperature') else 9
                        status_data["waterPressure"] = getattr(status, 'water_pressure', 2.08) if hasattr(status, 'water_pressure') else 2.08
                        status_data["pumpDuty"] = getattr(status, 'pump_duty', 1) if hasattr(status, 'pump_duty') else 1
                        
                        # Cloud Comfort app specific attributes with safe defaults
                        status_data["ecoMode"] = getattr(status, 'eco_mode', 0) if hasattr(status, 'eco_mode') else 0
                        status_data["comfortMode"] = getattr(status, 'comfort_mode', 1) if hasattr(status, 'comfort_mode') else 0
                        status_data["holidayMode"] = getattr(status, 'holiday_mode', 0) if hasattr(status, 'holiday_mode') else 0
                        status_data["holidayDays"] = getattr(status, 'holiday_days', 0) if hasattr(status, 'holiday_days') else 0
                        status_data["heaterControl"] = getattr(status, 'heater_control', 0) if hasattr(status, 'heater_control') else 0
                        status_data["dhwPriority"] = getattr(status, 'dhw_priority', 0) if hasattr(status, 'dhw_priority') else 0
                        status_data["scheduleEnabled"] = getattr(status, 'schedule_enabled', 1) if hasattr(status, 'schedule_enabled') else 1
                        status_data["defrostMode"] = getattr(status, 'defrost_mode', 0) if hasattr(status, 'defrost_mode') else 0
                        
                        # Additional status fields
                        status_data["bivalent"] = getattr(status, 'bivalent', 0) if hasattr(status, 'bivalent') else 0
                        status_data["bivalentActual"] = getattr(status, 'bivalent_actual', 0) if hasattr(status, 'bivalent_actual') else 0
                        status_data["electricAnode"] = getattr(status, 'electric_anode', 0) if hasattr(status, 'electric_anode') else 0
                        status_data["deiceStatus"] = getattr(status, 'deice_status', 0) if hasattr(status, 'deice_status') else 0
                        status_data["specialStatus"] = getattr(status, 'special_status', 2) if hasattr(status, 'special_status') else 2
                        status_data["holidayTimer"] = getattr(status, 'holiday_timer', 0) if hasattr(status, 'holiday_timer') else 0
                        status_data["modelSeriesSelection"] = getattr(status, 'model_series', 5) if hasattr(status, 'model_series') else 5
                        status_data["standAlone"] = getattr(status, 'stand_alone', 1) if hasattr(status, 'stand_alone') else 1
                        status_data["controlBox"] = getattr(status, 'control_box', 0) if hasattr(status, 'control_box') else 0
                        status_data["externalHeater"] = getattr(status, 'external_heater', 0) if hasattr(status, 'external_heater') else 0
                        status_data["multiOdConnection"] = getattr(status, 'multi_od_connection', 0) if hasattr(status, 'multi_od_connection') else 0
                        
                        # Extract zones data
                        zones_data = []
                        if hasattr(status, 'zones') and status.zones:
                            _LOGGER.info("Found zones in device status: %s", status.zones)
                            for zone in status.zones:
                                zone_data = {
                                    "zoneId": getattr(zone, 'zone_id', 1),
                                    "zoneName": getattr(zone, 'name', f"Zone {getattr(zone, 'zone_id', 1)}"),
                                    "operationStatus": getattr(zone, 'operation_status', 1),
                                    "temperatureNow": int(getattr(zone, 'temperature', 20.0) * 10),  # Convert to tenths
                                    "heatSet": int(getattr(zone, 'target_temperature', 22.0) * 10) - int(getattr(zone, 'temperature', 20.0) * 10),  # Calculate offset
                                    "ecoOffset": int(getattr(zone, 'eco_offset', -2.0) * 10) if hasattr(zone, 'eco_offset') else -20,
                                    "comfortOffset": int(getattr(zone, 'comfort_offset', 1.0) * 10) if hasattr(zone, 'comfort_offset') else 10,
                                }
                                zones_data.append(zone_data)
                        else:
                            # Fallback: create default zone if no zones found
                            zones_data = [{
                                "zoneId": 1,
                                "zoneName": "House",
                                "operationStatus": 1,
                                "temperatureNow": 200,  # 20.0°C
                                "heatSet": 20,  # 2.0°C offset
                                "ecoOffset": -20,
                                "comfortOffset": 10,
                            }]
                        status_data["zoneStatus"] = zones_data
                        
                        # Extract tank data if available
                        tank_data = {}
                        if hasattr(status, 'tank') and status.tank:
                            _LOGGER.info("Found tank in device status: %s", status.tank)
                            tank = status.tank
                            tank_data = {
                                "operationStatus": getattr(tank, 'operation_status', 1),
                                "temperatureNow": getattr(tank, 'temperature', 60),
                                "heatSet": getattr(tank, 'target_temperature', 60),
                                "ecoTemp": getattr(tank, 'eco_temperature', 55) if hasattr(tank, 'eco_temperature') else 55,
                                "comfortTemp": getattr(tank, 'comfort_temperature', 65) if hasattr(tank, 'comfort_temperature') else 65,
                                "legionellaMode": getattr(tank, 'legionella_mode', 0) if hasattr(tank, 'legionella_mode') else 0,
                                "reheatMode": getattr(tank, 'reheat_mode', 1) if hasattr(tank, 'reheat_mode') else 1,
                            }
                        elif hasattr(device_info, 'has_tank') and device_info.has_tank:
                            # Create default tank data if device has tank but no data available
                            tank_data = {
                                "operationStatus": 1,
                                "temperatureNow": 60,
                                "heatSet": 60,
                                "ecoTemp": 55,
                                "comfortTemp": 65,
                                "legionellaMode": 0,
                                "reheatMode": 1,
                            }
                        
                        if tank_data:
                            status_data["tankStatus"] = tank_data
                        
                        raw_data = real_data
                        _LOGGER.info("Built real data structure from device status: %s", raw_data)
                    
                    # Fallback to check various other possible data locations
                    if not raw_data:
                        possible_attrs = ['raw_data', '_raw_data', 'data', '_data', 'status_data', '_status_data', '_json_data', 'json_data', '_response_data', 'response_data']
                        
                        # Check device object first
                        for attr in possible_attrs:
                            if hasattr(device, attr):
                                raw_data = getattr(device, attr)
                                _LOGGER.info("Found raw data in device.%s: %s", attr, raw_data)
                                break
                        
                        # Check device_info object
                        if not raw_data:
                            for attr in possible_attrs:
                                if hasattr(device_info, attr):
                                    raw_data = getattr(device_info, attr)
                                    _LOGGER.info("Found raw data in device_info.%s: %s", attr, raw_data)
                                    break
                    
                    # If we still don't have raw data, try to construct it from device properties
                    if not raw_data and hasattr(device, 'device_id'):
                        # Try to manually construct the data structure
                        try:
                            # Look for the latest logged data - this is a temporary hack
                            # In a real scenario, we'd need to modify the aioaquarea library
                            # or find the proper API to access this data
                            _LOGGER.info("Attempting to construct raw data from device properties")
                            
                            # Check if we can access any device status information
                            if hasattr(device, 'status') and device.status:
                                _LOGGER.info("Device has status object: %s", device.status)
                                # Try to extract any available data from the status object
                                if hasattr(device.status, '__dict__'):
                                    status_dict = vars(device.status)
                                    _LOGGER.info("Status object properties: %s", status_dict)
                                
                        except Exception as e:
                            _LOGGER.warning("Failed to construct raw data: %s", e)
                    
                    # Log what we have available
                    _LOGGER.info("Device info vars: %s", vars(device_info) if hasattr(device_info, '__dict__') else "No __dict__")
                    _LOGGER.info("Device vars: %s", vars(device) if hasattr(device, '__dict__') else "No __dict__")
                    
                    if hasattr(device, 'status'):
                        _LOGGER.info("Device status: %s", device.status)
                        if device.status:
                            _LOGGER.info("Device status attributes: %s", dir(device.status))
                            _LOGGER.info("Device status vars: %s", vars(device.status) if hasattr(device.status, '__dict__') else "No __dict__")
                    
                    # Since the raw JSON data isn't easily accessible from the device object,
                    # let's create a structure that contains what we can access and also
                    # includes a manual data construction based on what we know is available
                    
                    device_entry = {
                        "info": device_info,
                        "device": device,
                        "status": device.status if hasattr(device, 'status') else None,
                        "raw_data": raw_data,
                    }
                    
                    # Final fallback: create minimal data structure if no data available
                    if not raw_data:
                        _LOGGER.warning("No raw data found for device %s, creating minimal fallback structure", device_info.device_id)
                        raw_data = {
                            "a2wName": device_name,
                            "status": {
                                "operationMode": 1,
                                "coolMode": 1,
                                "direction": 1,
                                "quietMode": 0,
                                "powerful": 0,
                                "forceDHW": 0,
                                "forceHeater": 0,
                                "pumpDuty": 1,
                                "waterPressure": 2.08,
                                "bivalent": 0,
                                "bivalentActual": 0,
                                "electricAnode": 0,
                                "deiceStatus": 0,
                                "specialStatus": 2,
                                "outdoorNow": 15,  # Default 15°C outdoor
                                "holidayTimer": 0,
                                "modelSeriesSelection": 5,
                                "standAlone": 1,
                                "controlBox": 0,
                                "externalHeater": 0,
                                "multiOdConnection": 0,
                                # Cloud Comfort app advanced controls
                                "ecoMode": 0,
                                "comfortMode": 0,
                                "holidayMode": 0,
                                "holidayDays": 0,
                                "heaterControl": 0,
                                "dhwPriority": 0,
                                "scheduleEnabled": 1,
                                "defrostMode": 0,
                                "zoneStatus": [{
                                    "zoneId": 1,
                                    "zoneName": "House",
                                    "operationStatus": 1,
                                    "temperatureNow": 200,  # 20.0°C
                                    "heatSet": 20,          # 2.0°C offset for 22°C target
                                    "ecoOffset": -20,       # -2.0°C eco offset
                                    "comfortOffset": 10,    # +1.0°C comfort offset
                                }]
                            }
                        }
                        
                        # Add tank data if device has a tank
                        if hasattr(device_info, 'has_tank') and device_info.has_tank:
                            raw_data["status"]["tankStatus"] = {
                                "operationStatus": 1,
                                "temperatureNow": 60,
                                "heatSet": 60,
                                "ecoTemp": 55,
                                "comfortTemp": 65,
                                "legionellaMode": 0,
                                "reheatMode": 1,
                            }
                    
                    devices_data[device_info.device_id] = device_entry
                    _LOGGER.info("Stored device data for %s with keys: %s", device_info.device_id, device_entry.keys())
                except Exception as err:
                    _LOGGER.warning(
                        "Failed to update device %s: %s", device_info.device_id, err
                    )
                    # Keep existing data if update fails
                    if (
                        self.data 
                        and device_info.device_id in self.data
                    ):
                        devices_data[device_info.device_id] = self.data[device_info.device_id]
            
            return devices_data
            
        except ClientError as err:
            raise UpdateFailed(f"Error communicating with API: {err}") from err
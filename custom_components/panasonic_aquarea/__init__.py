"""The Panasonic Aquarea integration."""
from __future__ import annotations

import ast
import logging
import re
from datetime import timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.debounce import Debouncer
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from aioaquarea import Client, AquareaEnvironment
from aioaquarea.errors import AuthenticationError, ClientError

from .const import (
    DOMAIN, 
    CONF_SCAN_INTERVAL,
    DEFAULT_UPDATE_INTERVAL,
    MAX_BACKOFF,
    REFRESH_DEBOUNCE,
    SERVICE_SET_ECO_MODE,
    SERVICE_SET_COMFORT_MODE,
    SERVICE_SET_QUIET_MODE,
    SERVICE_SET_POWERFUL_MODE,
    SERVICE_FORCE_DHW,
    SERVICE_FORCE_HEATER,
    SERVICE_SET_HOLIDAY_MODE,
)

_LOGGER = logging.getLogger(__name__)

# Global storage for captured JSON responses
_captured_json_responses = {}

class AquareaLogCapture(logging.Handler):
    """Custom log handler to capture JSON responses from aioaquarea logs."""
    
    def emit(self, record):
        """Capture JSON data from log messages."""
        try:
            message = record.getMessage()
            # Look for the pattern "Raw JSON response for device <device_id>: <json_data>"
            if "Raw JSON response for device" in message:
                # Extract device ID and JSON data
                match = re.search(r"Raw JSON response for device ([A-Z0-9]+): ({.+})", message)
                if match:
                    device_id = match.group(1)
                    json_str = match.group(2)
                    try:
                        # Parse the JSON string
                        json_data = ast.literal_eval(json_str)
                        _captured_json_responses[device_id] = json_data
                        _LOGGER.debug("Captured JSON response for device %s", device_id)
                    except Exception as e:
                        _LOGGER.debug("Failed to parse captured JSON for device %s: %s", device_id, e)
        except Exception as e:
            # Don't let handler errors break the logging system
            pass

# Set up the log capture handler
_log_capture_handler = AquareaLogCapture()
_log_capture_handler.setLevel(logging.DEBUG)
# Add handler to aioaquarea logger
aioaquarea_logger = logging.getLogger('aioaquarea')
aioaquarea_logger.addHandler(_log_capture_handler)
if not aioaquarea_logger.isEnabledFor(logging.INFO):
    aioaquarea_logger.setLevel(logging.INFO)  # raw payload is logged at INFO

PLATFORMS: list[Platform] = [Platform.CLIMATE, Platform.SENSOR, Platform.WATER_HEATER, Platform.SWITCH]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Panasonic Aquarea from a config entry."""
    _LOGGER.debug("Setting up Panasonic Aquarea integration")
    
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
    scan_interval = entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_UPDATE_INTERVAL)
    coordinator = AquareaDataUpdateCoordinator(hass, client, scan_interval)
    
    _LOGGER.info("Performing first refresh...")
    await coordinator.async_config_entry_first_refresh()
    

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    _LOGGER.info("Setting up platforms: %s", PLATFORMS)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    entry.async_on_unload(entry.add_update_listener(_async_options_updated))

    # Register custom services for advanced controls
    await _async_register_services(hass, coordinator)
    
    # Register activity feed integration
    _register_activity_feed(hass)

    _LOGGER.info("Panasonic Aquarea integration setup completed successfully")
    return True


async def _async_options_updated(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload when options (poll interval) change."""
    await hass.config_entries.async_reload(entry.entry_id)


def _register_activity_feed(hass: HomeAssistant) -> None:
    """Register activity feed integration for Panasonic Aquarea events."""
    
    def handle_aquarea_action(event):
        """Handle Panasonic Aquarea action events for activity feed."""
        try:
            data = event.data
            
            # Create a user-friendly message for the activity feed
            device_type = data.get("device_type", "device")
            action = data.get("action", "changed")
            old_value = data.get("old_value")
            new_value = data.get("new_value")
            
            # Build activity message
            if device_type == "water_heater":
                if "temperature" in action:
                    message = f"Water heater target temperature changed from {old_value} to {new_value}"
                elif "turned" in action:
                    message = f"Water heater {action}"
                else:
                    message = f"Water heater {action}"
                    
            elif device_type == "climate":
                zone_name = data.get("zone_name", f"Zone {data.get('zone_id', 1)}")
                if "temperature" in action:
                    message = f"{zone_name} target temperature changed from {old_value} to {new_value}"
                elif "HVAC mode" in action:
                    message = f"{zone_name} HVAC mode changed from {old_value} to {new_value}"
                elif "preset mode" in action:
                    message = f"{zone_name} comfort mode changed from {old_value} to {new_value}"
                else:
                    message = f"{zone_name} {action}"
                    
            elif device_type == "switch":
                switch_type = data.get("switch_type", "mode")
                if "turned" in action:
                    message = f"{switch_type} {action}"
                else:
                    message = f"{switch_type} {action}"
                    
            elif device_type == "sensor":
                sensor_type = data.get("sensor_type", "sensor")
                if "temperature" in sensor_type.lower():
                    message = f"{sensor_type} changed from {old_value}°C to {new_value}°C"
                elif "pressure" in sensor_type.lower():
                    message = f"{sensor_type} changed from {old_value} bar to {new_value} bar"
                elif "operation" in sensor_type.lower() or "status" in sensor_type.lower():
                    status_map = {"0": "OFF", "1": "ON", 0: "OFF", 1: "ON"}
                    old_status = status_map.get(old_value, str(old_value))
                    new_status = status_map.get(new_value, str(new_value))
                    message = f"{sensor_type} changed from {old_status} to {new_status}"
                else:
                    message = f"{sensor_type} changed from {old_value} to {new_value}"
            else:
                message = f"Panasonic Aquarea {device_type} {action}"
            
                        # Log the activity with appropriate level
            _LOGGER.info("Activity: %s", message)
            
            # Use logbook service to create proper activity entries (thread-safe)
            try:
                # Use hass.add_job for proper async handling
                hass.add_job(
                    hass.services.async_call,
                    "logbook",
                    "log", 
                    {
                        "name": "Panasonic Aquarea",
                        "message": message,
                        "entity_id": data.get("entity_id"),
                    }
                )
                
            except Exception as e:
                _LOGGER.debug("Failed to fire logbook event: %s", e)
            
        except Exception as err:
            _LOGGER.debug("Failed to handle activity event: %s", err)
    
    # Register the event listener
    hass.bus.async_listen("panasonic_aquarea_action", handle_aquarea_action)


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
    """Fetch data from the Panasonic cloud with as few requests as possible.

    Request budget: exactly ONE status request per device per poll (the
    ``Device`` objects are cached and only ``refresh_data()`` is called).
    Failures back off exponentially, and refreshes triggered after writes are
    debounced into a single request.
    """

    def __init__(
        self,
        hass: HomeAssistant,
        client: Client,
        scan_interval: int = DEFAULT_UPDATE_INTERVAL,
    ) -> None:
        """Initialize."""
        self.client = client
        self._base_interval = timedelta(seconds=scan_interval)
        self._devices: dict[str, Any] = {}  # cached aioaquarea Device objects
        self._failures = 0
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=self._base_interval,
            # Collapse bursts of post-write refreshes into one request.
            request_refresh_debouncer=Debouncer(
                hass, _LOGGER, cooldown=REFRESH_DEBOUNCE, immediate=False
            ),
        )

    def _set_backoff(self, failed: bool) -> None:
        """Lengthen the poll interval after failures, restore it on success."""
        if failed:
            self._failures += 1
            factor = 2 ** min(self._failures, 6)
            self.update_interval = min(self._base_interval * factor, MAX_BACKOFF)
            _LOGGER.warning(
                "Panasonic update failed (%d in a row); next poll in %s",
                self._failures,
                self.update_interval,
            )
        elif self._failures:
            _LOGGER.info("Panasonic API recovered; resuming normal polling")
            self._failures = 0
            self.update_interval = self._base_interval

    async def _async_update_data(self):
        """Fetch one status per device."""
        try:
            devices_info = await self.client.get_devices()  # cached by aioaquarea
        except AuthenticationError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except ClientError as err:
            self._set_backoff(True)
            raise UpdateFailed(f"Error communicating with API: {err}") from err

        devices_data: dict[str, Any] = {}
        errors: list[Exception] = []

        for device_info in devices_info:
            device_id = device_info.device_id
            try:
                _captured_json_responses.pop(device_id, None)
                device = self._devices.get(device_id)
                if device is None:
                    # get_device() already performs the first status request.
                    device = await self.client.get_device(device_info=device_info)
                    self._devices[device_id] = device
                else:
                    await device.refresh_data()

                raw_data = _captured_json_responses.get(device_id)
                if raw_data is None:
                    # Never fabricate values: reuse last good data if we have it.
                    previous = (self.data or {}).get(device_id)
                    raw_data = previous.get("raw_data") if previous else None
                    if raw_data is None:
                        raise UpdateFailed(f"No status payload for {device_id}")

                devices_data[device_id] = {
                    "info": device_info,
                    "device": device,
                    "status": getattr(device, "status", None),
                    "raw_data": raw_data,
                }
            except AuthenticationError as err:
                raise ConfigEntryAuthFailed(str(err)) from err
            except Exception as err:  # noqa: BLE001
                errors.append(err)
                _LOGGER.warning("Failed to update device %s: %s", device_id, err)
                self._devices.pop(device_id, None)  # rebuild next time
                if self.data and device_id in self.data:
                    devices_data[device_id] = self.data[device_id]

        if errors and len(errors) == len(devices_info):
            self._set_backoff(True)
            raise UpdateFailed(f"All devices failed to update: {errors[0]}")

        self._set_backoff(bool(errors))
        return devices_data

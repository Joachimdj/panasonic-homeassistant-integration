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

from .const import DOMAIN, UPDATE_INTERVAL

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.CLIMATE, Platform.SENSOR, Platform.WATER_HEATER]


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

    _LOGGER.info("Panasonic Aquarea integration setup completed successfully")
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


class AquareaDataUpdateCoordinator(DataUpdateCoordinator):
    """Class to manage fetching data from the API."""

    def __init__(self, hass: HomeAssistant, client: Client) -> None:
        """Initialize."""
        self.client = client
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
                    
                    # Try to get raw data if available
                    raw_data = None
                    possible_attrs = ['raw_data', '_raw_data', 'data', '_data', 'status_data', '_status_data']
                    
                    for attr in possible_attrs:
                        if hasattr(device, attr):
                            raw_data = getattr(device, attr)
                            _LOGGER.info("Found raw data in device.%s: %s", attr, raw_data)
                            break
                    
                    # Also try to get it from device_info
                    if not raw_data:
                        for attr in possible_attrs:
                            if hasattr(device_info, attr):
                                raw_data = getattr(device_info, attr)
                                _LOGGER.info("Found raw data in device_info.%s: %s", attr, raw_data)
                                break
                    
                    # Log what we have available
                    _LOGGER.info("Device info vars: %s", vars(device_info) if hasattr(device_info, '__dict__') else "No __dict__")
                    _LOGGER.info("Device vars: %s", vars(device) if hasattr(device, '__dict__') else "No __dict__")
                    
                    if hasattr(device, 'status'):
                        _LOGGER.info("Device status: %s", device.status)
                        if device.status:
                            _LOGGER.info("Device status attributes: %s", dir(device.status))
                            _LOGGER.info("Device status vars: %s", vars(device.status) if hasattr(device.status, '__dict__') else "No __dict__")
                    
                    # Create a more comprehensive device data structure
                    device_entry = {
                        "info": device_info,
                        "device": device,
                        "status": device.status if hasattr(device, 'status') else None,
                        "raw_data": raw_data,
                    }
                    
                    # If we have the raw JSON structure from logs, try to construct it
                    # This is a fallback for when the library doesn't expose the data properly
                    if not raw_data and hasattr(device, '_last_response'):
                        device_entry["raw_data"] = device._last_response
                    
                    devices_data[device_info.device_id] = device_entry
                    _LOGGER.info("Stored device data for %s: %s", device_info.device_id, device_entry)
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
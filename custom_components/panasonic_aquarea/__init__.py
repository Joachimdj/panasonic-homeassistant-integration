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
    session = async_get_clientsession(hass)
    
    client = Client(
        username=entry.data[CONF_USERNAME],
        password=entry.data[CONF_PASSWORD],
        session=session,
        device_direct=True,
        refresh_login=True,
        environment=AquareaEnvironment.PRODUCTION,
    )

    coordinator = AquareaDataUpdateCoordinator(hass, client)
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

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
                    _LOGGER.debug("Device info: %s", device_info)
                    _LOGGER.debug("Device: %s", device)
                    
                    # Try to get raw data if available
                    raw_data = None
                    if hasattr(device, 'raw_data'):
                        raw_data = device.raw_data
                    elif hasattr(device, '_raw_data'):
                        raw_data = device._raw_data
                    elif hasattr(device, 'data'):
                        raw_data = device.data
                        
                    if raw_data:
                        _LOGGER.info("Raw device data found: %s", raw_data)
                    
                    devices_data[device_info.device_id] = {
                        "info": device_info,
                        "device": device,
                        "status": device.status if hasattr(device, 'status') else None,
                        "raw_data": raw_data,
                    }
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
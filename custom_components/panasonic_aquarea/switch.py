"""Platform for switch integration - Cloud Comfort app controls."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.switch import (
    SwitchEntity,
    SwitchDeviceClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import AquareaDataUpdateCoordinator
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the switch platform."""
    coordinator: AquareaDataUpdateCoordinator = hass.data[DOMAIN][config_entry.entry_id]
    
    entities = []
    for device_id, device_data in coordinator.data.items():
        # Add Cloud Comfort app control switches for each device
        entities.extend([
            AquareaEcoModeSwitch(coordinator, device_id),
            AquareaComfortModeSwitch(coordinator, device_id),
            AquareaQuietModeSwitch(coordinator, device_id),
            AquareaPowerfulModeSwitch(coordinator, device_id),
            AquareaForceHeaterSwitch(coordinator, device_id),
            AquareaHolidayModeSwitch(coordinator, device_id),
            AquareaScheduleEnabledSwitch(coordinator, device_id),
        ])
        
        # Add tank-specific switches if device has a tank
        device_info = device_data.get("info")
        raw_data = device_data.get("raw_data")
        
        has_tank = False
        if device_info and hasattr(device_info, 'has_tank'):
            has_tank = device_info.has_tank
        elif raw_data and 'status' in raw_data and 'tankStatus' in raw_data['status']:
            has_tank = True
            
        if has_tank:
            entities.extend([
                AquareaForceDHWSwitch(coordinator, device_id),
                AquareaDHWPrioritySwitch(coordinator, device_id),
                AquareaLegionellaModeSwitch(coordinator, device_id),
                AquareaReheatModeSwitch(coordinator, device_id),
            ])
    
    async_add_entities(entities)


class AquareaSwitchBase(CoordinatorEntity, SwitchEntity):
    """Base class for Aquarea switches."""

    def __init__(
        self,
        coordinator: AquareaDataUpdateCoordinator,
        device_id: str,
        switch_type: str,
    ) -> None:
        """Initialize the switch."""
        super().__init__(coordinator)
        self._device_id = device_id
        self._switch_type = switch_type
        
        device_data = self.coordinator.data.get(device_id, {})
        device_info = device_data.get("info")
        raw_data = device_data.get("raw_data")
        
        # Get device name
        device_name = "Unknown Device"
        if device_info and hasattr(device_info, 'name'):
            device_name = device_info.name
        elif raw_data and 'a2wName' in raw_data:
            device_name = raw_data['a2wName']
            
        self._attr_name = f"{device_name} {switch_type}"
        self._attr_unique_id = f"{device_id}_{switch_type.lower().replace(' ', '_')}"

    @property
    def device_info(self) -> dict[str, Any]:
        """Return device information."""
        device_data = self.coordinator.data.get(self._device_id, {})
        device_info = device_data.get("info")
        raw_data = device_data.get("raw_data")
        
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


class AquareaEcoModeSwitch(AquareaSwitchBase):
    """Eco mode switch from Cloud Comfort app."""

    def __init__(
        self,
        coordinator: AquareaDataUpdateCoordinator,
        device_id: str,
    ) -> None:
        """Initialize the eco mode switch."""
        super().__init__(coordinator, device_id, "Eco Mode")
        self._attr_device_class = SwitchDeviceClass.SWITCH
        self._attr_icon = "mdi:leaf"

    @property
    def is_on(self) -> bool:
        """Return true if the switch is on."""
        device_data = self.coordinator.data.get(self._device_id)
        if not device_data:
            return False
            
        raw_data = device_data.get("raw_data")
        if raw_data and 'status' in raw_data:
            return bool(raw_data['status'].get('ecoMode', 0))
        return False

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        device_data = self.coordinator.data.get(self._device_id)
        if not device_data or not device_data.get("device"):
            return

        device = device_data["device"]
        try:
            if hasattr(device, 'set_eco_mode'):
                await device.set_eco_mode(True)
                await self.coordinator.async_request_refresh()
        except Exception as err:
            _LOGGER.error("Failed to turn on eco mode: %s", err)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        device_data = self.coordinator.data.get(self._device_id)
        if not device_data or not device_data.get("device"):
            return

        device = device_data["device"]
        try:
            if hasattr(device, 'set_eco_mode'):
                await device.set_eco_mode(False)
                await self.coordinator.async_request_refresh()
        except Exception as err:
            _LOGGER.error("Failed to turn off eco mode: %s", err)


class AquareaComfortModeSwitch(AquareaSwitchBase):
    """Comfort mode switch from Cloud Comfort app."""

    def __init__(
        self,
        coordinator: AquareaDataUpdateCoordinator,
        device_id: str,
    ) -> None:
        """Initialize the comfort mode switch."""
        super().__init__(coordinator, device_id, "Comfort Mode")
        self._attr_device_class = SwitchDeviceClass.SWITCH
        self._attr_icon = "mdi:sofa"

    @property
    def is_on(self) -> bool:
        """Return true if the switch is on."""
        device_data = self.coordinator.data.get(self._device_id)
        if not device_data:
            return False
            
        raw_data = device_data.get("raw_data")
        if raw_data and 'status' in raw_data:
            return bool(raw_data['status'].get('comfortMode', 0))
        return False

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        device_data = self.coordinator.data.get(self._device_id)
        if not device_data or not device_data.get("device"):
            return

        device = device_data["device"]
        try:
            if hasattr(device, 'set_comfort_mode'):
                await device.set_comfort_mode(True)
                await self.coordinator.async_request_refresh()
        except Exception as err:
            _LOGGER.error("Failed to turn on comfort mode: %s", err)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        device_data = self.coordinator.data.get(self._device_id)
        if not device_data or not device_data.get("device"):
            return

        device = device_data["device"]
        try:
            if hasattr(device, 'set_comfort_mode'):
                await device.set_comfort_mode(False)
                await self.coordinator.async_request_refresh()
        except Exception as err:
            _LOGGER.error("Failed to turn off comfort mode: %s", err)


class AquareaQuietModeSwitch(AquareaSwitchBase):
    """Quiet mode switch from Cloud Comfort app."""

    def __init__(
        self,
        coordinator: AquareaDataUpdateCoordinator,
        device_id: str,
    ) -> None:
        """Initialize the quiet mode switch."""
        super().__init__(coordinator, device_id, "Quiet Mode")
        self._attr_device_class = SwitchDeviceClass.SWITCH
        self._attr_icon = "mdi:volume-off"

    @property
    def is_on(self) -> bool:
        """Return true if the switch is on."""
        device_data = self.coordinator.data.get(self._device_id)
        if not device_data:
            return False
            
        raw_data = device_data.get("raw_data")
        if raw_data and 'status' in raw_data:
            return bool(raw_data['status'].get('quietMode', 0))
        return False

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        device_data = self.coordinator.data.get(self._device_id)
        if not device_data or not device_data.get("device"):
            return

        device = device_data["device"]
        try:
            if hasattr(device, 'set_quiet_mode'):
                await device.set_quiet_mode(True)
                await self.coordinator.async_request_refresh()
        except Exception as err:
            _LOGGER.error("Failed to turn on quiet mode: %s", err)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        device_data = self.coordinator.data.get(self._device_id)
        if not device_data or not device_data.get("device"):
            return

        device = device_data["device"]
        try:
            if hasattr(device, 'set_quiet_mode'):
                await device.set_quiet_mode(False)
                await self.coordinator.async_request_refresh()
        except Exception as err:
            _LOGGER.error("Failed to turn off quiet mode: %s", err)


class AquareaPowerfulModeSwitch(AquareaSwitchBase):
    """Powerful mode switch from Cloud Comfort app."""

    def __init__(
        self,
        coordinator: AquareaDataUpdateCoordinator,
        device_id: str,
    ) -> None:
        """Initialize the powerful mode switch."""
        super().__init__(coordinator, device_id, "Powerful Mode")
        self._attr_device_class = SwitchDeviceClass.SWITCH
        self._attr_icon = "mdi:fire"

    @property
    def is_on(self) -> bool:
        """Return true if the switch is on."""
        device_data = self.coordinator.data.get(self._device_id)
        if not device_data:
            return False
            
        raw_data = device_data.get("raw_data")
        if raw_data and 'status' in raw_data:
            return bool(raw_data['status'].get('powerful', 0))
        return False

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        device_data = self.coordinator.data.get(self._device_id)
        if not device_data or not device_data.get("device"):
            return

        device = device_data["device"]
        try:
            if hasattr(device, 'set_powerful_mode'):
                await device.set_powerful_mode(True)
                await self.coordinator.async_request_refresh()
        except Exception as err:
            _LOGGER.error("Failed to turn on powerful mode: %s", err)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        device_data = self.coordinator.data.get(self._device_id)
        if not device_data or not device_data.get("device"):
            return

        device = device_data["device"]
        try:
            if hasattr(device, 'set_powerful_mode'):
                await device.set_powerful_mode(False)
                await self.coordinator.async_request_refresh()
        except Exception as err:
            _LOGGER.error("Failed to turn off powerful mode: %s", err)


class AquareaForceHeaterSwitch(AquareaSwitchBase):
    """Force heater switch from Cloud Comfort app."""

    def __init__(
        self,
        coordinator: AquareaDataUpdateCoordinator,
        device_id: str,
    ) -> None:
        """Initialize the force heater switch."""
        super().__init__(coordinator, device_id, "Force Heater")
        self._attr_device_class = SwitchDeviceClass.SWITCH
        self._attr_icon = "mdi:heating-coil"

    @property
    def is_on(self) -> bool:
        """Return true if the switch is on."""
        device_data = self.coordinator.data.get(self._device_id)
        if not device_data:
            return False
            
        raw_data = device_data.get("raw_data")
        if raw_data and 'status' in raw_data:
            return bool(raw_data['status'].get('forceHeater', 0))
        return False

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        device_data = self.coordinator.data.get(self._device_id)
        if not device_data or not device_data.get("device"):
            return

        device = device_data["device"]
        try:
            if hasattr(device, 'set_force_heater'):
                await device.set_force_heater(True)
                await self.coordinator.async_request_refresh()
        except Exception as err:
            _LOGGER.error("Failed to turn on force heater: %s", err)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        device_data = self.coordinator.data.get(self._device_id)
        if not device_data or not device_data.get("device"):
            return

        device = device_data["device"]
        try:
            if hasattr(device, 'set_force_heater'):
                await device.set_force_heater(False)
                await self.coordinator.async_request_refresh()
        except Exception as err:
            _LOGGER.error("Failed to turn off force heater: %s", err)


class AquareaHolidayModeSwitch(AquareaSwitchBase):
    """Holiday mode switch from Cloud Comfort app."""

    def __init__(
        self,
        coordinator: AquareaDataUpdateCoordinator,
        device_id: str,
    ) -> None:
        """Initialize the holiday mode switch."""
        super().__init__(coordinator, device_id, "Holiday Mode")
        self._attr_device_class = SwitchDeviceClass.SWITCH
        self._attr_icon = "mdi:beach"

    @property
    def is_on(self) -> bool:
        """Return true if the switch is on."""
        device_data = self.coordinator.data.get(self._device_id)
        if not device_data:
            return False
            
        raw_data = device_data.get("raw_data")
        if raw_data and 'status' in raw_data:
            return bool(raw_data['status'].get('holidayMode', 0))
        return False

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        device_data = self.coordinator.data.get(self._device_id)
        if not device_data or not device_data.get("device"):
            return

        device = device_data["device"]
        try:
            if hasattr(device, 'set_holiday_mode'):
                await device.set_holiday_mode(True)
                await self.coordinator.async_request_refresh()
        except Exception as err:
            _LOGGER.error("Failed to turn on holiday mode: %s", err)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        device_data = self.coordinator.data.get(self._device_id)
        if not device_data or not device_data.get("device"):
            return

        device = device_data["device"]
        try:
            if hasattr(device, 'set_holiday_mode'):
                await device.set_holiday_mode(False)
                await self.coordinator.async_request_refresh()
        except Exception as err:
            _LOGGER.error("Failed to turn off holiday mode: %s", err)


class AquareaScheduleEnabledSwitch(AquareaSwitchBase):
    """Schedule enabled switch from Cloud Comfort app."""

    def __init__(
        self,
        coordinator: AquareaDataUpdateCoordinator,
        device_id: str,
    ) -> None:
        """Initialize the schedule enabled switch."""
        super().__init__(coordinator, device_id, "Schedule Enabled")
        self._attr_device_class = SwitchDeviceClass.SWITCH
        self._attr_icon = "mdi:calendar-clock"

    @property
    def is_on(self) -> bool:
        """Return true if the switch is on."""
        device_data = self.coordinator.data.get(self._device_id)
        if not device_data:
            return False
            
        raw_data = device_data.get("raw_data")
        if raw_data and 'status' in raw_data:
            return bool(raw_data['status'].get('scheduleEnabled', 0))
        return False

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        device_data = self.coordinator.data.get(self._device_id)
        if not device_data or not device_data.get("device"):
            return

        device = device_data["device"]
        try:
            if hasattr(device, 'set_schedule_enabled'):
                await device.set_schedule_enabled(True)
                await self.coordinator.async_request_refresh()
        except Exception as err:
            _LOGGER.error("Failed to turn on schedule: %s", err)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        device_data = self.coordinator.data.get(self._device_id)
        if not device_data or not device_data.get("device"):
            return

        device = device_data["device"]
        try:
            if hasattr(device, 'set_schedule_enabled'):
                await device.set_schedule_enabled(False)
                await self.coordinator.async_request_refresh()
        except Exception as err:
            _LOGGER.error("Failed to turn off schedule: %s", err)


class AquareaForceDHWSwitch(AquareaSwitchBase):
    """Force DHW switch from Cloud Comfort app."""

    def __init__(
        self,
        coordinator: AquareaDataUpdateCoordinator,
        device_id: str,
    ) -> None:
        """Initialize the force DHW switch."""
        super().__init__(coordinator, device_id, "Force DHW")
        self._attr_device_class = SwitchDeviceClass.SWITCH
        self._attr_icon = "mdi:water-boiler"

    @property
    def is_on(self) -> bool:
        """Return true if the switch is on."""
        device_data = self.coordinator.data.get(self._device_id)
        if not device_data:
            return False
            
        raw_data = device_data.get("raw_data")
        if raw_data and 'status' in raw_data:
            return bool(raw_data['status'].get('forceDHW', 0))
        return False

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        device_data = self.coordinator.data.get(self._device_id)
        if not device_data or not device_data.get("device"):
            return

        device = device_data["device"]
        try:
            if hasattr(device, 'set_force_dhw'):
                await device.set_force_dhw(True)
                await self.coordinator.async_request_refresh()
        except Exception as err:
            _LOGGER.error("Failed to turn on force DHW: %s", err)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        device_data = self.coordinator.data.get(self._device_id)
        if not device_data or not device_data.get("device"):
            return

        device = device_data["device"]
        try:
            if hasattr(device, 'set_force_dhw'):
                await device.set_force_dhw(False)
                await self.coordinator.async_request_refresh()
        except Exception as err:
            _LOGGER.error("Failed to turn off force DHW: %s", err)


class AquareaDHWPrioritySwitch(AquareaSwitchBase):
    """DHW priority switch from Cloud Comfort app."""

    def __init__(
        self,
        coordinator: AquareaDataUpdateCoordinator,
        device_id: str,
    ) -> None:
        """Initialize the DHW priority switch."""
        super().__init__(coordinator, device_id, "DHW Priority")
        self._attr_device_class = SwitchDeviceClass.SWITCH
        self._attr_icon = "mdi:priority-high"

    @property
    def is_on(self) -> bool:
        """Return true if the switch is on."""
        device_data = self.coordinator.data.get(self._device_id)
        if not device_data:
            return False
            
        raw_data = device_data.get("raw_data")
        if raw_data and 'status' in raw_data:
            return bool(raw_data['status'].get('dhwPriority', 0))
        return False

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        device_data = self.coordinator.data.get(self._device_id)
        if not device_data or not device_data.get("device"):
            return

        device = device_data["device"]
        try:
            if hasattr(device, 'set_dhw_priority'):
                await device.set_dhw_priority(True)
                await self.coordinator.async_request_refresh()
        except Exception as err:
            _LOGGER.error("Failed to turn on DHW priority: %s", err)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        device_data = self.coordinator.data.get(self._device_id)
        if not device_data or not device_data.get("device"):
            return

        device = device_data["device"]
        try:
            if hasattr(device, 'set_dhw_priority'):
                await device.set_dhw_priority(False)
                await self.coordinator.async_request_refresh()
        except Exception as err:
            _LOGGER.error("Failed to turn off DHW priority: %s", err)


class AquareaLegionellaModeSwitch(AquareaSwitchBase):
    """Legionella mode switch from Cloud Comfort app."""

    def __init__(
        self,
        coordinator: AquareaDataUpdateCoordinator,
        device_id: str,
    ) -> None:
        """Initialize the legionella mode switch."""
        super().__init__(coordinator, device_id, "Legionella Mode")
        self._attr_device_class = SwitchDeviceClass.SWITCH
        self._attr_icon = "mdi:shield-check"

    @property
    def is_on(self) -> bool:
        """Return true if the switch is on."""
        device_data = self.coordinator.data.get(self._device_id)
        if not device_data:
            return False
            
        raw_data = device_data.get("raw_data")
        if raw_data and 'status' in raw_data and 'tankStatus' in raw_data['status']:
            tank_status = raw_data['status']['tankStatus']
            return bool(tank_status.get('legionellaMode', 0))
        return False

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        device_data = self.coordinator.data.get(self._device_id)
        if not device_data or not device_data.get("device"):
            return

        device = device_data["device"]
        try:
            if hasattr(device, 'set_legionella_mode'):
                await device.set_legionella_mode(True)
                await self.coordinator.async_request_refresh()
        except Exception as err:
            _LOGGER.error("Failed to turn on legionella mode: %s", err)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        device_data = self.coordinator.data.get(self._device_id)
        if not device_data or not device_data.get("device"):
            return

        device = device_data["device"]
        try:
            if hasattr(device, 'set_legionella_mode'):
                await device.set_legionella_mode(False)
                await self.coordinator.async_request_refresh()
        except Exception as err:
            _LOGGER.error("Failed to turn off legionella mode: %s", err)


class AquareaReheatModeSwitch(AquareaSwitchBase):
    """Reheat mode switch from Cloud Comfort app."""

    def __init__(
        self,
        coordinator: AquareaDataUpdateCoordinator,
        device_id: str,
    ) -> None:
        """Initialize the reheat mode switch."""
        super().__init__(coordinator, device_id, "Reheat Mode")
        self._attr_device_class = SwitchDeviceClass.SWITCH
        self._attr_icon = "mdi:sync"

    @property
    def is_on(self) -> bool:
        """Return true if the switch is on."""
        device_data = self.coordinator.data.get(self._device_id)
        if not device_data:
            return False
            
        raw_data = device_data.get("raw_data")
        if raw_data and 'status' in raw_data and 'tankStatus' in raw_data['status']:
            tank_status = raw_data['status']['tankStatus']
            return bool(tank_status.get('reheatMode', 0))
        return False

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        device_data = self.coordinator.data.get(self._device_id)
        if not device_data or not device_data.get("device"):
            return

        device = device_data["device"]
        try:
            if hasattr(device, 'set_reheat_mode'):
                await device.set_reheat_mode(True)
                await self.coordinator.async_request_refresh()
        except Exception as err:
            _LOGGER.error("Failed to turn on reheat mode: %s", err)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        device_data = self.coordinator.data.get(self._device_id)
        if not device_data or not device_data.get("device"):
            return

        device = device_data["device"]
        try:
            if hasattr(device, 'set_reheat_mode'):
                await device.set_reheat_mode(False)
                await self.coordinator.async_request_refresh()
        except Exception as err:
            _LOGGER.error("Failed to turn off reheat mode: %s", err)
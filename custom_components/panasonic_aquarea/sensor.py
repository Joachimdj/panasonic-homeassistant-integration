"""Platform for sensor integration."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.sensor import (
    SensorEntity,
    SensorDeviceClass,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTemperature, UnitOfPressure, PERCENTAGE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from . import AquareaDataUpdateCoordinator
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the sensor platform."""
    coordinator: AquareaDataUpdateCoordinator = hass.data[DOMAIN][config_entry.entry_id]
    
    entities = []
    for device_id, device_data in coordinator.data.items():
        device_info = device_data.get("info")
        raw_data = device_data.get("raw_data")
        
        _LOGGER.info("Setting up sensors for device %s, raw_data available: %s", device_id, raw_data is not None)
        
        # Zone temperature sensors - try device_info first
        zones = []
        if device_info and hasattr(device_info, 'zones'):
            zones = device_info.zones
            _LOGGER.info("Found zones in device_info: %s", zones)
        # Fallback to raw data if available
        elif raw_data and 'status' in raw_data and 'zoneStatus' in raw_data['status']:
            _LOGGER.info("Found zones in raw_data: %s", raw_data['status']['zoneStatus'])
            for zone_status in raw_data['status']['zoneStatus']:
                zones.append({
                    'zone_id': zone_status.get('zoneId', 1),
                    'name': zone_status.get('zoneName', f"Zone {zone_status.get('zoneId', 1)}")
                })
        else:
            _LOGGER.warning("No zone data found for device %s", device_id)
        
        for zone in zones:
            zone_id = getattr(zone, 'zone_id', None) or zone.get('zone_id')
            zone_name = getattr(zone, 'name', None) or zone.get('name')
            if zone_id and zone_name:
                # Zone temperature sensor
                entities.append(
                    AquareaTemperatureSensor(coordinator, device_id, zone_id, zone_name)
                )
                # Zone operation status sensor
                entities.append(
                    AquareaZoneOperationSensor(coordinator, device_id, zone_id, zone_name)
                )
        
        # System sensors (device-level data)
        entities.extend([
            # Temperature sensors
            AquareaOutdoorTemperatureSensor(coordinator, device_id),
            
            # Status sensors
            AquareaOperationModeSensor(coordinator, device_id),
            AquareaCoolModeSensor(coordinator, device_id),
            AquareaQuietModeSensor(coordinator, device_id),
            AquareaPowerfulSensor(coordinator, device_id),
            AquareaForceDHWSensor(coordinator, device_id),
            AquareaForceHeaterSensor(coordinator, device_id),
            AquareaPumpDutySensor(coordinator, device_id),
            AquareaDirectionSensor(coordinator, device_id),
            
            # Cloud Comfort app sensors
            AquareaEcoModeSensor(coordinator, device_id),
            AquareaComfortModeSensor(coordinator, device_id),
            AquareaHolidayModeSensor(coordinator, device_id),
            AquareaHolidayDaysSensor(coordinator, device_id),
            AquareaHeaterControlSensor(coordinator, device_id),
            AquareaDHWPrioritySensor(coordinator, device_id),
            AquareaScheduleEnabledSensor(coordinator, device_id),
            AquareaDefrostModeSensor(coordinator, device_id),
            
            # Pressure sensor
            AquareaWaterPressureSensor(coordinator, device_id),
            
            # Status indicators
            AquareaBivalentSensor(coordinator, device_id),
            AquareaBivalentActualSensor(coordinator, device_id),
            AquareaElectricAnodeSensor(coordinator, device_id),
            AquareaDeiceStatusSensor(coordinator, device_id),
            AquareaSpecialStatusSensor(coordinator, device_id),
            AquareaHolidayTimerSensor(coordinator, device_id),
            AquareaModelSeriesSensor(coordinator, device_id),
            AquareaStandAloneSensor(coordinator, device_id),
            AquareaControlBoxSensor(coordinator, device_id),
            AquareaExternalHeaterSensor(coordinator, device_id),
            AquareaMultiOdConnectionSensor(coordinator, device_id),
        ])
        
        # Tank temperature sensor (if has tank)
        has_tank = False
        if device_info and hasattr(device_info, 'has_tank'):
            has_tank = device_info.has_tank
        elif raw_data and 'status' in raw_data and 'tankStatus' in raw_data['status']:
            # If tank status exists in raw data, assume it has a tank
            has_tank = True
            
        if has_tank:
            entities.extend([
                AquareaTankTemperatureSensor(coordinator, device_id),
                AquareaTankOperationSensor(coordinator, device_id),
                # Cloud Comfort tank sensors
                AquareaTankEcoTemperatureSensor(coordinator, device_id),
                AquareaTankComfortTemperatureSensor(coordinator, device_id),
                AquareaLegionellaModeSensor(coordinator, device_id),
                AquareaReheatModeSensor(coordinator, device_id),
            ])
    
    async_add_entities(entities)


class AquareaSensorBase(CoordinatorEntity, SensorEntity):
    """Base class for Aquarea sensors."""

    def __init__(
        self,
        coordinator: AquareaDataUpdateCoordinator,
        device_id: str,
        sensor_type: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._device_id = device_id
        self._sensor_type = sensor_type
        
        device_data = self.coordinator.data.get(device_id, {})
        device_info = device_data.get("info")
        raw_data = device_data.get("raw_data")
        
        # Get device name
        device_name = "Unknown Device"
        if device_info and hasattr(device_info, 'name'):
            device_name = device_info.name
        elif raw_data and 'a2wName' in raw_data:
            device_name = raw_data['a2wName']
            
        self._attr_name = f"{device_name} {sensor_type}"
        self._attr_unique_id = f"{device_id}_{sensor_type.lower().replace(' ', '_')}"
        self._last_logged_value = None

    def _should_log_change(self, new_value: Any, old_value: Any) -> bool:
        """Determine if a sensor value change should be logged to activity."""
        if old_value is None or new_value is None:
            return False
            
        # For temperature sensors, log changes >= 1 degree
        if "temperature" in self._sensor_type.lower():
            try:
                old_float = float(old_value)
                new_float = float(new_value)
                return abs(new_float - old_float) >= 1.0
            except (ValueError, TypeError):
                return False
        
        # For pressure sensors, log changes >= 0.5 bar
        if "pressure" in self._sensor_type.lower():
            try:
                old_float = float(old_value)
                new_float = float(new_value)
                return abs(new_float - old_float) >= 0.5
            except (ValueError, TypeError):
                return False
                
        # For percentage sensors, log changes >= 10%
        if "duty" in self._sensor_type.lower() or "percentage" in self._sensor_type.lower():
            try:
                old_float = float(old_value)
                new_float = float(new_value)
                return abs(new_float - old_float) >= 10.0
            except (ValueError, TypeError):
                return False
        
        # For operation status, log all changes
        if "operation" in self._sensor_type.lower() or "status" in self._sensor_type.lower():
            return str(old_value) != str(new_value)
            
        return False

    def _log_sensor_change(self, old_value: Any, new_value: Any) -> None:
        """Log significant sensor value changes for the Activity widget."""
        try:
            if self._should_log_change(new_value, old_value):
                # Log with INFO level to ensure it appears in Home Assistant activity
                _LOGGER.info("%s changed from %s to %s for device %s", 
                           self._sensor_type, old_value, new_value, self._device_id)
                
                # Fire a custom event for the activity widget
                if self.hass:
                    self.hass.bus.async_fire(
                        "panasonic_aquarea_action",
                        {
                            "entity_id": self.entity_id,
                            "device_id": self._device_id,
                            "sensor_type": self._sensor_type,
                            "action": "value changed",
                            "old_value": old_value,
                            "new_value": new_value,
                            "timestamp": dt_util.utcnow().isoformat(),
                            "device_type": "sensor"
                        }
                    )
                
                # Update last logged value
                self._last_logged_value = new_value
        except Exception as err:
            _LOGGER.debug("Failed to log sensor change: %s", err)

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


class AquareaTemperatureSensor(AquareaSensorBase):
    """Representation of a zone temperature sensor."""

    def __init__(
        self,
        coordinator: AquareaDataUpdateCoordinator,
        device_id: str,
        zone_id: int,
        zone_name: str,
    ) -> None:
        """Initialize the temperature sensor."""
        super().__init__(coordinator, device_id, f"{zone_name} Temperature")
        self._zone_id = zone_id
        self._attr_device_class = SensorDeviceClass.TEMPERATURE
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS

    @property
    def native_value(self) -> float | None:
        """Return the state of the sensor."""
        device_data = self.coordinator.data.get(self._device_id)
        if not device_data or not device_data.get("device"):
            return None
            
        device = device_data["device"]
        current_value = None
        
        # Try to get temperature from structured device.status first
        if hasattr(device, 'status') and device.status:
            if hasattr(device.status, 'zones'):
                for zone in device.status.zones:
                    if zone.zone_id == self._zone_id:
                        temp = getattr(zone, 'temperature', None)
                        if temp is not None:
                            current_value = temp
                            break
        
        # Try to get temperature from raw data as fallback
        if current_value is None:
            raw_data = device_data.get("raw_data")
            if raw_data and 'status' in raw_data and 'zoneStatus' in raw_data['status']:
                for zone_status in raw_data['status']['zoneStatus']:
                    if zone_status.get('zoneId') == self._zone_id:
                        temp_now = zone_status.get('temperatureNow')
                        if temp_now is not None:
                            # Convert from tenths of degrees to degrees
                            current_value = float(temp_now) / 10.0
                            break
        
        # Log significant changes for activity widget
        if current_value is not None:
            old_value = getattr(self, '_last_value', None)
            if old_value != current_value:
                self._log_sensor_change(old_value, current_value)
                self._last_value = current_value
        
        return current_value


class AquareaTankTemperatureSensor(AquareaSensorBase):
    """Representation of a tank temperature sensor."""

    def __init__(
        self,
        coordinator: AquareaDataUpdateCoordinator,
        device_id: str,
    ) -> None:
        """Initialize the tank temperature sensor."""
        super().__init__(coordinator, device_id, "Tank Temperature")
        self._attr_device_class = SensorDeviceClass.TEMPERATURE
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS

    @property
    def native_value(self) -> float | None:
        """Return the state of the sensor."""
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
                # Tank temperature is already in degrees
                return float(temp_now)
        
        return None


class AquareaZoneOperationSensor(AquareaSensorBase):
    """Zone operation status sensor."""

    def __init__(
        self,
        coordinator: AquareaDataUpdateCoordinator,
        device_id: str,
        zone_id: int,
        zone_name: str,
    ) -> None:
        """Initialize the zone operation sensor."""
        super().__init__(coordinator, device_id, f"{zone_name} Operation Status")
        self._zone_id = zone_id

    @property
    def native_value(self) -> str | None:
        """Return the state of the sensor."""
        device_data = self.coordinator.data.get(self._device_id)
        if not device_data:
            return None
            
        raw_data = device_data.get("raw_data")
        if raw_data and 'status' in raw_data and 'zoneStatus' in raw_data['status']:
            for zone_status in raw_data['status']['zoneStatus']:
                if zone_status.get('zoneId') == self._zone_id:
                    operation_status = zone_status.get('operationStatus')
                    return "On" if operation_status == 1 else "Off"
        return None


class AquareaOutdoorTemperatureSensor(AquareaSensorBase):
    """Outdoor temperature sensor."""

    def __init__(
        self,
        coordinator: AquareaDataUpdateCoordinator,
        device_id: str,
    ) -> None:
        """Initialize the outdoor temperature sensor."""
        super().__init__(coordinator, device_id, "Outdoor Temperature")
        self._attr_device_class = SensorDeviceClass.TEMPERATURE
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS

    @property
    def native_value(self) -> float | None:
        """Return the state of the sensor."""
        device_data = self.coordinator.data.get(self._device_id)
        if not device_data:
            return None
            
        raw_data = device_data.get("raw_data")
        if raw_data and 'status' in raw_data:
            outdoor_now = raw_data['status'].get('outdoorNow')
            if outdoor_now is not None:
                return float(outdoor_now)
        return None


class AquareaOperationModeSensor(AquareaSensorBase):
    """Operation mode sensor."""

    def __init__(
        self,
        coordinator: AquareaDataUpdateCoordinator,
        device_id: str,
    ) -> None:
        """Initialize the operation mode sensor."""
        super().__init__(coordinator, device_id, "Operation Mode")

    @property
    def native_value(self) -> str | None:
        """Return the state of the sensor."""
        device_data = self.coordinator.data.get(self._device_id)
        if not device_data:
            return None
            
        raw_data = device_data.get("raw_data")
        if raw_data and 'status' in raw_data:
            mode = raw_data['status'].get('operationMode')
            mode_map = {
                0: "Off",
                1: "Heat", 
                2: "Cool",
                3: "Auto"
            }
            return mode_map.get(mode, f"Mode {mode}")
        return None


class AquareaCoolModeSensor(AquareaSensorBase):
    """Cool mode sensor."""

    def __init__(
        self,
        coordinator: AquareaDataUpdateCoordinator,
        device_id: str,
    ) -> None:
        """Initialize the cool mode sensor."""
        super().__init__(coordinator, device_id, "Cool Mode")

    @property
    def native_value(self) -> str | None:
        """Return the state of the sensor."""
        device_data = self.coordinator.data.get(self._device_id)
        if not device_data:
            return None
            
        raw_data = device_data.get("raw_data")
        if raw_data and 'status' in raw_data:
            cool_mode = raw_data['status'].get('coolMode')
            return "Enabled" if cool_mode == 1 else "Disabled"
        return None


class AquareaQuietModeSensor(AquareaSensorBase):
    """Quiet mode sensor."""

    def __init__(
        self,
        coordinator: AquareaDataUpdateCoordinator,
        device_id: str,
    ) -> None:
        """Initialize the quiet mode sensor."""
        super().__init__(coordinator, device_id, "Quiet Mode")

    @property
    def native_value(self) -> str | None:
        """Return the state of the sensor."""
        device_data = self.coordinator.data.get(self._device_id)
        if not device_data:
            return None
            
        raw_data = device_data.get("raw_data")
        if raw_data and 'status' in raw_data:
            quiet_mode = raw_data['status'].get('quietMode')
            return "On" if quiet_mode == 1 else "Off"
        return None


class AquareaPowerfulSensor(AquareaSensorBase):
    """Powerful mode sensor."""

    def __init__(
        self,
        coordinator: AquareaDataUpdateCoordinator,
        device_id: str,
    ) -> None:
        """Initialize the powerful mode sensor."""
        super().__init__(coordinator, device_id, "Powerful Mode")

    @property
    def native_value(self) -> str | None:
        """Return the state of the sensor."""
        device_data = self.coordinator.data.get(self._device_id)
        if not device_data:
            return None
            
        raw_data = device_data.get("raw_data")
        if raw_data and 'status' in raw_data:
            powerful = raw_data['status'].get('powerful')
            return "On" if powerful == 1 else "Off"
        return None


class AquareaForceDHWSensor(AquareaSensorBase):
    """Force DHW sensor."""

    def __init__(
        self,
        coordinator: AquareaDataUpdateCoordinator,
        device_id: str,
    ) -> None:
        """Initialize the force DHW sensor."""
        super().__init__(coordinator, device_id, "Force DHW")

    @property
    def native_value(self) -> str | None:
        """Return the state of the sensor."""
        device_data = self.coordinator.data.get(self._device_id)
        if not device_data:
            return None
            
        raw_data = device_data.get("raw_data")
        if raw_data and 'status' in raw_data:
            force_dhw = raw_data['status'].get('forceDHW')
            return "On" if force_dhw == 1 else "Off"
        return None


class AquareaForceHeaterSensor(AquareaSensorBase):
    """Force heater sensor."""

    def __init__(
        self,
        coordinator: AquareaDataUpdateCoordinator,
        device_id: str,
    ) -> None:
        """Initialize the force heater sensor."""
        super().__init__(coordinator, device_id, "Force Heater")

    @property
    def native_value(self) -> str | None:
        """Return the state of the sensor."""
        device_data = self.coordinator.data.get(self._device_id)
        if not device_data:
            return None
            
        raw_data = device_data.get("raw_data")
        if raw_data and 'status' in raw_data:
            force_heater = raw_data['status'].get('forceHeater')
            return "On" if force_heater == 1 else "Off"
        return None


class AquareaPumpDutySensor(AquareaSensorBase):
    """Pump duty sensor."""

    def __init__(
        self,
        coordinator: AquareaDataUpdateCoordinator,
        device_id: str,
    ) -> None:
        """Initialize the pump duty sensor."""
        super().__init__(coordinator, device_id, "Pump Duty")
        self._attr_native_unit_of_measurement = PERCENTAGE

    @property
    def native_value(self) -> int | None:
        """Return the state of the sensor."""
        device_data = self.coordinator.data.get(self._device_id)
        if not device_data:
            return None
            
        raw_data = device_data.get("raw_data")
        if raw_data and 'status' in raw_data:
            pump_duty = raw_data['status'].get('pumpDuty')
            if pump_duty is not None:
                return int(pump_duty)
        return None


class AquareaDirectionSensor(AquareaSensorBase):
    """Direction sensor."""

    def __init__(
        self,
        coordinator: AquareaDataUpdateCoordinator,
        device_id: str,
    ) -> None:
        """Initialize the direction sensor."""
        super().__init__(coordinator, device_id, "Direction")

    @property
    def native_value(self) -> str | None:
        """Return the state of the sensor."""
        device_data = self.coordinator.data.get(self._device_id)
        if not device_data:
            return None
            
        raw_data = device_data.get("raw_data")
        if raw_data and 'status' in raw_data:
            direction = raw_data['status'].get('direction')
            direction_map = {
                0: "Automatic",
                1: "Up", 
                2: "Down",
                3: "Fixed"
            }
            return direction_map.get(direction, f"Direction {direction}")
        return None


class AquareaWaterPressureSensor(AquareaSensorBase):
    """Water pressure sensor."""

    def __init__(
        self,
        coordinator: AquareaDataUpdateCoordinator,
        device_id: str,
    ) -> None:
        """Initialize the water pressure sensor."""
        super().__init__(coordinator, device_id, "Water Pressure")
        self._attr_device_class = SensorDeviceClass.PRESSURE
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_native_unit_of_measurement = UnitOfPressure.BAR

    @property
    def native_value(self) -> float | None:
        """Return the state of the sensor."""
        device_data = self.coordinator.data.get(self._device_id)
        if not device_data:
            return None
            
        raw_data = device_data.get("raw_data")
        if raw_data and 'status' in raw_data:
            pressure = raw_data['status'].get('waterPressure')
            if pressure is not None:
                return float(pressure)
        return None


class AquareaBivalentSensor(AquareaSensorBase):
    """Bivalent sensor."""

    def __init__(
        self,
        coordinator: AquareaDataUpdateCoordinator,
        device_id: str,
    ) -> None:
        """Initialize the bivalent sensor."""
        super().__init__(coordinator, device_id, "Bivalent")

    @property
    def native_value(self) -> str | None:
        """Return the state of the sensor."""
        device_data = self.coordinator.data.get(self._device_id)
        if not device_data:
            return None
            
        raw_data = device_data.get("raw_data")
        if raw_data and 'status' in raw_data:
            bivalent = raw_data['status'].get('bivalent')
            return "Active" if bivalent == 1 else "Inactive"
        return None


class AquareaBivalentActualSensor(AquareaSensorBase):
    """Bivalent actual sensor."""

    def __init__(
        self,
        coordinator: AquareaDataUpdateCoordinator,
        device_id: str,
    ) -> None:
        """Initialize the bivalent actual sensor."""
        super().__init__(coordinator, device_id, "Bivalent Actual")

    @property
    def native_value(self) -> str | None:
        """Return the state of the sensor."""
        device_data = self.coordinator.data.get(self._device_id)
        if not device_data:
            return None
            
        raw_data = device_data.get("raw_data")
        if raw_data and 'status' in raw_data:
            bivalent_actual = raw_data['status'].get('bivalentActual')
            return "Active" if bivalent_actual == 1 else "Inactive"
        return None


class AquareaElectricAnodeSensor(AquareaSensorBase):
    """Electric anode sensor."""

    def __init__(
        self,
        coordinator: AquareaDataUpdateCoordinator,
        device_id: str,
    ) -> None:
        """Initialize the electric anode sensor."""
        super().__init__(coordinator, device_id, "Electric Anode")

    @property
    def native_value(self) -> str | None:
        """Return the state of the sensor."""
        device_data = self.coordinator.data.get(self._device_id)
        if not device_data:
            return None
            
        raw_data = device_data.get("raw_data")
        if raw_data and 'status' in raw_data:
            electric_anode = raw_data['status'].get('electricAnode')
            return "On" if electric_anode == 1 else "Off"
        return None


class AquareaDeiceStatusSensor(AquareaSensorBase):
    """Deice status sensor."""

    def __init__(
        self,
        coordinator: AquareaDataUpdateCoordinator,
        device_id: str,
    ) -> None:
        """Initialize the deice status sensor."""
        super().__init__(coordinator, device_id, "Deice Status")

    @property
    def native_value(self) -> str | None:
        """Return the state of the sensor."""
        device_data = self.coordinator.data.get(self._device_id)
        if not device_data:
            return None
            
        raw_data = device_data.get("raw_data")
        if raw_data and 'status' in raw_data:
            deice_status = raw_data['status'].get('deiceStatus')
            return "Active" if deice_status == 1 else "Inactive"
        return None


class AquareaSpecialStatusSensor(AquareaSensorBase):
    """Special status sensor."""

    def __init__(
        self,
        coordinator: AquareaDataUpdateCoordinator,
        device_id: str,
    ) -> None:
        """Initialize the special status sensor."""
        super().__init__(coordinator, device_id, "Special Status")

    @property
    def native_value(self) -> int | None:
        """Return the state of the sensor."""
        device_data = self.coordinator.data.get(self._device_id)
        if not device_data:
            return None
            
        raw_data = device_data.get("raw_data")
        if raw_data and 'status' in raw_data:
            special_status = raw_data['status'].get('specialStatus')
            if special_status is not None:
                return int(special_status)
        return None


class AquareaHolidayTimerSensor(AquareaSensorBase):
    """Holiday timer sensor."""

    def __init__(
        self,
        coordinator: AquareaDataUpdateCoordinator,
        device_id: str,
    ) -> None:
        """Initialize the holiday timer sensor."""
        super().__init__(coordinator, device_id, "Holiday Timer")

    @property
    def native_value(self) -> str | None:
        """Return the state of the sensor."""
        device_data = self.coordinator.data.get(self._device_id)
        if not device_data:
            return None
            
        raw_data = device_data.get("raw_data")
        if raw_data and 'status' in raw_data:
            holiday_timer = raw_data['status'].get('holidayTimer')
            return "Active" if holiday_timer == 1 else "Inactive"
        return None


class AquareaModelSeriesSensor(AquareaSensorBase):
    """Model series sensor."""

    def __init__(
        self,
        coordinator: AquareaDataUpdateCoordinator,
        device_id: str,
    ) -> None:
        """Initialize the model series sensor."""
        super().__init__(coordinator, device_id, "Model Series")

    @property
    def native_value(self) -> int | None:
        """Return the state of the sensor."""
        device_data = self.coordinator.data.get(self._device_id)
        if not device_data:
            return None
            
        raw_data = device_data.get("raw_data")
        if raw_data and 'status' in raw_data:
            model_series = raw_data['status'].get('modelSeriesSelection')
            if model_series is not None:
                return int(model_series)
        return None


class AquareaStandAloneSensor(AquareaSensorBase):
    """Stand alone sensor."""

    def __init__(
        self,
        coordinator: AquareaDataUpdateCoordinator,
        device_id: str,
    ) -> None:
        """Initialize the stand alone sensor."""
        super().__init__(coordinator, device_id, "Stand Alone")

    @property
    def native_value(self) -> str | None:
        """Return the state of the sensor."""
        device_data = self.coordinator.data.get(self._device_id)
        if not device_data:
            return None
            
        raw_data = device_data.get("raw_data")
        if raw_data and 'status' in raw_data:
            stand_alone = raw_data['status'].get('standAlone')
            return "Yes" if stand_alone == 1 else "No"
        return None


class AquareaControlBoxSensor(AquareaSensorBase):
    """Control box sensor."""

    def __init__(
        self,
        coordinator: AquareaDataUpdateCoordinator,
        device_id: str,
    ) -> None:
        """Initialize the control box sensor."""
        super().__init__(coordinator, device_id, "Control Box")

    @property
    def native_value(self) -> str | None:
        """Return the state of the sensor."""
        device_data = self.coordinator.data.get(self._device_id)
        if not device_data:
            return None
            
        raw_data = device_data.get("raw_data")
        if raw_data and 'status' in raw_data:
            control_box = raw_data['status'].get('controlBox')
            return "Active" if control_box == 1 else "Inactive"
        return None


class AquareaExternalHeaterSensor(AquareaSensorBase):
    """External heater sensor."""

    def __init__(
        self,
        coordinator: AquareaDataUpdateCoordinator,
        device_id: str,
    ) -> None:
        """Initialize the external heater sensor."""
        super().__init__(coordinator, device_id, "External Heater")

    @property
    def native_value(self) -> str | None:
        """Return the state of the sensor."""
        device_data = self.coordinator.data.get(self._device_id)
        if not device_data:
            return None
            
        raw_data = device_data.get("raw_data")
        if raw_data and 'status' in raw_data:
            external_heater = raw_data['status'].get('externalHeater')
            return "Active" if external_heater == 1 else "Inactive"
        return None


class AquareaMultiOdConnectionSensor(AquareaSensorBase):
    """Multi OD connection sensor."""

    def __init__(
        self,
        coordinator: AquareaDataUpdateCoordinator,
        device_id: str,
    ) -> None:
        """Initialize the multi OD connection sensor."""
        super().__init__(coordinator, device_id, "Multi OD Connection")

    @property
    def native_value(self) -> str | None:
        """Return the state of the sensor."""
        device_data = self.coordinator.data.get(self._device_id)
        if not device_data:
            return None
            
        raw_data = device_data.get("raw_data")
        if raw_data and 'status' in raw_data:
            multi_od = raw_data['status'].get('multiOdConnection')
            return "Connected" if multi_od == 1 else "Disconnected"
        return None


class AquareaTankOperationSensor(AquareaSensorBase):
    """Tank operation sensor."""

    def __init__(
        self,
        coordinator: AquareaDataUpdateCoordinator,
        device_id: str,
    ) -> None:
        """Initialize the tank operation sensor."""
        super().__init__(coordinator, device_id, "Tank Operation")

    @property
    def native_value(self) -> str | None:
        """Return the state of the sensor."""
        device_data = self.coordinator.data.get(self._device_id)
        if not device_data:
            return None
            
        raw_data = device_data.get("raw_data")
        if raw_data and 'status' in raw_data and 'tankStatus' in raw_data['status']:
            tank_status = raw_data['status']['tankStatus']
            operation_status = tank_status.get('operationStatus')
            return "On" if operation_status == 1 else "Off"
        return None


# Cloud Comfort App specific sensors

class AquareaEcoModeSensor(AquareaSensorBase):
    """Eco mode sensor from Cloud Comfort app."""

    def __init__(
        self,
        coordinator: AquareaDataUpdateCoordinator,
        device_id: str,
    ) -> None:
        """Initialize the eco mode sensor."""
        super().__init__(coordinator, device_id, "Eco Mode")

    @property
    def native_value(self) -> str | None:
        """Return the state of the sensor."""
        device_data = self.coordinator.data.get(self._device_id)
        if not device_data:
            return None
            
        raw_data = device_data.get("raw_data")
        if raw_data and 'status' in raw_data:
            eco_mode = raw_data['status'].get('ecoMode')
            return "On" if eco_mode == 1 else "Off"
        return None


class AquareaComfortModeSensor(AquareaSensorBase):
    """Comfort mode sensor from Cloud Comfort app."""

    def __init__(
        self,
        coordinator: AquareaDataUpdateCoordinator,
        device_id: str,
    ) -> None:
        """Initialize the comfort mode sensor."""
        super().__init__(coordinator, device_id, "Comfort Mode")

    @property
    def native_value(self) -> str | None:
        """Return the state of the sensor."""
        device_data = self.coordinator.data.get(self._device_id)
        if not device_data:
            return None
            
        raw_data = device_data.get("raw_data")
        if raw_data and 'status' in raw_data:
            comfort_mode = raw_data['status'].get('comfortMode')
            return "On" if comfort_mode == 1 else "Off"
        return None


class AquareaHolidayModeSensor(AquareaSensorBase):
    """Holiday mode sensor from Cloud Comfort app."""

    def __init__(
        self,
        coordinator: AquareaDataUpdateCoordinator,
        device_id: str,
    ) -> None:
        """Initialize the holiday mode sensor."""
        super().__init__(coordinator, device_id, "Holiday Mode")

    @property
    def native_value(self) -> str | None:
        """Return the state of the sensor."""
        device_data = self.coordinator.data.get(self._device_id)
        if not device_data:
            return None
            
        raw_data = device_data.get("raw_data")
        if raw_data and 'status' in raw_data:
            holiday_mode = raw_data['status'].get('holidayMode')
            return "On" if holiday_mode == 1 else "Off"
        return None


class AquareaHolidayDaysSensor(AquareaSensorBase):
    """Holiday days remaining sensor from Cloud Comfort app."""

    def __init__(
        self,
        coordinator: AquareaDataUpdateCoordinator,
        device_id: str,
    ) -> None:
        """Initialize the holiday days sensor."""
        super().__init__(coordinator, device_id, "Holiday Days Remaining")
        self._attr_native_unit_of_measurement = "days"

    @property
    def native_value(self) -> int | None:
        """Return the state of the sensor."""
        device_data = self.coordinator.data.get(self._device_id)
        if not device_data:
            return None
            
        raw_data = device_data.get("raw_data")
        if raw_data and 'status' in raw_data:
            holiday_days = raw_data['status'].get('holidayDays')
            if holiday_days is not None:
                return int(holiday_days)
        return None


class AquareaHeaterControlSensor(AquareaSensorBase):
    """Heater control sensor from Cloud Comfort app."""

    def __init__(
        self,
        coordinator: AquareaDataUpdateCoordinator,
        device_id: str,
    ) -> None:
        """Initialize the heater control sensor."""
        super().__init__(coordinator, device_id, "Heater Control")

    @property
    def native_value(self) -> str | None:
        """Return the state of the sensor."""
        device_data = self.coordinator.data.get(self._device_id)
        if not device_data:
            return None
            
        raw_data = device_data.get("raw_data")
        if raw_data and 'status' in raw_data:
            heater_control = raw_data['status'].get('heaterControl')
            control_map = {
                0: "Auto",
                1: "Force On",
                2: "Force Off"
            }
            return control_map.get(heater_control, f"Mode {heater_control}")
        return None


class AquareaDHWPrioritySensor(AquareaSensorBase):
    """DHW priority sensor from Cloud Comfort app."""

    def __init__(
        self,
        coordinator: AquareaDataUpdateCoordinator,
        device_id: str,
    ) -> None:
        """Initialize the DHW priority sensor."""
        super().__init__(coordinator, device_id, "DHW Priority")

    @property
    def native_value(self) -> str | None:
        """Return the state of the sensor."""
        device_data = self.coordinator.data.get(self._device_id)
        if not device_data:
            return None
            
        raw_data = device_data.get("raw_data")
        if raw_data and 'status' in raw_data:
            dhw_priority = raw_data['status'].get('dhwPriority')
            return "Priority" if dhw_priority == 1 else "Normal"
        return None


class AquareaScheduleEnabledSensor(AquareaSensorBase):
    """Schedule enabled sensor from Cloud Comfort app."""

    def __init__(
        self,
        coordinator: AquareaDataUpdateCoordinator,
        device_id: str,
    ) -> None:
        """Initialize the schedule enabled sensor."""
        super().__init__(coordinator, device_id, "Schedule Enabled")

    @property
    def native_value(self) -> str | None:
        """Return the state of the sensor."""
        device_data = self.coordinator.data.get(self._device_id)
        if not device_data:
            return None
            
        raw_data = device_data.get("raw_data")
        if raw_data and 'status' in raw_data:
            schedule_enabled = raw_data['status'].get('scheduleEnabled')
            return "On" if schedule_enabled == 1 else "Off"
        return None


class AquareaDefrostModeSensor(AquareaSensorBase):
    """Defrost mode sensor from Cloud Comfort app."""

    def __init__(
        self,
        coordinator: AquareaDataUpdateCoordinator,
        device_id: str,
    ) -> None:
        """Initialize the defrost mode sensor."""
        super().__init__(coordinator, device_id, "Defrost Mode")

    @property
    def native_value(self) -> str | None:
        """Return the state of the sensor."""
        device_data = self.coordinator.data.get(self._device_id)
        if not device_data:
            return None
            
        raw_data = device_data.get("raw_data")
        if raw_data and 'status' in raw_data:
            defrost_mode = raw_data['status'].get('defrostMode')
            return "Active" if defrost_mode == 1 else "Normal"
        return None


# Cloud Comfort Tank specific sensors

class AquareaTankEcoTemperatureSensor(AquareaSensorBase):
    """Tank eco temperature sensor from Cloud Comfort app."""

    def __init__(
        self,
        coordinator: AquareaDataUpdateCoordinator,
        device_id: str,
    ) -> None:
        """Initialize the tank eco temperature sensor."""
        super().__init__(coordinator, device_id, "Tank Eco Temperature")
        self._attr_device_class = SensorDeviceClass.TEMPERATURE
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS

    @property
    def native_value(self) -> float | None:
        """Return the state of the sensor."""
        device_data = self.coordinator.data.get(self._device_id)
        if not device_data:
            return None
            
        raw_data = device_data.get("raw_data")
        if raw_data and 'status' in raw_data and 'tankStatus' in raw_data['status']:
            tank_status = raw_data['status']['tankStatus']
            eco_temp = tank_status.get('ecoTemp')
            if eco_temp is not None:
                return float(eco_temp)
        return None


class AquareaTankComfortTemperatureSensor(AquareaSensorBase):
    """Tank comfort temperature sensor from Cloud Comfort app."""

    def __init__(
        self,
        coordinator: AquareaDataUpdateCoordinator,
        device_id: str,
    ) -> None:
        """Initialize the tank comfort temperature sensor."""
        super().__init__(coordinator, device_id, "Tank Comfort Temperature")
        self._attr_device_class = SensorDeviceClass.TEMPERATURE
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS

    @property
    def native_value(self) -> float | None:
        """Return the state of the sensor."""
        device_data = self.coordinator.data.get(self._device_id)
        if not device_data:
            return None
            
        raw_data = device_data.get("raw_data")
        if raw_data and 'status' in raw_data and 'tankStatus' in raw_data['status']:
            tank_status = raw_data['status']['tankStatus']
            comfort_temp = tank_status.get('comfortTemp')
            if comfort_temp is not None:
                return float(comfort_temp)
        return None


class AquareaLegionellaModeSensor(AquareaSensorBase):
    """Legionella mode sensor from Cloud Comfort app."""

    def __init__(
        self,
        coordinator: AquareaDataUpdateCoordinator,
        device_id: str,
    ) -> None:
        """Initialize the legionella mode sensor."""
        super().__init__(coordinator, device_id, "Legionella Mode")

    @property
    def native_value(self) -> str | None:
        """Return the state of the sensor."""
        device_data = self.coordinator.data.get(self._device_id)
        if not device_data:
            return None
            
        raw_data = device_data.get("raw_data")
        if raw_data and 'status' in raw_data and 'tankStatus' in raw_data['status']:
            tank_status = raw_data['status']['tankStatus']
            legionella_mode = tank_status.get('legionellaMode')
            return "Active" if legionella_mode == 1 else "Off"
        return None


class AquareaReheatModeSensor(AquareaSensorBase):
    """Reheat mode sensor from Cloud Comfort app."""

    def __init__(
        self,
        coordinator: AquareaDataUpdateCoordinator,
        device_id: str,
    ) -> None:
        """Initialize the reheat mode sensor."""
        super().__init__(coordinator, device_id, "Reheat Mode")

    @property
    def native_value(self) -> str | None:
        """Return the state of the sensor."""
        device_data = self.coordinator.data.get(self._device_id)
        if not device_data:
            return None
            
        raw_data = device_data.get("raw_data")
        if raw_data and 'status' in raw_data and 'tankStatus' in raw_data['status']:
            tank_status = raw_data['status']['tankStatus']
            reheat_mode = tank_status.get('reheatMode')
            return "On" if reheat_mode == 1 else "Off"
        return None
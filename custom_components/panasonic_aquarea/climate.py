"""Climate platform: one entity per heating/cooling zone."""
from __future__ import annotations

import logging
from typing import Any

from aioaquarea.data import (
    DeviceAction,
    ExtendedOperationMode,
    OperationStatus,
    SensorMode,
    SpecialStatus,
    UpdateOperationMode,
)
from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import AquareaDataUpdateCoordinator
from .const import COMFORT_COMFORT, COMFORT_ECO, COMFORT_NORMAL, DOMAIN
from .controls import AquareaEntity, async_command

_LOGGER = logging.getLogger(__name__)

HVAC_TO_UPDATE_MODE = {
    HVACMode.OFF: UpdateOperationMode.OFF,
    HVACMode.HEAT: UpdateOperationMode.HEAT,
    HVACMode.COOL: UpdateOperationMode.COOL,
    HVACMode.AUTO: UpdateOperationMode.AUTO,
}

PRESET_TO_SPECIAL = {
    COMFORT_ECO: SpecialStatus.ECO,
    COMFORT_COMFORT: SpecialStatus.COMFORT,
    COMFORT_NORMAL: None,
}
SPECIAL_TO_PRESET = {
    SpecialStatus.ECO: COMFORT_ECO,
    SpecialStatus.COMFORT: COMFORT_COMFORT,
    None: COMFORT_NORMAL,
}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up one climate entity per zone reported by the device."""
    coordinator: AquareaDataUpdateCoordinator = hass.data[DOMAIN][config_entry.entry_id]

    entities = []
    for device_id, device_data in coordinator.data.items():
        device = device_data.get("device")
        if device is None:
            continue
        for zone_id, zone in device.zones.items():
            entities.append(AquareaClimate(coordinator, device_id, zone_id, zone.name))
    async_add_entities(entities)


class AquareaClimate(AquareaEntity, ClimateEntity):
    """A heating/cooling zone of an Aquarea heat pump."""

    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_target_temperature_step = 1
    _enable_turn_on_off_backwards_compatibility = False

    def __init__(
        self,
        coordinator: AquareaDataUpdateCoordinator,
        device_id: str,
        zone_id: int,
        zone_name: str,
    ) -> None:
        super().__init__(coordinator, device_id)
        self._zone_id = zone_id
        self._attr_name = f"{self.device_name} {zone_name}"
        self._attr_unique_id = f"{device_id}_zone_{zone_id}"

    # ---- typed accessors -------------------------------------------------
    @property
    def zone(self):
        device = self.device
        return device.zones.get(self._zone_id) if device is not None else None

    @property
    def available(self) -> bool:
        return super().available and self.zone is not None

    @property
    def _cooling_mode(self) -> bool:
        device = self.device
        return device is not None and device.mode in (
            ExtendedOperationMode.COOL,
            ExtendedOperationMode.AUTO_COOL,
        )

    # ---- features --------------------------------------------------------
    @property
    def supported_features(self) -> ClimateEntityFeature:
        features = ClimateEntityFeature.TURN_ON | ClimateEntityFeature.TURN_OFF
        zone, device = self.zone, self.device
        if zone is not None and zone.supports_set_temperature:
            features |= ClimateEntityFeature.TARGET_TEMPERATURE
        if device is not None and device.support_special_status:
            features |= ClimateEntityFeature.PRESET_MODE
        return features

    @property
    def hvac_modes(self) -> list[HVACMode]:
        modes = [HVACMode.OFF, HVACMode.HEAT]
        device = self.device
        if device is not None and device.support_cooling(self._zone_id):
            modes += [HVACMode.COOL, HVACMode.AUTO]
        return modes

    @property
    def preset_modes(self) -> list[str]:
        return [COMFORT_ECO, COMFORT_NORMAL, COMFORT_COMFORT]

    # ---- state -----------------------------------------------------------
    @property
    def hvac_mode(self) -> HVACMode | None:
        device, zone = self.device, self.zone
        if device is None or zone is None:
            return None
        if (
            device.operation_status == OperationStatus.OFF
            or zone.operation_status == OperationStatus.OFF
            or device.mode == ExtendedOperationMode.OFF
        ):
            return HVACMode.OFF
        if device.mode in (ExtendedOperationMode.AUTO_HEAT, ExtendedOperationMode.AUTO_COOL):
            return HVACMode.AUTO
        if device.mode == ExtendedOperationMode.COOL:
            return HVACMode.COOL
        return HVACMode.HEAT

    @property
    def hvac_action(self) -> HVACAction | None:
        device = self.device
        if device is None or self.hvac_mode == HVACMode.OFF:
            return HVACAction.OFF if device is not None else None
        return {
            DeviceAction.HEATING: HVACAction.HEATING,
            DeviceAction.COOLING: HVACAction.COOLING,
        }.get(device.current_action, HVACAction.IDLE)

    @property
    def preset_mode(self) -> str | None:
        device = self.device
        if device is None or not device.support_special_status:
            return None
        return SPECIAL_TO_PRESET.get(device.special_status, COMFORT_NORMAL)

    @property
    def current_temperature(self) -> float | None:
        zone = self.zone
        return float(zone.temperature) if zone is not None else None

    @property
    def target_temperature(self) -> float | None:
        zone = self.zone
        if zone is None:
            return None
        value = zone.cool_target_temperature if self._cooling_mode else zone.heat_target_temperature
        return float(value) if value is not None else None

    @property
    def min_temp(self) -> float:
        zone = self.zone
        value = None
        if zone is not None:
            value = zone.cool_min if self._cooling_mode else zone.heat_min
        return float(value) if value is not None else super().min_temp

    @property
    def max_temp(self) -> float:
        zone = self.zone
        value = None
        if zone is not None:
            value = zone.cool_max if self._cooling_mode else zone.heat_max
        return float(value) if value is not None else super().max_temp

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        device, zone = self.device, self.zone
        if device is None or zone is None:
            return None
        sensor = zone.cool_sensor_mode if self._cooling_mode else zone.heat_sensor_mode
        return {
            # "compensation" means the target is an offset on the heating curve,
            # not an absolute room/flow temperature.
            "setpoint_type": "compensation" if sensor == SensorMode.COMPENSATION_CURVE else "direct",
            "outdoor_temperature": device.temperature_outdoor,
            "quiet_mode": device.quiet_mode.name.lower(),
            "powerful_time": device.powerful_time.name.lower(),
        }

    # ---- commands --------------------------------------------------------
    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        device = self.device
        if device is None:
            return
        if hvac_mode not in self.hvac_modes:
            raise ServiceValidationError(f"HVAC mode {hvac_mode} is not supported by this zone")
        old = self.hvac_mode
        await async_command(
            self.coordinator,
            lambda: device.set_mode(HVAC_TO_UPDATE_MODE[hvac_mode], self._zone_id),
            f"set HVAC mode to {hvac_mode}",
        )
        self._fire_action(
            "climate", "HVAC mode changed", old, hvac_mode, zone_id=self._zone_id
        )

    async def async_turn_on(self) -> None:
        mode = HVACMode.HEAT if HVACMode.HEAT in self.hvac_modes else self.hvac_modes[-1]
        await self.async_set_hvac_mode(mode)

    async def async_turn_off(self) -> None:
        await self.async_set_hvac_mode(HVACMode.OFF)

    async def async_set_temperature(self, **kwargs: Any) -> None:
        temperature = kwargs.get(ATTR_TEMPERATURE)
        device, zone = self.device, self.zone
        if temperature is None or device is None or zone is None:
            return
        if not zone.supports_set_temperature:
            raise ServiceValidationError("This zone uses an external sensor; its target cannot be set")
        if device.mode == ExtendedOperationMode.OFF:
            raise ServiceValidationError("Turn the heat pump on before changing the target")
        value = int(round(float(temperature)))
        if not self.min_temp <= value <= self.max_temp:
            raise ServiceValidationError(
                f"Target {value} is outside the allowed range {self.min_temp:g} to {self.max_temp:g}"
            )
        old = self.target_temperature
        await async_command(
            self.coordinator,
            lambda: device.set_temperature(value, self._zone_id),
            f"set target temperature to {value}",
        )
        self._fire_action("climate", "target temperature changed", old, value, zone_id=self._zone_id)

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        device = self.device
        if device is None:
            return
        if preset_mode not in PRESET_TO_SPECIAL:
            raise ServiceValidationError(f"Unknown preset {preset_mode}")
        old = self.preset_mode
        await async_command(
            self.coordinator,
            lambda: device.set_special_status(PRESET_TO_SPECIAL[preset_mode]),
            f"set preset to {preset_mode}",
        )
        self._fire_action("climate", "preset mode changed", old, preset_mode, zone_id=self._zone_id)

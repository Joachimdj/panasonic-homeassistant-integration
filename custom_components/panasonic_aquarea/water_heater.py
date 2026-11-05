"""Water heater platform for the domestic hot water tank."""
from __future__ import annotations

import logging
from typing import Any

from aioaquarea.data import ForceDHW, OperationStatus
from homeassistant.components.water_heater import (
    STATE_HEAT_PUMP,
    STATE_PERFORMANCE,
    WaterHeaterEntity,
    WaterHeaterEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_TEMPERATURE, STATE_OFF, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import AquareaDataUpdateCoordinator
from .const import DOMAIN
from .controls import AquareaEntity, async_command

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Create a water heater for every device that has a tank."""
    coordinator: AquareaDataUpdateCoordinator = hass.data[DOMAIN][config_entry.entry_id]
    async_add_entities(
        AquareaWaterHeater(coordinator, device_id)
        for device_id, data in coordinator.data.items()
        if data.get("device") is not None and data["device"].has_tank
    )


class AquareaWaterHeater(AquareaEntity, WaterHeaterEntity):
    """The hot water tank of an Aquarea heat pump."""

    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_supported_features = (
        WaterHeaterEntityFeature.TARGET_TEMPERATURE
        | WaterHeaterEntityFeature.ON_OFF
        | WaterHeaterEntityFeature.OPERATION_MODE
    )
    _attr_operation_list = [STATE_OFF, STATE_HEAT_PUMP, STATE_PERFORMANCE]

    def __init__(self, coordinator: AquareaDataUpdateCoordinator, device_id: str) -> None:
        super().__init__(coordinator, device_id)
        self._attr_name = f"{self.device_name} Water Heater"
        self._attr_unique_id = f"{device_id}_water_heater"

    @property
    def tank(self):
        device = self.device
        return device.tank if device is not None else None

    @property
    def available(self) -> bool:
        return super().available and self.tank is not None

    @property
    def current_temperature(self) -> float | None:
        tank = self.tank
        return float(tank.temperature) if tank is not None else None

    @property
    def target_temperature(self) -> float | None:
        tank = self.tank
        return float(tank.target_temperature) if tank is not None else None

    @property
    def min_temp(self) -> float:
        tank = self.tank
        return float(tank.heat_min) if tank is not None else super().min_temp

    @property
    def max_temp(self) -> float:
        tank = self.tank
        return float(tank.heat_max) if tank is not None else super().max_temp

    @property
    def current_operation(self) -> str | None:
        tank, device = self.tank, self.device
        if tank is None or device is None:
            return None
        if tank.operation_status == OperationStatus.OFF:
            return STATE_OFF
        return STATE_PERFORMANCE if device.force_dhw == ForceDHW.ON else STATE_HEAT_PUMP

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        device = self.device
        if device is None:
            return None
        return {"force_dhw": device.force_dhw == ForceDHW.ON}

    async def async_set_temperature(self, **kwargs: Any) -> None:
        temperature = kwargs.get(ATTR_TEMPERATURE)
        tank = self.tank
        if temperature is None or tank is None:
            return
        value = int(round(float(temperature)))
        if not tank.heat_min <= value <= tank.heat_max:
            raise ServiceValidationError(
                f"Target {value} is outside the allowed range {tank.heat_min} to {tank.heat_max}"
            )
        old = self.target_temperature
        await async_command(
            self.coordinator,
            lambda: tank.set_target_temperature(value),
            f"set tank target to {value}",
        )
        self._fire_action("water_heater", "temperature changed", old, value)

    async def async_turn_on(self, **kwargs: Any) -> None:
        tank = self.tank
        if tank is not None:
            await async_command(self.coordinator, tank.turn_on, "turn on the tank")
            self._fire_action("water_heater", "turned on")

    async def async_turn_off(self, **kwargs: Any) -> None:
        tank = self.tank
        if tank is not None:
            await async_command(self.coordinator, tank.turn_off, "turn off the tank")
            self._fire_action("water_heater", "turned off")

    async def async_set_operation_mode(self, operation_mode: str) -> None:
        device, tank = self.device, self.tank
        if device is None or tank is None:
            return
        if operation_mode not in self._attr_operation_list:
            raise ServiceValidationError(f"Unknown operation mode {operation_mode}")

        async def _apply() -> None:
            if operation_mode == STATE_OFF:
                await device.set_force_dhw(ForceDHW.OFF)
                await tank.turn_off()
                return
            await tank.turn_on()
            await device.set_force_dhw(
                ForceDHW.ON if operation_mode == STATE_PERFORMANCE else ForceDHW.OFF
            )

        old = self.current_operation
        await async_command(self.coordinator, _apply, f"set tank mode to {operation_mode}")
        self._fire_action("water_heater", "operation mode changed", old, operation_mode)

"""Number platform: heating-curve offset for 'compensation curve' zones.

On those zones the cloud's setpoint is an offset (e.g. -5..+5) applied to the
heating curve, not a temperature, so it is exposed as a number instead of a
climate target. Zones with a direct temperature setpoint use the climate
entity's target temperature instead.
"""
from __future__ import annotations

import logging

from aioaquarea.data import ExtendedOperationMode
from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import AquareaDataUpdateCoordinator
from .const import DOMAIN
from .controls import AquareaEntity, async_command, is_offset_zone

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: AquareaDataUpdateCoordinator = hass.data[DOMAIN][config_entry.entry_id]
    entities = []
    for device_id, data in coordinator.data.items():
        device = data.get("device")
        if device is None:
            continue
        for zone_id, zone in device.zones.items():
            if is_offset_zone(zone):
                entities.append(AquareaOffsetNumber(coordinator, device_id, zone_id, zone.name))
    async_add_entities(entities)


class AquareaOffsetNumber(AquareaEntity, NumberEntity):
    """Heating/cooling curve offset of one zone (follows the current mode)."""

    _attr_mode = NumberMode.BOX
    _attr_native_step = 1
    _attr_icon = "mdi:thermometer-plus"

    def __init__(
        self,
        coordinator: AquareaDataUpdateCoordinator,
        device_id: str,
        zone_id: int,
        zone_name: str,
    ) -> None:
        super().__init__(coordinator, device_id)
        self._zone_id = zone_id
        self._attr_name = f"{self.device_name} {zone_name} Offset"
        self._attr_unique_id = f"{device_id}_zone_{zone_id}_offset"

    @property
    def zone(self):
        device = self.device
        return device.zones.get(self._zone_id) if device is not None else None

    @property
    def available(self) -> bool:
        return super().available and self.zone is not None

    @property
    def _cooling(self) -> bool:
        device = self.device
        return device is not None and device.mode in (
            ExtendedOperationMode.COOL,
            ExtendedOperationMode.AUTO_COOL,
        )

    @property
    def native_value(self) -> float | None:
        zone = self.zone
        if zone is None:
            return None
        value = zone.cool_target_temperature if self._cooling else zone.heat_target_temperature
        return float(value) if value is not None else None

    @property
    def native_min_value(self) -> float:
        zone = self.zone
        value = None if zone is None else (zone.cool_min if self._cooling else zone.heat_min)
        return float(value) if value is not None else -5.0

    @property
    def native_max_value(self) -> float:
        zone = self.zone
        value = None if zone is None else (zone.cool_max if self._cooling else zone.heat_max)
        return float(value) if value is not None else 5.0

    async def async_set_native_value(self, value: float) -> None:
        device = self.device
        if device is None:
            return
        if device.mode == ExtendedOperationMode.OFF:
            raise ServiceValidationError("Turn the heat pump on before changing the offset")
        offset = int(round(value))
        if not self.native_min_value <= offset <= self.native_max_value:
            raise ServiceValidationError(
                f"Offset {offset} is outside {self.native_min_value:g} to {self.native_max_value:g}"
            )
        old = self.native_value
        await async_command(
            self.coordinator,
            lambda: device.set_temperature(offset, self._zone_id),
            f"set offset to {offset}",
        )
        self._fire_action("climate", "offset changed", old, offset, zone_id=self._zone_id)

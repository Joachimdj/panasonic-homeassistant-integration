"""Switches for the Aquarea special modes (all backed by real aioaquarea calls)."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import AquareaDataUpdateCoordinator
from .const import DOMAIN
from .controls import (
    FEATURES,
    REMOVED_SWITCH_NAMES,
    AquareaEntity,
    Feature,
    async_command,
    switch_unique_id,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the switch platform."""
    coordinator: AquareaDataUpdateCoordinator = hass.data[DOMAIN][config_entry.entry_id]
    registry = er.async_get(hass)

    entities: list[AquareaSwitch] = []
    for device_id, device_data in coordinator.data.items():
        device = device_data.get("device")
        if device is None:
            continue

        # Drop switches from earlier versions that had no API behind them.
        for name in REMOVED_SWITCH_NAMES:
            entity_id = registry.async_get_entity_id(
                "switch", DOMAIN, switch_unique_id(device_id, name)
            )
            if entity_id:
                _LOGGER.info("Removing unsupported switch %s", entity_id)
                registry.async_remove(entity_id)

        for feature in FEATURES.values():
            if feature.supported(device):
                entities.append(AquareaSwitch(coordinator, device_id, feature))

    async_add_entities(entities)


class AquareaSwitch(AquareaEntity, SwitchEntity):
    """One special mode of the heat pump."""

    def __init__(
        self,
        coordinator: AquareaDataUpdateCoordinator,
        device_id: str,
        feature: Feature,
    ) -> None:
        super().__init__(coordinator, device_id)
        self._feature = feature
        self._attr_name = f"{self.device_name} {feature.name}"
        self._attr_unique_id = switch_unique_id(device_id, feature.name)
        self._attr_icon = feature.icon

    @property
    def is_on(self) -> bool | None:
        device = self.device
        return self._feature.is_on(device) if device is not None else None

    async def _async_set(self, on: bool) -> None:
        device = self.device
        if device is None:
            return
        old = self.is_on
        await async_command(
            self.coordinator,
            lambda: self._feature.setter(device, on),
            f"turn {'on' if on else 'off'} {self._feature.name.lower()}",
        )
        self._fire_action(
            "switch",
            "turned on" if on else "turned off",
            "ON" if old else "OFF",
            "ON" if on else "OFF",
            switch_type=self._feature.name,
        )

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self._async_set(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self._async_set(False)

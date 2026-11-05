"""Shared helpers and real aioaquarea calls for the Aquarea controls.

Every write goes through ``async_command``: the call is made against the
aioaquarea ``Device`` (with the proper enums), errors are surfaced to the user
as ``HomeAssistantError`` instead of being swallowed, and a *debounced*
coordinator refresh is requested afterwards. Entities never pre-write guessed
values into the cached data, so what the UI shows is always what the cloud
reported.
"""
from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from aioaquarea.data import (
    ForceDHW,
    ForceHeater,
    HolidayTimer,
    PowerfulTime,
    QuietMode,
    SensorMode,
    SpecialStatus,
)
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from .const import DOMAIN

if TYPE_CHECKING:  # pragma: no cover
    from . import AquareaDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

EVENT_ACTION = "panasonic_aquarea_action"


async def async_command(
    coordinator: AquareaDataUpdateCoordinator,
    call: Callable[[], Awaitable[Any]],
    action: str,
) -> None:
    """Run one aioaquarea write, surface failures, then request a refresh."""
    try:
        await call()
    except HomeAssistantError:
        raise
    except Exception as err:  # noqa: BLE001
        _LOGGER.warning("Could not %s: %s", action, err)
        raise HomeAssistantError(f"Could not {action}: {err}") from err
    # Debounced by the coordinator: a burst of changes becomes one request.
    await coordinator.async_request_refresh()


class AquareaEntity(CoordinatorEntity):
    """Common base: typed device access, device info and activity events."""

    _attr_has_entity_name = False

    def __init__(self, coordinator: AquareaDataUpdateCoordinator, device_id: str) -> None:
        super().__init__(coordinator)
        self._device_id = device_id

    @property
    def _device_data(self) -> dict[str, Any]:
        return (self.coordinator.data or {}).get(self._device_id, {})

    @property
    def device(self):
        """The cached aioaquarea Device (None while unavailable)."""
        return self._device_data.get("device")

    @property
    def device_name(self) -> str:
        info = self._device_data.get("info")
        raw = self._device_data.get("raw_data") or {}
        return getattr(info, "name", None) or raw.get("a2wName") or "Aquarea"

    @property
    def available(self) -> bool:
        return super().available and self.device is not None

    @property
    def device_info(self) -> dict[str, Any]:
        info = self._device_data.get("info")
        return {
            "identifiers": {(DOMAIN, self._device_id)},
            "name": self.device_name,
            "manufacturer": "Panasonic",
            "model": getattr(info, "model", None) or "Aquarea Heat Pump",
            "sw_version": getattr(info, "firmware_version", None),
        }

    def _fire_action(self, device_type: str, action: str, old: Any = None, new: Any = None, **extra: Any) -> None:
        """Fire the event consumed by the activity feed listener."""
        if self.hass is None:
            return
        self.hass.bus.async_fire(
            EVENT_ACTION,
            {
                "entity_id": self.entity_id,
                "device_id": self._device_id,
                "device_type": device_type,
                "action": action,
                "old_value": old,
                "new_value": new,
                "timestamp": dt_util.utcnow().isoformat(),
                **extra,
            },
        )


# --------------------------------------------------------------------------
# Real library calls shared by the switch entities and the services.
# --------------------------------------------------------------------------

async def _set_eco(device, on: bool) -> None:
    if on:
        await device.set_special_status(SpecialStatus.ECO)
    elif device.special_status == SpecialStatus.ECO:
        await device.set_special_status(None)


async def _set_comfort(device, on: bool) -> None:
    if on:
        await device.set_special_status(SpecialStatus.COMFORT)
    elif device.special_status == SpecialStatus.COMFORT:
        await device.set_special_status(None)


async def _set_quiet(device, on: bool) -> None:
    await device.set_quiet_mode(QuietMode.LEVEL1 if on else QuietMode.OFF)


async def _set_powerful(device, on: bool) -> None:
    await device.set_powerful_time(PowerfulTime.ON_30MIN if on else PowerfulTime.OFF)


async def _set_force_heater(device, on: bool) -> None:
    await device.set_force_heater(ForceHeater.ON if on else ForceHeater.OFF)


async def _set_holiday(device, on: bool) -> None:
    await device.set_holiday_timer(HolidayTimer.ON if on else HolidayTimer.OFF)


async def _set_force_dhw(device, on: bool) -> None:
    await device.set_force_dhw(ForceDHW.ON if on else ForceDHW.OFF)


@dataclass(frozen=True)
class Feature:
    """One on/off feature of the heat pump backed by a real library call."""

    key: str  # service/helper key
    name: str  # entity name suffix; also feeds the (unchanged) unique_id
    icon: str
    is_on: Callable[[Any], bool]
    setter: Callable[[Any, bool], Awaitable[None]]
    supported: Callable[[Any], bool]


FEATURES: dict[str, Feature] = {
    f.key: f
    for f in (
        Feature("eco", "Eco Mode", "mdi:leaf",
                lambda d: d.special_status == SpecialStatus.ECO, _set_eco,
                lambda d: d.support_special_status),
        Feature("comfort", "Comfort Mode", "mdi:sofa",
                lambda d: d.special_status == SpecialStatus.COMFORT, _set_comfort,
                lambda d: d.support_special_status),
        Feature("quiet", "Quiet Mode", "mdi:volume-off",
                lambda d: d.quiet_mode != QuietMode.OFF, _set_quiet,
                lambda d: True),
        Feature("powerful", "Powerful Mode", "mdi:fire",
                lambda d: d.powerful_time != PowerfulTime.OFF, _set_powerful,
                lambda d: True),
        Feature("force_heater", "Force Heater", "mdi:heating-coil",
                lambda d: d.force_heater == ForceHeater.ON, _set_force_heater,
                lambda d: True),
        Feature("holiday", "Holiday Mode", "mdi:beach",
                lambda d: d.holiday_timer == HolidayTimer.ON, _set_holiday,
                lambda d: True),
        Feature("force_dhw", "Force DHW", "mdi:water-boiler",
                lambda d: d.force_dhw == ForceDHW.ON, _set_force_dhw,
                lambda d: d.has_tank),
    )
}

# Switches from older versions that never had a library call behind them.
REMOVED_SWITCH_NAMES = ("Schedule Enabled", "DHW Priority", "Legionella Mode", "Reheat Mode")


def switch_unique_id(device_id: str, name: str) -> str:
    return f"{device_id}_{name.lower().replace(' ', '_')}"


def is_offset_zone(zone) -> bool:
    """True when the zone's setpoint is a heating-curve offset, not a temperature."""
    return (
        zone.supports_set_temperature
        and zone.heat_sensor_mode == SensorMode.COMPENSATION_CURVE
    )

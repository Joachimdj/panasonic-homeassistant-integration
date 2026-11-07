"""Diagnostics: a redacted snapshot to attach to bug reports.

Never contains credentials, account e-mail, device ids or the device's name.
"""
from __future__ import annotations

from importlib import metadata
from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .controls import is_offset_zone

TO_REDACT = {
    "username", "password", "email", "unique_id", "title",
    "a2wName", "name", "gwid", "deviceGuid", "device_id", "long_id", "ownerFlg",
}


def _library_version() -> str | None:
    try:
        return metadata.version("aioaquarea")
    except metadata.PackageNotFoundError:
        return None


def _zone_summary(zone) -> dict[str, Any]:
    return {
        "name": zone.name,
        "type": str(zone.type),
        "sensor": str(zone.sensor_mode),
        # The library always says "Direct"; this is what the integration uses.
        "library_heat_sensor_mode": str(zone.heat_sensor_mode),
        "setpoint_is_offset": is_offset_zone(zone),
        "cool_mode": zone.cool_mode,
        "operation_status": zone.operation_status.name,
        "temperature": zone.temperature,
        "heat_target": zone.heat_target_temperature,
        "heat_range": [zone.heat_min, zone.heat_max],
        "cool_target": zone.cool_target_temperature,
        "cool_range": [zone.cool_min, zone.cool_max],
        "supports_set_temperature": zone.supports_set_temperature,
    }


def _device_summary(device) -> dict[str, Any]:
    tank = device.tank
    return {
        "model": device.model,
        "firmware": device.firmware_version,
        "mode": device.mode.name,
        "operation_status": device.operation_status.name,
        "special_status": device.special_status.name if device.special_status else None,
        "quiet_mode": device.quiet_mode.name,
        "powerful_time": device.powerful_time.name,
        "force_dhw": device.force_dhw.name,
        "force_heater": device.force_heater.name,
        "holiday_timer": device.holiday_timer.name,
        "direction": device.current_direction.name,
        "pump_duty": device.pump_duty.name,
        "outdoor_temperature": device.temperature_outdoor,
        "fault": device.current_error.error_code if device.is_on_error else None,
        "has_tank": device.has_tank,
        "tank": None if tank is None else {
            "operation_status": tank.operation_status.name,
            "temperature": tank.temperature,
            "target": tank.target_temperature,
            "range": [tank.heat_min, tank.heat_max],
        },
        "zones": {str(zid): _zone_summary(z) for zid, z in device.zones.items()},
    }


async def async_get_config_entry_diagnostics(hass: HomeAssistant, entry: ConfigEntry) -> dict[str, Any]:
    coordinator = hass.data.get(DOMAIN, {}).get(entry.entry_id)
    devices: dict[str, Any] = {}
    if coordinator is not None:
        # Device ids are replaced by an index so reports cannot be tied to an account.
        for index, data in enumerate((coordinator.data or {}).values()):
            device = data.get("device")
            devices[f"device_{index}"] = {
                "typed": _device_summary(device) if device is not None else None,
                "raw_status": async_redact_data(data.get("raw_data") or {}, TO_REDACT),
                "measured_consumption_kwh_today": data.get("consumption"),
            }

    return {
        "entry": async_redact_data(
            {"data": dict(entry.data), "options": dict(entry.options), "state": entry.state.value},
            TO_REDACT,
        ),
        "versions": {"aioaquarea": _library_version()},
        "coordinator": None if coordinator is None else {
            "update_interval_s": coordinator.update_interval.total_seconds() if coordinator.update_interval else None,
            "last_update_success": coordinator.last_update_success,
            "last_exception": repr(coordinator.last_exception) if coordinator.last_exception else None,
            "consecutive_failures": coordinator._failures,  # noqa: SLF001
        },
        "devices": devices,
    }

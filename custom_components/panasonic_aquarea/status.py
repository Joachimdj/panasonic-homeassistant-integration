"""Fetch and parse the device status ourselves (one request, raw JSON kept).

aioaquarea 1.0.x throws the raw JSON away and mis-parses two fields:
``operation_status`` is read from ``specialStatus`` and ``special_status`` is
hard-coded to ``None``. That made eco/comfort impossible to read. We therefore
perform the same status request the library does, keep the JSON for the
sensors, and build the library's ``DeviceStatus`` with a correct parser.
"""
from __future__ import annotations

import datetime as dt
import logging
from typing import Any

from aioaquarea.data import (
    DeviceDirection,
    DeviceModeStatus,
    DeviceStatus,
    DeviceZoneStatus,
    ExtendedOperationMode,
    FaultError,
    ForceDHW,
    ForceHeater,
    HolidayTimer,
    OperationStatus,
    PowerfulTime,
    PumpDuty,
    QuietMode,
    SpecialStatus,
    TankStatus,
)
from aioaquarea.statistics import DateType

_LOGGER = logging.getLogger(__name__)

STATUS_PATH = "remote/v1/app/common/transfer"


def _enum(enum_cls, value, default):
    """Tolerant enum conversion: unknown values fall back instead of raising."""
    try:
        return enum_cls(value)
    except (ValueError, TypeError):
        return default


def parse_status(raw: dict[str, Any], long_id: str) -> DeviceStatus:
    """Build the library's DeviceStatus from the cloud JSON."""
    st = raw.get("status") or {}

    raw_mode = st.get("operationMode")
    mode = (
        ExtendedOperationMode.OFF
        if raw_mode in (None, 99)
        else _enum(ExtendedOperationMode, raw_mode, ExtendedOperationMode.OFF)
    )

    tank = st.get("tankStatus")
    zones = [
        DeviceZoneStatus(
            zone_id=z.get("zoneId"),
            temperature=z.get("temperatureNow"),
            operation_status=_enum(OperationStatus, z.get("operationStatus"), OperationStatus.OFF),
            heat_max=z.get("heatMax"),
            heat_min=z.get("heatMin"),
            heat_set=z.get("heatSet"),
            cool_max=z.get("coolMax"),
            cool_min=z.get("coolMin"),
            cool_set=z.get("coolSet"),
            comfort_cool=z.get("comfortCool"),
            comfort_heat=z.get("comfortHeat"),
            eco_cool=z.get("ecoCool"),
            eco_heat=z.get("ecoHeat"),
        )
        for z in st.get("zoneStatus", [])
        if isinstance(z, dict)
    ]

    special = st.get("specialStatus")
    return DeviceStatus(
        long_id=long_id,
        # The cloud has no single on/off flag: the unit is "on" when it has a mode.
        operation_status=OperationStatus.OFF if mode == ExtendedOperationMode.OFF else OperationStatus.ON,
        device_status=_enum(DeviceModeStatus, st.get("deiceStatus"), DeviceModeStatus.NORMAL),
        temperature_outdoor=st.get("outdoorNow"),
        operation_mode=mode,
        fault_status=[
            FaultError(f.get("errorMessage"), f.get("errorCode"))
            for f in st.get("faultStatus", [])
            if isinstance(f, dict)
        ],
        direction=_enum(DeviceDirection, st.get("direction"), DeviceDirection.IDLE),
        pump_duty=_enum(PumpDuty, st.get("pumpDuty"), PumpDuty.OFF),
        tank_status=(
            [
                TankStatus(
                    _enum(OperationStatus, tank.get("operationStatus"), OperationStatus.OFF),
                    tank.get("temperatureNow"),
                    tank.get("heatMax"),
                    tank.get("heatMin"),
                    tank.get("heatSet"),
                )
            ]
            if tank
            else []
        ),
        zones=zones,
        quiet_mode=_enum(QuietMode, st.get("quietMode", 0), QuietMode.OFF),
        force_dhw=_enum(ForceDHW, st.get("forceDHW", 0), ForceDHW.OFF),
        force_heater=_enum(ForceHeater, st.get("forceHeater", 0), ForceHeater.OFF),
        holiday_timer=_enum(HolidayTimer, st.get("holidayTimer", 0), HolidayTimer.OFF),
        powerful_time=_enum(PowerfulTime, st.get("powerful", 0), PowerfulTime.OFF),
        special_status=SpecialStatus(special) if special in (1, 2) else None,
    )


async def fetch_status_json(client, gwid: str) -> dict[str, Any]:
    """POST the status request the library uses (live device data), return JSON.

    One request, no silent retry against the cached endpoint: the coordinator's
    exponential backoff decides what to do after a failure.
    """
    if not client.is_logged:
        await client.login()
    payload = {
        "apiName": f"/remote/v1/api/devices?gwid={gwid}&deviceDirect=1",
        "requestMethod": "GET",
    }
    response = await client._api_client.request(  # noqa: SLF001 - no public equivalent
        "POST", url=STATUS_PATH, json=payload, throw_on_error=True
    )
    data = await response.json()
    if not isinstance(data, dict) or "status" not in data:
        raise ValueError(f"Unexpected status payload for {gwid}")
    return data


async def fetch_today_consumption(client, long_id: str, today: dt.date) -> dict[str, float] | None:
    """Sum today's measured consumption (kWh) from Panasonic's statistics."""
    items = await client.get_device_consumption(long_id, DateType.DAY, today.strftime("%Y%m%d"))
    if not items:
        return None

    def total(attr: str) -> float:
        return round(sum(float(v) for i in items if (v := getattr(i, attr)) is not None), 3)

    heat, cool, tank = total("heat_consumption"), total("cool_consumption"), total("tank_consumption")
    return {"heat": heat, "cool": cool, "tank": tank, "total": round(heat + cool + tank, 3)}

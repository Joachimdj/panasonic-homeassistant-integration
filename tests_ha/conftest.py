"""Fixtures: load the integration in a real Home Assistant against a fake cloud."""
from __future__ import annotations

import types
from unittest.mock import patch

import pytest
from aioaquarea.data import (
    DeviceZoneInfo, SensorMode, ZoneSensor, ZoneType,
)
from aioaquarea.entities import DeviceImpl
from pytest_homeassistant_custom_component.common import MockConfigEntry

import custom_components.panasonic_aquarea  # noqa: F401  (patch targets must be importable)
import custom_components.panasonic_aquarea.config_flow  # noqa: F401

DOMAIN = "panasonic_aquarea"

# Shape of a real cloud response (values from a live log, names scrubbed).
REAL = {
    "operation": "FFFFFFFF", "ownerFlg": True, "a2wName": "My Heat Pump",
    "status": {
        "serviceType": "STD_ADP-TAW1", "operationMode": 1, "coolMode": 1, "direction": 2,
        "quietMode": 0, "powerful": 0, "forceDHW": 0, "forceHeater": 0, "tank": 1,
        "multiOdConnection": 0, "pumpDuty": 1, "bivalent": 0, "bivalentActual": 0,
        "waterPressure": 2.18, "electricAnode": 0, "deiceStatus": 0, "specialStatus": 2,
        "outdoorNow": 7, "holidayTimer": 0, "modelSeriesSelection": 5, "standAlone": 1,
        "controlBox": 0, "externalHeater": 0,
        "zoneStatus": [{"zoneId": 1, "zoneName": "House", "zoneType": 0, "zoneSensor": 0,
            "operationStatus": 1, "temperatureNow": 49, "heatMin": -5, "heatMax": 5,
            "coolMin": -5, "coolMax": 5, "heatSet": 5, "coolSet": 0, "ecoHeat": -5,
            "ecoCool": 5, "comfortHeat": 5, "comfortCool": -5}],
        "tankStatus": {"operationStatus": 1, "temperatureNow": 61, "heatMin": 40, "heatMax": 75, "heatSet": 60},
    },
}


class _Resp:
    def __init__(self, data): self._d = data
    async def json(self): return self._d


class _Api:
    def __init__(self, cloud): self.cloud = cloud
    async def request(self, method, url=None, json=None, throw_on_error=False):
        self.cloud.status_requests += 1
        if self.cloud.fail_status:
            raise RuntimeError("cloud unavailable")
        return _Resp(self.cloud.payload)


class FakeCloud:
    """Shared state between the test and the fake client."""
    def __init__(self):
        self.payload = REAL
        self.calls: list[tuple] = []
        self.status_requests = 0
        self.fail_status = False
        self.fail_posts: str | None = None
        self.auth_error = False
        self.sensor_mode = SensorMode.COMPENSATION_CURVE


def make_client_class(cloud: FakeCloud):
    class FakeClient:
        is_logged = True

        def __init__(self, *a, **k):
            self._api_client = _Api(cloud)

        async def login(self): pass

        async def get_devices(self):
            if cloud.auth_error:
                from aioaquarea.errors import AuthenticationError
                raise AuthenticationError("401", "bad password")
            zone = DeviceZoneInfo(1, "House", list(ZoneType)[0], False, ZoneSensor.INTERNAL, cloud.sensor_mode, None)
            return [types.SimpleNamespace(
                device_id="B1", long_id="L", name="My Heat Pump", model="WH-MDC", firmware_version="1.0",
                has_tank=True, zones=[zone])]

        async def get_device_status(self, info):  # replaced by the coordinator
            raise AssertionError("library status fetch must be replaced")

        async def get_device(self, device_info=None, **k):
            st = await self.get_device_status(device_info)
            i = device_info
            return DeviceImpl(i.device_id, i.long_id, i.name, i.firmware_version, i.model,
                              i.has_tank, i.zones, st, self)

        async def get_device_consumption(self, long_id, aggregation, date):
            row = types.SimpleNamespace(heat_consumption=1.5, cool_consumption=None, tank_consumption=0.5)
            return [row]

        def __getattr__(self, name):
            if name.startswith("post_"):
                async def rec(*args, **kwargs):
                    cloud.calls.append((name, args))
                    if cloud.fail_posts == name:
                        raise RuntimeError("429 too many requests")
                return rec
            raise AttributeError(name)

    return FakeClient


@pytest.fixture(autouse=True)
def _enable(enable_custom_integrations):
    yield


@pytest.fixture
def cloud():
    return FakeCloud()


@pytest.fixture
async def setup_integration(hass, cloud):
    """Return an async callable that sets the entry up; unloads it afterwards.

    The fake Client stays patched for the whole test so reloads keep using it.
    """
    entries = []
    with patch(f"custom_components.{DOMAIN}.Client", make_client_class(cloud)):

        async def _setup(options=None):
            entry = MockConfigEntry(domain=DOMAIN, data={"username": "u@example.com", "password": "pw"},
                                    options=options or {}, unique_id="u@example.com")
            entry.add_to_hass(hass)
            entries.append(entry)
            await hass.config_entries.async_setup(entry.entry_id)
            await hass.async_block_till_done()
            return entry

        yield _setup
        for entry in entries:
            if entry.state.value == "loaded":
                await hass.config_entries.async_unload(entry.entry_id)
                await hass.async_block_till_done()

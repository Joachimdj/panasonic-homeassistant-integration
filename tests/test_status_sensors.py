"""Status parsing, coordinator request budget, offset number, sensors, energy."""
import asyncio, sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from stub_ha import *
import importlib, logging

pkg = importlib.import_module("custom_components.panasonic_aquarea")
status_mod = importlib.import_module("custom_components.panasonic_aquarea.status")
number = importlib.import_module("custom_components.panasonic_aquarea.number")
sensor = importlib.import_module("custom_components.panasonic_aquarea.sensor")
climate = importlib.import_module("custom_components.panasonic_aquarea.climate")

# Shape of a real cloud response (values from a live log, names scrubbed).
REAL = {
    "operation": "FFFFFFFF", "ownerFlg": True, "a2wName": "My Heat Pump",
    "status": {
        "serviceType": "STD_ADP-TAW1", "operationMode": 1, "coolMode": 1, "direction": 2,
        "quietMode": 0, "powerful": 0, "forceDHW": 1, "forceHeater": 0, "tank": 1,
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

fails = []
def check(name, cond, extra=""):
    print(("PASS " if cond else "FAIL ") + name + (f"  {extra}" if extra and not cond else ""))
    if not cond: fails.append(name)

class Resp:
    def __init__(s, d): s.d = d
    async def json(s): return s.d
class Api:
    def __init__(s): s.requests = []; s.payload = REAL
    async def request(s, method, url=None, json=None, throw_on_error=False):
        s.requests.append(json["apiName"]); return Resp(s.payload)
class Cl(FakeClient):
    is_logged = True
    def __init__(s):
        super().__init__(); s._api_client = Api(); s.consumption_calls = 0
    async def login(s): pass
    async def get_devices(s):
        return [types.SimpleNamespace(device_id="B1", long_id="L", name="My Heat Pump", model="m",
                firmware_version="f", has_tank=True, zones=[DeviceZoneInfo(1, "House", list(ZoneType)[0], False,
                ZoneSensor.INTERNAL, SensorMode.COMPENSATION_CURVE, None)])]
    async def get_device_status(s, info): raise AssertionError("library fetch must be replaced")
    async def get_device(s, device_info=None, **k):
        st = await s.get_device_status(device_info)
        i = device_info
        return DeviceImpl(i.device_id, i.long_id, i.name, i.firmware_version, i.model, i.has_tank, i.zones, st, s)
    async def get_device_consumption(s, long_id, aggregation, date):
        s.consumption_calls += 1
        class It:  # hourly rows as the statistics endpoint returns them
            def __init__(s, h, t): s.heat_consumption, s.cool_consumption, s.tank_consumption = h, None, t
        return [It(0.5, 0.1), It(0.25, 0.2), It(None, None)]

async def main():
    # ---- parser on real-shaped JSON
    st = status_mod.parse_status(REAL, "L")
    check("parser: special status COMFORT from specialStatus=2", st.special_status == SpecialStatus.COMFORT, st.special_status)
    check("parser: operation_status ON when mode set (lib used specialStatus)", st.operation_status == OperationStatus.ON)
    check("parser: force dhw / tank / zone", st.force_dhw == ForceDHW.ON and st.tank_status[0].heat_set == 60 and st.zones[0].heat_set == 5)
    off = status_mod.parse_status({"status": {**REAL["status"], "operationMode": 99, "specialStatus": 0, "direction": 9}}, "L")
    check("parser: mode 99 -> OFF, unknown values tolerated", off.operation_mode == ExtendedOperationMode.OFF and off.operation_status == OperationStatus.OFF and off.special_status is None)

    # ---- coordinator: one request per poll, raw kept, library fetch bypassed
    cl = Cl(); c = pkg.AquareaDataUpdateCoordinator(None, cl, 90)
    for _ in range(3):
        d = await c._async_update_data(); c.data = d
    check("exactly one status request per poll", len(cl._api_client.requests) == 3, cl._api_client.requests)
    check("status request uses live device endpoint", all("deviceDirect=1" in r for r in cl._api_client.requests))
    check("raw JSON kept for sensors", d["B1"]["raw_data"]["status"]["waterPressure"] == 2.18)
    check("typed special status correct", d["B1"]["device"].special_status == SpecialStatus.COMFORT)
    check("consumption fetched once within the hour", cl.consumption_calls == 1, cl.consumption_calls)
    check("consumption summed", d["B1"]["consumption"] == {"heat": 0.75, "cool": 0.0, "tank": 0.3, "total": 1.05}, d["B1"]["consumption"])
    REAL2 = {**REAL, "status": {**REAL["status"], "zoneStatus": [{**REAL["status"]["zoneStatus"][0], "temperatureNow": 52}]}}
    cl._api_client.payload = REAL2
    d = await c._async_update_data(); c.data = d
    check("zone temperature follows the poll", d["B1"]["device"].zones[1].temperature == 52)

    # ---- climate/number for a compensation-curve zone
    coord = DUC(None, None); coord.data = d
    cz = climate.AquareaClimate(coord, "B1", 1, "House")
    check("climate has no TARGET_TEMPERATURE for offset zone", not (cz.supported_features & Flag.TARGET_TEMPERATURE))
    check("climate preset reads COMFORT from real data", cz.preset_mode == "comfort", cz.preset_mode)
    try: await cz.async_set_temperature(temperature=2); check("climate rejects offset zone temperature", False)
    except SVE: check("climate rejects offset zone temperature", True)
    n = number.AquareaOffsetNumber(coord, "B1", 1, "House")
    check("number reads offset and range", (n.native_value, n.native_min_value, n.native_max_value) == (5.0, -5.0, 5.0))
    cl.calls.clear(); await n.async_set_native_value(3)
    check("number writes heat offset for zone", cl.calls == [("post_device_zone_heat_temperature", ("L", 1, 3))], cl.calls)
    try: await n.async_set_native_value(15); check("number rejects out of range", False)
    except SVE: check("number rejects out of range", True)

    # ---- sensors
    ents = {}
    dev = d["B1"]["device"]
    for sd in list(sensor.DEVICE_SENSORS) + list(sensor.TANK_SENSORS):
        if sd.applies(dev): ents[sd.name] = sensor.AquareaSensor(coord, "B1", sd)
    check("outdoor temp", ents["Outdoor Temperature"].native_value == 7)
    check("water pressure from raw", ents["Water Pressure"].native_value == 2.18)
    check("tank temp/target", (ents["Tank Temperature"].native_value, ents["Tank Target Temperature"].native_value) == (61, 60))
    check("operation mode name", ents["Operation Mode"].native_value == "Heat", ents["Operation Mode"].native_value)
    check("direction not misnamed (2 = Water)", ents["Direction"].native_value == "Water", ents["Direction"].native_value)
    check("fault none", ents["Fault"].native_value == "None")
    check("energy today is measured total", ents["Energy Today"].native_value == 1.05)
    check("dhw energy", ents["DHW Energy Today"].native_value == 0.3)
    check("no cooling energy sensor without cooling zone", "Cooling Energy Today" not in ents)
    check("energy unique id kept", ents["Energy Today"]._attr_unique_id == "B1_energy_today")
    check("removed fakes are gone", not any(k in ents for k in ("Power Consumption", "Energy Total", "COP (Coefficient of Performance)", "Eco Mode")))

    print("failures:", fails or "none")
asyncio.run(main())
sys.exit(1 if fails else 0)

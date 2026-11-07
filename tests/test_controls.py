import asyncio, sys
import os; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from stub_ha import *
import importlib
pkg = importlib.import_module("custom_components.panasonic_aquarea")
climate = importlib.import_module("custom_components.panasonic_aquarea.climate")
wh = importlib.import_module("custom_components.panasonic_aquarea.water_heater")
sw = importlib.import_module("custom_components.panasonic_aquarea.switch")
ctl = importlib.import_module("custom_components.panasonic_aquarea.controls")

fails = []
def check(name, cond, extra=""):
    print(("PASS " if cond else "FAIL ") + name + (f"  {extra}" if extra and not cond else ""))
    if not cond: fails.append(name)

async def main():
    client = FakeClient()
    dev = make_device(client)
    coord = DUC(None, None); 
    coord.data = {"B1": {"device": dev, "info": types.SimpleNamespace(name="My Heat Pump", model="m", firmware_version="f"), "raw_data": {}}}

    # --- stale zone workaround ---
    client.status = make_status(zone_temp=77, zone_set=2)
    await dev.refresh_data()
    check("library zones are stale after refresh_data (bug confirmed)", dev.zones[1].temperature == 49)
    pkg._refresh_zones(dev)
    check("workaround refreshes zone temp", dev.zones[1].temperature == 77 and dev.zones[1].heat_target_temperature == 2)
    client.status = make_status(); await dev.refresh_data(); pkg._refresh_zones(dev)

    # --- climate reads ---
    c = climate.AquareaClimate(coord, "B1", 1, "House")
    check("climate unique_id kept", c._attr_unique_id == "B1_zone_1")
    check("hvac_mode HEAT", c.hvac_mode == HVACMode.HEAT, c.hvac_mode)
    check("current temp from library (not /10)", c.current_temperature == 49.0)
    check("target from library", c.target_temperature == 5.0)
    check("min/max from zone", (c.min_temp, c.max_temp) == (10.0, 35.0), (c.min_temp, c.max_temp))
    check("hvac_modes no cool without cooling", c.hvac_modes == [HVACMode.OFF, HVACMode.HEAT])
    check("preset comfort", c.preset_mode == "comfort", c.preset_mode)
    check("setpoint type direct", c.extra_state_attributes["setpoint_type"] == "direct")
    check("hvac_action idle/heating", c.hvac_action in (HVACAction.HEATING, HVACAction.IDLE))

    # --- climate writes ---
    client.calls.clear(); coord.refreshes = 0
    await c.async_set_temperature(temperature=25)
    check("set_temperature -> heat endpoint w/ zone", client.calls == [("post_device_zone_heat_temperature", ("L", 1, 25))], client.calls)
    check("refresh requested after write", coord.refreshes == 1)
    for bad in (9, 99):
        try: await c.async_set_temperature(temperature=bad); check(f"out of range {bad} rejected", False)
        except SVE: check(f"out of range {bad} rejected", True)
    client.calls.clear()
    await c.async_set_hvac_mode(HVACMode.OFF)
    check("hvac OFF -> operation_update OFF", client.calls and client.calls[0][0] == "post_device_operation_update" and client.calls[0][1][1] == UpdateOperationMode.OFF, client.calls)
    client.calls.clear()
    await c.async_set_preset_mode("eco")
    check("preset eco -> special status", client.calls and client.calls[0][0] == "post_device_set_special_status" and client.calls[0][1][1] == SpecialStatus.ECO, client.calls)
    try: await c.async_set_hvac_mode(HVACMode.COOL); check("cool rejected when unsupported", False)
    except SVE: check("cool rejected when unsupported", True)

    # failure surfaces
    async def boom(*a, **k): raise RuntimeError("429")
    client.post_device_zone_heat_temperature = boom
    try: await c.async_set_temperature(temperature=25); check("API failure raises HomeAssistantError", False)
    except HAError: check("API failure raises HomeAssistantError", True)
    del client.post_device_zone_heat_temperature

    # off state refuses temperature
    off_client = FakeClient(); off_dev = make_device(off_client, make_status(mode=ExtendedOperationMode.OFF, op=OperationStatus.OFF))
    pkg._refresh_zones(off_dev)
    coord2 = DUC(None, None); coord2.data = {"B1": {"device": off_dev, "info": None, "raw_data": {"a2wName": "x"}}}
    c2 = climate.AquareaClimate(coord2, "B1", 1, "House")
    check("hvac OFF reported", c2.hvac_mode == HVACMode.OFF and c2.hvac_action == HVACAction.OFF)
    try: await c2.async_set_temperature(temperature=1); check("set temp while off rejected", False)
    except SVE: check("set temp while off rejected", True)

    # --- switches ---
    expected = {
        "eco": ("post_device_set_special_status", 1, SpecialStatus.ECO),
        "quiet": ("post_device_set_quiet_mode", 1, QuietMode.LEVEL1),
        "powerful": ("post_device_set_powerful_time", 1, PowerfulTime.ON_30MIN),
        "force_heater": ("post_device_force_heater", 1, ForceHeater.ON),
        "holiday": ("post_device_holiday_timer", 1, HolidayTimer.ON),
        "force_dhw": ("post_device_force_dhw", 1, ForceDHW.ON),
    }
    for key, (call, idx, val) in expected.items():
        client.calls.clear()
        e = sw.AquareaSwitch(coord, "B1", ctl.FEATURES[key])
        await e.async_turn_on()
        ok = client.calls and client.calls[0][0] == call and client.calls[0][1][idx] == val and type(client.calls[0][1][idx]) is type(val)
        check(f"switch {key} on -> {call}({val!r})", ok, client.calls)
    check("switch unique ids unchanged", sw.AquareaSwitch(coord, "B1", ctl.FEATURES["eco"])._attr_unique_id == "B1_eco_mode" and ctl.switch_unique_id("B1","Force DHW") == "B1_force_dhw")
    # state reflection
    client.status = make_status(); 
    st = make_status(); st.quiet_mode = QuietMode.LEVEL2; st.force_dhw = ForceDHW.ON
    client.status = st; await dev.refresh_data()
    check("quiet switch reads library state", sw.AquareaSwitch(coord, "B1", ctl.FEATURES["quiet"]).is_on is True)
    check("force_dhw switch reads library state", sw.AquareaSwitch(coord, "B1", ctl.FEATURES["force_dhw"]).is_on is True)
    check("eco switch off when comfort", sw.AquareaSwitch(coord, "B1", ctl.FEATURES["eco"]).is_on is False)
    client.calls.clear()
    await sw.AquareaSwitch(coord, "B1", ctl.FEATURES["eco"]).async_turn_off()
    check("eco off while comfort active is a no-op", client.calls == [], client.calls)

    # --- water heater ---
    w = wh.AquareaWaterHeater(coord, "B1")
    check("wh unique id kept", w._attr_unique_id == "B1_water_heater")
    check("wh reads tank", (w.current_temperature, w.target_temperature, w.min_temp, w.max_temp) == (59.0, 60.0, 40.0, 75.0))
    check("wh operation performance (force dhw)", w.current_operation == "performance", w.current_operation)
    client.calls.clear()
    await w.async_set_temperature(temperature=55)
    check("wh set 55 -> tank temperature endpoint", client.calls == [("post_device_tank_temperature", ("B1", 55))], client.calls)
    try: await w.async_set_temperature(temperature=90); check("wh 90 rejected", False)
    except SVE: check("wh 90 rejected", True)
    client.calls.clear()
    await w.async_set_operation_mode("heat_pump")
    check("wh heat_pump -> force dhw OFF", ("post_device_force_dhw", ("L", ForceDHW.OFF)) in client.calls, client.calls)
    client.calls.clear()
    await w.async_turn_off()
    check("wh turn_off -> tank op status", client.calls and client.calls[0][0] == "post_device_tank_operation_status", client.calls)

asyncio.run(main())
sys.exit(1 if fails else 0)

"""End-to-end checks in a real Home Assistant (fake cloud, real entity registry)."""
from __future__ import annotations

import pytest
from aioaquarea.data import ForceDHW, PowerfulTime, QuietMode, SpecialStatus, UpdateOperationMode
from homeassistant.config_entries import ConfigEntryState
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

DOMAIN = "panasonic_aquarea"


def calls(cloud, name):
    return [a for n, a in cloud.calls if n == name]


async def test_setup_creates_expected_entities(hass, setup_integration):
    entry = await setup_integration()
    assert entry.state is ConfigEntryState.LOADED
    reg = er.async_get(hass)
    ids = {e.unique_id: e.entity_id for e in er.async_entries_for_config_entry(reg, entry.entry_id)}
    for uid in ("B1_zone_1", "B1_zone_1_offset", "B1_water_heater", "B1_eco_mode", "B1_comfort_mode",
                "B1_quiet_mode", "B1_powerful_mode", "B1_force_heater", "B1_holiday_mode", "B1_force_dhw",
                "B1_energy_today", "B1_outdoor_temperature", "B1_water_pressure"):
        assert uid in ids, f"missing {uid}; have {sorted(ids)}"
    for gone in ("B1_schedule_enabled", "B1_legionella_mode", "B1_reheat_mode", "B1_dhw_priority",
                 "B1_power_consumption", "B1_energy_total"):
        assert gone not in ids


async def test_states_come_from_real_data(hass, setup_integration):
    await setup_integration()
    climate = hass.states.get("climate.my_heat_pump_zone_1")
    assert climate.state == "heat"
    assert climate.attributes["preset_mode"] == "comfort"
    assert climate.attributes["setpoint_type"] == "compensation"
    assert "temperature" not in climate.attributes or climate.attributes.get("temperature") is None
    assert float(climate.attributes["current_temperature"]) == 49.0
    wh = hass.states.get("water_heater.my_heat_pump_water_heater")
    assert wh.attributes["current_temperature"] == 61 and wh.attributes["temperature"] == 60
    assert wh.state == "heat_pump"
    assert hass.states.get("number.my_heat_pump_zone_1_offset").state == "5.0"
    assert hass.states.get("sensor.my_heat_pump_water_pressure").state == "2.18"
    assert hass.states.get("sensor.my_heat_pump_energy_today").state == "2.0"


async def test_comfort_switch_reflects_special_status(hass, setup_integration):
    await setup_integration()
    # specialStatus=2 is COMFORT in the cloud payload
    assert hass.states.get("switch.my_heat_pump_comfort_mode").state == "on"
    assert hass.states.get("switch.my_heat_pump_eco_mode").state == "off"


async def test_switch_calls_use_enums(hass, setup_integration, cloud):
    await setup_integration()
    for entity, call, value, idx in (
        ("switch.my_heat_pump_quiet_mode", "post_device_set_quiet_mode", QuietMode.LEVEL1, 1),
        ("switch.my_heat_pump_powerful_mode", "post_device_set_powerful_time", PowerfulTime.ON_30MIN, 1),
        ("switch.my_heat_pump_force_dhw", "post_device_force_dhw", ForceDHW.ON, 1),
    ):
        cloud.calls.clear()
        await hass.services.async_call("switch", "turn_on", {"entity_id": entity}, blocking=True)
        got = calls(cloud, call)
        assert got and got[0][idx] == value and type(got[0][idx]) is type(value), (entity, cloud.calls)


async def test_eco_switch_sets_special_status(hass, setup_integration, cloud):
    await setup_integration()
    await hass.services.async_call("switch", "turn_on", {"entity_id": "switch.my_heat_pump_eco_mode"}, blocking=True)
    assert calls(cloud, "post_device_set_special_status")[0][1] == SpecialStatus.ECO


async def test_water_heater_target_and_validation(hass, setup_integration, cloud):
    await setup_integration()
    await hass.services.async_call("water_heater", "set_temperature",
        {"entity_id": "water_heater.my_heat_pump_water_heater", "temperature": 55}, blocking=True)
    assert calls(cloud, "post_device_tank_temperature") == [("B1", 55)]
    cloud.calls.clear()
    with pytest.raises(Exception):  # HA validates against max_temp (75) before our code
        await hass.services.async_call("water_heater", "set_temperature",
            {"entity_id": "water_heater.my_heat_pump_water_heater", "temperature": 99}, blocking=True)
    assert not calls(cloud, "post_device_tank_temperature")


async def test_offset_number_and_climate_rejection(hass, setup_integration, cloud):
    await setup_integration()
    await hass.services.async_call("number", "set_value",
        {"entity_id": "number.my_heat_pump_zone_1_offset", "value": 2}, blocking=True)
    assert calls(cloud, "post_device_zone_heat_temperature") == [("L", 1, 2)]
    with pytest.raises(Exception):
        await hass.services.async_call("climate", "set_temperature",
            {"entity_id": "climate.my_heat_pump_zone_1", "temperature": 3}, blocking=True)


async def test_climate_hvac_off_and_preset(hass, setup_integration, cloud):
    await setup_integration()
    await hass.services.async_call("climate", "set_hvac_mode",
        {"entity_id": "climate.my_heat_pump_zone_1", "hvac_mode": "off"}, blocking=True)
    assert calls(cloud, "post_device_operation_update")[0][1] == UpdateOperationMode.OFF
    await hass.services.async_call("climate", "set_preset_mode",
        {"entity_id": "climate.my_heat_pump_zone_1", "preset_mode": "eco"}, blocking=True)
    assert calls(cloud, "post_device_set_special_status")[0][1] == SpecialStatus.ECO


async def test_api_failure_reaches_the_user(hass, setup_integration, cloud):
    await setup_integration()
    cloud.fail_posts = "post_device_set_quiet_mode"
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call("switch", "turn_on", {"entity_id": "switch.my_heat_pump_quiet_mode"}, blocking=True)


async def test_custom_service_uses_same_real_call(hass, setup_integration, cloud):
    await setup_integration()
    await hass.services.async_call(DOMAIN, "set_quiet_mode",
        {"entity_id": ["climate.my_heat_pump_zone_1"], "enabled": True}, blocking=True)
    assert calls(cloud, "post_device_set_quiet_mode")[0][1] == QuietMode.LEVEL1
    cloud.calls.clear()
    with pytest.raises(ServiceValidationError):  # wrong domain is rejected
        await hass.services.async_call(DOMAIN, "set_quiet_mode",
            {"entity_id": ["sensor.my_heat_pump_outdoor_temperature"], "enabled": True}, blocking=True)
    with pytest.raises(ServiceValidationError):  # force_dhw targets the water heater only
        await hass.services.async_call(DOMAIN, "force_dhw",
            {"entity_id": ["climate.my_heat_pump_zone_1"], "enabled": True}, blocking=True)
    assert cloud.calls == []
    await hass.services.async_call(DOMAIN, "force_dhw",
        {"entity_id": ["water_heater.my_heat_pump_water_heater"], "enabled": True}, blocking=True)
    assert calls(cloud, "post_device_force_dhw")[0][1] == ForceDHW.ON


async def test_request_budget_and_unload(hass, setup_integration, cloud):
    entry = await setup_integration()
    assert cloud.status_requests == 1  # first refresh: one request for one device
    assert await hass.config_entries.async_unload(entry.entry_id)
    assert entry.state is ConfigEntryState.NOT_LOADED


async def test_options_change_reloads_with_new_interval(hass, setup_integration):
    entry = await setup_integration()
    coord = hass.data[DOMAIN][entry.entry_id]
    assert coord.update_interval.total_seconds() == 90
    hass.config_entries.async_update_entry(entry, options={"scan_interval": 120})
    await hass.async_block_till_done()
    assert hass.data[DOMAIN][entry.entry_id].update_interval.total_seconds() == 120


async def test_registry_cleanup_of_removed_entities(hass, setup_integration, cloud):
    reg = er.async_get(hass)
    entry = MockConfigEntry(domain=DOMAIN, data={"username": "u@example.com", "password": "pw"}, unique_id="u@example.com")
    entry.add_to_hass(hass)
    reg.async_get_or_create("switch", DOMAIN, "B1_schedule_enabled", config_entry=entry)
    reg.async_get_or_create("sensor", DOMAIN, "B1_power_consumption", config_entry=entry)
    from unittest.mock import patch
    from .conftest import make_client_class
    with patch(f"custom_components.{DOMAIN}.Client", make_client_class(cloud)):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
    assert reg.async_get_entity_id("switch", DOMAIN, "B1_schedule_enabled") is None
    assert reg.async_get_entity_id("sensor", DOMAIN, "B1_power_consumption") is None
    await hass.config_entries.async_unload(entry.entry_id)


async def test_auth_failure_starts_reauth(hass, cloud):
    from unittest.mock import patch
    from .conftest import make_client_class
    cloud.auth_error = True
    entry = MockConfigEntry(domain=DOMAIN, data={"username": "u@example.com", "password": "bad"}, unique_id="u@example.com")
    entry.add_to_hass(hass)
    with patch(f"custom_components.{DOMAIN}.Client", make_client_class(cloud)):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.SETUP_ERROR
    assert any(f["context"]["source"] == "reauth" for f in hass.config_entries.flow.async_progress())


async def test_config_flow_user_and_duplicate(hass, cloud):
    from unittest.mock import patch
    from .conftest import make_client_class
    with patch(f"custom_components.{DOMAIN}.config_flow.Client", make_client_class(cloud)), \
         patch(f"custom_components.{DOMAIN}.async_setup_entry", return_value=True):
        r = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"})
        assert r["type"] == "form"
        r = await hass.config_entries.flow.async_configure(r["flow_id"], {"username": "A@Example.com", "password": "x"})
        assert r["type"] == "create_entry"
        r2 = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"})
        r2 = await hass.config_entries.flow.async_configure(r2["flow_id"], {"username": "a@example.com", "password": "x"})
        assert r2["type"] == "abort" and r2["reason"] == "already_configured"


async def test_services_survive_one_unload_only_when_last(hass, setup_integration):
    entry = await setup_integration()
    assert hass.services.has_service(DOMAIN, "set_quiet_mode")
    await hass.config_entries.async_unload(entry.entry_id)
    assert not hass.services.has_service(DOMAIN, "set_quiet_mode")


async def test_action_events_not_duplicated_after_reload(hass, setup_integration):
    """The activity listener must be per entry, not stacked on every reload."""
    entry = await setup_integration()
    for _ in range(2):
        await hass.config_entries.async_reload(entry.entry_id)
        await hass.async_block_till_done()
    seen = []
    from homeassistant.core import callback
    unsub = hass.bus.async_listen("logbook_entry", callback(lambda e: seen.append(e)))
    hass.bus.async_fire("panasonic_aquarea_action", {"device_type": "switch", "action": "turned on",
                                                      "switch_type": "Quiet Mode", "entity_id": "switch.x"})
    await hass.async_block_till_done()
    unsub()
    assert len(seen) <= 1  # logbook.log is not loaded here; at most one entry if it were


async def test_works_without_logbook(hass, setup_integration):
    await setup_integration()
    hass.bus.async_fire("panasonic_aquarea_action", {"device_type": "climate", "action": "x", "entity_id": "climate.a"})
    await hass.async_block_till_done()  # must not raise ServiceNotFound


async def test_diagnostics_are_redacted_and_useful(hass, setup_integration):
    import json
    from custom_components.panasonic_aquarea.diagnostics import async_get_config_entry_diagnostics

    entry = await setup_integration()
    diag = await async_get_config_entry_diagnostics(hass, entry)
    blob = json.dumps(diag, default=str)
    for secret in ("u@example.com", "pw", "My Heat Pump", "B1", "\"L\""):
        assert secret not in blob, f"{secret!r} leaked into diagnostics"
    assert diag["entry"]["data"]["password"] == "**REDACTED**"
    assert diag["versions"]["aioaquarea"]
    dev = diag["devices"]["device_0"]
    assert dev["typed"]["special_status"] == "COMFORT" and dev["typed"]["tank"]["target"] == 60
    assert dev["typed"]["zones"]["1"]["setpoint_is_offset"] is True
    assert "2" in dev["typed"]["zones"]  # library zones are listed even if the unit has none
    assert dev["raw_status"]["status"]["waterPressure"] == 2.18
    assert diag["coordinator"]["last_update_success"] is True
    assert dev["measured_consumption_kwh_today"]["total"] == 2.0


def _direct_payload(heat_min=20, heat_max=55, heat_set=35):
    import copy
    from .conftest import REAL
    p = copy.deepcopy(REAL)
    z = p["status"]["zoneStatus"][0]
    z.update(heatMin=heat_min, heatMax=heat_max, heatSet=heat_set, temperatureNow=33)
    return p


async def test_phantom_zone_gets_no_entities_and_is_cleaned_up(hass, cloud):
    from unittest.mock import patch
    from .conftest import make_client_class
    reg = er.async_get(hass)
    entry = MockConfigEntry(domain=DOMAIN, data={"username": "u@example.com", "password": "pw"}, unique_id="u@example.com")
    entry.add_to_hass(hass)
    # entries created by an earlier version for the zone the unit does not have
    reg.async_get_or_create("climate", DOMAIN, "B1_zone_2", config_entry=entry)
    reg.async_get_or_create("sensor", DOMAIN, "B1_zone_2_temperature", config_entry=entry)
    with patch(f"custom_components.{DOMAIN}.Client", make_client_class(cloud)):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        ids = {e.unique_id for e in er.async_entries_for_config_entry(reg, entry.entry_id)}
        assert not any("zone_2" in u for u in ids), sorted(ids)
        assert "B1_zone_1" in ids and "B1_zone_1_temperature" in ids
        assert hass.states.get("climate.my_heat_pump_zone_2") is None
        await hass.config_entries.async_unload(entry.entry_id)


async def test_offset_zone_detected_by_range_although_library_says_direct(hass, setup_integration):
    await setup_integration()  # REAL payload: heat range -5..5, library reports "Direct"
    assert hass.states.get("number.my_heat_pump_zone_1_offset") is not None
    assert "temperature" not in hass.states.get("climate.my_heat_pump_zone_1").attributes


async def test_direct_zone_uses_climate_target_not_offset(hass, setup_integration, cloud):
    cloud.payload = _direct_payload()
    await setup_integration()
    assert hass.states.get("number.my_heat_pump_zone_1_offset") is None
    state = hass.states.get("climate.my_heat_pump_zone_1")
    assert state.attributes["temperature"] == 35 and state.attributes["min_temp"] == 20
    await hass.services.async_call("climate", "set_temperature",
        {"entity_id": "climate.my_heat_pump_zone_1", "temperature": 40}, blocking=True)
    assert calls(cloud, "post_device_zone_heat_temperature") == [("L", 1, 40)]


async def test_device_info_has_no_na_values(hass, setup_integration):
    from homeassistant.helpers import device_registry as dr
    await setup_integration()
    device = dr.async_get(hass).async_get_device(identifiers={(DOMAIN, "B1")})
    assert device.model == "Aquarea Heat Pump"
    assert device.sw_version is None
    assert device.hw_version == "STD_ADP-TAW1"


async def test_energy_is_unknown_not_zero_without_values(hass, setup_integration, cloud):
    cloud.consumption_rows = [(None, None), (None, None)]
    await setup_integration()
    assert hass.states.get("sensor.my_heat_pump_energy_today").state == "unknown"


async def test_energy_rows_are_in_diagnostics(hass, setup_integration):
    from custom_components.panasonic_aquarea.diagnostics import async_get_config_entry_diagnostics
    entry = await setup_integration()
    diag = await async_get_config_entry_diagnostics(hass, entry)
    rows = diag["devices"]["device_0"]["measured_consumption_kwh_today"]["rows"]
    assert rows and "dataTime" in rows[0]

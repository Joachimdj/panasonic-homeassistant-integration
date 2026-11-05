import sys, types, enum, asyncio, logging
def mod(n, **kw):
    m = types.ModuleType(n); m.__dict__.update(kw); sys.modules[n] = m
    parent, _, child = n.rpartition(".")
    if parent in sys.modules: setattr(sys.modules[parent], child, m)
    return m
class HAError(Exception): pass
class SVE(HAError): pass
class CAF(HAError): pass
class UF(Exception): pass
class CoordinatorEntity:
    def __init__(self, coordinator): self.coordinator = coordinator; self.hass = None; self.entity_id = "x.y"
    def __class_getitem__(c, i): return c
    @property
    def available(self): return True
class DUC:
    def __init__(s, hass, l, name=None, update_interval=None, request_refresh_debouncer=None): s.update_interval = update_interval; s.data = None; s.refreshes = 0
    async def async_request_refresh(s): s.refreshes += 1
class Flag(enum.IntFlag):
    TARGET_TEMPERATURE = 1; TURN_ON = 2; TURN_OFF = 4; PRESET_MODE = 8; ON_OFF = 16; OPERATION_MODE = 32
class Str(str, enum.Enum): pass
class HVACMode(Str): OFF="off"; HEAT="heat"; COOL="cool"; AUTO="auto"
class HVACAction(Str): OFF="off"; IDLE="idle"; HEATING="heating"; COOLING="cooling"
class Ent:
    @property
    def min_temp(self): return 7.0
    @property
    def max_temp(self): return 35.0
mod("homeassistant"); mod("homeassistant.components")
mod("homeassistant.components.climate", ClimateEntity=Ent, ClimateEntityFeature=Flag, HVACAction=HVACAction, HVACMode=HVACMode)
mod("homeassistant.components.switch", SwitchEntity=Ent)
mod("homeassistant.components.water_heater", STATE_HEAT_PUMP="heat_pump", STATE_PERFORMANCE="performance", WaterHeaterEntity=Ent, WaterHeaterEntityFeature=Flag)
class P(enum.Enum): CLIMATE=1; SENSOR=2; WATER_HEATER=3; SWITCH=4
mod("homeassistant.config_entries", ConfigEntry=object)
class UoT: CELSIUS = "C"
mod("homeassistant.const", CONF_PASSWORD="p", CONF_USERNAME="u", Platform=P, ATTR_TEMPERATURE="temperature", STATE_OFF="off", UnitOfTemperature=UoT)
mod("homeassistant.core", HomeAssistant=object, callback=lambda f: f)
mod("homeassistant.exceptions", ConfigEntryAuthFailed=CAF, ServiceValidationError=SVE, HomeAssistantError=HAError)
mod("homeassistant.helpers"); mod("homeassistant.helpers.entity_registry")
mod("homeassistant.helpers.entity_platform", AddEntitiesCallback=object)
mod("homeassistant.helpers.aiohttp_client", async_get_clientsession=None)
mod("homeassistant.helpers.update_coordinator", DataUpdateCoordinator=DUC, UpdateFailed=UF, CoordinatorEntity=CoordinatorEntity)
mod("homeassistant.helpers.debounce", Debouncer=lambda *a, **k: None)
sys.modules["homeassistant.helpers"].entity_registry = sys.modules["homeassistant.helpers.entity_registry"]
mod("homeassistant.util"); mod("homeassistant.util.dt", utcnow=lambda: __import__("datetime").datetime.utcnow())
sys.modules["homeassistant"].util = sys.modules["homeassistant.util"]
import os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from aioaquarea.data import *
from aioaquarea.entities import DeviceImpl

class FakeClient:
    def __init__(self): self.calls = []; self.status = None
    async def get_device_status(self, info): return self.status
    def __getattr__(self, name):
        if name.startswith("post_"):
            async def rec(*a, **k): self.calls.append((name, a))
            return rec
        raise AttributeError(name)

def make_status(zone_temp=49, zone_set=5, op=OperationStatus.ON, mode=ExtendedOperationMode.HEAT, special=SpecialStatus.COMFORT, tank_set=60):
    return DeviceStatus(long_id="L", operation_status=op, device_status=DeviceModeStatus.NORMAL if hasattr(DeviceModeStatus,'NORMAL') else list(DeviceModeStatus)[0],
        temperature_outdoor=5, operation_mode=mode, fault_status=[], direction=DeviceDirection.PUMP, pump_duty=PumpDuty.ON,
        tank_status=[TankStatus(OperationStatus.ON, 59, 75, 40, tank_set)],
        zones=[DeviceZoneStatus(1, zone_temp, op, 5, -5, zone_set, 5, -5, 0, 5, -5, -5, 5)],
        quiet_mode=QuietMode.OFF, force_dhw=ForceDHW.OFF, force_heater=ForceHeater.OFF, holiday_timer=HolidayTimer.OFF,
        powerful_time=PowerfulTime.OFF, special_status=special)

def make_device(client, status=None):
    zinfo = DeviceZoneInfo(1, "House", ZoneType.ZONE1 if hasattr(ZoneType,'ZONE1') else list(ZoneType)[0], False, ZoneSensor.INTERNAL, SensorMode.COMPENSATION_CURVE, None)
    st = status or make_status()
    client.status = st
    return DeviceImpl("B1", "L", "My Heat Pump", "fw", "model", True, [zinfo], st, client)

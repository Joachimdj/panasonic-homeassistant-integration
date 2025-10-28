"""Constants for the Panasonic Aquarea integration."""

DOMAIN = "panasonic_aquarea"

# Configuration
CONF_DEVICE_DIRECT = "device_direct"

# Update intervals
UPDATE_INTERVAL = 30  # seconds

# Device types
DEVICE_TYPE_HEAT_PUMP = "heat_pump"

# Platforms
PLATFORMS = ["climate", "sensor", "water_heater", "switch"]

# Operation modes from Panasonic Cloud Comfort app
OPERATION_MODE_AUTO = "auto"
OPERATION_MODE_HEAT = "heat" 
OPERATION_MODE_COOL = "cool"
OPERATION_MODE_OFF = "off"
OPERATION_MODE_ECO = "eco"
OPERATION_MODE_COMFORT = "comfort"

# Special operation modes
MODE_QUIET = "quiet"
MODE_POWERFUL = "powerful"
MODE_FORCE_DHW = "force_dhw"
MODE_FORCE_HEATER = "force_heater"
MODE_HOLIDAY = "holiday"

# Heater/Boiler control modes
HEATER_AUTO = "auto"
HEATER_ON = "on"
HEATER_OFF = "off"
HEATER_ECO = "eco"

# Comfort settings
COMFORT_ECO = "eco"
COMFORT_NORMAL = "normal"
COMFORT_COMFORT = "comfort"

# Service names for advanced controls
SERVICE_SET_ECO_MODE = "set_eco_mode"
SERVICE_SET_COMFORT_MODE = "set_comfort_mode"  
SERVICE_SET_QUIET_MODE = "set_quiet_mode"
SERVICE_SET_POWERFUL_MODE = "set_powerful_mode"
SERVICE_FORCE_DHW = "force_dhw"
SERVICE_FORCE_HEATER = "force_heater"
SERVICE_SET_HOLIDAY_MODE = "set_holiday_mode"
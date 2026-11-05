# Panasonic Aquarea Home Assistant Integration

A custom Home Assistant integration for Panasonic Aquarea heat pumps using the aioaquarea library.

## Features

- **Climate Control**: Control heating/cooling modes and temperature settings for each zone
- **Temperature Monitoring**: Monitor current temperatures for all zones and tank
- **Water Heater Control**: Control and monitor the hot water tank (if equipped)
- **Energy Monitoring**: *Estimated* power and energy (derived from operation mode and pump duty; not measured by the heat pump)
- **Special modes**: Eco, comfort, quiet, powerful, force heater, holiday and force DHW switches
- **Activity Integration**: Automatic logging of all changes to Home Assistant's Activity widget
- **Polling**: One cloud request per device every 90 seconds by default (configurable under **Configure**, minimum 60 s). Panasonic rate-limits its cloud API, so failures back off automatically up to 15 minutes.

## Installation

### Method 1: Manual Installation

1. Copy the `custom_components/panasonic_aquarea` folder to your Home Assistant `config/custom_components/` directory.

2. Restart Home Assistant.

3. Go to **Settings** → **Devices & Services** → **Add Integration** and search for "Panasonic Aquarea".

### Method 2: HACS (Recommended)

1. Add this repository as a custom repository in HACS:

   - Go to HACS → Integrations → ⋯ → Custom repositories
   - Repository: `https://github.com/Joachimdj/panasonic-homeassistant-integration`
   - Category: Integration

2. Install the integration through HACS.

3. Restart Home Assistant.

4. Add the integration through the UI.

## Configuration

1. In Home Assistant, go to **Settings** → **Devices & Services**.
2. Click **Add Integration** and search for "Panasonic Aquarea".
3. Enter your Panasonic Smart Cloud credentials:
   - **Username**: Your Panasonic Smart Cloud email
   - **Password**: Your Panasonic Smart Cloud password

## Entities

After configuration, the integration will create the following entities for each device:

### Climate Entities

- `climate.{device_name}_{zone_name}` - Climate control for each zone

### Sensor Entities

#### Temperature Sensors
- `sensor.{device_name}_{zone_name}_temperature` - Current temperature for each zone
- `sensor.{device_name}_tank_temperature` - Tank temperature (if equipped)
- `sensor.{device_name}_outdoor_temperature` - Outdoor temperature

#### Energy Monitoring Sensors
- `sensor.{device_name}_power_consumption` - Real-time power consumption (W)
- `sensor.{device_name}_energy_today` - Daily energy consumption (kWh)
- `sensor.{device_name}_energy_total` - Total energy consumption (kWh)
- `sensor.{device_name}_heating_energy_today` - Daily heating energy (kWh)
- `sensor.{device_name}_dhw_energy_today` - Daily hot water energy (kWh)
- `sensor.{device_name}_cop` - Coefficient of Performance efficiency rating

#### Status Sensors
- `sensor.{device_name}_operation_mode` - Current operation mode
- `sensor.{device_name}_pump_duty` - Pump duty cycle percentage
- `sensor.{device_name}_water_pressure` - System water pressure
- And many more operational sensors...

### Water Heater Entities

- `water_heater.{device_name}_water_heater` - Hot water tank control (if equipped). Operation modes: `off`, `heat_pump`, `performance` (= force DHW).

### Switches

`Eco Mode`, `Comfort Mode`, `Quiet Mode`, `Powerful Mode`, `Force Heater`, `Holiday Mode` and (with a tank) `Force DHW`. Eco and comfort are mutually exclusive presets, also available as climate presets. Quiet turns on level 1, powerful runs for 30 minutes.

### How controls behave

- Commands are sent to the Panasonic cloud and the entity shows the new state after the next (debounced, ~15 s) refresh. Nothing is shown optimistically; if a command fails you get an error in the UI.
- A zone's target temperature is an absolute value for *Direct* zones and an offset on the heating curve for *Compensation curve* zones. The climate attribute `setpoint_type` tells you which; min/max come from the device.
- Setting the temperature while the heat pump is off is rejected.
- The old Schedule, DHW priority, Legionella and Reheat switches were removed: the cloud API library has no calls for them.

## Example Device: "My Heat Pump"

A single-zone device with a tank gives these entities:

```yaml
climate.my_heat_pump_house
sensor.my_heat_pump_house_temperature
sensor.my_heat_pump_tank_temperature
water_heater.my_heat_pump_water_heater
```

## Automation Examples

### Set heating schedule

```yaml
automation:
  - alias: "Morning Heating"
    trigger:
      platform: time
      at: "06:00:00"
    action:
      - service: climate.set_hvac_mode
        target:
          entity_id: climate.my_heat_pump_zone_1
        data:
          hvac_mode: heat
      - service: climate.set_temperature
        target:
          entity_id: climate.my_heat_pump_zone_1
        data:
          temperature: 22
```

### Tank temperature monitoring

```yaml
automation:
  - alias: "Low Tank Temperature Alert"
    trigger:
      platform: numeric_state
      entity_id: sensor.my_heat_pump_tank_temperature
      below: 45
    action:
      - service: notify.mobile_app_your_phone
        data:
          message: "Hot water tank temperature is low: {{ states('sensor.my_heat_pump_tank_temperature') }}°C"
```

## Troubleshooting

### Authentication Issues

- Verify your Panasonic Smart Cloud credentials
- Check that your account has access to the device
- Try logging out and back in to the Panasonic Smart Cloud app

### Connection Issues

- Check your internet connection
- Verify the Panasonic Smart Cloud service is operational
- Check Home Assistant logs for detailed error messages

### No Devices Found

- Ensure your device is properly connected to the Panasonic Smart Cloud
- Check that the device appears in the official Panasonic app
- Wait a few minutes and try reloading the integration

## Support

- [GitHub Issues](https://github.com/Joachimdj/panasonic-homeassistant-integration/issues)
- [Home Assistant Community Forum](https://community.home-assistant.io/)

## Credits

This integration uses the [aioaquarea](https://github.com/cjaliaga/aioaquarea) library by Carlos J. Aliaga.

## Development

`python tests/test_controls.py` checks every control against the real `aioaquarea` device classes with Home Assistant stubbed out (needs only `pip install aioaquarea`).

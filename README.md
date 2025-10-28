# Panasonic Aquarea Home Assistant Integration

A custom Home Assistant integration for Panasonic Aquarea heat pumps using the aioaquarea library.

## Features

- **Climate Control**: Control heating/cooling modes and temperature settings for each zone
- **Temperature Monitoring**: Monitor current temperatures for all zones and tank
- **Water Heater Control**: Control and monitor the hot water tank (if equipped)
- **Real-time Updates**: Automatic data refresh every 30 seconds

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

- `sensor.{device_name}_{zone_name}_temperature` - Current temperature for each zone
- `sensor.{device_name}_tank_temperature` - Tank temperature (if equipped)

### Water Heater Entities

- `water_heater.{device_name}_water_heater` - Hot water tank control (if equipped)

## Example Device: "Langagervej"

Based on your device, you would get these entities:

```yaml
climate.langagervej_zone_1
climate.langagervej_zone_2
sensor.langagervej_zone_1_temperature
sensor.langagervej_zone_2_temperature
sensor.langagervej_tank_temperature
water_heater.langagervej_water_heater
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
          entity_id: climate.langagervej_zone_1
        data:
          hvac_mode: heat
      - service: climate.set_temperature
        target:
          entity_id: climate.langagervej_zone_1
        data:
          temperature: 22
```

### Tank temperature monitoring

```yaml
automation:
  - alias: "Low Tank Temperature Alert"
    trigger:
      platform: numeric_state
      entity_id: sensor.langagervej_tank_temperature
      below: 45
    action:
      - service: notify.mobile_app_your_phone
        data:
          message: "Hot water tank temperature is low: {{ states('sensor.langagervej_tank_temperature') }}°C"
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

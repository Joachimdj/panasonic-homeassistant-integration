# Panasonic Aquarea Cloud Comfort App Features

## Overview

Version 1.1.0 adds comprehensive support for advanced controls from the Panasonic Cloud Comfort app, bringing professional-grade heat pump management to Home Assistant.

## New Features

### 🏠 Advanced Climate Controls

**Preset Modes** - Available through the climate entity:
- **Eco Mode**: Energy-saving operation with reduced heating/cooling performance
- **Comfort Mode**: Optimized for maximum comfort with enhanced performance  
- **Normal Mode**: Standard balanced operation
- **Quiet Mode**: Reduced noise operation for nighttime use
- **Powerful Mode**: Maximum heating/cooling performance
- **Force Heater**: Forces use of backup/external heater
- **Holiday Mode**: Energy-saving mode for extended absences

### 🔄 Smart Control Switches

**Climate Control Switches**:
- `switch.eco_mode` - Energy efficiency optimization
- `switch.comfort_mode` - Maximum comfort settings
- `switch.quiet_mode` - Low noise operation  
- `switch.powerful_mode` - High performance heating/cooling
- `switch.force_heater` - Force external heater usage
- `switch.holiday_mode` - Extended absence energy saving
- `switch.schedule_enabled` - Enable/disable programmed schedules

**Water Heater Control Switches**:
- `switch.force_dhw` - Force domestic hot water priority
- `switch.dhw_priority` - Prioritize hot water over heating
- `switch.legionella_mode` - Anti-legionella protection cycle
- `switch.reheat_mode` - Automatic reheating when needed

### 📊 Enhanced Monitoring Sensors

**Cloud Comfort Status Sensors**:
- `sensor.eco_mode` - Current eco mode status
- `sensor.comfort_mode` - Current comfort mode status  
- `sensor.holiday_mode` - Holiday mode activation status
- `sensor.holiday_days_remaining` - Days left in holiday mode
- `sensor.heater_control` - External heater control mode (Auto/Force On/Force Off)
- `sensor.dhw_priority` - Hot water priority status
- `sensor.schedule_enabled` - Programming schedule status
- `sensor.defrost_mode` - Active defrost cycle indication

**Enhanced Water Tank Sensors**:
- `sensor.tank_eco_temperature` - Target temperature in eco mode
- `sensor.tank_comfort_temperature` - Target temperature in comfort mode
- `sensor.legionella_mode` - Anti-legionella cycle status
- `sensor.reheat_mode` - Automatic reheat function status

### 🎛️ Advanced Services

**Custom Services for Automation**:

```yaml
# Set eco mode via automation
service: panasonic_aquarea.set_eco_mode
target:
  entity_id: climate.langagervej_house
data:
  enabled: true

# Force hot water priority
service: panasonic_aquarea.force_dhw  
target:
  entity_id: water_heater.langagervej_water_heater
data:
  enabled: true

# Enable holiday mode for 14 days
service: panasonic_aquarea.set_holiday_mode
target:
  entity_id: climate.langagervej_house  
data:
  enabled: true
  duration_days: 14
```

### 📱 Climate Entity Enhancements

**Additional State Attributes**:
```yaml
# Example climate entity attributes
eco_mode: false
comfort_mode: true
quiet_mode: false
powerful_mode: false
force_dhw: false
force_heater: false
holiday_mode: false
holiday_days_remaining: 0
outdoor_temperature: 9
water_pressure: 2.08
pump_duty: 1
defrost_mode: false
external_heater: false
schedule_enabled: true
zone_operation_status: 1
eco_offset: -0.2
comfort_offset: 0.1
```

**Water Heater Operation Modes**:
- `eco` - Energy-saving hot water heating
- `normal` - Standard operation  
- `comfort` - Enhanced hot water performance
- `force_dhw` - Priority hot water mode

## Usage Examples

### Automation Examples

**Energy Saving Schedule**:
```yaml
automation:
  - alias: "Evening Eco Mode"
    trigger:
      platform: time
      at: "22:00:00"
    action:
      - service: switch.turn_on
        target:
          entity_id: switch.langagervej_eco_mode
      - service: switch.turn_on
        target:
          entity_id: switch.langagervej_quiet_mode

  - alias: "Morning Comfort Mode"  
    trigger:
      platform: time
      at: "06:00:00"
    action:
      - service: switch.turn_off
        target:
          entity_id: switch.langagervej_eco_mode
      - service: switch.turn_on
        target:
          entity_id: switch.langagervej_comfort_mode
```

**Holiday Mode Activation**:
```yaml
script:
  activate_holiday_mode:
    sequence:
      - service: panasonic_aquarea.set_holiday_mode
        target:
          entity_id: climate.langagervej_house
        data:
          enabled: true
          duration_days: {{ states('input_number.holiday_days') | int }}
      - service: switch.turn_on
        target:
          entity_id: switch.langagervej_eco_mode
```

**Smart Hot Water Management**:
```yaml
automation:
  - alias: "Morning Hot Water Boost"
    trigger:
      platform: time  
      at: "05:30:00"
    action:
      - service: switch.turn_on
        target:
          entity_id: switch.langagervej_force_dhw
      - delay: "01:00:00"
      - service: switch.turn_off
        target:
          entity_id: switch.langagervej_force_dhw
```

### Dashboard Cards

**Climate Control Card**:
```yaml
type: entities
title: Heat Pump Controls
entities:
  - climate.langagervej_house
  - switch.langagervej_eco_mode
  - switch.langagervej_comfort_mode  
  - switch.langagervej_quiet_mode
  - switch.langagervej_powerful_mode
  - sensor.langagervej_outdoor_temperature
```

**Water Heater Management**:
```yaml
type: entities
title: Hot Water Controls
entities:
  - water_heater.langagervej_water_heater
  - switch.langagervej_force_dhw
  - switch.langagervej_dhw_priority
  - sensor.langagervej_tank_temperature
  - sensor.langagervej_tank_eco_temperature
  - sensor.langagervej_tank_comfort_temperature
```

## Technical Details

### Data Structure

The integration now processes extended JSON data from the Panasonic Cloud Comfort app:

```json
{
  "status": {
    "ecoMode": 0,
    "comfortMode": 1, 
    "quietMode": 0,
    "powerful": 0,
    "forceDHW": 0,
    "forceHeater": 0,
    "holidayMode": 0,
    "holidayDays": 0,
    "heaterControl": 0,
    "dhwPriority": 0,
    "scheduleEnabled": 1,
    "defrostMode": 0,
    "tankStatus": {
      "ecoTemp": 55,
      "comfortTemp": 65,
      "legionellaMode": 0,
      "reheatMode": 1
    }
  }
}
```

### Compatibility

- **Home Assistant**: 2023.1.0+
- **aioaquarea**: >=1.0.0
- **HACS**: Full compatibility with custom services
- **Existing Configurations**: Fully backward compatible

## Migration from v1.0.x

Existing configurations will continue to work without changes. New entities and services are automatically added when upgrading to v1.1.0.

## Support

For issues related to Cloud Comfort app features:
1. Check that your Panasonic device supports the specific feature
2. Verify the Cloud Comfort app shows the same data
3. Enable debug logging: `custom_components.panasonic_aquarea: debug`
4. Report issues at: https://github.com/Joachimdj/panasonic-homeassistant-integration/issues
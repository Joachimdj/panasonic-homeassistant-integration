# Panasonic Aquarea Energy Usage Monitoring

## Overview

The Panasonic Aquarea integration now includes comprehensive energy consumption monitoring sensors that provide detailed kWh usage tracking for your heat pump system.

## Energy Sensors

### 1. Power Consumption (`sensor.{device}_power_consumption`)
- **Unit**: Watts (W)
- **Type**: Instantaneous power consumption
- **Description**: Real-time power consumption estimation based on operation mode, pump duty cycle, and active features
- **Calculation**: 
  - Heat mode: 1.5-2.5 kW base + pump duty scaling
  - Cool mode: 1.2-2.0 kW base + pump duty scaling
  - Standby: ~50W
  - Powerful mode: +30% consumption
  - Electric heater: +3000W when active

### 2. Energy Today (`sensor.{device}_energy_today`)
- **Unit**: kWh
- **Type**: Daily total energy consumption
- **Description**: Cumulative energy consumption since midnight
- **Reset**: Automatically resets at midnight each day
- **Accuracy**: Updates every 30 seconds based on current power consumption

### 3. Energy Total (`sensor.{device}_energy_total`)
- **Unit**: kWh
- **Type**: Total cumulative energy consumption
- **Description**: Total energy consumption since the integration was first started
- **Persistence**: Accumulates across Home Assistant restarts
- **Use Case**: Long-term energy monitoring and cost calculation

### 4. Heating Energy Today (`sensor.{device}_heating_energy_today`)
- **Unit**: kWh
- **Type**: Daily heating-specific energy consumption
- **Description**: Energy consumed specifically for heating operations
- **Filter**: Only counts energy when operation mode is "Heat"
- **Reset**: Daily at midnight

### 5. DHW Energy Today (`sensor.{device}_dhw_energy_today`)
- **Unit**: kWh
- **Type**: Daily domestic hot water energy consumption
- **Description**: Energy consumed for hot water production
- **Filter**: Counts energy when DHW is forced or tank is actively heating
- **Allocation**: Assumes 60% of power goes to DHW when tank is heating
- **Reset**: Daily at midnight

### 6. COP - Coefficient of Performance (`sensor.{device}_cop`)
- **Unit**: Ratio (no unit)
- **Type**: Efficiency measurement
- **Description**: Estimated coefficient of performance based on outdoor temperature
- **Range**: Typically 2.0 - 4.5
- **Factors**:
  - Outdoor temperature (primary factor)
  - Powerful mode (reduces efficiency by ~15%)
  - Only calculated during heating mode

## Energy Efficiency Metrics

### COP (Coefficient of Performance) Estimates

| Outdoor Temperature | Estimated COP | Efficiency Level |
|-------------------|---------------|------------------|
| ≥ 10°C           | 4.5           | Excellent        |
| 5°C - 9°C        | 4.0           | Very Good        |
| 0°C - 4°C        | 3.5           | Good             |
| -5°C - -1°C      | 3.0           | Moderate         |
| -10°C - -6°C     | 2.5           | Fair             |
| < -10°C          | 2.0           | Basic            |

*Note: COP is reduced by 15% when Powerful mode is active*

## Home Assistant Energy Dashboard Integration

### Adding to Energy Dashboard

1. Go to **Settings** → **Dashboards** → **Energy**
2. Add the following sensors to track your heat pump energy usage:

#### Grid Consumption
- Add: `sensor.{device}_power_consumption` (for real-time monitoring)
- Add: `sensor.{device}_energy_total` (for cumulative tracking)

#### Individual Devices
- **Heating**: `sensor.{device}_heating_energy_today`
- **Hot Water**: `sensor.{device}_dhw_energy_today`

### Creating Energy Cost Tracking

```yaml
# configuration.yaml
utility_meter:
  aquarea_monthly:
    source: sensor.{device}_energy_total
    cycle: monthly
  
  aquarea_weekly:
    source: sensor.{device}_energy_total
    cycle: weekly

template:
  - sensor:
      - name: "Heat Pump Daily Cost"
        unit_of_measurement: "€"
        state: "{{ (states('sensor.{device}_energy_today') | float * 0.25) | round(2) }}"
        # Assuming 0.25 €/kWh - adjust for your electricity rate
```

## Automation Examples

### High Energy Usage Alert

```yaml
automation:
  - alias: "Heat Pump High Energy Usage Alert"
    trigger:
      platform: numeric_state
      entity_id: sensor.{device}_power_consumption
      above: 3000  # Alert when consumption exceeds 3kW
      for: "00:10:00"  # For 10 minutes
    action:
      service: notify.mobile_app_your_phone
      data:
        message: "Heat pump is consuming {{ states('sensor.{device}_power_consumption') }}W for over 10 minutes"

  - alias: "Daily Energy Usage Report"
    trigger:
      platform: time
      at: "23:55:00"
    action:
      service: notify.mobile_app_your_phone
      data:
        message: >
          Heat pump energy usage today:
          Total: {{ states('sensor.{device}_energy_today') }} kWh
          Heating: {{ states('sensor.{device}_heating_energy_today') }} kWh
          DHW: {{ states('sensor.{device}_dhw_energy_today') }} kWh
          Avg COP: {{ states('sensor.{device}_cop') }}
```

### Efficiency Monitoring

```yaml
automation:
  - alias: "Low COP Alert"
    trigger:
      platform: numeric_state
      entity_id: sensor.{device}_cop
      below: 2.5
      for: "00:30:00"
    condition:
      condition: state
      entity_id: sensor.{device}_operation_mode
      state: "Heat"
    action:
      service: notify.mobile_app_your_phone
      data:
        message: "Heat pump COP is low ({{ states('sensor.{device}_cop') }}) - check for issues"
```

## Lovelace Dashboard Cards

### Energy Overview Card

```yaml
type: entities
title: Heat Pump Energy Usage
entities:
  - entity: sensor.{device}_power_consumption
    name: Current Power
  - entity: sensor.{device}_energy_today
    name: Today's Usage
  - entity: sensor.{device}_heating_energy_today
    name: Heating Today
  - entity: sensor.{device}_dhw_energy_today
    name: Hot Water Today
  - entity: sensor.{device}_cop
    name: Efficiency (COP)
```

### Energy History Graph

```yaml
type: history-graph
title: Power Consumption History
entities:
  - sensor.{device}_power_consumption
hours_to_show: 24
refresh_interval: 0
```

## Data Accuracy Notes

### Estimation Method
- Power consumption is **estimated** based on operational parameters
- Actual consumption may vary based on:
  - Specific heat pump model and size
  - Installation conditions
  - Maintenance status
  - Refrigerant levels
  - Ductwork efficiency

### Calibration
For more accurate readings, you can:
1. Install a dedicated energy meter
2. Adjust the power calculation formulas in `sensor.py`
3. Calibrate based on your electricity bill data

### Limitations
- DHW energy allocation (60%) is an estimate
- COP calculations are based on typical heat pump performance
- No compensation for defrost cycles or unusual conditions

## Advanced Configuration

### Custom Power Calculations

To adjust power calculations for your specific heat pump model, modify the `AquareaPowerConsumptionSensor` class in `sensor.py`:

```python
# Example: Adjust base power for different heat pump sizes
if operation_mode == 1:  # Heat mode
    # For 12kW heat pump:
    base_power = 2000 + (pump_duty * 800)
    # For 6kW heat pump:
    # base_power = 1000 + (pump_duty * 400)
```

### Integration with Solar Systems

If you have solar panels, you can track net energy usage:

```yaml
template:
  - sensor:
      - name: "Heat Pump Net Energy Today"
        unit_of_measurement: "kWh"
        state: >
          {{ (states('sensor.{device}_energy_today') | float - 
              states('sensor.solar_production_today') | float) | round(3) }}
```

This comprehensive energy monitoring system gives you complete visibility into your Panasonic Aquarea heat pump's energy consumption, helping you optimize efficiency and manage energy costs.
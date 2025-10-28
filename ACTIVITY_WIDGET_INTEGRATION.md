# Activity Widget Integration

## Overview

The Panasonic Aquarea integration now includes comprehensive activity logging for the Home Assistant Activity widget (History/Logbook). All control actions and significant sensor value changes are tracked and displayed in the Home Assistant activity feed.

## What Gets Logged

### 🎛️ **Control Actions**

**Water Heater Controls:**
- Temperature changes: "Water heater target temperature changed from 55°C to 60°C"
- Operation state: "Water heater turned on" / "Water heater turned off"

**Climate Controls:**
- Zone temperature changes: "House target temperature changed from 20°C to 22°C"
- HVAC mode changes: "House HVAC mode changed from OFF to HEAT"
- Comfort mode changes: "House comfort mode changed from Normal to Eco"

**Switch Controls:**
- Mode toggles: "Eco Mode turned on" / "Eco Mode turned off"
- Cloud Comfort features: "Quiet Mode turned on", "Powerful Mode turned off"

### 📊 **Sensor Value Changes**

**Temperature Sensors:**
- Significant changes (≥1°C): "House Temperature changed from 19.5°C to 21.2°C"
- Tank temperature: "Tank Temperature changed from 58°C to 60°C"

**Pressure Sensors:**
- Significant changes (≥0.5 bar): "Water Pressure changed from 2.0 bar to 2.6 bar"

**Operation Status:**
- State changes: "Tank Operation Status changed from OFF to ON"
- System status: "Pump Operation changed from OFF to ON"

**Performance Sensors:**
- Significant changes (≥10%): "Pump Duty changed from 45% to 65%"

## Implementation Details

### 🔧 **Event System**

Each entity fires custom events when state changes occur:

```python
# Custom event structure
{
    "entity_id": "water_heater.langagervej_tank",
    "device_id": "B497204181",
    "action": "temperature changed",
    "old_value": "55°C",
    "new_value": "60°C",
    "timestamp": "2025-10-28T12:32:39.123456+00:00",
    "device_type": "water_heater"
}
```

### 📝 **Logbook Integration**

The integration automatically creates logbook entries for all events:

```python
# Logbook entry for activity feed
{
    "name": "Panasonic Aquarea",
    "message": "Water heater target temperature changed from 55°C to 60°C",
    "domain": "panasonic_aquarea",
    "entity_id": "water_heater.langagervej_tank",
    "source": "panasonic_aquarea"
}
```

### 🎯 **Smart Filtering**

Only significant changes are logged to avoid spam:

- **Temperature**: Changes ≥ 1.0°C
- **Pressure**: Changes ≥ 0.5 bar  
- **Percentage**: Changes ≥ 10%
- **Status**: All ON/OFF state changes
- **Controls**: All manual user actions

## Activity Widget Benefits

### 📈 **System Monitoring**
- Track when temperature setpoints are changed
- Monitor system operation state changes
- See when comfort modes are activated

### 🔍 **Troubleshooting**
- Identify when issues started by looking at activity timeline
- Correlate user actions with system behavior
- Track automatic vs manual operation changes

### 📊 **Usage Analytics**
- See patterns of temperature adjustments
- Monitor how often different modes are used
- Track system performance over time

### 🏠 **Family Coordination**
- Family members can see recent temperature changes
- Understand who made what adjustments when
- Coordinate heating/cooling preferences

## Viewing Activity

### Home Assistant UI
1. **History Tab**: View timeline of all changes
2. **Logbook**: See human-readable activity messages
3. **Entity History**: Individual entity change tracking

### Example Activity Messages
```
12:32 PM - Water heater target temperature changed from 55°C to 60°C
12:35 PM - House HVAC mode changed from OFF to HEAT  
12:40 PM - Eco Mode turned on
12:45 PM - House Temperature changed from 19.5°C to 21.2°C
01:15 PM - Tank Operation Status changed from OFF to ON
```

## Configuration

### Automatic Setup
- Activity logging is enabled automatically when integration loads
- No additional configuration required
- Events appear in Home Assistant logs and activity feed immediately

### Log Level Control
- Activity messages logged at INFO level
- Enable DEBUG logging for troubleshooting: `custom_components.panasonic_aquarea: debug`

### Event Filtering
Modify thresholds in sensor base class if needed:
- Temperature: `>= 1.0°C` change threshold
- Pressure: `>= 0.5 bar` change threshold  
- Percentage: `>= 10%` change threshold

## Technical Implementation

### Event Bus System
- Custom event type: `panasonic_aquarea_action`
- Automatic logbook entry creation
- Timestamped with ISO format
- Device and entity identification included

### Performance Considerations
- Smart change detection prevents log spam
- Events only fired for significant value changes
- Lightweight event payload structure
- No impact on entity update performance

The Activity widget integration provides complete visibility into your Panasonic Aquarea heat pump system operations, making it easy to track changes, troubleshoot issues, and understand system behavior over time.
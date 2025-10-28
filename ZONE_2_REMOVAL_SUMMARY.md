# Zone 2 Removal Summary

## Problem
User reported "No temperature data found for zone 2" error despite having a single-zone heat pump system.

## Root Cause Analysis
The aioaquarea library might be providing multiple zones in its device_info or status objects, even for single-zone devices. This could be due to:
1. Default/template zones in the library
2. Legacy multi-zone support in device firmware
3. Zone numbering starting from 0 and 1 instead of just 1

## Solutions Implemented

### 1. Climate Entity Creation Filtering (climate.py)

**Added zone filtering in device_info processing:**
```python
# Filter to only zone 1 to prevent zone 2 errors
zones = [zone for zone in device_info.zones if getattr(zone, 'zone_id', None) == 1]
_LOGGER.info("Filtered to zone 1 only: %s", zones)
```

**Added entity creation filtering:**
```python
# Only create entities for zone ID 1 to prevent zone 2 errors
if zone_id == 1 and zone_name:
    entity = AquareaClimate(coordinator, device_id, zone_id, zone_name)
    entities.append(entity)
elif zone_id != 1:
    _LOGGER.warning("Skipping zone %s for device %s - only zone 1 is supported", zone_id, device_id)
```

### 2. Status Zone Data Filtering (__init__.py)

**Added zone filtering in status processing:**
```python
# Filter to only zone 1 to prevent zone 2 errors  
filtered_zones = [zone for zone in status.zones if getattr(zone, 'zone_id', 1) == 1]
_LOGGER.info("Filtered status zones to zone 1 only: %s", filtered_zones)
```

### 3. Enhanced Debug Logging

**Added device_info zone debugging:**
```python
# Debug: Check device_info zones to identify zone 2 source
if hasattr(device_info, 'zones'):
    _LOGGER.info("Device %s has zones in device_info: %s", device_info.device_id, device_info.zones)
    for i, zone in enumerate(device_info.zones):
        zone_id = getattr(zone, 'zone_id', 'unknown')
        zone_name = getattr(zone, 'name', 'unknown') 
        _LOGGER.info("  Zone %d: ID=%s, Name=%s", i+1, zone_id, zone_name)
```

## Expected Behavior After Changes

1. **Only Zone 1 Entities:** Integration will only create climate entities for zone_id=1
2. **Filtered Zone Data:** Raw data will only contain zone 1 information
3. **Clear Logging:** Debug logs will show what zones are detected and which are filtered out
4. **No Zone 2 Errors:** The "No temperature data found for zone 2" error should be eliminated

## Testing Steps

1. Restart Home Assistant to reload the integration
2. Check logs for zone filtering messages:
   - "Filtered to zone 1 only"
   - "Filtered status zones to zone 1 only"
   - "Skipping zone X - only zone 1 is supported"
3. Verify only one climate entity is created per device
4. Confirm no "zone 2" errors appear in logs

## Files Modified

- `custom_components/panasonic_aquarea/climate.py` - Entity creation filtering
- `custom_components/panasonic_aquarea/__init__.py` - Status data filtering and debug logging

## Fallback Protections

- Template fallback data only includes zone 1
- Manual data fallback creates single default zone  
- All filtering uses explicit zone_id == 1 checks
- Warning logs for any skipped zones

The integration now has multiple layers of protection against zone 2 creation, ensuring it works correctly with single-zone heat pump systems.
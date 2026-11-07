# Changelog

## 1.2.1

### Fixes
- No more phantom **Zone 2**: zone entities are only created for zones the unit reports, and entities an earlier version created for other zones are removed automatically.
- Heating-curve zones are recognised by their range (an offset such as -5..+5), so they get the `number.*_offset` entity instead of a climate temperature. (aioaquarea reports every zone as "Direct".)
- Device info no longer shows `N/A` for model and firmware; the adapter type is shown as hardware version.
- Energy sensors show `unknown` instead of `0.00` when Panasonic returns no values; the raw statistics rows are included in diagnostics.

## 1.2.0

### Fewer requests (fixes the account being blocked by Panasonic)
- One status request per device per poll (was two). Default interval 90 s (was 30 s), configurable under **Configure** (minimum 60 s).
- Exponential backoff up to 15 minutes after failures; a rejected password now starts the reauth flow.
- Refreshes after commands are debounced into one request.

### Controls now actually call the Panasonic API
- Climate, water heater, switches and services use real `aioaquarea` calls with proper enums and an explicit zone. Errors are shown in the UI instead of being swallowed; nothing is simulated.
- The water heater target now changes the tank (it used to be reported as success but never applied).
- Compensation-curve zones get a `number.*_offset` entity instead of a misleading temperature slider.
- Eco and comfort are readable again (aioaquarea parsed `special_status` as always `None`).

### Data
- Measured energy: `energy_today`, `heating_energy_today`, `cooling_energy_today`, `dhw_energy_today` (kWh, refreshed hourly, usable in the Energy dashboard).
- New sensors: fault, tank target temperature. Zone temperature is no longer divided by 10.
- Download diagnostics (redacted) from the integration page.

### Removed (entries are cleaned up automatically)
- Estimated power, energy total and COP sensors (not measured data).
- Schedule, DHW priority, Legionella and Reheat switches, and sensors that read values the cloud never sends or mirrored a switch.

### Fixes and internals
- Services validate their target, work with several accounts and are registered once.
- The activity listener is registered per entry and works without the logbook integration.
- Test suite in a real Home Assistant (`pytest`), CI on every pull request; minimum Home Assistant 2024.11.
- Personal device name and id removed from docs and scripts.

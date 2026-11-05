# Energy monitoring

The energy sensors report what Panasonic's cloud statistics say the heat pump consumed **today** (kWh). Nothing is estimated: earlier versions derived "power" and "COP" from the operation mode and pump duty, which was not real data, so those sensors were removed.

| Entity | Meaning |
|---|---|
| `sensor.{device}_energy_today` | Total consumption today |
| `sensor.{device}_heating_energy_today` | Space heating |
| `sensor.{device}_cooling_energy_today` | Cooling (only if a zone supports cooling) |
| `sensor.{device}_dhw_energy_today` | Hot water tank (only with a tank) |

All four use `state_class: total_increasing` and `device_class: energy`, so they work in the Energy dashboard; the daily reset is handled as a new cycle.

## Things to know

- The statistics are fetched at most **once an hour** per device (one extra request), so values lag by up to an hour and Panasonic may publish them in coarse steps.
- If the statistics endpoint returns nothing, the sensors keep their last value, or are `unknown` if there has never been one.
- Panasonic buckets days in UTC in this library version, so "today" can be off by your UTC offset around midnight.
- There is no live power (W) or COP sensor: the heat pump does not report them through this API. If you want power, use a smart meter on the heat pump's supply.

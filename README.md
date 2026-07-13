# Delta Energy

Delta Energy is a small Home Assistant custom integration intended mainly as a companion helper for [`tuya-local`](https://github.com/make-all/tuya-local) devices that report energy consumption as interval/delta values.

Some Tuya devices do not expose a continuously increasing total energy counter. Instead, they report:

* interval energy value, for example `0.01 kWh`
* interval start timestamp
* interval end timestamp

In `tuya-local`, these can be exposed as one energy sensor with the start/end timestamps available as attributes.

Delta Energy reads that source sensor and creates calculated Home Assistant sensors:

* accumulated total energy in `kWh`
* average power in `W`

## Primary use case

This integration was created for Tuya HVAC / air conditioner devices supported through `tuya-local`, for example devices that expose data similar to:

```text
DP127 = energy value
DP128 = interval start time
DP129 = interval end time
```

The expected input is a Home Assistant sensor where:

```text
state = interval energy in kWh
attribute = interval start timestamp
attribute = interval end timestamp
```

Example source entity:

```text
sensor.kuchyne_klima_energy
```

Example attributes:

```text
electricity_starttime: 1780000000
electricity_endtime: 1780000120
```

## What it does

Delta Energy accumulates interval energy values into a `total_increasing` energy sensor.

It also calculates average power from the same interval data:

```text
power_w = delta_kwh * 3600000 / interval_seconds
```

For example:

```text
0.01 kWh over 120 seconds = 300 W
```

## Why this is separate from tuya-local

The `tuya-local` integration focuses on exposing raw Tuya local protocol data to Home Assistant.

Accumulating interval values requires state tracking, duplicate interval protection, and restore handling after restart. That logic is intentionally kept outside `tuya-local` and handled by this separate helper integration.

## Installation

Copy the integration directory to Home Assistant:

```text
/config/custom_components/delta_energy
```

Expected structure:

```text
custom_components/
└── delta_energy/
    ├── __init__.py
    ├── manifest.json
    ├── const.py
    ├── config_flow.py
    └── sensor.py
```

Then restart Home Assistant.

## Configuration

After restart, add the integration from Home Assistant UI:

```text
Settings → Devices & services → Add integration → Delta Energy
```

Configure:

```text
Name: Kitchen AC
Source entity: sensor.kuchyne_klima_energy
Start attribute: electricity_starttime
End attribute: electricity_endtime
Averaging window: 600
```

The source entity should be the raw energy sensor created by `tuya-local`.

## Created entities

For each configured source sensor, Delta Energy creates:

```text
sensor.<name>_total_energy
sensor.<name>_average_power
```

The total energy sensor is suitable for Home Assistant long-term statistics and Energy Dashboard usage.

## Notes

Delta Energy ignores repeated updates with the same end timestamp, so the same interval should not be counted twice.

After Home Assistant restart, the total energy value is restored from the previous state.

The average power window is not restored after restart; it is rebuilt from new incoming samples.

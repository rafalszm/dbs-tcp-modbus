# DBS TCP Modbus

Custom integration for Home Assistant that reads Modbus TCP stations directly from
controllers exposing Modbus TCP. Each station is added as a separate integration entry
and appears in Home Assistant as one device with many entities.

Version `1.0.1` is read-only. It creates `sensor` and `binary_sensor` entities and does
not write coils or registers.

## Installation

### HACS

1. Open HACS in Home Assistant.
2. Go to `Integrations`.
3. Open the three-dot menu and choose `Custom repositories`.
4. Add repository URL: `https://github.com/rafalszm/dbs-tcp-modbus`.
5. Select category `Integration`.
6. Install `DBS TCP Modbus`.
7. Restart Home Assistant.
8. Go to `Settings -> Devices & services -> Add integration`.
9. Search for `DBS TCP Modbus`.

Updates are handled by HACS from GitHub releases. Version numbers use SemVer:
`MAJOR.MINOR.PATCH` in `custom_components/dbs_tcp_modbus/manifest.json` and matching
GitHub release tags with a `v` prefix, for example `v1.0.2`.

### Manual

1. Copy `custom_components/dbs_tcp_modbus` into `/config/custom_components/`.
2. Restart Home Assistant.
3. Go to `Settings -> Devices & services -> Add integration`.
4. Search for `DBS TCP Modbus`.

## Adding a Station

The setup form asks for:

- station name
- host/IP
- port, usually `502`
- Modbus unit/slave ID
- scan interval and timeout
- CSV register map pasted into the form

Add every physical station as a separate integration entry. This keeps each station as
its own Home Assistant device.

Existing stations can be reconfigured from the integration entry. Changing the IP address,
port, unit ID, scan settings, or CSV map keeps the same Home Assistant device identity.
During reconfiguration the integration validates the CSV map but does not block saving on
a failed Modbus read. If the controller is unreachable after saving, entities become
unavailable until communication recovers.

## CSV Map

Required columns:

```csv
key,name,function,address,type
```

Optional columns:

```csv
unit,scale,offset,precision,device_class,state_class,icon,section,enabled_by_default,count,word_order,byte_order
```

Supported function codes:

- `1` - coils
- `2` - discrete inputs
- `3` - holding registers
- `4` - input registers

Supported types:

- `coil`
- `discrete`
- `uint16`
- `int16`
- `uint32`
- `int32`
- `float32`

Addresses are zero-based, matching `pymodbus`. If a controller manual numbers a register
as `40001`, the Modbus address is usually `0`.

Example:

```csv
key,name,function,address,type,unit,scale,precision,device_class,state_class
water_pressure,Water pressure,4,999,uint16,bar,0.1,1,pressure,measurement
pump_running,Pump running,1,10,coil,,,,running,
```

See `examples/feliksow.csv` for a larger map.

## Repository

GitHub: `https://github.com/rafalszm/dbs-tcp-modbus`

## License

DBS TCP Modbus is proprietary software. All rights reserved.

Private, non-commercial testing is allowed under the limited terms in `LICENSE`.
Commercial, professional, organizational, paid, hosted, customer-facing, or production
use requires a separate written commercial license from the copyright holder.

# DBS TCP Modbus

DBS TCP Modbus is a Home Assistant custom integration for read-only Modbus TCP stations.
Each station is added as a separate Home Assistant integration entry and appears as one
device with many entities.

## Installation

### Manual

1. Copy `custom_components/dbs_tcp_modbus` into `/config/custom_components/`.
2. Restart Home Assistant.
3. Go to Settings -> Devices & services -> Add integration.
4. Search for `DBS TCP Modbus`.

### HACS custom repository

Add this repository to HACS as a custom integration repository, install it, and restart
Home Assistant.

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
a failed Modbus read; if the controller is unreachable after saving, entities become
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

## Notes

Version `0.1.0` is read-only. It creates `sensor` and `binary_sensor` entities and does
not write coils or registers.

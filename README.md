# epics-device-lib

Reusable EPICS soft-IOC device drivers for laboratory instrumentation, built on
[python-softioc](https://github.com/dls-controls/pythonSoftIOC). Intended to be
consumed as a **git submodule** (mounted at `devices/`) inside a deployment repo
that runs [softioc_toolkit](https://github.com/YOUR_ORG/softioc_toolkit).

## Inheritance hierarchy

```
BaseDevice  (base_device.py)
├── ModbusDevice  (modbus_base.py)
│   ├── instruments/dat8017.py   — Datexel DAT8017 ADC (4-20 mA / voltage)
│   ├── instruments/dat8017_level.py — Datexel DAT8017-I 4-point LN2 level probe (Pt1000 current divider)
│   ├── instruments/dat8018.py   — Datexel DAT8018 thermocouple reader
│   ├── instruments/dat8024.py   — Datexel DAT8024 analog output module
│   └── instruments/dat8130.py   — Datexel DAT8130 relay / DI module
├── TelnetDevice  (telnet_base.py)
│   ├── instruments/ami136.py    — AMI Model 136 liquid-level monitor
│   ├── instruments/cm4g_magnet.py — Cryomagnetics Model 4G magnet power supply
│   ├── instruments/cs4_magnet.py  — Cryomagnetics CS-4 magnet power supply
│   ├── instruments/dp832.py     — Rigol DP832 programmable DC power supply
│   ├── instruments/lm500.py     — American Magnetics LM-500 level monitor
│   ├── instruments/ls218.py     — Lakeshore Model 218 temperature monitor
│   ├── instruments/ls336.py     — Lakeshore Model 336 temperature controller
│   ├── instruments/mks937b.py   — MKS 937B vacuum gauge controller
│   ├── instruments/si9700.py    — Scientific Instruments SI-9700 temperature controller
│   └── instruments/tpg_26x.py  — Pfeiffer TPG 261/262 vacuum gauge
└── BaseDevice (direct)
    ├── instruments/ioc_load.py  — Aggregate CPU/memory monitor for master_ioc.py processes
    └── instruments/zaber_motor.py — Zaber ASCII motor controller (TCP)
```

## Driver registry

| File | Hardware | Protocol | Key PV types |
|---|---|---|---|
| `dat8017.py` | Datexel DAT8017 | Modbus TCP | `aIn` (calibrated 4-20 mA / V) |
| `dat8017_level.py` | Datexel DAT8017-I | Modbus TCP | `boolIn` x4 (wet/dry per point), `aIn` (level %) |
| `dat8018.py` | Datexel DAT8018 | Modbus TCP | `aIn` (thermocouple °C) |
| `dat8024.py` | Datexel DAT8024 | Modbus TCP | `aOut` (0–5 V DAC) |
| `dat8130.py` | Datexel DAT8130 | Modbus TCP | `boolOut` (relay), `boolIn` (DI) |
| `ami136.py` | AMI 136 | Telnet | `aIn` (level %) |
| `cm4g_magnet.py` | Cryomagnetics 4G | Telnet | `aIn` V/I, `aOut` limits, `mbbOut` sweep |
| `cs4_magnet.py` | Cryomagnetics CS-4 | Telnet | `aIn` V/I, `aOut` limits, `mbbOut` sweep |
| `dp832.py` | Rigol DP832 | Telnet (LXI) | `aIn` V/I, `aOut` setpoints, `boolOut` output enable |
| `lm500.py` | AMI LM-500 | Telnet | `aIn` (level cm) |
| `ls218.py` | Lakeshore 218 | Telnet (RS-232) | `aIn` (temperature K) |
| `ls336.py` | Lakeshore 336 | Telnet (RS-232) | `aIn` T/heater, `aOut` SP/PID, `mbbOut` mode/range |
| `mks937b.py` | MKS 937B | Telnet (RS-485) | `aIn` (pressure mbar) |
| `si9700.py` | SI-9700 | Telnet (RS-232) | `aIn` T/heater, `aOut` SP, `mbbOut` mode |
| `tpg_26x.py` | Pfeiffer TPG 261/262 | Telnet (RS-232) | `aIn` (pressure mbar) |
| `ioc_load.py` | — (host process monitor) | psutil | `aIn` CPU/mem, `longIn` count |
| `zaber_motor.py` | Zaber ASCII chain | TCP (zaber-motion) | `aIn` pos, `aOut` move, `boolOut` home/stop/zero |

## Usage as a submodule

```bash
# Add to a deployment repo
git submodule add https://github.com/YOUR_ORG/epics-device-lib devices
git submodule update --init

# Pin to a specific release
git -C devices checkout v1.0.0
git add devices
git commit -m "Pin epics-device-lib to v1.0.0"
```

In `settings.yaml`, reference instruments as `devices.instruments.<module>`:

```yaml
lakeshore_218:
  module: 'devices.instruments.ls218'
  ...
```

Transport bases (if referenced directly) remain at `devices.<base>`:

```yaml
# example if a deployment subclasses a base directly
module: 'devices.modbus_base'
```

## Adding a new driver

1. Create `instruments/<yourdriver>.py` inheriting from `TelnetDevice`, `ModbusDevice`, or `BaseDevice`.
2. Implement `_create_pvs()`, `_create_connection()`, and `do_reads()`.
3. Use `from ..telnet_base import TelnetDevice, TelnetConnection` (or `..modbus_base` / `..base_device`).
4. Add an entry to the registry table above.
5. Commit, tag, and update the submodule pin in each deployment repo that needs it.

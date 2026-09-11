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
├── TelnetDevice  (telnet_base.py — transport in telnet_socket.py)
│   ├── instruments/ami136.py    — AMI Model 136 liquid-level monitor
│   ├── instruments/cm4g_magnet.py — Cryomagnetics Model 4G magnet power supply
│   ├── instruments/cs4_magnet.py  — Cryomagnetics CS-4 magnet power supply
│   ├── instruments/dp832.py     — Rigol DP832 programmable DC power supply
│   ├── instruments/lm500.py     — American Magnetics LM-500 level monitor
│   ├── instruments/ls218.py     — Lakeshore Model 218 temperature monitor
│   ├── instruments/ls336.py     — Lakeshore Model 336 temperature controller
│   ├── instruments/mks937b.py   — MKS 937B vacuum gauge controller
│   ├── instruments/si9700.py    — Scientific Instruments SI-9700 temperature controller
│   ├── instruments/tpg_26x.py  — Pfeiffer TPG 261/262 vacuum gauge
│   └── instruments/vaunix_lms.py — Vaunix Lab Brick LMS/BLX synthesiser (via USB-to-TCP shim)
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
| `vaunix_lms.py` | Vaunix Lab Brick LMS/BLX | TCP (USB shim) | `aIn` freq/power, `aOut` setpoints, `boolOut` RF/ref, `boolIn` PLL lock |
| `ioc_load.py` | — (host process monitor) | psutil | `aIn` CPU/mem, `longIn` count |
| `zaber_motor.py` | Zaber ASCII chain | TCP (zaber-motion) | `aIn` pos, `aOut` move, `boolOut` home/stop/zero |

## Telnet transport

`TelnetConnection` is backed by `telnet_socket.TelnetSocket`, not the standard
library's `telnetlib`, which PEP 594 removed in Python 3.13.

Despite the name, none of these instruments are Telnet servers. They sit on
serial-to-Ethernet adapter channels (ports 1001–1003, 4444, 5555, …) that carry
raw bytes, so what the drivers need is a socket with a buffer and a delimiter
search. `TelnetSocket` provides exactly the three calls the drivers use, with the
same signatures and return contracts:

| Call | Returns |
|---|---|
| `write(buffer)` | `None`; any `0xFF` byte is doubled per the protocol |
| `read_until(expected, timeout)` | bytes through the end of `expected` |
| `expect(patterns, timeout)` | `(index, match, text)`, or `(-1, None, text)` on timeout |

Behaviour preserved from `telnetlib`, because drivers depend on all three:

- **Unread bytes stay buffered** between calls, so a reply split across two
  reads is not lost.
- **Timeouts return the partial buffer rather than raising** — drivers treat a
  short read as the error signal and convert it to `OSError`.
- **`expect` returns text through the end of the match**, leaving the remainder
  buffered for the next call.

Telnet option negotiation is *refused* (`IAC WONT`/`IAC DONT`) rather than
ignored, mirroring `telnetlib` with no option callback installed. This only
matters if an adapter is configured for Telnet rather than raw TCP, in which case
the negotiation bytes would otherwise reach a driver's regex and fail in a
confusing way.

`TelnetSocket` imports only `re`, `socket` and `time` — no third-party
dependency, so deployments need no `requirements.txt` change.

### One rule for driver authors

**Always pass an explicit `timeout`.** `telnetlib` raised `EOFError` from
`read_until`/`expect` when called with `timeout=None` on a closed connection;
`TelnetSocket` returns the partial buffer instead. Every existing call site
passes a timeout, so the difference is unreachable today — keep it that way.

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
   Never import `telnet_socket` directly — `TelnetConnection` owns it.
4. Write response patterns as raw bytes literals (`rb'(-?\d+\.\d+)\sA'`). A
   plain `b'...'` pattern raises `SyntaxWarning` on Python 3.12+ for escapes
   like `\d` and `\s`, and becomes a `SyntaxError` in a later release.
5. Pass an explicit `timeout` to every `read_until` and `expect` call — see
   [Telnet transport](#telnet-transport).
6. Add an entry to the registry table above.
7. Commit, tag, and update the submodule pin in each deployment repo that needs it.

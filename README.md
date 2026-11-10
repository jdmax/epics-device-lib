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
│   ├── instruments/dat8017_azurlight.py — Datexel DAT8017-V reading Azurlight laser DB9 monitor outputs
│   ├── instruments/dat8018.py   — Datexel DAT8018 thermocouple reader
│   ├── instruments/dat8024.py   — Datexel DAT8024 analog output module
│   ├── instruments/dat8130.py   — Datexel DAT8130 relay / DI module
│   ├── instruments/dat8188.py   — Datexel DAT8188 8 DI / 8 PNP output module
│   └── instruments/dat8188_surestep.py — SureStep stepper drive in velocity mode via DAT8188 (digital); speed from a DAT8024, a dat8024 IOC PV, or a drive preset
├── TelnetDevice  (telnet_base.py — transport in telnet_socket.py)
│   ├── instruments/ami136.py    — AMI Model 136 liquid-level monitor
│   ├── instruments/bga244.py    — SRS BGA244 binary gas analyzer
│   ├── instruments/cm4g_magnet.py — Cryomagnetics Model 4G magnet power supply
│   ├── instruments/cs4_magnet.py  — Cryomagnetics CS-4 magnet power supply
│   ├── instruments/dp832.py     — Rigol DP832 programmable DC power supply
│   ├── instruments/eip_counter.py — EIP 588C microwave frequency counter (via Prologix GPIB-Ethernet)
│   ├── instruments/elva1_powmeter.py — ELVA-1 millimeter-wave power meter (untested)
│   ├── instruments/hfc300.py    — HFC300 mass flow controller
│   ├── instruments/lm500.py     — American Magnetics LM-500 level monitor
│   ├── instruments/ls218.py     — Lakeshore Model 218 temperature monitor
│   ├── instruments/ls336.py     — Lakeshore Model 336 temperature controller
│   ├── instruments/mks937b.py   — MKS 937B vacuum gauge controller
│   ├── instruments/si9700.py    — Scientific Instruments SI-9700 temperature controller
│   ├── instruments/tpg_26x.py  — Pfeiffer TPG 261/262 vacuum gauge
│   └── instruments/vaunix_lms.py — Vaunix Lab Brick LMS/BLX synthesiser (via USB-to-TCP shim)
└── BaseDevice (direct)
    ├── instruments/alicat_flow.py — Alicat mass flow controller (alicat library)
    ├── instruments/feedforward.py — Software feed-forward: transforms and sums source PVs (no hardware)
    ├── instruments/ioc_load.py  — Aggregate CPU/memory monitor for master_ioc.py processes
    ├── instruments/pid.py       — Self-contained software PID with anti-windup, bumpless transfer, feed-forward (no hardware)
    ├── instruments/pid_controller.py — Software PID backed by simple_pid (no hardware; same PVs as pid.py)
    └── instruments/zaber_motor.py — Zaber ASCII motor controller (TCP)
```

The software drivers (`pid`, `pid_controller`, `feedforward`, and the IOC-PV
speed source in `dat8188_surestep`) read and write other IOCs' PVs over Channel
Access with `aioca`. Other third-party dependencies are per driver: `alicat`
(`alicat_flow`), `simple_pid` (`pid_controller`), `zaber-motion`
(`zaber_motor`) and `psutil` (`ioc_load`).

## Driver registry

| File | Hardware | Protocol | Key PV types |
|---|---|---|---|
| `dat8017.py` | Datexel DAT8017 | Modbus TCP | `aIn` (calibrated 4-20 mA / V) |
| `dat8017_level.py` | Datexel DAT8017-I | Modbus TCP | `boolIn` x4 (wet/dry per point), `aIn` (level %) |
| `dat8017_azurlight.py` | Datexel DAT8017-V + Azurlight ALS laser | Modbus TCP | `aIn` x8 (diode currents A, power W, temps °C) |
| `dat8018.py` | Datexel DAT8018 | Modbus TCP | `aIn` (thermocouple °C) |
| `dat8024.py` | Datexel DAT8024 | Modbus TCP | `aOut` (0–5 V DAC) |
| `dat8130.py` | Datexel DAT8130 | Modbus TCP | `boolOut` (relay), `boolIn` (DI) |
| `dat8188.py` | Datexel DAT8188 | Modbus TCP | `boolOut` x8 (PNP out), `boolIn` x8 (DI) |
| `dat8188_surestep.py` | SureStep STP-DRV-4850/80100 via DAT8188 (+ DAT8024, its IOC, or preset speed) | Modbus TCP (+ CA) | `aOut` (speed rev/s), `boolOut` x3 (run, direction, enable), `boolIn` (fault) or `aIn` (tach rev/s) |
| `ami136.py` | AMI 136 | Telnet | `aIn` (level %) |
| `bga244.py` | SRS BGA244 | Telnet (RS-232) | `aIn` x6 (gas ratios, temperatures, pressure, normalized speed of sound) |
| `cm4g_magnet.py` | Cryomagnetics 4G | Telnet | `aIn` V/I, `aOut` limits, `mbbOut` sweep |
| `cs4_magnet.py` | Cryomagnetics CS-4 | Telnet | `aIn` V/I, `aOut` limits, `mbbOut` sweep |
| `dp832.py` | Rigol DP832 | Telnet (LXI) | `aIn` V/I, `aOut` setpoints, `boolOut` output enable |
| `eip_counter.py` | EIP 588C | Telnet (Prologix GPIB) | `aIn` (frequency GHz) |
| `elva1_powmeter.py` | ELVA-1 power meter | Telnet (RS-232) | `aIn` (power mW) |
| `hfc300.py` | HFC300 MFC | Telnet (RS-232) | `aIn` flow/T/state, `stringIn` valve, `aOut` SP/manual valve, `mbbOut` mode |
| `lm500.py` | AMI LM-500 | Telnet | `aIn` (level cm) |
| `ls218.py` | Lakeshore 218 | Telnet (RS-232) | `aIn` (temperature K) |
| `ls336.py` | Lakeshore 336 | Telnet (RS-232) | `aIn` T/heater, `aOut` SP/PID, `mbbOut` mode/range |
| `mks937b.py` | MKS 937B | Telnet (RS-485) | `aIn` (pressure mbar) |
| `si9700.py` | SI-9700 | Telnet (RS-232) | `aIn` T/heater, `aOut` SP, `mbbOut` mode |
| `tpg_26x.py` | Pfeiffer TPG 261/262 | Telnet (RS-232) | `aIn` (pressure mbar) |
| `vaunix_lms.py` | Vaunix Lab Brick LMS/BLX | TCP (USB shim) | `aIn` freq/power, `aOut` setpoints, `boolOut` RF/ref, `boolIn` PLL lock |
| `alicat_flow.py` | Alicat flow controller | TCP (alicat) | `aIn` flow/P/T/control, `aOut` setpoint |
| `feedforward.py` | — (software) | Channel Access | `aIn` CV + per-source In/FF, `aOut` Scale/Bias, `mbbOut` Enable |
| `pid.py` | — (software) | Channel Access | `aIn` PV/CV, `aOut` SP/gains/manual/limits, `mbbOut` Mode |
| `pid_controller.py` | — (software, simple_pid) | Channel Access | same PVs as `pid.py` |
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

## Example settings

Every driver has a ready-to-paste entry in
[`instruments/examples/<driver>.yaml`](instruments/examples/), named after the
driver (`lm500.py` → `lm500.yaml`). Each file's header comment says what the
driver talks to, which PVs it creates and any rules for the `channels` list;
driver-specific keys are commented inline.

IP addresses are placeholders from the 192.0.2.0/24 documentation range, and
`PREFIX:` in PV names (used by the software drivers `pid`, `pid_controller`,
`feedforward` and `dat8188_surestep`) stands for the prefix of the IOC that
serves that PV. Replace both before use.

The keys every entry shares (`module`, `autostart`, `delay`, `channels`,
optional per-PV `records` fields) and the required `general` block are
described in the [examples README](instruments/examples/README.md).

## Phoebus displays

[`instruments/gui/`](instruments/gui/) holds Phoebus / CS-Studio (`.bob`)
displays for the drivers. None hardcode PV names: they take macros (`P` for
`general.prefix`, `CH` for the `channels` entry, `LABEL`, and `GUI` for the
path back to this folder), so one file serves any IOC.

| Folder | Contents |
|---|---|
| [`subpanels/`](instruments/gui/subpanels/) | Full control screens: `pid`, `ls336`, `magnet` (CS-4 / 4G), `hfc300`, `feedforward`, `vaunix_lms`, `zaber_motor`, `surestep` |
| [`templates/`](instruments/gui/templates/) | Compact blocks to embed or paste into your own panels: generic `readback`, `setpoint`, `digital_in`, `digital_out`, plus per-driver blocks (`pid_compact`, `ls336_compact`, `si9700_compact`, `alicat_compact`, `hfc300_compact`, `magnet_compact`, `dp832_channel`, `level_probe`, `laser_monitor`, `bga244`, `zaber_compact`, `surestep_compact`, `ioc_load`). Compact blocks with a matching subpanel have a Details… button that opens it. |
| [`ioc/`](instruments/gui/ioc/) | IOC manager controls: `ioc_row.bob` for hand-built panels, and `make_ioc_panel.py`, which generates a full Stop/Run/Reset + heartbeat panel from a `settings.yaml` |

Generate the IOC control panel from a deployment repo with:

```bash
python devices/instruments/gui/ioc/make_ioc_panel.py settings.yaml gui/ioc_control.bob
```

The [GUI README](instruments/gui/README.md) lists which drivers and macros each
file takes, and how to embed, copy or open them from your own displays.

## Tests

```bash
pytest tests     # needs softioc, PyYAML and pytest
```

- `tests/test_examples.py` checks that every driver has an example, that each
  example builds its driver's PVs, that every `records` key names a PV the
  driver creates, and that every `settings['key']` the driver reads is present.
- `tests/test_gui.py` checks that every `.bob` file parses and that every
  Details… / Open Display target exists.

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
7. Add `instruments/examples/<yourdriver>.yaml` with a working settings entry,
   and run `pytest tests` (needs `softioc`, `PyYAML` and `pytest`). The test
   fails for a driver without an example, a settings key the driver reads but
   the example lacks, or a `records` entry for a PV the driver never creates.
8. Optionally add a template and/or subpanel under `instruments/gui/` using the
   `P` / `CH` / `LABEL` / `GUI` macros, and list it in the
   [GUI README](instruments/gui/README.md).
9. Commit, tag, and update the submodule pin in each deployment repo that needs it.

## Author
Written in 2023-2026 by J. Maxwell (https://orcid.org/0000-0003-2710-4646).

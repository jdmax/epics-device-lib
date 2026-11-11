# Phoebus displays

Phoebus / CS-Studio (`.bob`) displays for the drivers in `instruments/`. None
of them hardcode PV names; they all use macros, so one file serves any IOC.

```
gui/
├── subpanels/   full control screens, opened from a main panel
├── templates/   compact blocks to embed or copy into your own panels
└── ioc/         IOC manager controls (row template + panel generator)
```

## Macros

| Macro | Meaning | Default in the files |
|---|---|---|
| `P` | `general.prefix` from settings.yaml, e.g. `TGT:MEOP` | `TGT:EXAMPLE` |
| `CH` | the driver's `channels` entry, e.g. `PID_Temp` | `CH` |
| `LABEL` | text shown for the block | `$(CH)` |
| `GUI` | path to this `gui/` folder, used by the Details… buttons | `..` |

PVs are built as `$(P):$(CH)_<suffix>`, which matches what the drivers create.
A few drivers name each PV separately instead of using a channel prefix, so
their files take one macro per PV (see the table below).

## Using a template

**Embed it (recommended).** Add an *Embedded Display* widget, set *File* to the
template, and set its macros (e.g. `P=TGT:MEOP`, `CH=Liquifier`). The
template's Details… button then finds its subpanel, because `GUI=..` resolves
relative to the template file.

**Copy and paste it.** Open the template, select its group, and paste it into
your panel. Then set the macros on the pasted group's *Macros* property:
`CH`, `LABEL`, and `GUI` (the path from your panel to this folder, e.g.
`../devices/instruments/gui` from a deployment repo's `gui/`). Set `P` once on
the display.

**Opening a subpanel from your own button.** Use an *Action Button* with an
*Open Display* action pointing at `subpanels/<name>.bob`. Widget macros are
passed to the new display, so set `CH` on the button or on its group.

## Contents

### Subpanels

| File | Drivers | Macros |
|---|---|---|
| `pid.bob` | `pid`, `pid_controller` | `P`, `CH` |
| `ls336.bob` | `ls336` (control loops) | `P`, `CH` |
| `magnet.bob` | `cm4g_magnet` (4G and CS-4) | `P`, `CH` |
| `hfc300.bob` | `hfc300` | `P`, `CH` |
| `feedforward.bob` | `feedforward` (4 source rows) | `P`, `CH` |
| `vaunix_lms.bob` | `vaunix_lms` | `P`, `CH` |
| `zaber_motor.bob` | `zaber_motor` (4 preset rows) | `P`, `CH` |
| `surestep.bob` | `dat8188_surestep` | `P`, `SPEED`, `RUN`, `DIR`, `EN`, `OUT` |

The panels with a variable number of rows (feed-forward sources, Zaber
presets) show 4. Rows your IOC doesn't create show as disconnected; delete
them or copy one to add more.

### Templates

| File | Drivers | Macros | Details… opens |
|---|---|---|---|
| `readback.bob` | any single-value driver: `ls218`, `lm500`, `mks937b`, `tpg_26x`, `ami136`, `dat8017`, `dat8018`, `eip_counter`, `elva1_powmeter` | `CH`, `LABEL` | |
| `setpoint.bob` | `dat8024`, any lone aOut | `CH`, `RB` (readback PV, default `$(CH)`), `LABEL` | |
| `pid_compact.bob` | `pid`, `pid_controller` | `CH`, `LABEL` | `pid` |
| `ls336_compact.bob` | `ls336` | `CH`, `LABEL` | `ls336` |
| `si9700_compact.bob` | `si9700` | `CH`, `LABEL` | |
| `alicat_compact.bob` | `alicat_flow` | `CH`, `LABEL` | |
| `hfc300_compact.bob` | `hfc300` | `CH`, `LABEL` | `hfc300` |
| `magnet_compact.bob` | `cm4g_magnet` (4G and CS-4) | `CH`, `LABEL` | `magnet` |
| `dp832_channel.bob` | `dp832`: a header group plus one channel row; repeat the row per channel | `CH`, `LABEL` | |
| `digital_out.bob` | `dat8130`, `dat8188` outputs, any boolOut | `CH`, `LABEL` | |
| `digital_in.bob` | `dat8130`, `dat8188` inputs, any boolIn | `CH`, `LABEL` | |
| `level_probe.bob` | `dat8017_level` | `S1`–`S4` (sensors, top to bottom), `LABEL` | |
| `laser_monitor.bob` | `dat8017_azurlight` | one per channel, defaults match `examples/dat8017_azurlight.yaml` | |
| `bga244.bob` | `bga244` | `CH`, `LABEL` | |
| `zaber_compact.bob` | `zaber_motor` | `CH`, `LABEL` | `zaber_motor` |
| `surestep_compact.bob` | `dat8188_surestep` | `SPEED`, `RUN`, `DIR`, `EN`, `OUT`, `LABEL` | `surestep` |
| `ioc_load.bob` | `ioc_load` | `LABEL` | |

## IOC controls

These depend on the deployment repo's `ioc_manager.py`, which serves
`<prefix>:MAN:<ioc>_control` (Stop / Run / Reset), `<prefix>:MAN:<ioc>_hb`
(seconds since the IOC last updated) and `<prefix>:MAN:all`.

- `ioc/make_ioc_panel.py` builds a complete panel from a settings.yaml, with
  one row per IOC plus the *All autostart IOCs* control:

  ```
  python devices/instruments/gui/ioc/make_ioc_panel.py settings.yaml gui/ioc_control.bob
  ```

  The heartbeat is grey while an IOC isn't set to Run. While it is set to Run,
  the heartbeat is green, and turns red once it is older than
  `max(10 s, 5 × the IOC's delay)`. You can change both numbers with
  `--min-limit` and `--factor`. Rerun the script whenever you add or remove
  IOCs; it overwrites the output file.
- `ioc/ioc_row.bob` is a single row (macros `IOC`, `LABEL`) for hand-built
  panels. Its heartbeat limit is fixed at 10 s; edit the rule to change it.

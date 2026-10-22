# Example settings

One file per driver in `instruments/`, named after it (`lm500.py` → `lm500.yaml`).
Each holds a single IOC entry that can be pasted into a deployment repo's
`settings.yaml`. The header comment says what the driver talks to, what PVs it
creates, and any rules for the `channels` list.

IP addresses are placeholders from the 192.0.2.0/24 documentation range, and
`PREFIX:` in PV names stands for the prefix of whichever IOC serves that PV.
Replace both before use.

## Keys every entry has

The top-level key (`lm500:` etc.) is the IOC name passed to `master_ioc.py -i`.
It must be unique within a settings file.

| Key | Read by | Meaning |
|---|---|---|
| `module` | master_ioc | Driver import path, `devices.instruments.<driver>` |
| `autostart` | IOC manager | Start this IOC automatically |
| `delay` | master_ioc | Seconds between reads |
| `channels` | driver | List of PV names or name prefixes; meaning is per driver, see each file. Any entry containing `None` is skipped. |
| `records` | master_ioc | Optional. Per-PV EPICS record fields (`DESC`, `PREC`, `EGU`, `HIHI`/`HIGH`/`LOW`/`LOLO` alarm limits, `DRVH`/`DRVL` drive limits, ...). Keys must be PV names the driver creates; fields are set on the record before the IOC starts. |

Hardware drivers also take `ip`, `port` (a string) and `timeout` (seconds).
Anything else in an example is specific to that driver and is commented there.

The settings file also needs a `general` block, shared by all its IOCs:

```yaml
general:
  prefix: 'TGT:EXAMPLE'                 # PV prefix for every IOC in this file
  log_dir: 'logs'
  epics_addr_list: '127.255.255.255'    # EPICS_CA_ADDR_LIST
  delay: 0.5
```

## Keeping them current

`tests/test_examples.py` checks that every driver has an example, that each
example builds its driver's PVs, that every `records` key names a PV the driver
creates, and that every `settings['key']` the driver reads is present. When you
add a driver or change the settings it reads, update its example and run:

```
pytest tests
```

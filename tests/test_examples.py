"""Check instruments/examples/*.yaml against the drivers they configure.

Each example is loaded the way master_ioc.py loads a settings entry: the driver's
Device is built from it and its records fields are applied. No hardware is
contacted; connect() is never called.
"""
import importlib
import inspect
import re
from pathlib import Path

import pytest
import yaml

builder = pytest.importorskip('softioc.builder')

ROOT = Path(__file__).resolve().parents[1]
INSTRUMENTS = ROOT / 'instruments'
EXAMPLES = sorted((INSTRUMENTS / 'examples').glob('*.yaml'))
DRIVERS = sorted(p.stem for p in INSTRUMENTS.glob('*.py') if p.stem != '__init__')

SETTINGS_KEY = re.compile(r"settings\[['\"](\w+)['\"]\]")


def load_example(path):
    entries = yaml.safe_load(path.read_text())
    assert len(entries) == 1, f"{path.name} should hold exactly one IOC entry"
    return next(iter(entries.items()))


def import_driver(module_name):
    """Import a driver, skipping if a third-party package it needs is missing."""
    try:
        return importlib.import_module(module_name)
    except ModuleNotFoundError as e:
        if e.name and e.name.split('.')[0] == 'devices':
            raise
        pytest.skip(f"{e.name} not installed")


def required_keys(device_class):
    """settings['key'] lookups in the driver and the library base classes it uses.

    BaseDevice is left out: it reads settings['ip'] only to print a connection
    error, which hardware-free devices never reach.
    """
    keys = set()
    for cls in device_class.__mro__:
        if not cls.__module__.startswith('devices.') or cls.__name__ == 'BaseDevice':
            continue
        keys |= set(SETTINGS_KEY.findall(inspect.getsource(cls)))
    return keys


def test_every_driver_has_an_example():
    missing = set(DRIVERS) - {p.stem for p in EXAMPLES}
    assert not missing, f"No example in instruments/examples/ for: {sorted(missing)}"


@pytest.mark.parametrize('path', EXAMPLES, ids=lambda p: p.stem)
def test_example_matches_driver(path):
    name, settings = load_example(path)

    assert settings['module'] == f'devices.instruments.{path.stem}'
    for key in ('autostart', 'delay', 'channels'):
        assert key in settings, f"missing '{key}'"

    module = import_driver(settings['module'])

    missing = required_keys(module.Device) - set(settings)
    assert not missing, f"driver reads settings keys the example lacks: {sorted(missing)}"

    # A distinct prefix per example keeps record names unique within this process.
    prefix = f'EXAMPLE:{path.stem}'
    builder.SetDeviceName(prefix)
    device = module.Device(prefix, settings)

    records = settings.get('records') or {}
    unknown = set(records) - set(device.pvs)
    assert not unknown, f"records for PVs the driver does not create: {sorted(unknown)}"
    for pv_name, fields in records.items():
        for field, value in fields.items():
            setattr(device.pvs[pv_name], field, value)

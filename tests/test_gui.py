"""Checks on the Phoebus displays in instruments/gui."""
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

GUI = Path(__file__).resolve().parent.parent / 'instruments' / 'gui'
DISPLAYS = sorted(GUI.rglob('*.bob'))


def test_displays_exist():
    assert DISPLAYS, f'no .bob files under {GUI}'


@pytest.mark.parametrize('path', DISPLAYS, ids=lambda p: p.relative_to(GUI).as_posix())
def test_display_parses(path):
    root = ET.parse(path).getroot()
    assert root.tag == 'display'


@pytest.mark.parametrize('path', DISPLAYS, ids=lambda p: p.relative_to(GUI).as_posix())
def test_open_display_targets_exist(path):
    """Details buttons use $(GUI)/..., where GUI defaults to '..' from templates/."""
    root = ET.parse(path).getroot()
    for f in root.iter('file'):
        target = (path.parent / f.text.replace('$(GUI)', '..')).resolve()
        assert target.exists(), f'{path.name} opens missing {f.text}'

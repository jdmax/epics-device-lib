"""Build a Phoebus IOC control panel from a settings.yaml.

One row per IOC in the file: name, autostart flag, the IOC manager's
Stop/Run/Reset control (<prefix>:MAN:<ioc>_control) and its heartbeat
(<prefix>:MAN:<ioc>_hb, seconds since the IOC last wrote its _time PV).
The heartbeat turns green while the IOC is set to Run and has updated within
its limit, red once it is older, and grey while the IOC is not set to Run.
The limit is max(--min-limit, --factor * the IOC's delay).

A header row drives <prefix>:MAN:all, which the manager applies to every IOC
with autostart: True.

Usage:
    python make_ioc_panel.py settings.yaml ioc_control.bob [--factor 5] [--min-limit 10]

Rerun it whenever IOCs are added to or removed from settings.yaml. Edits
made to the output in Phoebus are lost on the next run.
"""
import argparse
from pathlib import Path
from xml.sax.saxutils import escape

import yaml

ROW = 26
NAME_W, AUTO_W, CTRL_W, HB_W = 220, 70, 110, 90
X_AUTO = 10 + NAME_W + 5
X_CTRL = X_AUTO + AUTO_W + 5
X_HB = X_CTRL + CTRL_W + 10
WIDTH = X_HB + HB_W + 20


def color(name, r, g, b, tag):
    return f'<{tag}><color name="{name}" red="{r}" green="{g}" blue="{b}"></color></{tag}>'


def widget(wtype, name, x, y, w, h, body, version='2.0.0'):
    return (f'  <widget type="{wtype}" version="{version}">\n'
            f'    <name>{escape(name)}</name>\n'
            f'    <x>{x}</x>\n    <y>{y}</y>\n    <width>{w}</width>\n    <height>{h}</height>\n'
            f'    {body}\n  </widget>\n')


def label(name, text, x, y, w, bold=False, align=0):
    font = ('<font><font name="Default Bold" family="Liberation Sans" style="BOLD" size="14.0">'
            '</font></font>' if bold else '')
    return widget('label', name, x, y, w, 20,
                  f'<text>{escape(text)}</text>{font}<horizontal_alignment>{align}</horizontal_alignment>'
                  '<vertical_alignment>1</vertical_alignment>')


def combo(name, pv, x, y, w, tip):
    return widget('combo', name, x, y, w, 22,
                  f'<pv_name>{escape(pv)}</pv_name><items_from_pv>true</items_from_pv>'
                  f'<tooltip>{escape(tip)}</tooltip>')


def heartbeat(name, hb_pv, control_pv, x, y, limit):
    rule = ('<rules><rule name="Heartbeat stale" prop_id="background_color" out_exp="false">'
            f'<exp bool_exp="pv1 != 1">{color("Read_Background", 240, 240, 240, "value")}</exp>'
            f'<exp bool_exp="pv0 &gt; {limit}">{color("MAJOR", 255, 0, 0, "value")}</exp>'
            f'<exp bool_exp="pv0 &lt;= {limit}">{color("OK", 0, 255, 0, "value")}</exp>'
            f'<pv_name>{escape(hb_pv)}</pv_name><pv_name>{escape(control_pv)}</pv_name></rule></rules>')
    return widget('textupdate', name, x, y, HB_W, 22,
                  f'<pv_name>{escape(hb_pv)}</pv_name><format>1</format><precision>1</precision>'
                  '<show_units>false</show_units><horizontal_alignment>1</horizontal_alignment>'
                  '<vertical_alignment>1</vertical_alignment><transparent>false</transparent>'
                  f'<tooltip>Seconds since last update; red above {limit} s</tooltip>{rule}')


def build(settings, factor, min_limit):
    general = settings.get('general', {})
    prefix = general.get('prefix', 'PREFIX')
    default_delay = float(general.get('delay', 1.0))
    iocs = [(k, v or {}) for k, v in settings.items() if 'general' not in k]
    man = f'{prefix}:MAN'

    ws = [widget('label', 'Title', 0, 0, WIDTH, 30,
                 f'<text>{escape(prefix)} IOC Control</text>'
                 '<font><font name="Header 2" family="Liberation Sans" style="BOLD" size="18.0"></font></font>'
                 f'{color("Header_ForeGround", 255, 255, 255, "foreground_color")}'
                 f'{color("Header_Background", 77, 77, 77, "background_color")}'
                 '<transparent>false</transparent><horizontal_alignment>1</horizontal_alignment>'
                 '<vertical_alignment>1</vertical_alignment>'),
          label('All label', 'All autostart IOCs', 10, 42, NAME_W + AUTO_W, bold=True),
          combo('All control', f'{man}:all', X_CTRL, 41, CTRL_W,
                'Stop / Run / Reset every IOC with autostart: True')]
    y = 80
    for text, x, w in [('IOC', 10, NAME_W), ('Autostart', X_AUTO, AUTO_W),
                       ('Control', X_CTRL, CTRL_W), ('Heartbeat (s)', X_HB, HB_W)]:
        ws.append(label(f'Header {text}', text, x, y, w, bold=True, align=0 if text == 'IOC' else 1))
    y += ROW
    for name, cfg in iocs:
        delay = float(cfg.get('delay', default_delay))
        limit = round(max(min_limit, factor * delay), 1)
        auto = 'yes' if cfg.get('autostart') else 'no'
        ctrl = f'{man}:{name}_control'
        ws += [label(f'{name} name', name, 10, y, NAME_W),
               label(f'{name} autostart', auto, X_AUTO, y, AUTO_W, align=1),
               combo(f'{name} control', ctrl, X_CTRL, y, CTRL_W, f'Stop / Run / Reset {name}'),
               heartbeat(f'{name} heartbeat', f'{man}:{name}_hb', ctrl, X_HB, y, limit)]
        y += ROW
    return ('<?xml version="1.0" encoding="UTF-8"?>\n'
            '<!-- Generated by devices/instruments/gui/ioc/make_ioc_panel.py; rerun it rather than editing. -->\n'
            f'<display version="2.0.0">\n  <name>{escape(prefix)} IOC Control</name>\n'
            f'  <width>{WIDTH}</width>\n  <height>{y + 10}</height>\n' + ''.join(ws) + '</display>\n')


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('settings', type=Path)
    ap.add_argument('output', type=Path)
    ap.add_argument('--factor', type=float, default=5.0, help='heartbeat limit = factor * delay')
    ap.add_argument('--min-limit', type=float, default=10.0, help='smallest heartbeat limit, seconds')
    a = ap.parse_args()
    settings = yaml.safe_load(a.settings.read_text())
    a.output.write_text(build(settings, a.factor, a.min_limit), encoding='utf-8', newline='\n')
    print(f'wrote {a.output}')


if __name__ == '__main__':
    main()

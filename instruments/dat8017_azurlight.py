import math
from ..modbus_base import ModbusDevice
from softioc import builder, alarm


class Device(ModbusDevice):
    """Azurlight ALS laser rear-panel DB9 monitor read via a Datexel DAT8017-V.

    The 8 monitor signals (DB9 pins 1-4, 6-9) are wired to DAT8017-V inputs
    0-7 in pin order; DB9 pin 5 (COMMON) goes to the module's input common.
    Each channel's conversion from volts is set in settings['calibration']:
        'current'  - pump diode current, I = V*5 (ImonA, ImonPA)
        'limit'    - pump diode current limit, I = (V-0.13)*5 (Lmon)
        'temp'     - NTC temperature, T = 1/(ln(V)/3450 + 1/298.15) - 273.15
                     (Tact-P, Tset-P, Tset-H, Tact-H)
        number     - linear scale, value = V*number (Pmon, from test report)
        [a, b]     - linear with offset, value = V*a + b
        anything else - raw volts

    When the laser is off all monitor outputs drop below ~0.2 V. The Lmon
    voltage is compared to settings['on_threshold'] to set Laser_On; while
    off, current and power channels read 0, and temperature and limit
    channels (meaningless without the controller driving them) go INVALID.
    """

    B_COEFF = 3450      # NTC beta value from Azurlight manual
    T_REF = 298.15      # K, temperature where Vt = 1 V
    OFF_INVALID = ('temp', 'limit')  # calibrations with no meaning while laser is off

    def __init__(self, device_name, settings):
        self.calibs = {}
        self.mv_per_count = settings.get('mv_per_count', 1.0)  # register units -> mV
        self.on_threshold = settings.get('on_threshold', 0.5)  # Lmon volts; above = laser on
        super().__init__(device_name, settings)

    def _create_pvs(self):
        """Create analog input PVs with calibration info, plus laser on/off state"""
        for channel in self._skip_none_channels():
            self.calibs[channel] = self.settings['calibration'].get(channel)
            self.pvs[channel] = builder.aIn(channel, **self.sevr)
        self.pvs['Laser_On'] = builder.boolIn('Laser_On', ZNAM='Off', ONAM='On', DISP=self.sevr['DISP'])

    async def do_reads(self):
        """Read all 8 voltage registers; channel index maps to physical input,
        so 'None' channels are skipped without shifting the others"""
        try:
            readings = self.t.read_all()
            volts = {ch: self._to_volts(readings[i])
                     for i, ch in enumerate(self.channels) if "None" not in ch}

            limit_chs = [ch for ch in volts if self.calibs[ch] == 'limit']
            laser_on = not limit_chs or volts[limit_chs[0]] > self.on_threshold
            self.pvs['Laser_On'].set(laser_on)
            self.remove_alarm('Laser_On')

            for channel, v in volts.items():
                calib = self.calibs[channel]
                if not laser_on and calib in self.OFF_INVALID:
                    self._set_invalid(channel)
                elif not laser_on:
                    self.pvs[channel].set(0.0)
                    self.remove_alarm(channel)
                else:
                    try:
                        self.pvs[channel].set(self._convert(channel, v))
                        self.remove_alarm(channel)
                    except ValueError as e:  # bad value on one channel; invalidate it alone
                        print(e)
                        self._set_invalid(channel)
            return True
        except (OSError, TypeError, AttributeError) as e:
            print(e)
            self._handle_read_error()
            self.set_alarm('Laser_On')
            return False

    def _set_invalid(self, channel):
        """Keep last value but mark it INVALID (undefined)"""
        self.pvs[channel].set_alarm(severity=3, alarm=alarm.UDF_ALARM)

    def _to_volts(self, raw_value):
        """Convert signed 16-bit register value to volts"""
        if raw_value > 32767:  # 16-bit two's complement
            raw_value -= 65536
        return raw_value * self.mv_per_count / 1000

    def _convert(self, channel, volts):
        """Apply channel calibration to a voltage"""
        calib = self.calibs[channel]
        if calib == 'current':
            return volts * 5
        if calib == 'limit':
            return (volts - 0.13) * 5
        if calib == 'temp':
            if volts <= 0:
                raise ValueError(f"{channel}: non-positive thermistor voltage {volts} V")
            return 1 / (math.log(volts) / self.B_COEFF + 1 / self.T_REF) - 273.15
        if isinstance(calib, (int, float)) and not isinstance(calib, bool):
            return volts * calib
        if isinstance(calib, list) and len(calib) == 2:
            return volts * calib[0] + calib[1]
        return volts

import math
from ..modbus_base import ModbusDevice
from softioc import builder


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
    """

    B_COEFF = 3450      # NTC beta value from Azurlight manual
    T_REF = 298.15      # K, temperature where Vt = 1 V

    def __init__(self, device_name, settings):
        self.calibs = {}
        self.mv_per_count = settings.get('mv_per_count', 1.0)  # register units -> mV
        super().__init__(device_name, settings)

    def _create_pvs(self):
        """Create analog input PVs with calibration info"""
        for channel in self._skip_none_channels():
            self.calibs[channel] = self.settings['calibration'].get(channel)
            self.pvs[channel] = builder.aIn(channel, **self.sevr)

    async def do_reads(self):
        """Read all 8 voltage registers; channel index maps to physical input,
        so 'None' channels are skipped without shifting the others"""
        try:
            readings = self.t.read_all()
            for i, channel in enumerate(self.channels):
                if "None" in channel:
                    continue
                try:
                    self.pvs[channel].set(self._process_reading(channel, readings[i]))
                    self.remove_alarm(channel)
                except ValueError as e:  # bad value on one channel; alarm it alone
                    print(e)
                    self.set_alarm(channel)
            return True
        except (OSError, TypeError, AttributeError) as e:
            print(e)
            self._handle_read_error()
            return False

    def _process_reading(self, channel, raw_value):
        """Convert signed register value to volts, then apply calibration"""
        if raw_value > 32767:  # 16-bit two's complement
            raw_value -= 65536
        volts = raw_value * self.mv_per_count / 1000
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

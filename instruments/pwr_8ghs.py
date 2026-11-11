"""Mini-Circuits PWR-8GHS-RC (PWR-SEN-8GHS-RC) CW average power sensor via Telnet.

SCPI over the sensor's own Telnet server (port 23 by default). Commands and
responses are terminated with CR/LF. On connect the sensor sends a bare line
feed; if password security is enabled the password must be the first command.

The sensor is put in low-noise measurement mode (:MODE:0) on every connection,
and the compensation frequency is (re)applied, since the reading is only within
spec when the compensation frequency matches the signal.

PVs (channel name taken from settings 'channels', one entry):
    {ch}       aIn   power in dBm (-99 dBm means below the sensor's useable range)
    {ch}_Freq  aOut  compensation frequency in MHz
    {ch}_Temp  aIn   internal sensor temperature in C (uncalibrated)
"""
import logging
import re
from softioc import builder
from ..telnet_base import TelnetDevice, TelnetConnection


class Device(TelnetDevice):
    """PVs and read/set logic for a Mini-Circuits PWR-8GHS-RC power sensor"""

    def _create_pvs(self):
        for channel in self._skip_none_channels():
            self.pvs[channel] = builder.aIn(channel, **self.sevr)
            self.pvs[channel + '_Freq'] = builder.aOut(channel + '_Freq', on_update_name=self.do_sets)
            self.pvs[channel + '_Temp'] = builder.aIn(channel + '_Temp')

    def _create_connection(self):
        return DeviceConnection(
            self.settings['ip'],
            self.settings['port'],
            self.settings['timeout'],
            self._target_freq(),
            self.settings.get('password'),
        )

    def _target_freq(self):
        """Compensation frequency to apply on (re)connect: the PV if it has been set, else settings."""
        channel = self._skip_none_channels()[0]
        pv_freq = self.pvs[channel + '_Freq'].get()
        return pv_freq if pv_freq else self.settings['freq']

    def read_outs(self):
        """Read compensation frequency back into its OUT PV at the start of the IOC"""
        channel = self._skip_none_channels()[0]
        try:
            self.pvs[channel + '_Freq'].set(self.t.read_freq(), process=False)
        except OSError:
            logging.error("PWR-8GHS read out error on %s", channel)

    def do_sets(self, new_value, pv):
        """Write compensation frequency to sensor"""
        channel = self._skip_none_channels()[0]
        try:
            value = self.t.set_freq(new_value)
            self.pvs[channel + '_Freq'].set(value, process=False)
        except OSError:
            self.reconnect()

    async def do_reads(self):
        channel = self._skip_none_channels()[0]
        try:
            power = self.t.read_power()
            temp = self.t.read_temp()
            self.pvs[channel].set(power)
            self.pvs[channel + '_Temp'].set(temp)
            self._handle_read_success()
            return True
        except OSError:
            self._handle_read_error()
            return False


class DeviceConnection(TelnetConnection):
    """SCPI over Telnet to a Mini-Circuits PWR-8GHS-RC"""

    number = re.compile(r'[-+]?\d+(?:\.\d+)?')

    def __init__(self, host, port, timeout, freq, password=None):
        super().__init__(host, port, timeout)
        try:
            self.tn.read_until(b'\n', timeout=1)   # discard the greeting line feed
            if password:
                if self.query(f'PWD={password};').strip() != '1':
                    logging.error("PWR-8GHS password rejected on %s", self.host)
            self.command(':MODE:0')                # low noise mode
            self.set_freq(freq)
        except Exception as e:
            logging.error(f"PWR-8GHS init failed on {self.host}: {e}")

    def query(self, cmd):
        """Send a command, return the first non-empty response line."""
        self.tn.write(bytes(cmd + '\r\n', 'ascii'))
        for _ in range(3):   # skip stray blank lines (e.g. a late greeting)
            data = self.tn.read_until(b'\n', timeout=self.timeout).decode('ascii', errors='replace')
            if not data:
                break
            if data.strip():
                if 'unknown' in data.lower() or 'unrecognized' in data.lower() or 'Model:' in data:
                    raise OSError(f'PWR-8GHS rejected {cmd!r}: {data.strip()!r}')
                return data
        raise OSError(f'PWR-8GHS no response to {cmd!r}')

    def command(self, cmd):
        """Send a set command; sensor replies 1 on success."""
        reply = self.query(cmd).strip()
        if reply != '1':
            raise OSError(f'PWR-8GHS {cmd!r} failed: {reply!r}')

    def _number(self, cmd):
        data = self.query(cmd)
        m = self.number.search(data)
        if not m:
            raise OSError(f'PWR-8GHS parse failed for {cmd!r}: {data!r}')
        return float(m.group())

    def read_power(self):
        """Power in dBm, e.g. '-22.050 dBm'"""
        return self._number(':POWER?')

    def read_temp(self):
        """Internal temperature, e.g. '+25.50,'"""
        return self._number(':TEMP?')

    def read_freq(self):
        """Compensation frequency in MHz, e.g. '2500.000000 MHz'"""
        return self._number(':FREQ?')

    def set_freq(self, freq):
        """Set compensation frequency in MHz, return value read back"""
        self.command(f':FREQ:{freq:g}')
        return self.read_freq()

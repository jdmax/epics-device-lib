"""SRS SR844 RF lock-in amplifier via RS-232 serial-to-Ethernet adapter.

Minimal PV set for reading the demodulated signal against an external reference:

    {ch}_X, {ch}_Y, {ch}_R   aIn      outputs in V
    {ch}_Theta               aIn      phase in degrees
    {ch}_Freq                aIn      measured reference frequency in Hz
    {ch}_Sens                mbbOut   sensitivity (fixed; no autorange is ever sent)
    {ch}_TC                  mbbOut   time constant
    {ch}_Unlock              boolIn   reference unlock / out of range since last poll (MAJOR)
    {ch}_Overload            boolIn   input/IF/filter overload since last poll (MAJOR)

X, Y, R, Theta and Freq carry a MAJOR alarm whenever an unlock or overload was
latched during the poll that produced them, or the front panel was touched, so
downstream logic can reject them by severity.

The LIA status register (LIAS?) latches events and clears on read. It is read
after SNAP?, so a flag covers the interval in which that snapshot was taken.

SNAP? returns X, Y and R with offsets and ratio applied, so on every connect the
modes that would silently change X/Y are switched off: XY and R offsets, ratio,
2F detection and Rel mode. A front-panel key press or knob turn (*ESR bit 6) is
detected on the next poll: that reading is flagged, the configuration below is
re-applied and Sens/TC are read back into their PVs.

Optional settings applied on every connect (omit to leave the instrument as is):
    ref_impedance:    '50' or '10k'   REF IN impedance (REFZ); also forces external reference (FMOD 0)
    input_impedance:  '50' or '1M'    SIGNAL IN impedance (INPZ)
    slope:            'none', '6', '12', '18' or '24'   filter slope in dB/oct (OFSL)
    wide_reserve:     'high', 'normal' or 'low_noise'   RF reserve (WRSV)
    close_reserve:    'high', 'normal' or 'low_noise'   IF reserve (CRSV)
    phase:            degrees, reference phase (PHAS)
"""
import logging
import re
from softioc import builder, alarm
from ..telnet_base import TelnetDevice, TelnetConnection

SENS = ['100 nV', '300 nV', '1 uV', '3 uV', '10 uV', '30 uV', '100 uV', '300 uV',
        '1 mV', '3 mV', '10 mV', '30 mV', '100 mV', '300 mV', '1 V']
# SR844 goes to 30 ks (index 17); mbbOut holds 16 states, so stop at 3 ks.
TC = ['100 us', '300 us', '1 ms', '3 ms', '10 ms', '30 ms', '100 ms', '300 ms',
      '1 s', '3 s', '10 s', '30 s', '100 s', '300 s', '1 ks', '3 ks']

UNLOCK_BITS = 0x03    # LIAS bit 0 ULK reference unlock, bit 1 FRQ reference out of range
OVERLOAD_BITS = 0x70  # LIAS bit 4 INP signal input, bit 5 RSV IF amplifier, bit 6 FLT time constant filter
ESR_ERROR = 0x30      # *ESR bit 4 EXE execution error, bit 5 CMD illegal command
ESR_PANEL = 0x40      # *ESR bit 6 URQ key press or knob rotation


class Device(TelnetDevice):
    """PVs and read/set logic for an SRS SR844 lock-in"""

    def _create_pvs(self):
        ch = self._skip_none_channels()[0]
        self.ch = ch
        self.meas = ['X', 'Y', 'R', 'Theta', 'Freq']
        for m in self.meas:
            self.pvs[f'{ch}_{m}'] = builder.aIn(f'{ch}_{m}')
        self.pvs[f'{ch}_Sens'] = builder.mbbOut(f'{ch}_Sens', *SENS, on_update_name=self.do_sets)
        self.pvs[f'{ch}_TC'] = builder.mbbOut(f'{ch}_TC', *TC, on_update_name=self.do_sets)
        self.pvs[f'{ch}_Unlock'] = builder.boolIn(f'{ch}_Unlock', 'Locked', 'Unlocked', OSV='MAJOR')
        self.pvs[f'{ch}_Overload'] = builder.boolIn(f'{ch}_Overload', 'OK', 'Overload', OSV='MAJOR')

    def _create_connection(self):
        keys = ('ref_impedance', 'input_impedance', 'slope', 'wide_reserve', 'close_reserve', 'phase')
        return DeviceConnection(
            self.settings['ip'],
            self.settings['port'],
            self.settings['timeout'],
            {k: self.settings.get(k) for k in keys},
        )

    def read_outs(self):
        """Read sensitivity and time constant into OUT PVs at the start of the IOC"""
        try:
            self._sync_outs()
        except OSError:
            logging.error("SR844 read out error")

    def _sync_outs(self):
        sens = self.t.query_int('SENS?')
        tc = self.t.query_int('OFLT?')
        self.pvs[f'{self.ch}_Sens'].set(sens, process=False)
        if tc < len(TC):
            self.pvs[f'{self.ch}_TC'].set(tc, process=False)
        else:
            logging.warning("SR844 time constant index %d beyond 3 ks, not shown in %s_TC", tc, self.ch)

    def do_sets(self, new_value, pv):
        pv_name = pv.replace(self.device_name + ':', '')
        try:
            if pv_name.endswith('_Sens'):
                self.t.command(f'SENS {int(new_value)}')
            elif pv_name.endswith('_TC'):
                self.t.command(f'OFLT {int(new_value)}')
            self._sync_outs()
        except OSError:
            self.reconnect()

    async def do_reads(self):
        ch = self.ch
        try:
            x, y, r, theta, freq = self.t.snap()
            status = self.t.query_int('LIAS?')
            touched = bool(self.t.query_int('*ESR?') & ESR_PANEL) or self.t.panel_touched
            if touched:
                logging.warning("SR844 front panel used; re-applying configuration")
                self.t.configure()
                self._sync_outs()
        except OSError:
            for m in self.meas:
                self.pvs[f'{ch}_{m}'].set_alarm(severity=alarm.INVALID_ALARM, alarm=alarm.READ_ALARM)
            self.reconnect()
            return False

        unlock = bool(status & UNLOCK_BITS)
        overload = bool(status & OVERLOAD_BITS)
        self.pvs[f'{ch}_Unlock'].set(int(unlock))
        self.pvs[f'{ch}_Overload'].set(int(overload))
        if unlock or overload or touched:
            sevr, stat = alarm.MAJOR_ALARM, alarm.STATE_ALARM
        else:
            sevr, stat = alarm.NO_ALARM, alarm.NO_ALARM
        for m, v in zip(self.meas, (x, y, r, theta, freq)):
            self.pvs[f'{ch}_{m}'].set(v, severity=sevr, alarm=stat)
        return True


class DeviceConnection(TelnetConnection):
    """SR844 RS-232 command interface. Commands end in LF; replies end in CR."""

    terminator = re.compile(rb'[\r\n]')
    REFZ = {'50': 0, '10k': 1}
    INPZ = {'50': 0, '1M': 1}
    SLOPE = {'none': 0, '6': 1, '12': 2, '18': 3, '24': 4}
    RESERVE = {'high': 0, 'normal': 1, 'low_noise': 2}

    def __init__(self, host, port, timeout, config):
        super().__init__(host, port, timeout)
        self.config = config
        self.panel_touched = False
        try:
            self.configure()
        except Exception as e:
            logging.error(f"SR844 init failed on {self.host}: {e}")

    def configure(self):
        """Put the instrument in a known measurement state."""
        c = self.config
        self.write('OUTX 0')    # send replies to RS-232
        # Modes that change what SNAP? returns for X/Y/R: all off.
        for cmd in ('HARM 0', 'DRAT 0', 'RMOD 0', 'DOFF 1,0,0', 'DOFF 2,0,0', 'DOFF 1,1,0'):
            self.command(cmd)
        if c.get('ref_impedance') is not None:
            self.command('FMOD 0')    # external reference
            self.command(f'REFZ {self.REFZ[str(c["ref_impedance"])]}')
        if c.get('input_impedance') is not None:
            self.command(f'INPZ {self.INPZ[str(c["input_impedance"])]}')
        if c.get('slope') is not None:
            self.command(f'OFSL {self.SLOPE[str(c["slope"])]}')
        if c.get('wide_reserve') is not None:
            self.command(f'WRSV {self.RESERVE[c["wide_reserve"]]}')
        if c.get('close_reserve') is not None:
            self.command(f'CRSV {self.RESERVE[c["close_reserve"]]}')
        if c.get('phase') is not None:
            self.command(f'PHAS {float(c["phase"]):.2f}')
        self.query('LIAS?')     # clear status latched during reconfiguration
        self.panel_touched = False

    def write(self, cmd):
        self.tn.write(bytes(cmd + '\n', 'ascii'))

    def command(self, cmd):
        """Send a set command (no reply), then check the error bits."""
        self.write(cmd)
        esr = self.query_int('*ESR?')   # reading clears it, so keep the panel bit
        self.panel_touched |= bool(esr & ESR_PANEL)
        if esr & ESR_ERROR:
            raise OSError(f'SR844 rejected {cmd!r}')

    def query(self, cmd):
        """Send a query, return the first non-empty reply line."""
        try:
            self.write(cmd)
            for _ in range(3):   # skip the empty half of a CR/LF pair
                idx, _, data = self.tn.expect([self.terminator], timeout=self.timeout)
                if idx < 0:
                    break
                if data.strip():
                    return data.decode('ascii', errors='replace').strip()
        except Exception as e:
            raise OSError(f'SR844 query {cmd!r} failed on {self.host}: {e}')
        raise OSError(f'SR844 no reply to {cmd!r} on {self.host}')

    def query_int(self, cmd):
        try:
            return int(self.query(cmd))
        except ValueError as e:
            raise OSError(f'SR844 parse failed for {cmd!r}: {e}')

    def snap(self):
        """Simultaneous X, Y, R[V], theta, ref frequency (SNAP? 1,2,3,5,8)."""
        data = self.query('SNAP? 1,2,3,5,8')
        try:
            values = [float(v) for v in data.split(',')]
        except ValueError:
            raise OSError(f'SR844 SNAP parse failed: {data!r}')
        if len(values) != 5:
            raise OSError(f'SR844 SNAP returned {len(values)} values: {data!r}')
        return values

import aioca
from ..modbus_base import ModbusDevice, ModbusConnection
from .dat8188 import DeviceConnection as DAT8188Connection
from softioc import builder, alarm


class Device(ModbusDevice):
    """SureStep advanced microstepping drive (STP-DRV-4850 / STP-DRV-80100)
    in velocity (oscillator) mode. A Datexel DAT8188 drives the digital lines;
    the speed comes from one of three sources, chosen by
    settings['speed_source']:

        'dac'    - a DAT8024 output owned by this IOC
                   (dac_ip, dac_port, dac_channel)
        'pv'     - an output PV, in volts, of an already running dat8024 IOC,
                   written over Channel Access (speed_pv, the full PV name)
        'preset' - no DAT8024: the drive runs at the fixed speed set in
                   SureMotion Pro (preset_rps, optional, for display only)

    The drive has no network interface; it must first be set up with
    SureMotion Pro (see HOW TO below). The 5 entries of settings['channels']
    have fixed roles by position; use 'None' for one that is not wired:
        0  speed   aOut, rev/s  -> drive AIN    (aIn showing preset_rps in 'preset';
                                                 drop DRVH/DRVL from its records then)
        1  run     boolOut      DAT8188 output 0 -> drive STEP (run/stop)
        2  dir     boolOut      DAT8188 output 1 -> drive DIR
        3  enable  boolOut      DAT8188 output 2 -> drive EN
        4  out     boolIn       DAT8188 input 0  <- drive OUT, fault  (out_function 'fault')
                   aIn, rev/s   DAT8188 input 0  <- drive OUT, tach   (out_function 'tach')

    The drive has one digital output, so position 4 is either a fault
    alarm or a measured speed from the tach pulses. For 'tach', the DAT8188
    measures input 0's frequency (register 40035, up to 300 Hz, 1 ms minimum
    pulse) and speed = frequency * freq_scale / tach_ppr. tach_ppr is the
    drive's tach pulses per motor revolution and must be set; freq_scale is Hz
    per register count (default 1.0, check against the DAT8188 user guide).
    The measured speed is unsigned. Keep tach_ppr * top speed (rev/s) under
    300 Hz; above that the reading is not valid.

    settings 'ip'/'port' are the DAT8188. Speed volts = speed / rps_per_volt,
    clamped to 0..max_volts; direction comes only from the dir channel. In
    'pv' mode the other IOC's DRVH/DRVL still apply to the volts written.

    Energizing EN turns the motor current OFF (manual p. 4-9). With
    enable_inverted True (default) the driver inverts the coil, so the enable
    PV reads Enabled when the DAT8188 output is off. Set it False only if the
    EN input has been reconfigured to enable when energized.

    Readbacks go into the OUT PVs with process=False, so they show what the
    modules hold without calling do_sets and writing it back. The speed
    readback is rounded to the channel's PREC (default 3).

    WIRING (SureStep manual ch. 4, "Connecting to a PLC with Sink or Source
    12-24 VDC Outputs" - the DAT8188 outputs are sourcing/PNP)
      - The DAT8188 PNP outputs source 10.5-30 V (500 mA/channel). STEP and
        DIR are 5 V max and EN is 12 V max, so at 24 V put a 2200 ohm 1/4 W
        dropping resistor in series with each (~9 mA): output -> resistor ->
        STEP+ / DIR+ / EN+, and STEP- / DIR- / EN- -> DAT8188 0 V (COM).
      - Drive OUT is an isolated transistor (5-24 V, 10 mA max): OUT+ ->
        +24 V, OUT- -> DAT8188 input 0, and the input common -> that 24 V
        supply's 0 V. DAT8188 inputs are wet contacts (ON 10-30 V, OFF 0-3 V,
        4.7 kohm, so ~5 mA at 24 V) isolated from the outputs, so they need
        that supply; a 5-12 V supply is too low for a reliable ON.
      - DAT8024 output -> AIN, its common -> drive GND. AIN is NOT optically
        isolated (manual p. 4-10): make sure the DAT8024 and drive grounds
        are compatible before connecting.
      - Recommended: enable the DAT8188 watchdog (coil 00161, timer register
        40013, safe states via 40012) from its web page, so Run drops off if
        the IOC stops talking to it.

    HOW TO: put the drive in velocity (oscillator) mode with SureMotion Pro.
    Menu names may differ slightly between software versions.
      1. Connect the STP-232RJ11-CBL from a PC to the drive's RJ11 port,
         power the drive, start SureMotion Pro and connect on that COM port.
         Upload the drive's present settings first so you start from them.
      2. Motor: pick the motor model (or enter its rated current), set the
         running current and the idle current reduction.
      3. Control mode: choose Velocity (Oscillator) mode, not Step &
         Direction or Joystick.
      4. Speed: for 'dac' or 'pv', set the speed source to the analog input,
         0-5 V. Set the full-scale speed (rev/s at 5 V) to 5 * rps_per_volt,
         offset 0, and a small deadband so 0 V is a clean stop. For 'preset',
         enter the fixed running speed instead and copy it to preset_rps.
         Set accel/decel ramps; the drive ramps, the IOC only sets the target.
      5. Inputs: STEP input = Run/Stop, run when energized (manual p. 4-9:
         "closed = run"). DIR input = Direction; check which way energized
         turns and swap the dir PV's ZNAM/ONAM under records if reversed. EN
         input = Motor Enable (not Speed Select); leave it disabling when
         energized and keep enable_inverted True.
      6. Output: for out_function 'fault', OUT = Fault, closed on fault, so
         the fault PV reads Fault when the drive faults. (If you choose open
         on fault, swap ZNAM/ONAM and ZSV/OSV for that PV under records.)
         For 'tach', OUT = Tach; copy its pulses per revolution to tach_ppr.
         If the DAT8188 needs frequency measurement turned on for input 0,
         do that from its web page or Dev9K.
      7. Download the configuration to the drive (it is kept in flash), power
         cycle it, run Self Test, then try it with the motor unloaded: Enable,
         set a low speed, Run, toggle Dir.
    """

    SPEED, RUN, DIR, ENABLE, FAULT = range(5)
    OUTPUTS = {RUN: (0, 'Stop', 'Run'),          # role: (DAT8188 output, ZNAM, ONAM)
               DIR: (1, 'CW', 'CCW'),
               ENABLE: (2, 'Disabled', 'Enabled')}
    FAULT_INPUT = 0     # DAT8188 input for the drive's OUT (fault or tach)
    SOURCES = ('dac', 'pv', 'preset')
    OUT_FUNCTIONS = ('fault', 'tach')
    MAX_FREQ = 300      # Hz, DAT8188 frequency measurement limit
    DEFAULT_PREC = 3

    def __init__(self, device_name, settings):
        self.source = settings.get('speed_source', 'dac')
        if self.source not in self.SOURCES:
            raise ValueError(f"speed_source must be one of {self.SOURCES}, not {self.source!r}")
        self.dac_ip = settings.get('dac_ip')
        self.dac_port = settings.get('dac_port', '502')
        self.dac_channel = settings.get('dac_channel', 0)       # DAT8024 output 0-3 for speed
        self.speed_pv = settings.get('speed_pv')                 # full PV name on a dat8024 IOC
        self.preset_rps = settings.get('preset_rps')             # drive's preset speed, display only
        if self.source == 'dac' and not self.dac_ip:
            raise ValueError("speed_source 'dac' needs dac_ip")
        if self.source == 'pv' and not self.speed_pv:
            raise ValueError("speed_source 'pv' needs speed_pv")
        self.rps_per_volt = settings.get('rps_per_volt', 1.0)   # rev/s per volt at the drive's AIN
        self.max_volts = settings.get('max_volts', 5.0)         # AIN upper limit
        self.enable_inverted = settings.get('enable_inverted', True)  # EN energized = motor off
        self.out_function = settings.get('out_function', 'fault')     # drive OUT: 'fault' or 'tach'
        if self.out_function not in self.OUT_FUNCTIONS:
            raise ValueError(f"out_function must be one of {self.OUT_FUNCTIONS}, not {self.out_function!r}")
        self.tach_ppr = settings.get('tach_ppr')                       # tach pulses per motor rev
        self.freq_scale = settings.get('freq_scale', 1.0)              # Hz per DAT8188 frequency count
        if self.out_function == 'tach' and not self.tach_ppr:
            raise ValueError("out_function 'tach' needs tach_ppr")
        self.dac = None
        super().__init__(device_name, settings)

    def _role(self, role):
        """PV name for a role, or None if absent or 'None'"""
        if role < len(self.channels) and "None" not in self.channels[role]:
            return self.channels[role]
        return None

    def _create_pvs(self):
        records = self.settings.get('records', {})
        speed = self._role(self.SPEED)
        if speed:
            self.prec = records.get(speed, {}).get('PREC', self.DEFAULT_PREC)
            if self.source == 'preset':
                kw = {} if self.preset_rps is None else {'initial_value': self.preset_rps}
                self.pvs[speed] = builder.aIn(speed, **kw)
            else:
                self.pvs[speed] = builder.aOut(speed, on_update_name=self.do_sets, **self.sevr)
        for role, (_, znam, onam) in self.OUTPUTS.items():
            name = self._role(role)
            if name:
                self.pvs[name] = builder.boolOut(name, ZNAM=znam, ONAM=onam, on_update_name=self.do_sets)
        out = self._role(self.FAULT)
        if out and self.out_function == 'tach':
            self.tach_prec = records.get(out, {}).get('PREC', self.DEFAULT_PREC)
            self.pvs[out] = builder.aIn(out, **self.sevr)
        elif out:
            self.pvs[out] = builder.boolIn(out, ZNAM='OK', ONAM='Fault', OSV='MAJOR',
                                           DISP=self.sevr['DISP'])

    def _controls_speed(self):
        return self.source != 'preset' and self._role(self.SPEED) is not None

    def _digital_names(self):
        return [n for n in (self._role(r) for r in (self.RUN, self.DIR, self.ENABLE, self.FAULT)) if n]

    def _create_connection(self):
        """DAT8188 is self.t; a dedicated DAT8024 is self.dac"""
        if self.source == 'dac':
            self.dac = ModbusConnection(self.dac_ip, self.dac_port, self.settings['timeout'])
        return DAT8188Connection(self.settings['ip'], self.settings['port'], self.settings['timeout'])

    def _post_connect(self):
        self.read_outs()

    def read_outs(self):
        """Read and set OUT PVs at the start of the IOC. No reconnect here:
        this runs inside connect(), so do_reads handles a dead module. In
        'pv' mode the speed readback waits for the first do_reads."""
        try:
            self._update_digital()
            if self.source == 'dac' and self._controls_speed():
                self._set_speed_readback(self._read_dac_volts())
        except OSError as e:
            print(e)
            for name in self.pvs:
                self.set_alarm(name)

    async def do_reads(self):
        """Read the DAT8188 outputs and fault input, and the speed readback"""
        ok = True
        try:
            self._update_digital()
            for name in self._digital_names():
                self.remove_alarm(name)
            self._update_out()
        except OSError as e:
            print(e)
            for name in self._digital_names():
                self.set_alarm(name)
            ok = False
        if self._controls_speed():
            speed = self._role(self.SPEED)
            try:
                await self._update_speed()
                self.remove_alarm(speed)
            except (OSError, aioca.CANothing) as e:
                print(e)
                self.set_alarm(speed)
                if self.source == 'dac':  # a dead other IOC ('pv') is no reason to reconnect Modbus
                    ok = False
        if not ok:
            self.reconnect()
        return ok

    async def do_sets(self, new_value, pv):
        """Write speed to the DAT8024 (directly or via its IOC), or a digital
        line to the DAT8188"""
        pv_name = pv.replace(self.device_name + ':', '')
        role = self.channels.index(pv_name)
        try:
            if role == self.SPEED:
                volts = self._speed_to_volts(new_value)
                if self.source == 'dac':
                    self.dac.set_register(40 + self.dac_channel, round(volts * 1000))
                else:
                    await aioca.caput(self.speed_pv, volts, timeout=2, wait=True)
                await self._update_speed()
                self.remove_alarm(pv_name)
            else:
                state = bool(new_value)
                if role == self.ENABLE and self.enable_inverted:
                    state = not state
                self.t.set_output(self.OUTPUTS[role][0], state)
                self._update_digital()
        except aioca.CANothing as e:
            print(e)
            self.set_alarm(pv_name)
        except OSError as e:
            print(e)
            self.set_alarm(pv_name)
            self.reconnect()

    def _update_digital(self):
        """Put DAT8188 output states into the OUT PVs without processing them"""
        outputs = self.t.read_outputs()
        for role, (out, _, _) in self.OUTPUTS.items():
            name = self._role(role)
            if name:
                state = outputs[out]
                if role == self.ENABLE and self.enable_inverted:
                    state = not state
                self.pvs[name].set(state, process=False)

    def _update_out(self):
        """Read the drive's OUT: fault state, or speed from tach frequency.
        A tach frequency past the DAT8188's limit is set but marked INVALID."""
        out = self._role(self.FAULT)
        if not out:
            return
        if self.out_function == 'fault':
            self.pvs[out].set(self.t.read_inputs()[self.FAULT_INPUT])
            return
        hz = self.t.read_frequency(self.FAULT_INPUT) * self.freq_scale
        self.pvs[out].set(round(hz / self.tach_ppr, self.tach_prec))
        if hz > self.MAX_FREQ:
            self.pvs[out].set_alarm(severity=3, alarm=alarm.HW_LIMIT_ALARM)

    async def _update_speed(self):
        if self.source == 'dac':
            volts = self._read_dac_volts()
        else:
            volts = await aioca.caget(self.speed_pv, timeout=2)
        self._set_speed_readback(volts)

    def _read_dac_volts(self):
        regs = self.dac.read_registers(40 + self.dac_channel, 1)
        if not regs:  # pyModbusTCP returns None on failure
            raise OSError(f"DAT8024 read failed on {self.dac.host}")
        return regs[0] / 1000

    def _set_speed_readback(self, volts):
        self.pvs[self._role(self.SPEED)].set(round(volts * self.rps_per_volt, self.prec), process=False)

    def _speed_to_volts(self, speed):
        """Convert rev/s to AIN volts, clamped to the input range"""
        return min(max(speed / self.rps_per_volt, 0.0), self.max_volts)

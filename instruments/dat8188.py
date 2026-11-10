from ..modbus_base import ModbusDevice, ModbusConnection
from softioc import builder


class Device(ModbusDevice):
    """Datexel DAT8188 8 digital input / 8 PNP output module (Modbus TCP).

    Inputs are wet contacts: ON 10-30 V, OFF 0-3 V (either polarity), 4.7
    kohm, 5 ms sample time. Outputs are PNP, sourcing 10.5-30 V at up to
    500 mA per channel and 1 A per module, with over-current protection.

    settings['channels'] holds up to 16 entries by position: the first 8 are
    outputs 0-7 (boolOut), the next 8 are inputs 0-7 (boolIn). Use 'None' for
    an unused position; positions never shift.

    Output readbacks are put into the OUT PVs with process=False, so they show
    what the module holds without calling do_sets and writing it back.
    """

    N_OUT = 8
    N_IN = 8

    def _create_pvs(self):
        """Create boolOut PVs for outputs and boolIn PVs for inputs"""
        for i, channel in enumerate(self.channels[:self.N_OUT + self.N_IN]):
            if "None" in channel:
                continue
            if i < self.N_OUT:
                self.pvs[channel] = builder.boolOut(channel, on_update_name=self.do_sets)
            else:
                self.pvs[channel] = builder.boolIn(channel, DISP=self.sevr['DISP'])

    def _create_connection(self):
        return DeviceConnection(self.settings['ip'], self.settings['port'], self.settings['timeout'])

    def _post_connect(self):
        """After connection, read initial output values"""
        self.read_outs()

    def read_outs(self):
        """Read and set OUT PVs at the start of the IOC. No reconnect here:
        this runs inside connect(), so do_reads handles a dead module."""
        try:
            self._set_outs(self.t.read_outputs())
        except OSError as e:
            print(e)
            self._alarm(self.channels[:self.N_OUT])

    def do_sets(self, new_value, pv):
        """Set one output, then read all outputs back"""
        pv_name = pv.replace(self.device_name + ':', '')
        num = self.channels.index(pv_name)
        try:
            self._set_outs(self.t.set_output(num, new_value))
            self._handle_read_success(self.channels[:self.N_OUT])
        except OSError as e:
            print(e)
            self._handle_read_error(self.channels[:self.N_OUT])

    async def do_reads(self):
        """Read inputs and output readbacks"""
        try:
            self._set_outs(self.t.read_outputs())
            inputs = self.t.read_inputs()
            for i, channel in enumerate(self.channels[self.N_OUT:self.N_OUT + self.N_IN]):
                if "None" not in channel:
                    self.pvs[channel].set(inputs[i])
            self._handle_read_success()
            return True
        except OSError as e:
            print(e)
            self._handle_read_error()
            return False

    def _set_outs(self, values):
        """Put output states into OUT PVs without processing them"""
        for i, channel in enumerate(self.channels[:self.N_OUT]):
            if "None" not in channel:
                self.pvs[channel].set(values[i], process=False)

    def _alarm(self, channels):
        for channel in self._skip_none_channels(channels):
            self.set_alarm(channel)


class DeviceConnection(ModbusConnection):
    """Coil access for the DAT8188. The user guide numbers coils from 1
    (Output #0 = 00489, Input #0 = 00505); protocol addresses are one less.

    pyModbusTCP returns None/False on failure rather than raising, so each
    call checks the result and raises OSError.
    """

    OUT_ADDR = 488  # Output #0..#7
    IN_ADDR = 504   # Input #0..#7
    FREQ_ADDR = 34  # register 40035: Freq. Digital Input 0..3

    def read_frequency(self, num):
        """Raw frequency register for input {num} (0-3); units per the user
        guide (not stated in the register table). Up to 300 Hz, 1 ms min pulse."""
        try:
            values = self.m.read_input_registers(self.FREQ_ADDR + num, 1)
        except Exception as e:
            values = None
            print(f"DAT8188 read failed on {self.host}: {e}")
        if not values:
            raise OSError(f'DAT8188 read failed on {self.host}')
        return values[0]

    def read_outputs(self):
        """Read the 8 output states"""
        return self._read_coils(self.OUT_ADDR, 8)

    def read_inputs(self):
        """Read the 8 input states"""
        return self._read_coils(self.IN_ADDR, 8)

    def set_output(self, num, state):
        """Set output {num} (0-7) to state, then return all output states"""
        try:
            ok = self.m.write_single_coil(self.OUT_ADDR + num, bool(state))
        except Exception as e:
            ok = False
            print(f"DAT8188 write failed on {self.host}: {e}")
        if not ok:
            raise OSError(f'DAT8188 write failed on {self.host}')
        return self.read_outputs()

    def _read_coils(self, addr, number):
        try:
            values = self.m.read_coils(addr, number)
        except Exception as e:
            values = None
            print(f"DAT8188 read failed on {self.host}: {e}")
        if values is None or len(values) < number:
            raise OSError(f'DAT8188 read failed on {self.host}')
        return values

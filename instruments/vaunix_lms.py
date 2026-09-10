import logging
from softioc import builder
from ..telnet_base import TelnetDevice, TelnetConnection


class DeviceRefused(Exception):
    """The shim reached the Lab Brick and the Lab Brick declined.

    Kept apart from OSError on purpose. An out-of-range setpoint or an
    unsupported command says nothing about the health of the socket, so it must
    not drag the driver through a reconnect the way a transport failure does.
    """


class Device(TelnetDevice):
    """Vaunix Lab Brick LMS/BLX signal generator, reached through the TCP shim.

    The Lab Brick is a USB instrument with no network interface of its own, so
    it sits on a small Linux host running tools/vaunix_shim/vaunix_shim.py,
    which owns the USB connection and exposes a line protocol on a socket. That
    shim also handles the API's 10 Hz and 0.25 dB encodings, so everything here
    is in plain GHz and dBm.

    Settings:
        ip, port, timeout: where the shim is listening
        channels: single entry used as the PV name prefix, e.g. ['MW']
        multiplier: multiplier-chain factor for the output frequency PV
                    (1 if the synthesiser output is used directly)
    """

    def _create_pvs(self):
        self.multiplier = self.settings.get('multiplier', 1)

        for channel in self._skip_none_channels():
            # Frequency of the synthesiser itself, in GHz.
            self.pvs[channel + "_FI"] = builder.aIn(channel + "_FI", **self.sevr)
            self.pvs[channel + "_FC"] = builder.aOut(
                channel + "_FC", on_update_name=self.do_sets, **self.sevr)

            # Frequency at the far end of the multiplier chain. Derived, not
            # measured, so it is read-only.
            self.pvs[channel + "_OutFI"] = builder.aIn(channel + "_OutFI", **self.sevr)

            # Power in dBm. Named _PWRI/_PWRC rather than _PI/_PC because _PI
            # already reads as "pressure indicator" everywhere else here.
            self.pvs[channel + "_PWRI"] = builder.aIn(channel + "_PWRI", **self.sevr)
            self.pvs[channel + "_PWRC"] = builder.aOut(
                channel + "_PWRC", on_update_name=self.do_sets, **self.sevr)

            self.pvs[channel + "_RF"] = builder.boolOut(
                channel + "_RF", on_update_name=self.do_sets)
            self.pvs[channel + "_Ref"] = builder.boolOut(
                channel + "_Ref", on_update_name=self.do_sets)
            self.pvs[channel + "_Lock"] = builder.boolIn(channel + "_Lock")

    def _create_connection(self):
        return DeviceConnection(
            self.settings['ip'],
            self.settings['port'],
            self.settings['timeout']
        )

    def read_outs(self):
        """Seed the control PVs from the hardware at IOC start.

        Without this the setpoints would come up at zero and the first operator
        touch of any one of them would yank the others to zero with it.
        """
        channel = self._skip_none_channels()[0]
        try:
            freq, power, rf, ref, lock = self.t.read_all()
            self.pvs[channel + '_FC'].set(freq)
            self.pvs[channel + '_PWRC'].set(power)
            self.pvs[channel + '_RF'].set(rf)
            self.pvs[channel + '_Ref'].set(ref)
        except DeviceRefused as e:
            logging.error("Vaunix LMS refused the startup read: %s", e)
        except OSError:
            logging.error("Vaunix LMS read out error on %s", self.settings['ip'])
            self.reconnect()

    def do_sets(self, new_value, pv):
        """Push a control PV to the device and set the readback from its reply."""
        pv_name = pv.replace(self.device_name + ':', '')
        channel = pv_name.split("_")[0]
        try:
            if pv_name.endswith('_FC'):
                value = self.t.set_frequency(new_value)
                self.pvs[channel + '_FI'].set(value)
                self.pvs[channel + '_OutFI'].set(value * self.multiplier)
            elif pv_name.endswith('_PWRC'):
                self.pvs[channel + '_PWRI'].set(self.t.set_power(new_value))
            elif pv_name.endswith('_RF'):
                self.pvs[channel + '_RF'].set(self.t.set_rf(new_value))
            elif pv_name.endswith('_Ref'):
                self.pvs[channel + '_Ref'].set(self.t.set_ref(new_value))
            else:
                logging.error("Vaunix LMS control PV not categorized: %s", pv_name)
        except DeviceRefused as e:
            # The device said no. Put the setpoint back to what the hardware is
            # actually doing, so the screen never shows a value that was never
            # accepted, and leave the connection alone.
            logging.warning("Vaunix LMS rejected %s = %s: %s", pv_name, new_value, e)
            self.read_outs()
        except OSError:
            self.reconnect()
        return

    async def do_reads(self):
        """Poll every reading in one round trip."""
        channel = self._skip_none_channels()[0]
        try:
            freq, power, rf, ref, lock = self.t.read_all()
            self.pvs[channel + '_FI'].set(freq)
            self.pvs[channel + '_OutFI'].set(freq * self.multiplier)
            self.pvs[channel + '_PWRI'].set(power)
            self.pvs[channel + '_RF'].set(rf)
            self.pvs[channel + '_Ref'].set(ref)
            self.pvs[channel + '_Lock'].set(lock)

            self._handle_read_success()
            return True
        except DeviceRefused as e:
            # Hardware is reachable but unhappy. Flag it, but reconnecting
            # would not fix anything, so hold the connection.
            logging.warning("Vaunix LMS refused a read: %s", e)
            for ch in self._skip_none_channels():
                self.set_alarm(ch)
            return False
        except OSError:
            self._handle_read_error()
            return False

    def set_alarm(self, channel):
        """Alarm the readbacks rather than the bare channel name.

        The base class alarms self.pvs[channel], but this device names every PV
        with a suffix, so there is no PV under the bare channel name to alarm.
        """
        for suffix in ('_FI', '_OutFI', '_PWRI'):
            if channel + suffix in self.pvs:
                super().set_alarm(channel + suffix)

    def remove_alarm(self, channel):
        for suffix in ('_FI', '_OutFI', '_PWRI'):
            if channel + suffix in self.pvs:
                super().remove_alarm(channel + suffix)


class DeviceConnection(TelnetConnection):
    """Talk to the Lab Brick TCP shim.

    Every command gets exactly one response line back, so the socket cannot get
    out of step with the conversation. A reply starting with ERR means the shim
    reached the hardware and the hardware refused; that is raised as OSError so
    the driver takes its usual reconnect path.
    """

    def _command(self, command):
        try:
            self.tn.write(bytes(command + '\n', 'ascii'))
            data = self.tn.read_until(b'\n', timeout=self.timeout).decode('ascii')
        except Exception as e:
            logging.error("Vaunix shim command %r failed on %s: %s", command, self.host, e)
            raise OSError('Vaunix LMS command')

        reply = data.strip()
        if not reply:
            logging.error("Vaunix shim timed out on %s for %r", self.host, command)
            raise OSError('Vaunix LMS timeout')
        if reply.startswith('ERR'):
            logging.warning("Vaunix shim refused %r on %s: %s", command, self.host, reply)
            raise DeviceRefused(reply[3:].strip())
        return reply

    def read_all(self):
        """Return (freq_GHz, power_dBm, rf_on, internal_ref, pll_locked)."""
        reply = self._command('READ?')
        try:
            freq_hz, power, rf, ref, lock = reply.split()
            return (float(freq_hz) / 1e9, float(power),
                    int(rf), int(ref), int(lock))
        except ValueError:
            logging.error("Vaunix shim gave an unreadable READ? reply on %s: %r",
                          self.host, reply)
            raise OSError('Vaunix LMS read')

    def _set_value(self, command, kind):
        """Send a set command and return the value the shim echoes back."""
        reply = self._command(command)
        try:
            return float(reply.split()[1])
        except (IndexError, ValueError):
            logging.error("Vaunix shim gave an unreadable %s reply on %s: %r",
                          kind, self.host, reply)
            raise OSError('Vaunix LMS set')

    def set_frequency(self, ghz):
        """Set frequency, given in GHz; returns the achieved value in GHz."""
        return self._set_value(f"FREQ {ghz * 1e9:.0f}", 'FREQ') / 1e9

    def set_power(self, dbm):
        return self._set_value(f"POW {dbm:.2f}", 'POW')

    def set_rf(self, on):
        return int(self._set_value(f"RF {1 if on else 0}", 'RF'))

    def set_ref(self, internal):
        return int(self._set_value(f"REF {1 if internal else 0}", 'REF'))

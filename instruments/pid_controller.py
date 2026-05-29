import asyncio
import logging
from softioc import builder
from simple_pid import PID
from ..base_device import BaseDevice
import aioca


class Device(BaseDevice):
    """PID Controller Device

    Implements a software PID controller that reads from a process variable,
    computes the control output, and writes to an output variable.
    """

    def __init__(self, device_name, settings):
        # Store PID parameters before calling parent init
        outs = settings['outs']  # Fixed: was 'setting['out']'
        self.pid_params = {
            'kp': outs.get('kp', 1.0),
            'ki': outs.get('ki', 0.0),
            'kd': outs.get('kd', 0.0),
            'setpoint': outs.get('setpoint', 0.0),
            'output_limits': (outs.get('min_output', 0), outs.get('max_output', 100))  # Fixed: should get from outs
        }
        self.auto_mode = outs.get('auto_start', False)

        self.input_pv = settings.get('input_pv')
        self.output_pv = settings.get('output_pv')

        super().__init__(device_name, settings)

    def _create_pvs(self):
        """Create PID-specific PVs"""
        for channel in self._skip_none_channels():
            self.pvs[channel + "_SP"] = builder.aOut(
                channel + "_SP",
                initial_value=self.pid_params['setpoint'],
                on_update_name=self.do_sets,
                **self.sevr
            )
            self.pvs[channel + "_KP"] = builder.aOut(
                channel + "_KP",
                initial_value=self.pid_params['kp'],
                on_update_name=self.do_sets
            )
            self.pvs[channel + "_KI"] = builder.aOut(
                channel + "_KI",
                initial_value=self.pid_params['ki'],
                on_update_name=self.do_sets
            )
            self.pvs[channel + "_KD"] = builder.aOut(
                channel + "_KD",
                initial_value=self.pid_params['kd'],
                on_update_name=self.do_sets
            )
            # Process value (input) - read only
            self.pvs[channel + "_PV"] = builder.aIn(channel + "_PV", **self.sevr)
            # Control value (output) - read only for monitoring
            self.pvs[channel + "_CV"] = builder.aIn(channel + "_CV", **self.sevr)
            # Manual output value
            self.pvs[channel + "_MV"] = builder.aOut(
                channel + "_MV",
                initial_value=0.0,
                on_update_name=self.do_sets,
                **self.sevr
            )
            # Control mode: Auto/Manual
            self.pvs[channel + "_Mode"] = builder.mbbOut(
                channel + "_Mode",
                ("Manual", 'MINOR'),
                ("Auto", 0),
                initial_value=1 if self.auto_mode else 0,
                on_update_name=self.do_sets
            )
            # Output limits - Fixed: check for None instead of truthy/falsy
            max_limit = self.pid_params['output_limits'][1]
            min_limit = self.pid_params['output_limits'][0]
            self.pvs[channel + "_DRVH"] = builder.aOut(
                channel + "_DRVH",
                initial_value=max_limit if max_limit is not None else 100.0,
                on_update_name=self.do_sets
            )
            self.pvs[channel + "_DRVL"] = builder.aOut(
                channel + "_DRVL",
                initial_value=min_limit if min_limit is not None else -100.0,
                on_update_name=self.do_sets
            )

    def _create_connection(self):
        """Create PID connection (no physical connection needed)"""
        return PIDConnection(self.pid_params)

    def connect(self):
        """Initialize PID controller"""
        super().connect()
        # Update PID with current PV values
        self._update_pid_params()

    def _update_pid_params(self):
        """Update PID controller parameters"""
        if self.t and self.channels[0] != "None":
            channel = self.channels[0]
            self.t.update_params(
                kp=self.pvs[channel + "_KP"].get(),
                ki=self.pvs[channel + "_KI"].get(),
                kd=self.pvs[channel + "_KD"].get(),
                setpoint=self.pvs[channel + "_SP"].get(),
                output_limits=(
                    self.pvs[channel + "_DRVL"].get(),
                    self.pvs[channel + "_DRVH"].get()
                )
            )

    def do_sets(self, new_value, pv):
        """Handle PV set operations"""
        pv_name = pv.replace(self.device_name + ':', '')
        channel = pv_name.split("_")[0]

        # Update PID parameters when any control PV changes
        if any(suffix in pv_name for suffix in ["_KP", "_KI", "_KD", "_SP", "_DRVH", "_DRVL"]):
            self._update_pid_params()
        # Handle mode changes
        if "_Mode" in pv_name:
            mode = self.pvs[channel + "_Mode"].get()
            if mode == 0:  # Manual mode
                # Reset PID controller when switching to manual
                self.t.reset()

    async def do_reads(self):
        """Read input PV, compute PID output, and write to output PV"""
        try:
            for channel in self._skip_none_channels():
                # Read input PV from external source
                try:
                    input_value = await aioca.caget(self.input_pv, timeout=2)
                    self.pvs[channel + "_PV"].set(input_value)

                    mode = self.pvs[channel + "_Mode"].get()
                    if mode == 1:  # Auto mode
                        # Compute PID output
                        output = self.t.compute(input_value)
                        self.pvs[channel + "_CV"].set(output)
                        # Write to output PV if configured
                        if self.output_pv:
                            await aioca.caput(self.output_pv, output, timeout=2)
                    else:  # Manual mode
                        # Use manual value
                        manual_output = self.pvs[channel + "_MV"].get()
                        self.pvs[channel + "_CV"].set(manual_output)
                        # Write manual value to output PV if configured
                        if self.output_pv:
                            await aioca.caput(self.output_pv, manual_output, timeout=2)

                    self.remove_alarm(channel + "_PV")  # Fixed: clear alarms on success

                except aioca.CANothing as e:
                    logging.error(f"PID CA error: {e}")
                    self.set_alarm(channel + "_PV")  # Fixed: set alarm on CA error
                    return False

            self._handle_read_success()
            return True

        except Exception as e:
            logging.error(f"PID control error: {e}")
            self._handle_read_error()
            return False


class PIDConnection:
    """PID controller connection handler"""

    def __init__(self, params):
        self.pid = PID(
            params['kp'],
            params['ki'],
            params['kd'],
            setpoint=params['setpoint'],
            output_limits=params['output_limits']
        )

    def compute(self, input_value):
        """Compute PID output"""
        return self.pid(input_value)

    def update_params(self, **kwargs):
        """Update PID parameters"""
        if 'kp' in kwargs:
            self.pid.Kp = kwargs['kp']
        if 'ki' in kwargs:
            self.pid.Ki = kwargs['ki']
        if 'kd' in kwargs:
            self.pid.Kd = kwargs['kd']
        if 'setpoint' in kwargs:
            self.pid.setpoint = kwargs['setpoint']
        if 'output_limits' in kwargs:
            self.pid.output_limits = kwargs['output_limits']

    def reset(self):
        """Reset PID controller"""
        self.pid.reset()

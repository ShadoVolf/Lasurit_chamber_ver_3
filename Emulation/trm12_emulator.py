"""
TRM12 temperature controller emulator.
"""

import time
import random
from typing import Dict, Any, Optional, Tuple
from Emulation.base_emulator import BaseEmulator


class TRM12Emulator(BaseEmulator):
    """
    Emulator for Owen TRM12 temperature controller.
    Simulates temperature control, PID regulation, and sensor readings.
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize TRM12 emulator.
        
        :param config: Configuration dictionary
        """
        default_config = {
            'initial_temperature': 25.0,
            'heating_rate': 2.0,
            'cooling_rate': 1.0,
            'temperature_noise': 0.1,
            'simulation_interval': 0.5,
            'max_temperature': 300.0,
            'min_temperature': 0.0
        }
        if config:
            default_config.update(config)
        
        super().__init__(default_config)
        
        # Internal state
        self._temperature = self.config['initial_temperature']
        self._target_temperature = self._temperature
        self._output_power = 0.0
        self._pid_parameters = {
            0: {'P': 5.0, 'I': 10, 'D': 50, 'deadband': 0.0},
            1: {'P': 5.0, 'I': 10, 'D': 50, 'deadband': 0.0}
        }
        self._control_mode = 1  # RUN mode
        self._alarm_state = 0
        self._fan_speed = 0
        self._last_setpoint = {0: 25.0, 1: 25.0}
        
        # Correction parameters
        self._correction_points = [0.0, 100.0, 200.0]
        self._correction_offsets = [0.0, 0.0, 0.0]

    def _update(self):
        """Update temperature simulation."""
        with self._lock:
            # Simulate temperature change based on output power
            if self._output_power > 0:
                # Heating
                rate = self.config['heating_rate'] * (self._output_power / 100.0)
                self._temperature += rate * self.simulation_interval
            else:
                # Cooling
                rate = self.config['cooling_rate']
                self._temperature -= rate * self.simulation_interval * 0.5
            
            # Clamp temperature
            self._temperature = max(self.config['min_temperature'], 
                                   min(self.config['max_temperature'], self._temperature))
            
            # Add noise
            noise = random.uniform(-self.config['temperature_noise'], 
                                  self.config['temperature_noise'])
            self._temperature += noise
            
            # Simple PID simulation
            error = self._target_temperature - self._temperature
            pid_params = self._pid_parameters[0]
            
            # Simple P control
            self._output_power = min(100.0, max(0.0, 
                abs(error) * pid_params['P']))
            
            # If close to target, reduce power
            if abs(error) < pid_params.get('deadband', 0.5):
                self._output_power = 0.0
            
            self._last_update = time.time()

    def get_temperature(self, channel: int = 0) -> float:
        """Get current temperature for channel."""
        with self._lock:
            return self._temperature

    def set_temperature(self, temperature: float, channel: int = 0) -> bool:
        """Set target temperature for channel."""
        with self._lock:
            self._target_temperature = temperature
            self._last_setpoint[channel] = temperature
            return True

    def get_setpoint(self, channel: int = 0) -> float:
        """Get current setpoint for channel."""
        with self._lock:
            return self._last_setpoint.get(channel, self._target_temperature)

    def get_pid_parameters(self, channel: int = 0) -> Dict[str, Any]:
        """Get PID parameters for channel."""
        with self._lock:
            return self._pid_parameters.get(channel, {'P': 5.0, 'I': 10, 'D': 50})

    def set_pid_parameters(self, P: float, I: float, D: float, 
                           channel: int = 0, deadband: float = 0.0) -> Tuple[bool, str]:
        """Set PID parameters for channel."""
        with self._lock:
            self._pid_parameters[channel] = {
                'P': P,
                'I': I,
                'D': D,
                'deadband': deadband
            }
            return True, "OK"

    def get_output_power(self, channel: int = 0) -> float:
        """Get current output power percentage."""
        with self._lock:
            return self._output_power

    def set_control_mode(self, mode: int, channel: int = 0) -> bool:
        """Set control mode (0=STOP, 1=RUN, 2=MANUAL)."""
        with self._lock:
            self._control_mode = mode
            return True

    def get_control_mode(self, channel: int = 0) -> int:
        """Get current control mode."""
        with self._lock:
            return self._control_mode

    def get_fan_speed(self, channel: int = 0) -> int:
        """Get current fan speed."""
        with self._lock:
            return self._fan_speed

    def set_fan_speed(self, speed: int, channel: int = 0) -> bool:
        """Set fan speed."""
        with self._lock:
            self._fan_speed = max(0, min(100, speed))
            return True

    def reset(self) -> bool:
        """Reset the device."""
        with self._lock:
            self._temperature = self.config['initial_temperature']
            self._target_temperature = self._temperature
            self._output_power = 0.0
            self._control_mode = 1
            return True

    def get_device_info(self) -> Dict[str, Any]:
        """Get device information."""
        return {
            'device_type': 'TRM12',
            'firmware': '1.0.0',
            'serial': 'EMU001'
        }

    def get_statistics(self) -> Dict[str, Any]:
        """Get device statistics."""
        with self._lock:
            return {
                'temperature': self._temperature,
                'target': self._target_temperature,
                'output_power': self._output_power,
                'control_mode': self._control_mode,
                'fan_speed': self._fan_speed
            }

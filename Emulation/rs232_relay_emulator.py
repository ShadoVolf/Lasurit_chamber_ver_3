"""
RS232 4-pin Relay emulator.
"""

import time
from typing import Dict, Any, Optional, List
from Emulation.base_emulator import BaseEmulator


class RS232RelayEmulator(BaseEmulator):
    """
    Emulator for RS232-4pin-Relay device.
    Simulates relay control for shaft heating.
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize RS232 Relay emulator.
        
        :param config: Configuration dictionary
        """
        default_config = {
            'initial_state': False,
            'response_delay': 0.1,
            'simulation_interval': 0.5,
            'num_relays': 4
        }
        if config:
            default_config.update(config)
        
        super().__init__(default_config)
        
        # Internal state
        self._relay_states = [self.config['initial_state']] * self.config['num_relays']
        self._last_command = None
        self._last_command_time = 0.0
        self._error_state = False
        
        # Shaft temperature simulation
        self._shaft_temperatures = [25.0] * 4  # Temperature for each shaft
        self._shaft_heating = [False] * 4
        self._heating_rate = 1.0  # Degrees per second when heating
        self._cooling_rate = 0.5  # Degrees per second when cooling

    def _update(self):
        """Update relay simulation."""
        with self._lock:
            # Simulate shaft temperature changes
            for i in range(len(self._shaft_temperatures)):
                if self._shaft_heating[i]:
                    self._shaft_temperatures[i] += self._heating_rate * self.simulation_interval
                else:
                    self._shaft_temperatures[i] -= self._cooling_rate * self.simulation_interval
                
                # Clamp temperature
                self._shaft_temperatures[i] = max(0.0, min(200.0, self._shaft_temperatures[i]))
            
            self._last_update = time.time()

    def set_relay_state(self, relay_index: int, state: bool) -> bool:
        """Set relay state."""
        with self._lock:
            if 0 <= relay_index < len(self._relay_states):
                self._relay_states[relay_index] = state
                self._shaft_heating[relay_index] = state
                self._last_command = ('set_relay', relay_index, state)
                self._last_command_time = time.time()
                return True
            return False

    def get_relay_state(self, relay_index: int) -> bool:
        """Get relay state."""
        with self._lock:
            if 0 <= relay_index < len(self._relay_states):
                return self._relay_states[relay_index]
            return False

    def get_all_relay_states(self) -> List[bool]:
        """Get all relay states."""
        with self._lock:
            return self._relay_states.copy()

    def set_all_relays(self, state: bool) -> bool:
        """Set all relays to the same state."""
        with self._lock:
            for i in range(len(self._relay_states)):
                self._relay_states[i] = state
                self._shaft_heating[i] = state
            self._last_command = ('set_all', state)
            self._last_command_time = time.time()
            return True

    def toggle_relay(self, relay_index: int) -> bool:
        """Toggle relay state."""
        with self._lock:
            if 0 <= relay_index < len(self._relay_states):
                self._relay_states[relay_index] = not self._relay_states[relay_index]
                self._shaft_heating[relay_index] = self._relay_states[relay_index]
                self._last_command = ('toggle', relay_index)
                self._last_command_time = time.time()
                return True
            return False

    def get_shaft_temperature(self, shaft_index: int) -> float:
        """Get shaft temperature."""
        with self._lock:
            if 0 <= shaft_index < len(self._shaft_temperatures):
                return self._shaft_temperatures[shaft_index]
            return 0.0

    def get_all_shaft_temperatures(self) -> List[float]:
        """Get all shaft temperatures."""
        with self._lock:
            return self._shaft_temperatures.copy()

    def set_heating_parameters(self, heating_rate: float = None, 
                               cooling_rate: float = None) -> bool:
        """Set heating and cooling rates."""
        with self._lock:
            if heating_rate is not None:
                self._heating_rate = heating_rate
            if cooling_rate is not None:
                self._cooling_rate = cooling_rate
            return True

    def reset(self) -> bool:
        """Reset all relays."""
        with self._lock:
            for i in range(len(self._relay_states)):
                self._relay_states[i] = self.config['initial_state']
                self._shaft_heating[i] = False
                self._shaft_temperatures[i] = 25.0
            self._error_state = False
            self._last_command = None
            self._last_command_time = 0.0
            return True

    def get_last_command(self) -> Optional[tuple]:
        """Get last command."""
        with self._lock:
            return self._last_command

    def get_last_command_time(self) -> float:
        """Get last command time."""
        with self._lock:
            return self._last_command_time

    def get_statistics(self) -> Dict[str, Any]:
        """Get device statistics."""
        with self._lock:
            return {
                'relay_states': self._relay_states.copy(),
                'shaft_temperatures': self._shaft_temperatures.copy(),
                'last_command': self._last_command,
                'last_command_time': self._last_command_time,
                'error_state': self._error_state
            }

    def get_device_info(self) -> Dict[str, Any]:
        """Get device information."""
        return {
            'device_type': 'RS232-4pin-Relay',
            'firmware': '1.0.0',
            'serial': 'EMU001',
            'num_relays': self.config['num_relays']
        }

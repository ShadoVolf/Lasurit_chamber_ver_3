"""
BLSD20 motor driver emulator.
"""

import time
import random
from typing import Dict, Any, Optional, Tuple
from Emulation.base_emulator import BaseEmulator


class BLSD20Emulator(BaseEmulator):
    """
    Emulator for BLSD-20Modbus motor driver.
    Simulates motor control, speed regulation, and position tracking.
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize BLSD20 emulator.
        
        :param config: Configuration dictionary
        """
        default_config = {
            'initial_speed': 0,
            'max_speed': 3000,
            'acceleration': 100,
            'deceleration': 100,
            'initial_position': 0,
            'simulation_interval': 0.5,
            'max_current': 10000,
            'ref_current': 1000
        }
        if config:
            default_config.update(config)
        
        super().__init__(default_config)
        
        # Internal state
        self._current_speed = self.config['initial_speed']
        self._target_speed = self._current_speed
        self._position = self.config['initial_position']
        self._current = 0
        self._target_current = self.config.get('ref_current', 1000)
        self._motor_status = 0  # 0=STOP, 1=RUN, 2=FAULT
        self._direction = 1  # 1=forward, 0=reverse
        self._mode_device = 1  # 1=velocity mode
        self._mode_rotation = 1  # 1=normal
        self._error_code = 0
        self._is_running = False
        self._task_counter = 0
        
        # Temperature sensors
        self._temperatures = {
            'mcu': 25.0,
            'mosfet': 25.0,
            'brake': 25.0
        }
        
        # Statistics
        self._total_runtime = 0.0
        self._commands_processed = 0
        self._errors_generated = 0
        self._temperature_warnings = 0

    def _update(self):
        """Update motor simulation."""
        with self._lock:
            # Update runtime
            if self._is_running:
                self._total_runtime += self.simulation_interval
            
            # Simulate speed change
            if self._current_speed < self._target_speed:
                acceleration = self.config['acceleration']
                self._current_speed = min(self._target_speed, 
                                          self._current_speed + acceleration * self.simulation_interval)
            elif self._current_speed > self._target_speed:
                deceleration = self.config['deceleration']
                self._current_speed = max(self._target_speed, 
                                          self._current_speed - deceleration * self.simulation_interval)
            
            # Update position
            direction_factor = 1 if self._direction == 1 else -1
            self._position += self._current_speed * direction_factor * self.simulation_interval / 60.0
            
            # Simulate current
            if self._is_running:
                self._current = min(self.config['max_current'], 
                                   self._current + 100 * self.simulation_interval)
            else:
                self._current = max(0, self._current - 200 * self.simulation_interval)
            
            # Simulate temperature
            for temp_key in self._temperatures:
                # Temperature rises with current and speed
                temp_increase = (self._current / self.config['max_current']) * 0.5
                self._temperatures[temp_key] += temp_increase * self.simulation_interval
                # Natural cooling
                self._temperatures[temp_key] -= 0.1 * self.simulation_interval
                # Clamp to reasonable range
                self._temperatures[temp_key] = max(20.0, min(100.0, self._temperatures[temp_key]))
            
            # Add small noise
            for temp_key in self._temperatures:
                self._temperatures[temp_key] += random.uniform(-0.1, 0.1)
            
            self._last_update = time.time()

    def set_speed(self, speed: float) -> bool:
        """Set target speed."""
        with self._lock:
            self._target_speed = max(0, min(self.config['max_speed'], speed))
            self._commands_processed += 1
            return True

    def get_speed(self) -> float:
        """Get current speed."""
        with self._lock:
            return self._current_speed

    def get_target_speed(self) -> float:
        """Get target speed."""
        with self._lock:
            return self._target_speed

    def get_position(self) -> float:
        """Get current position."""
        with self._lock:
            return self._position

    def set_position(self, position: float) -> bool:
        """Set position (reset)."""
        with self._lock:
            self._position = position
            return True

    def get_current(self) -> float:
        """Get current motor current."""
        with self._lock:
            return self._current

    def set_current(self, current: float) -> bool:
        """Set target current."""
        with self._lock:
            self._target_current = current
            return True

    def get_target_current(self) -> float:
        """Get target current."""
        with self._lock:
            return self._target_current

    def start_motor(self) -> bool:
        """Start the motor."""
        with self._lock:
            if self._motor_status == 0:  # Only if stopped
                self._motor_status = 1
                self._is_running = True
                return True
            return False

    def stop_motor(self) -> bool:
        """Stop the motor."""
        with self._lock:
            self._motor_status = 0
            self._is_running = False
            self._target_speed = 0
            return True

    def emergency_stop(self) -> bool:
        """Emergency stop."""
        with self._lock:
            self._motor_status = 2  # FAULT
            self._is_running = False
            self._target_speed = 0
            self._error_code = 0x0001  # Emergency stop error
            self._errors_generated += 1
            return True

    def reset_errors(self) -> bool:
        """Reset error state."""
        with self._lock:
            self._error_code = 0
            self._motor_status = 0
            return True

    def get_motor_status(self) -> Dict[str, Any]:
        """Get motor status."""
        with self._lock:
            status_map = {
                0: 'STOP',
                1: 'RUN',
                2: 'FAULT'
            }
            return {
                'status': self._motor_status,
                'text': status_map.get(self._motor_status, 'UNKNOWN'),
                'is_running': self._is_running
            }

    def get_temperatures(self) -> Dict[str, float]:
        """Get temperature readings."""
        with self._lock:
            return self._temperatures.copy()

    def get_error_code(self) -> int:
        """Get error code."""
        with self._lock:
            return self._error_code

    def set_direction(self, direction: int) -> bool:
        """Set direction (0=reverse, 1=forward)."""
        with self._lock:
            self._direction = 1 if direction >= 1 else 0
            return True

    def get_direction(self) -> Dict[str, Any]:
        """Get direction."""
        with self._lock:
            return {
                'value': self._direction,
                'text': 'FORWARD' if self._direction == 1 else 'REVERSE'
            }

    def set_mode_device(self, mode: int) -> bool:
        """Set device mode."""
        with self._lock:
            self._mode_device = mode
            return True

    def get_mode_device(self) -> Dict[str, Any]:
        """Get device mode."""
        with self._lock:
            mode_map = {
                0: 'STOP',
                1: 'VELOCITY',
                2: 'POSITION',
                3: 'TORQUE'
            }
            return {
                'value': self._mode_device,
                'text': mode_map.get(self._mode_device, 'UNKNOWN')
            }

    def set_mode_rotation(self, mode: int) -> bool:
        """Set rotation mode."""
        with self._lock:
            self._mode_rotation = mode
            return True

    def get_mode_rotation(self) -> Dict[str, Any]:
        """Get rotation mode."""
        with self._lock:
            mode_map = {
                0: 'STOP',
                1: 'NORMAL',
                2: 'REVERSE'
            }
            return {
                'value': self._mode_rotation,
                'text': mode_map.get(self._mode_rotation, 'UNKNOWN')
            }

    def get_task_counter(self) -> int:
        """Get task counter."""
        with self._lock:
            return self._task_counter

    def increment_task_counter(self):
        """Increment task counter."""
        with self._lock:
            self._task_counter += 1

    def get_statistics(self) -> Dict[str, Any]:
        """Get device statistics."""
        with self._lock:
            return {
                'current_speed': self._current_speed,
                'target_speed': self._target_speed,
                'position': self._position,
                'current': self._current,
                'target_current': self._target_current,
                'motor_status': self._motor_status,
                'direction': self._direction,
                'mode_device': self._mode_device,
                'mode_rotation': self._mode_rotation,
                'error_code': self._error_code,
                'is_running': self._is_running,
                'task_counter': self._task_counter,
                'total_runtime': self._total_runtime,
                'commands_processed': self._commands_processed,
                'errors_generated': self._errors_generated,
                'temperatures': self._temperatures
            }

    def reset(self) -> bool:
        """Reset the device."""
        with self._lock:
            self._current_speed = self.config['initial_speed']
            self._target_speed = self._current_speed
            self._position = self.config['initial_position']
            self._current = 0
            self._motor_status = 0
            self._error_code = 0
            self._is_running = False
            self._task_counter = 0
            self._total_runtime = 0.0
            self._commands_processed = 0
            self._errors_generated = 0
            self._temperature_warnings = 0
            return True

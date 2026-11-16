"""
Adapter classes to make emulators compatible with existing driver interfaces.
"""

from typing import Dict, Any, Optional, Tuple, List
from Emulation.trm12_emulator import TRM12Emulator
from Emulation.blsd20_emulator import BLSD20Emulator
from Emulation.rs232_relay_emulator import RS232RelayEmulator


class EmulatedTRM12Driver:
    """
    Adapter that makes TRM12Emulator compatible with TRM12Driver interface.
    """

    def __init__(self, emulator: TRM12Emulator):
        self.emulator = emulator
        self._connected = True

    def is_connected(self) -> bool:
        return self._connected

    def connect(self) -> bool:
        self._connected = True
        return True

    def disconnect(self) -> None:
        self._connected = False

    def get_temperature(self, channel: int = 0) -> Optional[float]:
        return self.emulator.get_temperature(channel)

    def set_temperature(self, temperature: float, channel: int = 0) -> bool:
        return self.emulator.set_temperature(temperature, channel)

    def get_pid_parameters(self, channel: int = 0) -> Dict[str, Any]:
        return self.emulator.get_pid_parameters(channel)

    def set_pid_parameters(self, P: float, I: float, D: float, 
                           channel: int = 0, deadband: float = 0.0) -> Tuple[bool, str]:
        return self.emulator.set_pid_parameters(P, I, D, channel, deadband)

    def get_fan_speed(self, channel: int = 0) -> int:
        return self.emulator.get_fan_speed(channel)

    def set_fan_speed(self, speed: int, channel: int = 0) -> bool:
        return self.emulator.set_fan_speed(speed, channel)

    def get_device_info(self) -> Dict[str, Any]:
        return self.emulator.get_device_info()

    def get_statistics(self) -> Dict[str, Any]:
        return self.emulator.get_statistics()

    def reset(self) -> bool:
        return self.emulator.reset()


class EmulatedBLSD20Driver:
    """
    Adapter that makes BLSD20Emulator compatible with BLSD20ModbusDriver interface.
    """

    def __init__(self, emulator: BLSD20Emulator):
        self.emulator = emulator
        self.connected = True

    def connect(self) -> bool:
        self.connected = True
        return True

    def disconnect(self) -> None:
        self.connected = False

    def get_status(self) -> Optional[Dict[str, Any]]:
        return self.emulator.get_motor_status()

    def get_speed(self) -> float:
        return self.emulator.get_speed()

    def set_speed(self, speed: float) -> bool:
        return self.emulator.set_speed(speed)

    def get_target_speed(self) -> float:
        return self.emulator.get_target_speed()

    def get_position(self) -> float:
        return self.emulator.get_position()

    def start(self) -> bool:
        return self.emulator.start_motor()

    def stop(self) -> bool:
        return self.emulator.stop_motor()

    def emergency_stop(self) -> bool:
        return self.emulator.emergency_stop()

    def reset_errors(self) -> bool:
        return self.emulator.reset_errors()

    def get_current(self) -> float:
        return self.emulator.get_current()

    def set_current(self, current: float) -> bool:
        return self.emulator.set_current(current)

    def get_temperatures(self) -> Dict[str, float]:
        return self.emulator.get_temperatures()

    def get_error_code(self) -> int:
        return self.emulator.get_error_code()

    def set_direction(self, direction: int) -> bool:
        return self.emulator.set_direction(direction)

    def get_statistics(self) -> Dict[str, Any]:
        return self.emulator.get_statistics()


class EmulatedRS232RelayDriver:
    """
    Adapter that makes RS232RelayEmulator compatible with RS232RelayDriver interface.
    """

    def __init__(self, emulator: RS232RelayEmulator):
        self.emulator = emulator
        self._connected = True

    def is_connected(self) -> bool:
        return self._connected

    def connect(self) -> bool:
        self._connected = True
        return True

    def disconnect(self) -> None:
        self._connected = False

    def set_relay_state(self, relay_index: int, state: bool) -> bool:
        return self.emulator.set_relay_state(relay_index, state)

    def get_relay_state(self, relay_index: int) -> bool:
        return self.emulator.get_relay_state(relay_index)

    def get_all_relay_states(self) -> List[bool]:
        return self.emulator.get_all_relay_states()

    def set_all_relays(self, state: bool) -> bool:
        return self.emulator.set_all_relays(state)

    def toggle_relay(self, relay_index: int) -> bool:
        return self.emulator.toggle_relay(relay_index)

    def get_shaft_temperature(self, shaft_index: int) -> float:
        return self.emulator.get_shaft_temperature(shaft_index)

    def get_all_shaft_temperatures(self) -> List[float]:
        return self.emulator.get_all_shaft_temperatures()

    def reset(self) -> bool:
        return self.emulator.reset()

    def get_statistics(self) -> Dict[str, Any]:
        return self.emulator.get_statistics()

    def get_device_info(self) -> Dict[str, Any]:
        return self.emulator.get_device_info()

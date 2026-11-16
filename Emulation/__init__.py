"""
Emulation module for Lasurit Chamber devices.
Provides emulation for TRM12, BLSD20, and RS232 Relay devices.
"""

from Emulation.base_emulator import BaseEmulator
from Emulation.trm12_emulator import TRM12Emulator
from Emulation.blsd20_emulator import BLSD20Emulator
from Emulation.rs232_relay_emulator import RS232RelayEmulator
from Emulation.device_adapters import EmulatedTRM12Driver, EmulatedBLSD20Driver, EmulatedRS232RelayDriver
from Emulation.emulation_manager import EmulationManager, get_emulation_manager

__all__ = [
    'BaseEmulator',
    'TRM12Emulator',
    'BLSD20Emulator',
    'RS232RelayEmulator',
    'EmulatedTRM12Driver',
    'EmulatedBLSD20Driver',
    'EmulatedRS232RelayDriver',
    'EmulationManager',
    'get_emulation_manager'
]

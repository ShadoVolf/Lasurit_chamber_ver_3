"""
Emulation manager for Lasurit Chamber.
Centralized management of device emulation.
"""

import json
import os
from typing import Dict, Any, Optional
from Emulation.trm12_emulator import TRM12Emulator
from Emulation.blsd20_emulator import BLSD20Emulator
from Emulation.rs232_relay_emulator import RS232RelayEmulator


class EmulationManager:
    """
    Manages device emulation for the Lasurit Chamber system.
    Provides a centralized interface for enabling/disabling emulation
    and accessing emulated devices.
    """

    _instance = None

    def __new__(cls, config_file: str = None):
        """Singleton pattern."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self, config_file: str = None):
        """
        Initialize emulation manager.
        
        :param config_file: Path to emulation configuration file
        """
        if self._initialized:
            return
        
        self.config_file = config_file or 'emulation_config.json'
        self.config: Dict[str, Any] = {}
        self._load_config()
        
        # Device emulators
        self.trm12_emulator: Optional[TRM12Emulator] = None
        self.blsd20_emulator: Optional[BLSD20Emulator] = None
        self.rs232_relay_emulator: Optional[RS232RelayEmulator] = None
        
        # Initialize emulators if enabled
        self._init_emulators()
        
        self._initialized = True

    def _load_config(self):
        """Load configuration from file."""
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    self.config = json.load(f)
            else:
                # Default configuration
                self.config = {
                    'emulation_enabled': False,
                    'emulate_trm12': True,
                    'emulate_blsd20': True,
                    'emulate_rs232_relay': True,
                    'trm12_emulation': {
                        'initial_temperature': 25.0,
                        'heating_rate': 2.0,
                        'cooling_rate': 1.0,
                        'temperature_noise': 0.1,
                        'simulation_interval': 0.5
                    },
                    'blsd20_emulation': {
                        'initial_speed': 0,
                        'max_speed': 3000,
                        'acceleration': 100,
                        'deceleration': 100,
                        'initial_position': 0,
                        'simulation_interval': 0.5
                    },
                    'rs232_relay_emulation': {
                        'initial_state': False,
                        'response_delay': 0.1,
                        'simulation_interval': 0.5
                    }
                }
        except Exception as e:
            print(f"Error loading emulation config: {e}")
            self.config = {'emulation_enabled': False}

    def _init_emulators(self):
        """Initialize emulators based on configuration."""
        if not self.is_enabled():
            return
        
        # Initialize TRM12 emulator
        if self.config.get('emulate_trm12', True):
            trm12_config = self.config.get('trm12_emulation', {})
            self.trm12_emulator = TRM12Emulator(trm12_config)
            if self.trm12_emulator:
                self.trm12_emulator.start()
        
        # Initialize BLSD20 emulator
        if self.config.get('emulate_blsd20', True):
            blsd20_config = self.config.get('blsd20_emulation', {})
            self.blsd20_emulator = BLSD20Emulator(blsd20_config)
            if self.blsd20_emulator:
                self.blsd20_emulator.start()
        
        # Initialize RS232 Relay emulator
        if self.config.get('emulate_rs232_relay', True):
            rs232_config = self.config.get('rs232_relay_emulation', {})
            self.rs232_relay_emulator = RS232RelayEmulator(rs232_config)
            if self.rs232_relay_emulator:
                self.rs232_relay_emulator.start()

    def is_enabled(self) -> bool:
        """Check if emulation is enabled."""
        return self.config.get('emulation_enabled', False)

    def is_device_emulated(self, device_name: str) -> bool:
        """Check if a specific device is emulated."""
        device_map = {
            'trm12': 'emulate_trm12',
            'blsd20': 'emulate_blsd20',
            'rs232_relay': 'emulate_rs232_relay'
        }
        return self.is_enabled() and self.config.get(device_map.get(device_name, ''), False)

    def get_trm12_emulator(self) -> Optional[TRM12Emulator]:
        """Get TRM12 emulator instance."""
        return self.trm12_emulator

    def get_blsd20_emulator(self) -> Optional[BLSD20Emulator]:
        """Get BLSD20 emulator instance."""
        return self.blsd20_emulator

    def get_rs232_relay_emulator(self) -> Optional[RS232RelayEmulator]:
        """Get RS232 Relay emulator instance."""
        return self.rs232_relay_emulator

    def start_all(self):
        """Start all emulators."""
        if self.trm12_emulator and not self.trm12_emulator.is_running():
            self.trm12_emulator.start()
        if self.blsd20_emulator and not self.blsd20_emulator.is_running():
            self.blsd20_emulator.start()
        if self.rs232_relay_emulator and not self.rs232_relay_emulator.is_running():
            self.rs232_relay_emulator.start()

    def stop_all(self):
        """Stop all emulators."""
        if self.trm12_emulator:
            self.trm12_emulator.stop()
        if self.blsd20_emulator:
            self.blsd20_emulator.stop()
        if self.rs232_relay_emulator:
            self.rs232_relay_emulator.stop()

    def update_config(self, new_config: Dict[str, Any]):
        """Update configuration and reinitialize emulators if needed."""
        self.config.update(new_config)
        
        # Save to file
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"Error saving emulation config: {e}")
        
        # Reinitialize emulators if emulation state changed
        if 'emulation_enabled' in new_config:
            self.stop_all()
            self._init_emulators()

    def get_config(self) -> Dict[str, Any]:
        """Get current configuration."""
        return self.config.copy()

    def get_statistics(self) -> Dict[str, Any]:
        """Get statistics for all emulators."""
        stats = {
            'enabled': self.is_enabled(),
            'trm12': None,
            'blsd20': None,
            'rs232_relay': None
        }
        
        if self.trm12_emulator:
            stats['trm12'] = self.trm12_emulator.get_statistics()
        if self.blsd20_emulator:
            stats['blsd20'] = self.blsd20_emulator.get_statistics()
        if self.rs232_relay_emulator:
            stats['rs232_relay'] = self.rs232_relay_emulator.get_statistics()
        
        return stats


# Global instance
EMULATION_MANAGER = EmulationManager()


def get_emulation_manager() -> EmulationManager:
    """Get the global emulation manager instance."""
    return EMULATION_MANAGER


def is_emulation_enabled() -> bool:
    """Check if emulation is enabled."""
    return EMULATION_MANAGER.is_enabled()


def is_device_emulated(device_name: str) -> bool:
    """Check if a specific device is emulated."""
    return EMULATION_MANAGER.is_device_emulated(device_name)

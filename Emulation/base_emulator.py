"""
Base emulator class for device emulation.
"""

import json
import threading
import time
from typing import Dict, Any, Optional


class BaseEmulator:
    """
    Base class for all device emulators.
    Provides common functionality for emulated devices.
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the emulator.
        
        :param config: Configuration dictionary for the emulator
        """
        self.config = config or {}
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.RLock()
        self._last_update = time.time()
        self.simulation_interval = self.config.get('simulation_interval', 0.5)

    def start(self):
        """Start the emulation thread."""
        if not self._running:
            self._running = True
            self._thread = threading.Thread(target=self._simulation_loop, daemon=True)
            self._thread.start()

    def stop(self):
        """Stop the emulation thread."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=1.0)
            self._thread = None

    def _simulation_loop(self):
        """Main simulation loop."""
        while self._running:
            self._update()
            time.sleep(self.simulation_interval)

    def _update(self):
        """Update emulator state. To be overridden by subclasses."""
        self._last_update = time.time()

    def is_running(self) -> bool:
        """Check if emulator is running."""
        return self._running

    def get_config(self) -> Dict[str, Any]:
        """Get current configuration."""
        return self.config

    def set_config(self, config: Dict[str, Any]):
        """Set configuration."""
        with self._lock:
            self.config.update(config)
            if 'simulation_interval' in config:
                self.simulation_interval = config['simulation_interval']

"""
Модуль для просмотра настроек соединения RS485/RS232
Только для чтения, использует существующий класс DEVICES_DATA
"""

from .connection_options_window import ConnectionOptionsWindow
from .connection_options_manager import ConnectionOptionsManager

__all__ = [
    'ConnectionOptionsWindow',
    'ConnectionOptionsManager'
]
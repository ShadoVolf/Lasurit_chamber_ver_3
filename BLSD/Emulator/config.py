"""
Конфигурация для эмулятора BLSD-20Modbus.
"""

import os
import json
from typing import Dict, Any

from BLSD.Emulator.BLSD_Emulator import BLSDEmulator


class BLSDEmulatorConfig:
    """Класс для управления конфигурацией эмулятора."""

    DEFAULT_CONFIG = {
        'emulator': {
            'default_slave_id': 1,
            'default_motor_type': 'FL42BLS02',
            'default_simulation_speed': 1.0,
            'update_interval': 0.1,
            'command_interval': 0.05,
            'auto_start': True,
            'enable_logging': True,
            'log_level': 'INFO',
        },
        'motor': {
            'fl42bls02': {
                'n_poles': 8,
                'max_current': 20000,
                'max_speed': 4000,
                'default_acceleration': 100,
                'default_deceleration': 100,
            },
            'fl57bls02': {
                'n_poles': 4,
                'max_current': 15000,
                'max_speed': 3000,
                'default_acceleration': 80,
                'default_deceleration': 80,
            }
        },
        'simulation': {
            'temperature': {
                'base_mcu': 30.0,
                'base_mosfet': 30.0,
                'base_brake': 30.0,
                'heat_rate_running': 0.1,
                'cool_rate_idle': 0.05,
                'noise': 0.5,
            },
            'current': {
                'base_idle': 50,
                'noise': 50,
                'load_factor': 0.05,
            },
            'errors': {
                'probability': 0.01,
                'auto_clear_interval': 10.0,
            }
        },
        'modbus': {
            'supported_baudrates': [9600, 19200, 38400, 57600, 115200],
            'default_baudrate': 115200,
            'default_parity': 'E',
            'default_stopbits': 1,
            'default_bytesize': 8,
            'default_timeout': 1.0,
        }
    }

    def __init__(self, config_file: str = None):
        """
        Инициализация конфигурации.

        Args:
            config_file: Путь к файлу конфигурации (опционально)
        """
        self.config = self.DEFAULT_CONFIG.copy()

        if config_file and os.path.exists(config_file):
            self.load_config(config_file)

    def load_config(self, config_file: str):
        """Загрузка конфигурации из файла."""
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                user_config = json.load(f)
                self._deep_update(self.config, user_config)
        except Exception as e:
            print(f"Ошибка загрузки конфигурации: {e}")

    def save_config(self, config_file: str):
        """Сохранение конфигурации в файл."""
        try:
            os.makedirs(os.path.dirname(config_file), exist_ok=True)
            with open(config_file, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"Ошибка сохранения конфигурации: {e}")

    def get(self, key: str, default=None) -> Any:
        """Получение значения по ключу."""
        keys = key.split('.')
        value = self.config

        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default

        return value

    def set(self, key: str, value: Any):
        """Установка значения по ключу."""
        keys = key.split('.')
        config = self.config

        for k in keys[:-1]:
            if k not in config:
                config[k] = {}
            config = config[k]

        config[keys[-1]] = value

    def get_motor_config(self, motor_type: str) -> Dict[str, Any]:
        """Получение конфигурации для типа двигателя."""
        return self.config['motor'].get(motor_type.lower(), {})

    def create_emulator_from_config(self, config_name: str = 'default') -> 'BLSDEmulator':
        """Создание эмулятора на основе конфигурации."""


        # Получаем настройки
        slave_id = self.get(f'instances.{config_name}.slave_id', 1)
        motor_type = self.get(f'instances.{config_name}.motor_type', 'FL42BLS02')
        sim_speed = self.get(f'instances.{config_name}.simulation_speed', 1.0)

        # Создаем эмулятор
        emulator = BLSDEmulator(
            slave_id=slave_id,
            motor_type=motor_type,
            simulation_speed=sim_speed
        )

        # Настраиваем параметры симуляции
        error_prob = self.get('simulation.errors.probability', 0.01)
        emulator.set_error_probability(error_prob)

        return emulator

    def _deep_update(self, target: Dict, source: Dict):
        """Рекурсивное обновление словаря."""
        for key, value in source.items():
            if key in target and isinstance(target[key], dict) and isinstance(value, dict):
                self._deep_update(target[key], value)
            else:
                target[key] = value


# Создание глобальной конфигурации
config = BLSDEmulatorConfig()


def get_config():
    """Получение глобальной конфигурации."""
    return config
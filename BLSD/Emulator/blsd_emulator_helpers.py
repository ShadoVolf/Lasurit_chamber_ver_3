"""
Вспомогательные функции для эмулятора BLSD-20Modbus.
"""

import json
from typing import Dict, Any, List
from datetime import datetime


class BLSDEmulatorHelper:
    """Вспомогательный класс для работы с эмулятором."""

    @staticmethod
    def format_state_report(state: Dict[str, Any]) -> str:
        """Форматирование отчета о состоянии."""
        lines = []
        lines.append("=" * 60)
        lines.append(f"Отчет о состоянии BLSD-20 эмулятора")
        lines.append(f"Время: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append("=" * 60)

        # Статус двигателя
        motor = state.get('motor_status', {})
        lines.append(f"Статус двигателя: {motor.get('text', 'Неизвестно')}")

        lines.append(f"Ток: {state.get('current', 0)} мА")
        lines.append(f"Скорость: {state.get('speed', 0)} об/мин")
        lines.append(f"Целевая скорость: {state.get('target_speed', 0)} об/мин")
        lines.append(f"Позиция: {state.get('position', 0)}")

        # Температуры
        temps = state.get('temperatures', {})
        lines.append(f"Температура MCU: {temps.get('mcu', 0):.1f}°C")
        lines.append(f"Температура MOSFET: {temps.get('mosfet', 0):.1f}°C")
        lines.append(f"Температура тормоза: {temps.get('brake', 0):.1f}°C")

        # Ошибки
        error = state.get('error_code', 0)
        if error:
            lines.append(f"Код ошибки: 0x{error:04X}")
        else:
            lines.append("Ошибки: нет")

        # Режимы
        lines.append(f"Направление: {state.get('direction', {}).get('text', 'Неизвестно')}")
        lines.append(f"Режим устройства: {state.get('mode_device', {}).get('text', 'Неизвестно')}")
        lines.append(f"Режим вращения: {state.get('mode_rotation', {}).get('text', 'Неизвестно')}")

        lines.append(f"Двигатель работает: {'Да' if state.get('is_running') else 'Нет'}")
        lines.append(f"Счетчик задач: {state.get('task_counter', 0)}")

        # Статистика
        stats = state.get('statistics', {})
        lines.append("\nСтатистика:")
        lines.append(f"  Общее время работы: {stats.get('total_runtime', 0):.1f} сек")
        lines.append(f"  Обработано команд: {stats.get('commands_processed', 0)}")
        lines.append(f"  Сгенерировано ошибок: {stats.get('errors_generated', 0)}")
        lines.append(f"  Предупреждений о температуре: {stats.get('temperature_warnings', 0)}")

        lines.append("=" * 60)
        return '\n'.join(lines)

    @staticmethod
    def save_state_to_file(state: Dict[str, Any], filename: str):
        """Сохранение состояния в файл."""
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(state, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"Ошибка при сохранении состояния: {e}")

    @staticmethod
    def load_state_from_file(filename: str) -> Dict[str, Any]:
        """Загрузка состояния из файла."""
        try:
            with open(filename, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"Ошибка при загрузке состояния: {e}")
            return {}

    @staticmethod
    def create_default_config(motor_type: str = 'FL42BLS02') -> Dict[str, Any]:
        """Создание конфигурации по умолчанию."""
        return {
            'motor_type': motor_type,
            'slave_id': 1,
            'simulation_speed': 1.0,
            'settings': {
                'set_speed': 1000,
                'acceleration': 100,
                'deceleration': 100,
                'direction': 1,
                'ref_current': 10000,
                'hold_current': 1000,
                'mode_device': 1,
                'mode_rotation': 1,
            }
        }

    @staticmethod
    def parse_error_code(error_code: int) -> List[str]:
        """Парсинг кода ошибки."""
        errors = []

        error_bits = {
            0x0001: "Перегрев",
            0x0002: "Перегрузка по току",
            0x0004: "Ошибка связи",
            0x0008: "Ошибка энкодера",
            0x0010: "Ошибка драйвера",
            0x0020: "Ошибка питания",
            0x0040: "Ошибка тормоза",
            0x0080: "Ошибка температуры",
            0x0100: "Ошибка позиционирования",
            0x0200: "Ошибка скорости",
            0x0400: "Ошибка конфигурации",
            0x0800: "Ошибка памяти",
            0x1000: "Ошибка программы",
            0x2000: "Ошибка системы",
            0x4000: "Ошибка связи с хостом",
            0x8000: "Критическая ошибка",
        }

        for bit_mask, description in error_bits.items():
            if error_code & bit_mask:
                errors.append(description)

        return errors
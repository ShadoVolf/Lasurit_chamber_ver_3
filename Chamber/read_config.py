import os
import json
from typing import Optional, Dict, Any


def read_serial_number_from_config() -> str:
    """
    Читает серийный номер камеры из config.cfg
    Если файл не существует, создает его с номером 2405001
    """
    config_file = "config.cfg"
    default_serial = "2405001"

    try:
        # Если файл существует
        if os.path.exists(config_file):
            with open(config_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                serial_number = data.get("serial_number", default_serial)
                print(f"Прочитан серийный номер: {serial_number}")
                return serial_number
        else:
            # Создаем файл с дефолтным номером
            config_data = {
                "serial_number": default_serial,
                "created_date": "2024-01-01",
                "device_type": "Камера температурных испытаний",
                "description": "Конфигурационный файл системы управления камерой"
            }

            with open(config_file, 'w', encoding='utf-8') as f:
                json.dump(config_data, f, ensure_ascii=False, indent=2)

            print(f"Создан файл config.cfg с серийным номером: {default_serial}")
            return default_serial

    except Exception as e:
        print(f"Ошибка работы с config.cfg: {e}")
        return default_serial


def update_serial_number(new_serial: str) -> bool:
    """
    Обновляет серийный номер в config.cfg

    Args:
        new_serial: Новый серийный номер

    Returns:
        bool: Успех операции
    """
    try:
        config_data = {}
        config_file = "config.cfg"

        # Если файл существует, читаем его
        if os.path.exists(config_file):
            with open(config_file, 'r', encoding='utf-8') as f:
                config_data = json.load(f)

        # Обновляем серийный номер
        config_data["serial_number"] = new_serial
        config_data["last_modified"] = time.strftime("%Y-%m-%d %H:%M:%S")

        # Сохраняем
        with open(config_file, 'w', encoding='utf-8') as f:
            json.dump(config_data, f, ensure_ascii=False, indent=2)

        print(f"Серийный номер обновлен: {new_serial}")
        return True

    except Exception as e:
        print(f"Ошибка обновления серийного номера: {e}")
        return False


def get_device_config() -> Dict[str, Any]:
    """
    Получает полную конфигурацию устройства из config.cfg
    """
    config_file = "config.cfg"
    default_config = {
        "serial_number": "2405001",
        "device_type": "Камера температурных испытаний",
        "description": "Конфигурационный файл системы управления камерой",
        "created_date": "2024-01-01"
    }

    try:
        if os.path.exists(config_file):
            with open(config_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        else:
            # Создаем файл с дефолтной конфигурацией
            with open(config_file, 'w', encoding='utf-8') as f:
                json.dump(default_config, f, ensure_ascii=False, indent=2)
            return default_config

    except Exception as e:
        print(f"Ошибка чтения конфигурации: {e}")
        return default_config
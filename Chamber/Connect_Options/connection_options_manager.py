from typing import Dict, Any

from Ports_COM.Devices_Data import DEVICES_DATA


class ConnectionOptionsManager:
    """Менеджер для работы с настройками соединения на основе DEVICES_DATA"""

    @staticmethod
    def load_settings() -> Dict[str, Any]:
        """
        Загрузка текущих настроек из DEVICES_DATA

        Returns:
            Dict: Словарь с текущими настройками
        """
        try:
            # Используем метод из DEVICES_DATA, если он существует
            if hasattr(DEVICES_DATA, 'get_connection_settings'):
                return DEVICES_DATA.get_connection_settings()

            # Иначе собираем вручную
            return {
                "trm12": {
                    "com_port": DEVICES_DATA.trm12.com_port,
                    "baudrate": DEVICES_DATA.trm12.baudrate,
                    "data_bits": DEVICES_DATA.trm12.data_bits,
                    "stop_bits": DEVICES_DATA.trm12.stop_bits,
                    "parity": DEVICES_DATA.trm12.parity,
                    "timeout": DEVICES_DATA.trm12.timeout,
                    "address": DEVICES_DATA.trm12.address,
                    "connected": DEVICES_DATA.trm12.connected,
                    "auto_select_com": DEVICES_DATA.trm12.auto_select_com
                },
                "blsd20": {
                    "com_port": DEVICES_DATA.blsd20.com_port,
                    "baudrate": DEVICES_DATA.blsd20.baudrate,
                    "data_bits": DEVICES_DATA.blsd20.data_bits,
                    "stop_bits": DEVICES_DATA.blsd20.stop_bits,
                    "parity": DEVICES_DATA.blsd20.parity,
                    "timeout": DEVICES_DATA.blsd20.timeout,
                    "address": DEVICES_DATA.blsd20.address,
                    "connected": DEVICES_DATA.blsd20.connected,
                    "auto_select_com": DEVICES_DATA.blsd20.auto_select_com
                },
                "rs232_relay": {
                    "com_port": DEVICES_DATA.rs232_relay.com_port,
                    "baudrate": DEVICES_DATA.rs232_relay.baudrate,
                    "data_bits": DEVICES_DATA.rs232_relay.data_bits,
                    "stop_bits": DEVICES_DATA.rs232_relay.stop_bits,
                    "parity": DEVICES_DATA.rs232_relay.parity,
                    "timeout": DEVICES_DATA.rs232_relay.timeout,
                    "address": DEVICES_DATA.rs232_relay.address,
                    "connected": DEVICES_DATA.rs232_relay.connected,
                    "auto_select_com": DEVICES_DATA.rs232_relay.auto_select_com
                }
            }
        except Exception as e:
            print(f"Ошибка загрузки настроек из DEVICES_DATA: {e}")
            return {}

    @staticmethod
    def load_from_file(filename: str = "connection_settings.json") -> bool:
        """
        Загрузка настроек из файла в DEVICES_DATA

        Args:
            filename: Имя файла с настройками

        Returns:
            bool: True если успешно, False в противном случае
        """
        try:
            if hasattr(DEVICES_DATA, 'load_connection_settings_from_file'):
                return DEVICES_DATA.load_connection_settings_from_file(filename)

            print("Метод load_connection_settings_from_file не найден в DEVICES_DATA")
            return False
        except Exception as e:
            print(f"Ошибка загрузки настроек из файла: {e}")
            return False

    @staticmethod
    def save_to_file(filename: str = "connection_settings.json") -> bool:
        """
        Сохранение текущих настроек из DEVICES_DATA в файл

        Args:
            filename: Имя файла для сохранения

        Returns:
            bool: True если успешно, False в противном случае
        """
        try:
            if hasattr(DEVICES_DATA, 'save_connection_settings_to_file'):
                return DEVICES_DATA.save_connection_settings_to_file(filename)

            print("Метод save_connection_settings_to_file не найден в DEVICES_DATA")
            return False
        except Exception as e:
            print(f"Ошибка сохранения настроек в файл: {e}")
            return False

    @staticmethod
    def get_connected_devices_info() -> Dict[str, Any]:
        """
        Получение информации о подключенных устройствах

        Returns:
            Dict: Информация о устройствах
        """
        info = {
            "total_count": 0,
            "connected_count": 0,
            "devices": []
        }

        try:
            # Получаем список подключенных устройств
            connected_devices = DEVICES_DATA.get_devices() if hasattr(DEVICES_DATA, 'get_devices') else None

            if connected_devices:
                info["total_count"] = len(connected_devices)

                for device in connected_devices:
                    device_info = {
                        "type": str(device.type_).split('.')[-1] if hasattr(device, 'type_') else "Unknown",
                        "address": device.address if hasattr(device, 'address') else None,
                        "com_port": device.com_port if hasattr(device, 'com_port') else None,
                        "connected": device.connected if hasattr(device, 'connected') else False,
                        "has_driver": False
                    }

                    # Проверяем наличие драйвера
                    if hasattr(DEVICES_DATA, 'get_device_driver'):
                        driver = DEVICES_DATA.get_device_driver(device.type_)
                        device_info["has_driver"] = driver is not None

                    if device_info["connected"]:
                        info["connected_count"] += 1

                    info["devices"].append(device_info)

            # Проверяем статусы основных устройств
            device_statuses = [
                ("TRM-12", DEVICES_DATA.trm12.connected),
                ("BLSD-20", DEVICES_DATA.blsd20.connected),
                ("RS232-4pin-Relay", DEVICES_DATA.rs232_relay.connected)
            ]

            info["device_statuses"] = device_statuses

        except Exception as e:
            print(f"Ошибка получения информации об устройствах: {e}")

        return info
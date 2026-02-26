import json
import os
from typing import List
from Ports_COM.Device_connect_param import DeviceConnectionParams
from Ports_COM.client import DeviceInfo, DeviceType


class DEVICES_DATA:
    # Подключенные устройства
    connected_devices = None
    # Драйвера устройств (Словарь)
    device_drivers_dict = {}
    # Драйвер камеры
    camera_controller = None
    # GUI Owen
    owen_gui = None
    # GUI BLSD
    blsd_gui = None
    # Монитор температуры
    temperature_monitor = None

    # Параметры соединения для TRM-12
    trm12: DeviceConnectionParams = DeviceConnectionParams(
        com_port="COM1",
        baudrate=9600,
        data_bits=8,
        stop_bits=1,
        parity="N",
        timeout=1.0,
        address=1,
        connected=False,
        auto_select_com=True
    )

    # Параметры соединения для BLSD-20
    blsd20: DeviceConnectionParams = DeviceConnectionParams(
        com_port="COM1",
        baudrate=9600,
        data_bits=8,
        stop_bits=1,
        parity="N",
        timeout=1.0,
        address=1,
        connected=False,
        auto_select_com=True
    )

    # Параметры соединения для RS232-4pin-Relay
    rs232_relay: DeviceConnectionParams = DeviceConnectionParams(
        com_port="COM1",
        baudrate=9600,
        data_bits=8,
        stop_bits=1,
        parity="N",
        timeout=2.0,
        address=0,  # Устройство не имеет адреса
        connected=False,
        auto_select_com=True
    )

    # Устанавливает монитор температуры
    @staticmethod
    def set_temp_monitor(value):
        DEVICES_DATA.temperature_monitor =  value
    @staticmethod
    def get_temp_monitor():
        return  DEVICES_DATA.temperature_monitor

    # Задает GUI BLSD
    @staticmethod
    def set_blsd_gui(value):
        DEVICES_DATA.blsd_gui =  value
    @staticmethod
    def get_blsd_gui():
        return  DEVICES_DATA.blsd_gui

    # Задает GUI OWEN
    @staticmethod
    def set_owen_gui(value):
        DEVICES_DATA.owen_gui =  value
    @staticmethod
    def get_owen_gui():
        return  DEVICES_DATA.owen_gui

    # Задает драйвер камеры
    @staticmethod
    def set_chamber_controller(value):
        DEVICES_DATA.camera_controller = value
    @staticmethod
    def get_chamber_controller():
        return DEVICES_DATA.camera_controller

    # Устанавливает устройства
    @staticmethod
    def set_devices(value: List[DeviceInfo]):
        DEVICES_DATA.connected_devices = value

    @staticmethod
    def get_devices() -> List[DeviceInfo]:
        return DEVICES_DATA.connected_devices


    # Записывает активный драйвер устройства
    @staticmethod
    def add_device_driver(type_: DeviceType, driver):
        DEVICES_DATA.device_drivers_dict[type_] = driver
    # Возвращает активный драйвер устройства
    @staticmethod
    def get_device_driver(type_:DeviceType):
        if DEVICES_DATA.device_drivers_dict:
            if type_ in DEVICES_DATA.device_drivers_dict:
                return DEVICES_DATA.device_drivers_dict[type_]
            else:
                return None
        else:
            return None


    @classmethod
    def load_connection_settings_from_file(cls, filename: str = "connection_settings.json"):
        """
        Загрузка параметров соединения из файла JSON.

        Args:
            filename: Имя файла с настройками (по умолчанию connection_settings.json)

        Returns:
            bool: True если загрузка успешна, False в противном случае
        """
        try:
            if not os.path.exists(filename):
                print(f"Файл {filename} не найден. Используются настройки по умолчанию.")
                return False

            with open(filename, 'r', encoding='utf-8') as f:
                data = json.load(f)

            # Загрузка настроек для TRM-12
            if "trm12" in data:
                trm12_data = data["trm12"]
                cls.trm12 = DeviceConnectionParams(
                    com_port=trm12_data.get("com_port", cls.trm12.com_port),
                    baudrate=trm12_data.get("baudrate", cls.trm12.baudrate),
                    data_bits=trm12_data.get("data_bits", cls.trm12.data_bits),
                    stop_bits=trm12_data.get("stop_bits", cls.trm12.stop_bits),
                    parity=trm12_data.get("parity", cls.trm12.parity),
                    timeout=trm12_data.get("timeout", cls.trm12.timeout),
                    address=trm12_data.get("address", cls.trm12.address),
                    connected=trm12_data.get("connected", False),
                    auto_select_com=trm12_data.get("auto_select_com", cls.trm12.auto_select_com)
                )

            # Загрузка настроек для BLSD-20
            if "blsd20" in data:
                blsd20_data = data["blsd20"]
                cls.blsd20 = DeviceConnectionParams(
                    com_port=blsd20_data.get("com_port", cls.blsd20.com_port),
                    baudrate=blsd20_data.get("baudrate", cls.blsd20.baudrate),
                    data_bits=blsd20_data.get("data_bits", cls.blsd20.data_bits),
                    stop_bits=blsd20_data.get("stop_bits", cls.blsd20.stop_bits),
                    parity=blsd20_data.get("parity", cls.blsd20.parity),
                    timeout=blsd20_data.get("timeout", cls.blsd20.timeout),
                    address=blsd20_data.get("address", cls.blsd20.address),
                    connected=blsd20_data.get("connected", False),
                    auto_select_com=blsd20_data.get("auto_select_com", cls.blsd20.auto_select_com)
                )

            # Загрузка настроек для RS232-4pin-Relay
            if "rs232_relay" in data:
                relay_data = data["rs232_relay"]
                cls.rs232_relay = DeviceConnectionParams(
                    com_port=relay_data.get("com_port", cls.rs232_relay.com_port),
                    baudrate=relay_data.get("baudrate", cls.rs232_relay.baudrate),
                    data_bits=relay_data.get("data_bits", cls.rs232_relay.data_bits),
                    stop_bits=relay_data.get("stop_bits", cls.rs232_relay.stop_bits),
                    parity=relay_data.get("parity", cls.rs232_relay.parity),
                    timeout=relay_data.get("timeout", cls.rs232_relay.timeout),
                    address=relay_data.get("address", cls.rs232_relay.address),
                    connected=relay_data.get("connected", False),
                    auto_select_com=relay_data.get("auto_select_com", cls.rs232_relay.auto_select_com)
                )

            print(f"Настройки соединения загружены из файла {filename}")
            return True

        except json.JSONDecodeError as e:
            print(f"Ошибка формата JSON в файле {filename}: {e}")
            return False
        except Exception as e:
            print(f"Ошибка загрузки настроек из файла {filename}: {e}")
            return False

    @classmethod
    def save_connection_settings_to_file(cls, filename: str = "connection_settings.json"):
        """
        Сохранение текущих параметров соединения в файл JSON.

        Args:
            filename: Имя файла для сохранения (по умолчанию connection_settings.json)

        Returns:
            bool: True если сохранение успешно, False в противном случае
        """
        try:
            data = {
                "trm12": {
                    "com_port": cls.trm12.com_port,
                    "baudrate": cls.trm12.baudrate,
                    "data_bits": cls.trm12.data_bits,
                    "stop_bits": cls.trm12.stop_bits,
                    "parity": cls.trm12.parity,
                    "timeout": cls.trm12.timeout,
                    "address": cls.trm12.address,
                    "auto_select_com": cls.trm12.auto_select_com,
                    "connected": cls.trm12.connected
                },
                "blsd20": {
                    "com_port": cls.blsd20.com_port,
                    "baudrate": cls.blsd20.baudrate,
                    "data_bits": cls.blsd20.data_bits,
                    "stop_bits": cls.blsd20.stop_bits,
                    "parity": cls.blsd20.parity,
                    "timeout": cls.blsd20.timeout,
                    "address": cls.blsd20.address,
                    "auto_select_com": cls.blsd20.auto_select_com,
                    "connected": cls.blsd20.connected
                },
                "rs232_relay": {
                    "com_port": cls.rs232_relay.com_port,
                    "baudrate": cls.rs232_relay.baudrate,
                    "data_bits": cls.rs232_relay.data_bits,
                    "stop_bits": cls.rs232_relay.stop_bits,
                    "parity": cls.rs232_relay.parity,
                    "timeout": cls.rs232_relay.timeout,
                    "address": cls.rs232_relay.address,
                    "auto_select_com": cls.rs232_relay.auto_select_com,
                    "connected": cls.rs232_relay.connected
                }
            }

            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)

            print(f"Настройки соединения сохранены в файл {filename}")
            return True

        except Exception as e:
            print(f"Ошибка сохранения настроек в файл {filename}: {e}")
            return False

    @classmethod
    def get_connection_settings(cls):
        """
        Получение текущих параметров соединения в виде словаря.

        Returns:
            dict: Словарь с параметрами соединения для всех устройств
        """
        return {
            "trm12": {
                "com_port": cls.trm12.com_port,
                "baudrate": cls.trm12.baudrate,
                "data_bits": cls.trm12.data_bits,
                "stop_bits": cls.trm12.stop_bits,
                "parity": cls.trm12.parity,
                "timeout": cls.trm12.timeout,
                "address": cls.trm12.address,
                "connected": cls.trm12.connected,
                "auto_select_com": cls.trm12.auto_select_com
            },
            "blsd20": {
                "com_port": cls.blsd20.com_port,
                "baudrate": cls.blsd20.baudrate,
                "data_bits": cls.blsd20.data_bits,
                "stop_bits": cls.blsd20.stop_bits,
                "parity": cls.blsd20.parity,
                "timeout": cls.blsd20.timeout,
                "address": cls.blsd20.address,
                "connected": cls.blsd20.connected,
                "auto_select_com": cls.blsd20.auto_select_com
            },
            "rs232_relay": {
                "com_port": cls.rs232_relay.com_port,
                "baudrate": cls.rs232_relay.baudrate,
                "data_bits": cls.rs232_relay.data_bits,
                "stop_bits": cls.rs232_relay.stop_bits,
                "parity": cls.rs232_relay.parity,
                "timeout": cls.rs232_relay.timeout,
                "address": cls.rs232_relay.address,
                "connected": cls.rs232_relay.connected,
                "auto_select_com": cls.rs232_relay.auto_select_com
            }
        }
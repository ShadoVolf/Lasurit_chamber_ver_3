
import serial.tools.list_ports
from enum import Enum
from typing import Optional, List, Dict, Any

# Импортируем оба драйвера
from BLSD.client_blsd20 import BLSD20ModbusDriver
from RS232_4pin_Rele.Client import RS232RelayDriver
from owen.Client import ByteOrder, TRM12Driver
# Импортируем драйвер релейной платы



class DeviceType(Enum):
    """Типы поддерживаемых устройств."""
    TRM12 = "ОВЕН ТРМ12"
    BLSD20 = "BLSD-20"
    RS232_4PIN_RELAY = "RS232-4pin-Relay"  # Добавляем новое устройство


class DeviceInfo:
    """Класс для хранения информации об устройстве."""

    def __init__(self, port: str, device_type: DeviceType, description: str = "",
                 address: int = 1, baudrate: int = None, additional_info: Dict = None):
        self.port = port
        self.device_type = device_type
        self.description = description
        self.address = address
        self.baudrate = baudrate
        self.additional_info = additional_info or {}
        self.connected = False

    def __str__(self):
        baud_str = f", {self.baudrate} бод" if self.baudrate else ""
        addr_str = f"адрес: {self.address}" if self.address != 0 else "без адреса"
        return f"{self.port}: {self.device_type.value} ({addr_str}{baud_str})"

    def to_dict(self):
        """Преобразование в словарь для удобства."""
        return {
            'port': self.port,
            'device_type': self.device_type.value,
            'description': self.description,
            'address': self.address,
            'baudrate': self.baudrate,
            'connected': self.connected,
            'additional_info': self.additional_info
        }


class UniversalDeviceScanner:
    """
    Универсальный сканер COM-портов для обнаружения устройств ТРМ12, BLSD-20 и RS232-4pin-Relay.
    """

    # Стандартные настройки для сканирования
    DEFAULT_SETTINGS = {
        'trm12': {
            'addresses': [1, 2, 3, 16, 32],  # Типичные адреса ОВЕН
            'baudrates': [9600, 19200, 38400, 57600, 115200],
            'timeout': 0.3,
            'byte_order': ByteOrder.BIG_ENDIAN_SWAP
        },
        'blsd20': {
            'addresses': [1, 2, 3, 4, 5],
            'baudrates': [115200, 57600, 38400, 19200, 9600],
            'timeout': 0.3
        },
        'rs232_relay': {  # Добавляем настройки для релейной платы
            'baudrates': [9600, 19200, 38400, 57600, 115200],  # Стандартные скорости
            'timeout': 0.5,
            'channels': 4  # Количество реле
        }
    }

    def __init__(self, verbose: bool = False, target_types: List[DeviceType] = None):
        """
        Инициализация сканера.

        Args:
            verbose: Подробный вывод информации
            target_types: Типы устройств для поиска (None = все типы)
        """
        self.verbose = verbose
        self.target_types = target_types if target_types else list(DeviceType)
        self.found_devices: List[DeviceInfo] = []
        self.found_types = set()  # Множество найденных типов устройств

    def _log(self, message: str, level: str = "INFO"):
        """Логирование сообщений с учетом уровня подробности."""
        if self.verbose or level in ["ERROR", "WARNING"]:
            prefix = {
                "INFO": "[INFO]",
                "DEBUG": "[DEBUG]",
                "WARNING": "[⚠]",
                "ERROR": "[❌]",
                "SUCCESS": "[✅]"
            }.get(level, "[INFO]")
            print(f"{prefix} {message}")

    def _all_types_found(self) -> bool:
        """Проверяем, найдены ли все искомые типы устройств."""
        return all(device_type in self.found_types for device_type in self.target_types)

    def scan_ports(self) -> List[DeviceInfo]:
        """
        Сканирование всех доступных COM-портов на наличие устройств.
        Останавливается, когда найдены все искомые типы устройств.

        Returns:
            Список найденных устройств
        """
        self.found_devices = []
        self.found_types = set()

        # Получаем список всех COM-портов
        try:
            available_ports = list(serial.tools.list_ports.comports())
        except Exception as e:
            self._log(f"Ошибка получения списка портов: {e}", "ERROR")
            return []

        if not available_ports:
            self._log("Не найдено ни одного COM-порта", "WARNING")
            return []

        self._log(f"Найдено {len(available_ports)} COM-портов для сканирования")
        self._log(f"Ищем устройства: {[t.value for t in self.target_types]}")

        # Сканируем каждый порт до тех пор, пока не найдем все типы
        for port_info in available_ports:
            if self._all_types_found():
                self._log("Все искомые типы устройств найдены. Останавливаем поиск.", "SUCCESS")
                break

            self._scan_port(port_info)

        self._log(f"Сканирование завершено. Найдено устройств: {len(self.found_devices)}", "SUCCESS")
        return self.found_devices

    def _scan_port(self, port_info):
        """Сканирование одного COM-порта."""
        port = port_info.device
        description = port_info.description

        self._log(f"Сканирование порта {port}: {description}")

        # Определяем, какие типы устройств еще не найдены
        types_to_check = [t for t in self.target_types if t not in self.found_types]

        for device_type in types_to_check:
            if device_type == DeviceType.TRM12:
                device = self._scan_trm12(port, description)
                if device:
                    self.found_devices.append(device)
                    self.found_types.add(DeviceType.TRM12)
                    return  # Нашли устройство на этом порту, дальше не проверяем

            elif device_type == DeviceType.BLSD20:
                device = self._scan_blsd20(port, description)
                if device:
                    self.found_devices.append(device)
                    self.found_types.add(DeviceType.BLSD20)
                    return  # Нашли устройство на этом порту, дальше не проверяем

            elif device_type == DeviceType.RS232_4PIN_RELAY:
                device = self._scan_rs232_relay(port, description)
                if device:
                    self.found_devices.append(device)
                    self.found_types.add(DeviceType.RS232_4PIN_RELAY)
                    return  # Нашли устройство на этом порту, дальше не проверяем

    def _scan_trm12(self, port: str, description: str) -> Optional[DeviceInfo]:
        """Попытка обнаружения устройства ТРМ12 на порту."""
        self._log(f"  Проверка на ТРМ12...", "DEBUG")

        for baudrate in self.DEFAULT_SETTINGS['trm12']['baudrates']:
            for address in self.DEFAULT_SETTINGS['trm12']['addresses']:
                try:
                    driver = TRM12Driver(
                        port=port,
                        address=address,
                        baudrate=baudrate,
                        byte_order=self.DEFAULT_SETTINGS['trm12']['byte_order'],
                        timeout=self.DEFAULT_SETTINGS['trm12']['timeout']
                    )

                    if driver.connect():
                        try:
                            device_id = driver.read_parameter("DEV")
                            if device_id and len(str(device_id).strip()) > 0:
                                self._log(f"    Найден ТРМ12! Адрес: {address}, Скорость: {baudrate}", "SUCCESS")
                                additional_info = {}
                                try:
                                    firmware = driver.read_parameter("VER")
                                    status = driver.read_parameter("STAT")
                                    temperature = driver.read_parameter("PV", channel=0)
                                    if firmware:
                                        additional_info['firmware'] = str(firmware)
                                    if status is not None:
                                        additional_info['status'] = status
                                    if temperature is not None:
                                        additional_info['temperature'] = float(temperature)
                                except:
                                    pass

                                driver.disconnect()
                                return DeviceInfo(
                                    port=port,
                                    device_type=DeviceType.TRM12,
                                    description=f"{description} (ТРМ12)",
                                    address=address,
                                    baudrate=baudrate,
                                    additional_info=additional_info
                                )
                        except Exception as e:
                            if self.verbose:
                                self._log(f"    Ошибка чтения данных: {e}", "DEBUG")
                        finally:
                            driver.disconnect()
                except Exception as e:
                    if self.verbose:
                        self._log(f"    Ошибка проверки (адрес {address}, скорость {baudrate}): {str(e)[:50]}", "DEBUG")
        return None

    def _scan_blsd20(self, port: str, description: str) -> Optional[DeviceInfo]:
        """Попытка обнаружения устройства BLSD-20 на порту."""
        self._log(f"  Проверка на BLSD-20...", "DEBUG")

        for baudrate in self.DEFAULT_SETTINGS['blsd20']['baudrates']:
            for address in self.DEFAULT_SETTINGS['blsd20']['addresses']:
                try:
                    driver = BLSD20ModbusDriver(
                        port=port,
                        slave_id=address,
                        baudrate=baudrate,
                        timeout=self.DEFAULT_SETTINGS['blsd20']['timeout']
                    )

                    success = driver.connect()
                    if success:
                        try:
                            status = driver.get_status()
                            if status is not None:
                                self._log(f"    Найден BLSD-20! Адрес: {address}, Скорость: {baudrate}", "SUCCESS")
                                additional_info = {'status': status}
                                try:
                                    info = driver.get_device_info()
                                    additional_info['driver'] = info['Тип драйвера']
                                    additional_info['version'] = info['Версия аппаратной части']
                                    additional_info['ID'] = info['Идентификатор ПО']
                                    additional_info['version ID'] = info['Версия ПО']
                                except:
                                    pass

                                driver.disconnect()
                                return DeviceInfo(
                                    port=port,
                                    device_type=DeviceType.BLSD20,
                                    description=f"{description} (BLSD-20)",
                                    address=address,
                                    baudrate=baudrate,
                                    additional_info=additional_info
                                )
                        except Exception as e:
                            if self.verbose:
                                self._log(f"    Ошибка чтения данных: {e}", "DEBUG")
                        finally:
                            driver.disconnect()
                except Exception as e:
                    if self.verbose:
                        self._log(f"    Ошибка проверки (адрес {address}, скорость {baudrate}): {str(e)[:50]}", "DEBUG")
        return None

    def _scan_rs232_relay(self, port: str, description: str) -> Optional[DeviceInfo]:
        """Попытка обнаружения устройства RS232-4pin-Relay на порту."""
        self._log(f"  Проверка на RS232-4pin-Relay...", "DEBUG")

        for baudrate in self.DEFAULT_SETTINGS['rs232_relay']['baudrates']:
            try:
                driver = RS232RelayDriver(
                    port=port,
                    baudrate=baudrate,
                    timeout=self.DEFAULT_SETTINGS['rs232_relay']['timeout']
                )

                if driver.connect():
                    try:
                        # Пытаемся прочитать статус реле
                        status = driver.read_status()
                        if status and 'relay_states' in status:
                            self._log(f"    Найден RS232-4pin-Relay! Скорость: {baudrate}", "SUCCESS")

                            # Получаем информацию об устройстве
                            device_info = driver.get_device_info()
                            relay_states = driver.get_relay_states()

                            additional_info = {
                                'channels': device_info.get('channels', 4),
                                'manufacturer': device_info.get('manufacturer', 'RS232-4pin-Relay'),
                                'version': device_info.get('version', '1.0'),
                                'relay_states': {k: v.name for k, v in relay_states.items()}
                            }

                            driver.disconnect()
                            return DeviceInfo(
                                port=port,
                                device_type=DeviceType.RS232_4PIN_RELAY,
                                description=f"{description} (RS232-4pin-Relay)",
                                address=0,  # Устройство не имеет адреса
                                baudrate=baudrate,
                                additional_info=additional_info
                            )
                    except Exception as e:
                        if self.verbose:
                            self._log(f"    Ошибка чтения данных: {e}", "DEBUG")
                    finally:
                        driver.disconnect()
            except Exception as e:
                if self.verbose:
                    self._log(f"    Ошибка проверки (скорость {baudrate}): {str(e)[:50]}", "DEBUG")
        return None

    def get_found_devices(self) -> List[Dict]:
        """Получение списка найденных устройств в формате словарей."""
        return [device.to_dict() for device in self.found_devices]

    def print_results(self):
        """Вывод результатов сканирования в удобном формате."""
        if not self.found_devices:
            print("\n" + "=" * 60)
            print("УСТРОЙСТВА НЕ НАЙДЕНЫ")
            print("=" * 60)
            print("Рекомендации:")
            print("1. Проверьте подключение устройств")
            print("2. Убедитесь, что драйверы COM-портов установлены")
            print("3. Проверьте питание устройств")
            print("4. Попробуйте запустить сканирование с правами администратора")
            return

        print("\n" + "=" * 60)
        print(f"НАЙДЕНО УСТРОЙСТВ: {len(self.found_devices)}")
        print("=" * 60)

        for i, device in enumerate(self.found_devices, 1):
            print(f"\n{i}. {device}")
            print(f"   Описание: {device.description}")

            if device.additional_info:
                print("   Доп. информация:")
                for key, value in device.additional_info.items():
                    if key == 'relay_states' and isinstance(value, dict):
                        print(f"     Состояния реле:")
                        for relay, state in value.items():
                            print(f"       {relay}: {state}")
                    else:
                        print(f"     {key}: {value}")

        print("\n" + "=" * 60)
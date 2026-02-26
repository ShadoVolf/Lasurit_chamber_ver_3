
import time
from enum import Enum
from typing import Optional, Dict, List, Union, Any
import serial





class RelayState(Enum):
    """Состояния реле."""
    OPEN = 0  # COM подключен к NO
    CLOSE = 1  # COM подключен к NC
    UNKNOWN = 2


class RelayMode(Enum):
    """Режимы работы реле."""
    NORMAL = "normal"  # Обычный режим
    TOGGLE = "toggle"  # Переключение
    MOMENTARY = "momentary"  # Мгновенное срабатывание
    INTERLOCK = "interlock"  # Взаимоблокировка


class RS232RelayDriver:
    """
    Драйвер для релейной платы RS232-4pin-Relay.
    """

    # Конфигурация всех команд устройства
    COMMANDS = {
        # ============ СТАТУС И ИНФОРМАЦИЯ ============
        "STATUS": {
            "command": bytes.fromhex("55 56 00 00 00 00 00 AB"),
            "response_bytes": 8,
            "name": "Статус реле",
            "read_only": True
        },

        # ============ КОМАНДЫ УПРАВЛЕНИЯ РЕЛЕ 1 ============
        "RELAY1.OPEN": {
            "command": bytes.fromhex("55 56 00 00 00 01 01 AD"),
            "response_bytes": 0,
            "name": "Открыть реле 1"
        },
        "RELAY1.CLOSE": {
            "command": bytes.fromhex("55 56 00 00 00 01 02 AE"),
            "response_bytes": 0,
            "name": "Закрыть реле 1"
        },
        "RELAY1.TOGGLE": {
            "command": bytes.fromhex("55 56 00 00 00 01 03 AF"),
            "response_bytes": 0,
            "name": "Переключить реле 1"
        },
        "RELAY1.MOMENTARY": {
            "command": bytes.fromhex("55 56 00 00 00 01 04 B0"),
            "response_bytes": 0,
            "name": "Мгновенное реле 1"
        },
        "RELAY1.INTERLOCK": {
            "command": bytes.fromhex("55 56 00 00 00 01 05 B1"),
            "response_bytes": 0,
            "name": "Блокировка реле 1"
        },

        # ============ КОМАНДЫ УПРАВЛЕНИЯ РЕЛЕ 2 ============
        "RELAY2.OPEN": {
            "command": bytes.fromhex("55 56 00 00 00 02 01 AE"),
            "response_bytes": 0,
            "name": "Открыть реле 2"
        },
        "RELAY2.CLOSE": {
            "command": bytes.fromhex("55 56 00 00 00 02 02 AF"),
            "response_bytes": 0,
            "name": "Закрыть реле 2"
        },
        "RELAY2.TOGGLE": {
            "command": bytes.fromhex("55 56 00 00 00 02 03 B0"),
            "response_bytes": 0,
            "name": "Переключить реле 2"
        },
        "RELAY2.MOMENTARY": {
            "command": bytes.fromhex("55 56 00 00 00 02 04 B1"),
            "response_bytes": 0,
            "name": "Мгновенное реле 2"
        },
        "RELAY2.INTERLOCK": {
            "command": bytes.fromhex("55 56 00 00 00 02 05 B2"),
            "response_bytes": 0,
            "name": "Блокировка реле 2"
        },

        # ============ КОМАНДЫ УПРАВЛЕНИЯ РЕЛЕ 3 ============
        "RELAY3.OPEN": {
            "command": bytes.fromhex("55 56 00 00 00 03 01 AF"),
            "response_bytes": 0,
            "name": "Открыть реле 3"
        },
        "RELAY3.CLOSE": {
            "command": bytes.fromhex("55 56 00 00 00 03 02 B0"),
            "response_bytes": 0,
            "name": "Закрыть реле 3"
        },
        "RELAY3.TOGGLE": {
            "command": bytes.fromhex("55 56 00 00 00 03 03 B1"),
            "response_bytes": 0,
            "name": "Переключить реле 3"
        },
        "RELAY3.MOMENTARY": {
            "command": bytes.fromhex("55 56 00 00 00 03 04 B2"),
            "response_bytes": 0,
            "name": "Мгновенное реле 3"
        },
        "RELAY3.INTERLOCK": {
            "command": bytes.fromhex("55 56 00 00 00 03 05 B3"),
            "response_bytes": 0,
            "name": "Блокировка реле 3"
        },

        # ============ КОМАНДЫ УПРАВЛЕНИЯ РЕЛЕ 4 ============
        "RELAY4.OPEN": {
            "command": bytes.fromhex("55 56 00 00 00 04 01 B0"),
            "response_bytes": 0,
            "name": "Открыть реле 4"
        },
        "RELAY4.CLOSE": {
            "command": bytes.fromhex("55 56 00 00 00 04 02 B1"),
            "response_bytes": 0,
            "name": "Закрыть реле 4"
        },
        "RELAY4.TOGGLE": {
            "command": bytes.fromhex("55 56 00 00 00 04 03 B2"),
            "response_bytes": 0,
            "name": "Переключить реле 4"
        },
        "RELAY4.MOMENTARY": {
            "command": bytes.fromhex("55 56 00 00 00 04 04 B3"),
            "response_bytes": 0,
            "name": "Мгновенное реле 4"
        },
        "RELAY4.INTERLOCK": {
            "command": bytes.fromhex("55 56 00 00 00 04 05 B4"),
            "response_bytes": 0,
            "name": "Блокировка реле 4"
        },
    }

    def __init__(self, port: str, baudrate: int = 9600,
                 timeout: float = 1.0, retries: int = 3):
        """
        Инициализация драйвера для релейной платы RS232-4pin-Relay.

        :param port: Последовательный порт (COMx на Windows, /dev/ttyX на Linux)
        :param baudrate: Скорость обмена данными (по умолчанию 9600)
        :param timeout: Таймаут чтения/записи в секундах
        :param retries: Количество повторных попыток при ошибках
        """
        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout
        self.retries = retries

        # Создание последовательного соединения
        self._serial: Optional[serial.Serial] = None

        # Флаги состояния
        self._connected = False
        self._last_error = None
        self._debug = False

        # Параметры устройства
        self._channels = 4
        self._version = "1.0"
        self._manufacturer = "RS232-4pin-Relay"

    def enable_debug(self, enabled: bool = True):
        """Включение/выключение отладки."""
        self._debug = enabled

    def connect(self) -> bool:
        """Подключение к устройству."""
        try:
            self._serial = serial.Serial(
                port=self.port,
                baudrate=self.baudrate,
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                timeout=self.timeout
            )

            if self._serial.is_open:
                self._connected = True
                if self._debug:
                    print(f"Подключение к {self.port}: успешно")
                return True
            else:
                if self._debug:
                    print(f"Не удалось открыть порт {self.port}")
                return False

        except serial.SerialException as e:
            self._last_error = str(e)
            if self._debug:
                print(f"Ошибка подключения: {e}")
            return False
        except Exception as e:
            self._last_error = str(e)
            if self._debug:
                print(f"Неожиданная ошибка при подключении: {e}")
            return False

    def disconnect(self):
        """Отключение от устройства."""
        if self._serial and self._serial.is_open:
            self._serial.close()
        self._connected = False

        if self._debug:
            print("Отключено от устройства")

    def is_connected(self) -> bool:
        """Проверка подключения."""
        return self._connected and self._serial is not None and self._serial.is_open

    def get_last_error(self) -> str:
        """Получение последней ошибки."""
        return self._last_error or "Нет ошибок"

    def _send_command(self, cmd_name: str, retries: Optional[int] = None) -> Optional[bytes]:
        """
        Отправка команды на устройство с повторными попытками.

        :param cmd_name: Имя команды из COMMANDS
        :param retries: Количество повторных попыток (по умолчанию из настроек)
        :return: Ответ от устройства или None при ошибке
        """
        if cmd_name not in self.COMMANDS:
            self._last_error = f"Неизвестная команда: {cmd_name}"
            return None

        if not self.is_connected():
            self._last_error = "Устройство не подключено"
            return None

        command_config = self.COMMANDS[cmd_name]
        command = command_config["command"]
        expected_response_bytes = command_config.get("response_bytes", 0)

        retries = retries if retries is not None else self.retries

        for attempt in range(retries):
            try:
                if self._debug:
                    print(f"Отправка команды {cmd_name}: {command.hex().upper()}")

                # Очистка буферов перед отправкой
                self._serial.reset_input_buffer()
                self._serial.reset_output_buffer()

                # Отправка команды
                self._serial.write(command)

                # Если ожидается ответ
                if expected_response_bytes > 0:
                    time.sleep(0.1)  # Небольшая задержка для ответа
                    response = self._serial.read(expected_response_bytes)

                    if response and len(response) == expected_response_bytes:
                        if self._debug:
                            print(f"Получен ответ: {response.hex().upper()}")
                        return response
                    else:
                        if self._debug:
                            print(f"Неполный ответ: {response.hex().upper() if response else 'Нет ответа'}")
                        continue
                else:
                    # Для команд без ответа просто возвращаем команду
                    return command

            except serial.SerialException as e:
                self._last_error = f"Попытка {attempt + 1}/{retries} не удалась: {e}"
                if self._debug:
                    print(f"  Ошибка: {e}")
                if attempt < retries - 1:
                    time.sleep(0.1 * (attempt + 1))  # Экспоненциальная задержка
                else:
                    return None
            except Exception as e:
                self._last_error = f"Неожиданная ошибка: {e}"
                if self._debug:
                    print(f"  Неожиданная ошибка: {e}")
                return None

        return None

    # ============ ВЫСОКОУРОВНЕВЫЕ МЕТОДЫ ============

    def get_device_info(self) -> Dict[str, Any]:
        """Получение информации об устройстве."""
        return {
            "port": self.port,
            "baudrate": self.baudrate,
            "timeout": self.timeout,
            "retries": self.retries,
            "connected": self.is_connected(),
            "channels": self._channels,
            "version": self._version,
            "manufacturer": self._manufacturer,
        }

    def read_status(self) -> Dict[str, Any]:
        """
        Чтение статуса всех реле.

        :return: Словарь с состоянием каждого реле
        """
        response = self._send_command("STATUS")

        if not response or len(response) != 8:
            self._last_error = "Ошибка чтения статуса: неверный ответ"
            return {}
        # Парсинг ответа (предполагаем, что биты состояния находятся в 7-м байте)
        # В спецификации устройства должно быть указано, в каком байте хранится статус
        status_byte = response[6]
        states = {}

        for channel in range(1, self._channels + 1):
            # Проверяем бит для каждого канала
            # Предполагаем: бит 0 = канал 1, бит 1 = канал 2 и т.д.
            # 1 = открыто (NO), 0 = закрыто (NC)
            bit_mask = 1 << (channel - 1)
            if status_byte & bit_mask:
                states[f"RELAY{channel}"] = RelayState.OPEN
            else:
                states[f"RELAY{channel}"] = RelayState.CLOSE

        return {
            "raw_response": response.hex().upper(),
            "status_byte": status_byte,
            "relay_states": states,
        }

    def set_relay_state(self, channel: int, state: RelayState,
                        mode: RelayMode = RelayMode.NORMAL) -> bool:
        """
        Установка состояния реле.

        :param channel: Номер канала (1-4)
        :param state: Состояние реле (OPEN/CLOSE)
        :param mode: Режим работы реле
        :return: True если команда отправлена успешно, иначе False
        """
        if channel not in range(1, self._channels + 1):
            self._last_error = f"Неверный номер канала. Допустимые значения: 1-{self._channels}"
            return False

        # Определяем имя команды на основе параметров
        cmd_suffix = ""
        if mode == RelayMode.NORMAL:
            cmd_suffix = "OPEN" if state == RelayState.OPEN else "CLOSE"
        elif mode == RelayMode.TOGGLE:
            cmd_suffix = "TOGGLE"
        elif mode == RelayMode.MOMENTARY:
            cmd_suffix = "MOMENTARY"
        elif mode == RelayMode.INTERLOCK:
            cmd_suffix = "INTERLOCK"
        else:
            self._last_error = f"Неподдерживаемый режим: {mode}"
            return False

        cmd_name = f"RELAY{channel}.{cmd_suffix}"

        if cmd_name not in self.COMMANDS:
            self._last_error = f"Команда не найдена: {cmd_name}"
            return False

        result = self._send_command(cmd_name)
        return result is not None

    def open_relay(self, channel: int) -> bool:
        """
        Открыть реле (COM подключается к NO).

        :param channel: Номер канала (1-4)
        :return: True если команда отправлена успешно, иначе False
        """
        return self.set_relay_state(channel, RelayState.OPEN, RelayMode.NORMAL)

    def close_relay(self, channel: int) -> bool:
        """
        Закрыть реле (COM отключается от NO и подключается к NC).

        :param channel: Номер канала (1-4)
        :return: True если команда отправлена успешно, иначе False
        """
        return self.set_relay_state(channel, RelayState.CLOSE, RelayMode.NORMAL)

    def toggle_relay(self, channel: int) -> bool:
        """
        Переключить состояние реле.

        :param channel: Номер канала (1-4)
        :return: True если команда отправлена успешно, иначе False
        """
        return self.set_relay_state(channel, RelayState.OPEN, RelayMode.TOGGLE)

    def momentary_relay(self, channel: int, duration_ms: int = 200) -> bool:
        """
        Мгновенное срабатывание реле.

        :param channel: Номер канала (1-4)
        :param duration_ms: Длительность срабатывания в мс (только для информации)
        :return: True если команда отправлена успешно, иначе False
        """
        if self._debug:
            print(f"Мгновенное срабатывание канала {channel} на {duration_ms} мс")
        return self.set_relay_state(channel, RelayState.OPEN, RelayMode.MOMENTARY)

    def interlock_relay(self, channel: int) -> bool:
        """
        Включение реле с взаимоблокировкой.

        :param channel: Номер канала (1-4)
        :return: True если команда отправлена успешно, иначе False
        """
        return self.set_relay_state(channel, RelayState.OPEN, RelayMode.INTERLOCK)

    def open_all_relays(self) -> bool:
        """
        Открытие всех реле.

        :return: True если все команды отправлены успешно, иначе False
        """
        success = True
        for channel in range(1, self._channels + 1):
            if not self.open_relay(channel):
                success = False
        return success

    def close_all_relays(self) -> bool:
        """
        Закрытие всех реле.

        :return: True если все команды отправлены успешно, иначе False
        """
        success = True
        for channel in range(1, self._channels + 1):
            if not self.close_relay(channel):
                success = False
        return success

    def get_relay_states(self) -> Dict[str, RelayState]:
        """
        Получение состояний всех реле.

        :return: Словарь с состояниями реле
        """
        status = self.read_status()
        return status.get("relay_states", {})

    def get_relay_state(self, channel: int) -> Optional[RelayState]:
        """
        Получение состояния конкретного реле.

        :param channel: Номер канала (1-4)
        :return: Состояние реле или None при ошибке
        """
        states = self.get_relay_states()
        key = f"RELAY{channel}"
        return states.get(key)

    def execute_raw_command(self, command_hex: str) -> Optional[str]:
        """
        Выполнение сырой команды в hex-формате.

        :param command_hex: Команда в hex-формате (например, "55 56 00 00 00 01 01 AD")
        :return: Ответ в hex-формате или None при ошибке
        """
        try:
            # Удаляем пробелы и преобразуем в байты
            clean_hex = command_hex.replace(" ", "")
            if len(clean_hex) % 2 != 0:
                self._last_error = "Неверная длина hex-строки"
                return None

            command = bytes.fromhex(clean_hex)

            if self._debug:
                print(f"Выполнение сырой команды: {clean_hex.upper()}")

            # Отправка команды
            self._serial.reset_input_buffer()
            self._serial.reset_output_buffer()
            self._serial.write(command)

            # Чтение ответа (если есть)
            time.sleep(0.1)
            response = self._serial.read(8)  # Стандартная длина ответа

            if response:
                return response.hex().upper()
            else:
                return ""

        except ValueError as e:
            self._last_error = f"Неверный формат hex-строки: {e}"
            return None
        except Exception as e:
            self._last_error = str(e)
            return None

    def get_all_parameters(self) -> Dict[str, Any]:
        """Получение всех параметров устройства."""
        return {
            "device_info": self.get_device_info(),
            "relay_states": self.get_relay_states(),
            "connection_status": {
                "connected": self.is_connected(),
                "port": self.port,
                "baudrate": self.baudrate,
                "last_error": self.get_last_error(),
            },
        }





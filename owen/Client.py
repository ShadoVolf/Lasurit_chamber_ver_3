import struct
from enum import Enum
from typing import Optional, Dict, List, Union, Any
from pymodbus.client import ModbusSerialClient
from pymodbus.exceptions import ModbusException


class ByteOrder(Enum):
    """Порядок байтов."""
    BIG_ENDIAN = 'big'
    LITTLE_ENDIAN = 'little'
    BIG_ENDIAN_SWAP = 'big_swap'
    LITTLE_ENDIAN_SWAP = 'little_swap'


class ControlMode(Enum):
    """Режимы регулирования."""
    MANUAL = 2
    RUN = 1
    STOP = 0


class OutputLogic(Enum):
    """Типы логики работы выходов."""
    OFF = 0
    C_PID = 1
    H_PID = 2
    ALARM = 3
    CONV = 3


class AlarmType(Enum):
    """Типы сигнализаторов."""
    OFF = 0
    SP_P = 1
    SP_U = 2
    SP_HI = 3
    SP_LO = 4
    O_P = 5
    O_U = 6
    O_HI = 7
    O_LO = 8


class TRM12Driver:
    """
    Драйвер для контроллера температуры ТРМ12.
    """

    # Конфигурация всех параметров устройства
    PARAMETERS = {
        # ============ ИНФОРМАЦИЯ ОБ УСТРОЙСТВЕ ============
        "STAT": {"type": "U16", "index": {None: 0x1008}, "name": "Статус устройства"},
        "DEV": {"type": "STR", "index": {None: 0x1000}, "length": 8, "name": "Идентификатор устройства"},
        "VER": {"type": "STR", "index": {None: 0x1004}, "length": 8, "name": "Версия прошивки"},

        # ============ ТЕКУЩИЕ ЗНАЧЕНИЯ ============
        "PV": {"type": "F32", "index": {0: 0x1009, 1: 0x100B}, "name": "Текущее значение"},
        "FUN": {"type": "F32", "index": {0: 0x100D, 1: 0x100F}, "name": "Значение функции"},
        "SP": {"type": "F32", "index": {0: 0x100F, 1: 0x1011}, "name": "Уставка"},
        "OUT.P": {"type": "F32", "index": {0: 0x1013, 1: 0x1017}, "name": "Выходная мощность"},

        # ============ РЕЖИМЫ УПРАВЛЕНИЯ ============
        "CTRL": {"type": "U16", "index": {None: 0x1015}, "name": "Режим регулирования"},
        "RESET": {"type": "U16", "index": {None: 0x1016}, "name": "Сброс устройства"},

        # ============ ТОЧКИ КОРРЕКЦИИ ТЕМПЕРАТУРЫ ============
        "COR1.POINT": {"type": "F32", "index": {0: 0x0016, 1: 0x0116}, "name": "Точка коррекции 1"},
        "COR1.OFFSET": {"type": "F32", "index": {0: 0x0018, 1: 0x0118}, "name": "Смещение коррекции 1"},
        "COR1.CLR": {"type": "U16", "index": {0: 0x001A, 1: 0x011A}, "name": "Очистка коррекции 1"},

        "COR2.POINT": {"type": "F32", "index": {0: 0x001B, 1: 0x011B}, "name": "Точка коррекции 2"},
        "COR2.OFFSET": {"type": "F32", "index": {0: 0x001D, 1: 0x011D}, "name": "Смещение коррекции 2"},
        "COR2.CLR": {"type": "U16", "index": {0: 0x001F, 1: 0x011F}, "name": "Очистка коррекции 2"},

        "COR3.POINT": {"type": "F32", "index": {0: 0x0020, 1: 0x0120}, "name": "Точка коррекции 3"},
        "COR3.OFFSET": {"type": "F32", "index": {0: 0x0022, 1: 0x0122}, "name": "Смещение коррекции 3"},
        "COR3.CLR": {"type": "U16", "index": {0: 0x0024, 1: 0x0124}, "name": "Очистка коррекции 3"},

        # ============ ПИД-РЕГУЛЯТОР ============
        "PID.P": {"type": "F32", "index": {0: 0x0280}, "name": "Пропорциональная составляющая"},
        "PID.I": {"type": "U16", "index": {0: 0x0282}, "name": "Интегральная постоянная"},
        "PID.D": {"type": "U16", "index": {0: 0x0283}, "name": "Дифференциальная постоянная"},
        "USP": {"type": "F32", "index": {0: 0x0285}, "name": "Скорость изменения уставки"},
        "D.BND": {"type": "F32", "index": {0: 0x0289}, "name": "Зона нечувствительности"},

        # ============ ОГРАНИЧЕНИЯ ВЫХОДА ПИД ============
        "OL.L": {"type": "F32", "index": {0: 0x028F}, "name": "Нижний предел выходной мощности"},
        "OL.H": {"type": "F32", "index": {0: 0x0291}, "name": "Верхний предел выходной мощности"},
        "OL.U": {"type": "F32", "index": {0: 0x0293}, "name": "Макс. скорость изменения мощности"},

        # ============ ДИСКРЕТНЫЙ ВЫХОД 1 ============
        "LOG.D": {"type": "U16", "index": {0: 0x0220}, "name": "Тип логики дискретного выхода"},
        "HYST": {"type": "F32", "index": {0: 0x0221}, "name": "Гистерезис дискретного выхода"},

        # ============ АНАЛОГОВЫЙ ВЫХОД 1 ============
        "LOG.A": {"type": "U16", "index": {0: 0x0260}, "name": "Тип логики аналогового выхода"},
        "OUT.L": {"type": "F32", "index": {0: 0x0263}, "name": "Нижняя граница выхода"},
        "OUT.H": {"type": "F32", "index": {0: 0x0265}, "name": "Верхняя граница выхода"},

        # ============ СИГНАЛИЗАТОР ============
        "A.TYP": {"type": "U16", "index": {0: 0x0340}, "name": "Тип сигнализатор"},
        "A.BND": {"type": "F32", "index": {0: 0x0341}, "name": "Порог срабатывания"},
        "A.HYS": {"type": "F32", "index": {0: 0x0343}, "name": "Гистерезис сигнализатора"},

        # ============ ИНДИКАЦИЯ ============
        "SCR1": {"type": "U16", "index": {None: 0x0400}, "name": "Пользовательский экран 1"},
        "OUT.S": {"type": "U16", "index": {None: 0x0406}, "name": "Настройка вывода мощности"},

        # ============ RS-485 НАСТРОЙКИ ============
        "PROT": {"type": "U16", "index": {None: 0x0500}, "name": "Протокол связи"},
        "ADDR": {"type": "U16", "index": {None: 0x0501}, "name": "Адрес устройства"},
        "BAUD": {"type": "U16", "index": {None: 0x0502}, "name": "Скорость обмена"},
        "DPS": {"type": "U16", "index": {None: 0x0503}, "name": "Формат посылки данных"},

        # ============ АВТОНАСТРОЙКА ПИД ============
        "ANR": {"type": "U16", "index": {None: 0x02B0}, "name": "Автонастройка ПИД-регулятора"},
    }

    BAUD_RATE_MAP = {
        0: 2400, 1: 4800, 2: 9600, 3: 14400, 4: 19200,
        5: 28800, 6: 38400, 7: 57600, 8: 115200
    }

    PROTOCOL_MAP = {0: "RTU", 1: "ASCII"}

    def __init__(self, port: str, address: int = 1, baudrate: int = 9600,
                 byte_order: ByteOrder = ByteOrder.BIG_ENDIAN_SWAP,
                 timeout: float = 1.0, retries: int = 3):
        """
        Инициализация драйвера.

        :param port: Последовательный порт
        :param address: Адрес устройства Modbus
        :param baudrate: Скорость обмена
        :param byte_order: Порядок байтов для float32
        :param timeout: Таймаут запроса
        :param retries: Количество повторных попыток
        """
        self.port = port
        self.address = address
        self.baudrate = baudrate
        self.byte_order = byte_order

        # Создание клиента Modbus
        self.client = ModbusSerialClient(
            port=port,
            baudrate=baudrate,
            bytesize=8,
            parity='N',
            stopbits=1,
            timeout=timeout,
            retries=retries
        )

        # Флаги состояния
        self._connected = False
        self._last_error = None
        self._debug = False

    def enable_debug(self, enabled: bool = True):
        """Включение/выключение отладки."""
        self._debug = enabled

    def connect(self) -> bool:
        """Подключение к устройству."""
        try:
            self._connected = self.client.connect()
            if self._debug:
                print(f"Подключение к {self.port}: {self._connected}")
            return self._connected
        except Exception as e:
            self._last_error = str(e)
            if self._debug:
                print(f"Ошибка подключения: {e}")
            return False

    def disconnect(self):
        """Отключение от устройства."""
        if self.client.connected:
            self.client.close()
        self._connected = False

        if self._debug:
            print("Отключено от устройства")

    def is_connected(self) -> bool:
        """Проверка подключения."""
        return self._connected and self.client.connected

    def get_last_error(self) -> str:
        """Получение последней ошибки."""
        return self._last_error or "Нет ошибок"

    def _convert_float32_from_registers(self, registers: List[int]) -> float:
        """Преобразование регистров в float32."""
        if len(registers) != 2:
            raise ValueError(f"Для float32 требуется 2 регистра, получено {len(registers)}")

        reg0, reg1 = registers

        if self.byte_order == ByteOrder.BIG_ENDIAN:
            byte_data = struct.pack('>HH', reg0, reg1)
            result = struct.unpack('>f', byte_data)[0]
        elif self.byte_order == ByteOrder.LITTLE_ENDIAN:
            byte_data = struct.pack('<HH', reg0, reg1)
            result = struct.unpack('<f', byte_data)[0]
        elif self.byte_order == ByteOrder.BIG_ENDIAN_SWAP:
            byte_data = struct.pack('>HH', reg1, reg0)
            result = struct.unpack('>f', byte_data)[0]
        elif self.byte_order == ByteOrder.LITTLE_ENDIAN_SWAP:
            byte_data = struct.pack('<HH', reg1, reg0)
            result = struct.unpack('<f', byte_data)[0]
        else:
            raise ValueError(f"Неизвестный порядок байтов: {self.byte_order}")

        return result

    def _convert_float32_to_registers(self, value: float) -> List[int]:
        """Преобразование float32 в регистры."""
        if self.byte_order == ByteOrder.BIG_ENDIAN:
            byte_data = struct.pack('>f', value)
            reg0, reg1 = struct.unpack('>HH', byte_data)
            result = [reg0, reg1]
        elif self.byte_order == ByteOrder.LITTLE_ENDIAN:
            byte_data = struct.pack('<f', value)
            reg0, reg1 = struct.unpack('<HH', byte_data)
            result = [reg0, reg1]
        elif self.byte_order == ByteOrder.BIG_ENDIAN_SWAP:
            byte_data = struct.pack('>f', value)
            reg0, reg1 = struct.unpack('>HH', byte_data)
            result = [reg1, reg0]
        elif self.byte_order == ByteOrder.LITTLE_ENDIAN_SWAP:
            byte_data = struct.pack('<f', value)
            reg0, reg1 = struct.unpack('<HH', byte_data)
            result = [reg1, reg0]
        else:
            raise ValueError(f"Неизвестный порядок байтов: {self.byte_order}")

        return result

    def _get_parameter_address(self, param_name: str, channel: int = 0) -> tuple:
        """Получение адреса и типа параметра."""
        if param_name not in self.PARAMETERS:
            raise ValueError(f"Параметр '{param_name}' не найден")

        param = self.PARAMETERS[param_name]
        index_dict = param["index"]

        if None in index_dict:
            address = index_dict[None]
        elif channel in index_dict:
            address = index_dict[channel]
        else:
            first_key = next(iter(index_dict.keys()))
            address = index_dict[first_key]

        param_type = param["type"]

        return address, param_type

    def read_parameter(self, param_name: str, channel: int = 0) -> Optional[Union[int, float, str]]:
        """Чтение параметра по имени."""
        try:
            address, param_type = self._get_parameter_address(param_name, channel)

            if self._debug:
                print(f"Чтение {param_name} (канал {channel}) -> адрес {hex(address)}")

            if param_type == "U16":
                response = self.client.read_holding_registers(address, 1, slave=self.address)
                if not response.isError():
                    value = response.registers[0]
                    if self._debug:
                        print(f"  Получено: {value} ({hex(value)})")
                    return value

            elif param_type == "F32":
                response = self.client.read_holding_registers(address, 2, slave=self.address)
                if not response.isError():
                    value = self._convert_float32_from_registers(response.registers)
                    if self._debug:
                        print(f"  Получено: {value}")
                    return value

            elif param_type == "STR":
                length = self.PARAMETERS[param_name].get("length", 8)
                reg_count = (length + 1) // 2
                response = self.client.read_holding_registers(address, reg_count, slave=self.address)
                if not response.isError():
                    bytes_data = b''
                    for reg in response.registers:
                        bytes_data += struct.pack('>H', reg)
                    value = bytes_data.decode('ascii', errors='ignore').rstrip('\x00')
                    if self._debug:
                        print(f"  Получено: '{value}'")
                    return value

            else:
                raise ValueError(f"Неподдерживаемый тип данных: {param_type}")

        except (ModbusException, ValueError, struct.error) as e:
            self._last_error = f"Ошибка чтения параметра {param_name}: {e}"
            if self._debug:
                print(f"  Исключение: {e}")
            return None

        return None

    def write_parameter(self, param_name: str, value: Union[int, float, str], channel: int = 0) -> bool:
        """Запись значения параметра."""
        try:
            address, param_type = self._get_parameter_address(param_name, channel)

            if self._debug:
                print(f"Запись {param_name} (канал {channel}) = {value}")

            if param_type == "U16":
                response = self.client.write_register(address, int(value), slave=self.address)
                return not response.isError()

            elif param_type == "F32":
                registers = self._convert_float32_to_registers(float(value))
                response = self.client.write_registers(address, registers, slave=self.address)
                return not response.isError()

            elif param_type == "STR":
                bytes_data = value.encode('ascii')[:self.PARAMETERS[param_name].get("length", 8)]
                bytes_data = bytes_data.ljust(self.PARAMETERS[param_name].get("length", 8), b'\x00')

                reg_count = len(bytes_data) // 2
                registers = []
                for i in range(0, len(bytes_data), 2):
                    reg = struct.unpack('>H', bytes_data[i:i + 2])[0]
                    registers.append(reg)

                response = self.client.write_registers(address, registers, slave=self.address)
                return not response.isError()

            else:
                raise ValueError(f"Неподдерживаемый тип данных: {param_type}")

        except (ModbusException, ValueError, struct.error) as e:
            self._last_error = f"Ошибка записи параметра {param_name}: {e}"
            if self._debug:
                print(f"  Исключение: {e}")
            return False

    # ============ ВЫСОКОУРОВНЕВЫЕ МЕТОДЫ ============

    def get_device_info(self) -> Dict[str, Any]:
        """Получение информации об устройстве."""
        return {
            "device_id": self.read_parameter("DEV"),
            "firmware_version": self.read_parameter("VER"),
            "status": self.read_parameter("STAT"),
            "modbus_address": self.read_parameter("ADDR"),
            "baudrate": self.read_parameter("BAUD"),
        }

    def get_temperatures(self) -> Dict[str, float]:
        """Получение текущих температур всех каналов."""
        temps = {}
        for i in range(2):
            try:
                pv = self.read_parameter("PV", channel=i)
                if pv is not None:
                    temps[f"Канал {i + 1}"] = pv
            except:
                pass
        return temps

    def get_setpoints(self) -> Dict[str, float]:
        """Получение уставок всех каналов."""
        setpoints = {}
        for i in range(2):
            try:
                sp = self.read_parameter("SP", channel=i)
                if sp is not None:
                    setpoints[f"Канал {i + 1}"] = sp
            except:
                pass
        return setpoints

    def get_control_mode(self) -> Dict[str, Any]:
        """Получение режима регулирования."""
        ctrl = self.read_parameter("CTRL")
        mode_map = {2: "Ручной", 1: "Автоматический", 0: "Остановка"}
        mode_name = mode_map.get(ctrl, f"Неизвестно ({ctrl})")

        return {
            "code": ctrl,
            "name": mode_name,
            "output_power": self.read_parameter("OUT.P", channel=0),
        }

    def set_control_mode(self, mode: Union[int, ControlMode]) -> bool:
        """Установка режима регулирования."""
        if isinstance(mode, ControlMode):
            mode_value = mode.value
        else:
            mode_value = mode
        return self.write_parameter("CTRL", mode_value)

    def get_pid_parameters(self, channel: int = 0) -> Dict[str, Any]:
        """Получение параметров ПИД-регулятора."""
        return {
            "P": self.read_parameter("PID.P", channel),
            "I": self.read_parameter("PID.I", channel),
            "D": self.read_parameter("PID.D", channel),
            "deadband": self.read_parameter("D.BND", channel),
            "output_min": self.read_parameter("OL.L", channel),
            "output_max": self.read_parameter("OL.H", channel),
            "output_rate": self.read_parameter("OL.U", channel),
            "hysteresis": self.read_parameter("HYST", channel),
        }

    def set_pid_parameters(self, P: float = None, I: int = None, D: int = None,
                           deadband: float = None, output_min: float = None,
                           output_max: float = None, channel: int = 0) -> bool:
        """Установка параметров ПИД-регулятора."""
        results = []

        if P is not None:
            results.append(self.write_parameter("PID.P", P, channel))
        if I is not None:
            results.append(self.write_parameter("PID.I", I, channel))
        if D is not None:
            results.append(self.write_parameter("PID.D", D, channel))
        if deadband is not None:
            results.append(self.write_parameter("D.BND", deadband, channel))
        if output_min is not None:
            results.append(self.write_parameter("OL.L", output_min, channel))
        if output_max is not None:
            results.append(self.write_parameter("OL.H", output_max, channel))

        return all(results) if results else True

    def set_setpoint(self, value: float, channel: int = 0) -> bool:
        """Установка уставки температуры."""
        return self.write_parameter("SP", value, channel)

    def get_correction_points(self, channel: int = 0) -> Dict[str, Any]:
        """Получение всех трех точек коррекции температуры."""
        corrections = {}

        corrections["point1"] = {
            "point": self.read_parameter("COR1.POINT", channel),
            "offset": self.read_parameter("COR1.OFFSET", channel),
            "clear": self.read_parameter("COR1.CLR", channel),
        }

        corrections["point2"] = {
            "point": self.read_parameter("COR2.POINT", channel),
            "offset": self.read_parameter("COR2.OFFSET", channel),
            "clear": self.read_parameter("COR2.CLR", channel),
        }

        corrections["point3"] = {
            "point": self.read_parameter("COR3.POINT", channel),
            "offset": self.read_parameter("COR3.OFFSET", channel),
            "clear": self.read_parameter("COR3.CLR", channel),
        }

        return corrections

    def set_correction_point(self, point_num: int, point_value: float,
                             offset: float, channel: int = 0) -> bool:
        """Установка точки коррекции температуры."""
        if point_num not in [1, 2, 3]:
            raise ValueError("Номер точки коррекции должен быть 1, 2 или 3")

        results = []

        if point_num == 1:
            results.append(self.write_parameter("COR1.POINT", point_value, channel))
            results.append(self.write_parameter("COR1.OFFSET", offset, channel))
        elif point_num == 2:
            results.append(self.write_parameter("COR2.POINT", point_value, channel))
            results.append(self.write_parameter("COR2.OFFSET", offset, channel))
        elif point_num == 3:
            results.append(self.write_parameter("COR3.POINT", point_value, channel))
            results.append(self.write_parameter("COR3.OFFSET", offset, channel))

        return all(results)

    def get_output_status(self) -> Dict[str, Any]:
        """Получение статуса выходов."""
        return {
            "output_power_ch1": self.read_parameter("OUT.P", channel=0),
            "output_power_ch2": self.read_parameter("OUT.P", channel=1),
            "discrete_logic": self.read_parameter("LOG.D"),
            "analog_logic": self.read_parameter("LOG.A"),
            "analog_low_limit": self.read_parameter("OUT.L"),
            "analog_high_limit": self.read_parameter("OUT.H"),
        }

    def get_communication_settings(self) -> Dict[str, Any]:
        """Получение настроек связи."""
        baud_code = self.read_parameter("BAUD")
        baud_rate = self.BAUD_RATE_MAP.get(baud_code, "Неизвестно")

        protocol_code = self.read_parameter("PROT")
        protocol = self.PROTOCOL_MAP.get(protocol_code, "Неизвестно")

        return {
            "protocol": f"{protocol} ({protocol_code})",
            "address": self.read_parameter("ADDR"),
            "baudrate": f"{baud_rate} бод ({baud_code})",
            "data_format": self.read_parameter("DPS"),
        }

    def start_autotune(self) -> bool:
        """Запуск автонастройки ПИД."""
        return self.write_parameter("ANR", 1)

    def stop_autotune(self) -> bool:
        """Остановка автонастройки ПИД."""
        return self.write_parameter("ANR", 0)

    def get_all_parameters(self) -> Dict[str, Any]:
        """Получение всех основных параметров устройства."""
        return {
            "device_info": self.get_device_info(),
            "temperatures": self.get_temperatures(),
            "setpoints": self.get_setpoints(),
            "control_mode": self.get_control_mode(),
            "pid_parameters": self.get_pid_parameters(),
            "correction_points": self.get_correction_points(),
            "output_status": self.get_output_status(),
            "communication_settings": self.get_communication_settings(),
        }
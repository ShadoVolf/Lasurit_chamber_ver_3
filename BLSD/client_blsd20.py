from enum import IntEnum
from typing import Optional, Union, Tuple, Dict
from pymodbus.client import ModbusSerialClient
from pymodbus.exceptions import ModbusException
from pymodbus.transaction import ModbusRtuFramer

from BLSD.blsd_errors import BLSD20ErrorHandler


class BLSD20ModbusDriver:
    """
    Драйвер для управления BLSD-20Modbus контроллером бесколлекторного двигателя
    через интерфейс Modbus RTU/ASCII.
    """

    # Системные регистры (Holding Registers)
    REG_SYSTEM_AX = 0x7000
    REG_SYSTEM_BX = 0x7001
    REG_SYSTEM_CX = 0x7002
    REG_SYSTEM_DX = 0x7003
    REG_SYSTEM_EX = 0x7004
    REG_SYSTEM_FX = 0x7005
    REG_SYSTEM_PC = 0x7006

    # Регистры управления (Coils)
    COIL_START = 0x2000
    COIL_STOP = 0x2001
    COIL_HARD_STOP = 0x2002
    COIL_CLEAR_POSITION = 0x2003

    # Регистры состояния (Input Registers)
    REG_STATUS = 0x3000
    REG_CURRENT = 0x3001
    REG_SPEED = 0x3002
    REG_POSITION = 0x3003  # 32-bit, занимает 2 регистра
    REG_TEMP_MCU = 0x3005
    REG_TEMP_MOSFET = 0x3006
    REG_TEMP_BRAKE = 0x3007
    REG_TASK_COUNTER = 0x3008

    # Регистры идентификации (Input Registers)
    REG_HW_MAJOR = 0x8001  # Тип драйвера
    REG_HW_MINOR = 0x8002  # Версия аппаратной части
    REG_FW_MAJOR = 0x8003  # Идентификатор ПО
    REG_FW_MINOR = 0x8004  # Версия ПО

    # Регистры настройки (Holding Registers)
    REG_SLAVE_ADDR = 0x5000
    REG_MODBUS_TYPE = 0x5001
    REG_MODBUS_BAUD = 0x5002
    REG_TIMEOUT = 0x5003
    REG_MODE_DEVICE = 0x5004
    REG_MODE_USER_PROGRAM = 0x5005
    REG_MODE_ROTATION = 0x5006
    REG_MODE_EXT_IN = 0x5007
    REG_POSITION_N = 0x5008
    REG_REF_CURRENT = 0x5009
    REG_HOLD_CURRENT = 0x500A
    REG_SET_SPEED = 0x500B
    REG_ACCELERATION = 0x500C
    REG_DECELERATION = 0x500D
    REG_DIRECTION = 0x500E
    REG_N_POLES = 0x500F
    REG_USE_EXTERN_SPEED = 0x5010
    REG_OFFSET = 0x5015  # 32-bit
    REG_TARGET_POSITION = 0x5017  # 32-bit
    REG_POSITION1 = 0x5019  # 32-bit
    REG_POSITION2 = 0x501B  # 32-bit
    REG_POSITION3 = 0x501D  # 32-bit
    REG_POSITION4 = 0x501F  # 32-bit
    REG_ERROR = 0x5021
    REG_FLAG_SAVE_INI = 0x5022
    REG_FLAG_SAVE_PROGRAM = 0x5023
    REG_FLAG_RESTART = 0x5024

    # Состояния двигателя
    class MotorStatus(IntEnum):
        STOPPED = 0
        FORWARD = 1
        REVERSE = 2

    # Режимы работы
    class DeviceMode(IntEnum):
        MODBUS = 1
        EXTERNAL = 2

    # Направления вращения
    class Direction(IntEnum):
        FORWARD = 1
        REVERSE = 2

    # Режимы вращения
    class RotationMode(IntEnum):
        CONTINUOUS = 1
        OFFSET = 2
        POSITIONING = 3

    def __init__(self, port: str, slave_id: int = 1, baudrate: int = 115200,
                 timeout: float = 1.0, Motor_Type: str = 'FL42BLS02'):
        """
        Инициализация драйвера.

        Args:
            port: COM порт (например, 'COM3' или '/dev/ttyUSB0')
            slave_id: Modbus адрес устройства (по умолчанию 1)
            baudrate: Скорость передачи (по умолчанию 115200)
            timeout: Таймаут подключения в секундах
            Motor_Type: Тип двигателя
        """
        self.slave_id = slave_id
        self.connected = False
        self.n_pole = 8 if Motor_Type == 'FL42BLS02' else 4

        # Инициализация реального клиента с явным указанием RTU фреймера
        self.client = ModbusSerialClient(
            port=port,
            framer=ModbusRtuFramer,  # Явное указание RTU-режима
            baudrate=baudrate,
            bytesize=8,
            parity='E',  # Четность (Even)
            stopbits=1,
            timeout=timeout
        )

    def connect(self) -> bool:
        """Подключение к устройству."""
        try:
            self.connected = self.client.connect()
            if self.connected:
                # Проверяем подключение чтением регистра статуса
                test = self.get_status()
                return test is not None
        except Exception:
            pass
        return False

    def disconnect(self):
        """Отключение от устройства."""
        if self.connected:
            self.client.close()
            self.connected = False

    def _read_holding_register(self, address: int, count: int = 1) -> Optional[list]:
        """Чтение holding регистров."""
        try:
            response = self.client.read_holding_registers(
                address=address,
                count=count,
                slave=self.slave_id
            )
            if not response.isError():
                return response.registers
        except ModbusException:
            pass
        return None

    def _read_input_register(self, address: int, count: int = 1) -> Optional[list]:
        """Чтение input регистров."""
        try:
            response = self.client.read_input_registers(
                address=address,
                count=count,
                slave=self.slave_id
            )
            if not response.isError():
                return response.registers
        except ModbusException:
            pass
        return None

    def _write_register(self, address: int, values: Union[int, list]) -> bool:
        """Запись регистров."""
        try:
            if isinstance(values, int):
                values = [values]

            response = self.client.write_registers(
                address=address,
                values=values,
                slave=self.slave_id
            )
            return not response.isError()
        except ModbusException:
            return False

    def _write_coil(self, address: int, value: bool) -> bool:
        """Запись в coil (1-битный регистр)."""
        try:
            response = self.client.write_coil(
                address=address,
                value=value,
                slave=self.slave_id
            )
            return not response.isError()
        except ModbusException:
            return False

    # ===== Базовые операции управления =====

    def start_motor(self) -> bool:
        """Запуск двигателя с заданным ускорением."""
        return self._write_coil(self.COIL_START, True)

    def stop_motor(self) -> bool:
        """Остановка двигателя с заданным замедлением."""
        return self._write_coil(self.COIL_STOP, True)

    def emergency_stop(self) -> bool:
        """Аварийная остановка двигателя."""
        return self._write_coil(self.COIL_HARD_STOP, True)

    def clear_position(self) -> bool:
        """Сброс регистра позиции в ноль."""
        return self._write_coil(self.COIL_CLEAR_POSITION, True)

    # ===== Чтение состояния =====

    def get_status(self) -> Optional[int]:
        """Получение текущего состояния двигателя."""
        result = self._read_input_register(self.REG_STATUS)
        return result[0] if result else None

    def get_current(self) -> Optional[int]:
        """Получение текущего потребления (мА)."""
        result = self._read_input_register(self.REG_CURRENT)
        return result[0] if result else None

    def get_speed(self) -> Optional[int]:
        """Получение текущей скорости (об/мин)."""
        result = self._read_input_register(self.REG_SPEED)
        return result[0] if result else None

    def get_position(self) -> Optional[int]:
        """Получение текущей позиции (32-bit значение)."""
        result = self._read_input_register(self.REG_POSITION, 2)
        if result and len(result) >= 2:
            return self._from_32bit(result[0], result[1])
        return None

    def get_temperatures(self) -> dict:
        """Получение температур всех компонентов."""
        temps = {}
        regs = [self.REG_TEMP_MCU, self.REG_TEMP_MOSFET, self.REG_TEMP_BRAKE]
        names = ['mcu', 'mosfet', 'brake']

        for reg, name in zip(regs, names):
            result = self._read_input_register(reg)
            if result:
                temps[name] = result[0] / 10.0

        return temps

    def get_errors(self) -> Optional[int]:
        """Чтение регистра ошибок."""
        result = self._read_holding_register(self.REG_ERROR)
        return result[0] if result else None

    def get_detailed_error_info(self, format_type: str = "text") -> Union[dict, str]:
        """Получение подробной информации об ошибках устройства."""
        try:
            error_code = self.get_errors()
            if error_code is None:
                return "Не удалось прочитать регистр ошибок"

            if format_type == "dict":
                return BLSD20ErrorHandler.get_error_description(error_code)
            else:
                return BLSD20ErrorHandler.format_error_report(error_code, format_type)

        except Exception:
            return "Ошибка при получении информации об ошибках"

    def get_device_info(self) -> dict:
        """Получение информации об устройстве."""
        info = {}
        register_mapping = {
            self.REG_HW_MAJOR: "Тип драйвера",
            self.REG_HW_MINOR: "Версия аппаратной части",
            self.REG_FW_MAJOR: "Идентификатор ПО",
            self.REG_FW_MINOR: "Версия ПО"
        }

        for reg_addr, description in register_mapping.items():
            result = self._read_input_register(reg_addr)
            if result is not None:
                value = result[0]
                if description == "Тип драйвера" and value == 1000:
                    info[description] = "BLSD-20ModBus"
                else:
                    info[description] = value
                info[f"{description} (hex)"] = hex(value)
            else:
                info[description] = "Нет данных"

        return info

    # ===== Управление параметрами =====

    def get_set_speed(self) -> Optional[int]:
        """Получение установленной скорости вращения."""
        value = self._read_holding_register(self.REG_SET_SPEED)
        return value[0] if value else None

    def set_speed(self, speed: int) -> bool:
        """Установка скорости вращения (0-4000 об/мин)."""
        speed = max(0, min(4000, speed))
        return self._write_register(self.REG_SET_SPEED, speed)

    def set_acceleration(self, acc: int) -> bool:
        """Установка ускорения (10-1000)."""
        acc = max(10, min(1000, acc))
        return self._write_register(self.REG_ACCELERATION, acc)

    def set_deceleration(self, dec: int) -> bool:
        """Установка замедления (10-1000)."""
        dec = max(10, min(1000, dec))
        return self._write_register(self.REG_DECELERATION, dec)

    def set_direction(self, direction: Direction) -> bool:
        """Установка направления вращения."""
        return self._write_register(self.REG_DIRECTION, direction.value)

    def set_current_limit(self, current_ma: int) -> bool:
        """Установка ограничения тока (1000-20000 мА)."""
        current_ma = max(1000, min(20000, current_ma))
        return self._write_register(self.REG_REF_CURRENT, current_ma)

    def set_hold_current(self, current_ma: int) -> bool:
        """Установка тока удержания (0-1000 мА)."""
        current_ma = max(0, min(1000, current_ma))
        return self._write_register(self.REG_HOLD_CURRENT, current_ma)

    def set_device_mode(self, mode: DeviceMode) -> bool:
        """Установка режима работы устройства."""
        return self._write_register(self.REG_MODE_DEVICE, mode.value)

    def set_rotation_mode(self, mode: RotationMode) -> bool:
        """Установка режима вращения."""
        return self._write_register(self.REG_MODE_ROTATION, mode.value)

    def _to_32bit(self, value: int) -> Tuple[int, int]:
        """Преобразование 32-битного числа в два 16-битных регистра."""
        if value < 0:
            value = (1 << 32) + value
        low_word = value & 0xFFFF
        high_word = (value >> 16) & 0xFFFF
        return low_word, high_word

    def _from_32bit(self, low_word: int, high_word: int) -> int:
        """Преобразование двух 16-битных регистров в 32-битное число."""
        value = (high_word << 16) | low_word
        if value & 0x80000000:
            value = value - (1 << 32)
        return value

    def set_position(self, position: int, position_num: int = 1) -> bool:
        """Установка целевой позиции."""
        reg_map = {
            1: self.REG_POSITION1,
            2: self.REG_POSITION2,
            3: self.REG_POSITION3,
            4: self.REG_POSITION4
        }
        reg = reg_map.get(position_num)
        if not reg:
            raise ValueError("Номер позиции должен быть от 1 до 4")

        low_word, high_word = self._to_32bit(position)
        return self._write_register(reg, [low_word, high_word])

    def move_to_position(self, position_num: int) -> bool:
        """Перемещение в заданную позицию."""
        if position_num < 1 or position_num > 4:
            return False

        if not self.set_rotation_mode(self.RotationMode.POSITIONING):
            return False

        if not self._write_register(self.REG_POSITION_N, position_num):
            return False

        return self.start_motor()

    def move_offset(self, offset: int) -> bool:
        """Перемещение на заданное смещение."""
        if not self.set_rotation_mode(self.RotationMode.OFFSET):
            return False

        low_word, high_word = self._to_32bit(offset)
        if not self._write_register(self.REG_OFFSET, [low_word, high_word]):
            return False

        return self.start_motor()

    # ===== Системные функции =====

    def save_settings(self) -> bool:
        """Сохранение настроек в энергонезависимую память."""
        return self._write_register(self.REG_FLAG_SAVE_INI, 0x37FA)

    def restart_device(self) -> bool:
        """Перезагрузка устройства."""
        return self._write_register(self.REG_FLAG_RESTART, 0x95AF)

    def save_user_program(self) -> bool:
        """Сохранение пользовательской программы."""
        return self._write_register(self.REG_FLAG_SAVE_PROGRAM, 0x8426)

    def load_user_program(self) -> bool:
        """Загрузка пользовательской программы из памяти."""
        return self._write_register(self.REG_FLAG_SAVE_PROGRAM, 0x9346)

    def get_all_status(self) -> dict:
        """Получение полной информации о состоянии."""
        status = {}

        motor_status = self.get_status()
        if motor_status is not None:
            status['motor_status'] = motor_status
            status['motor_status_text'] = {
                0: "СТОП",
                1: "ВПЕРЕД",
                2: "НАЗАД"
            }.get(motor_status, "Неизвестно")

        current = self.get_current()
        if current is not None:
            status['current'] = current

        speed = self.get_speed()
        if speed is not None:
            status['speed'] = speed

        position = self.get_position()
        if position is not None:
            status['position'] = position

        temps = self.get_temperatures()
        if temps:
            status['temperatures'] = temps

        error_code = self.get_errors()
        if error_code is not None:
            status['error_code'] = error_code
            if error_code != 0:
                status['errors'] = self.get_detailed_error_info("dict")

        return status

    # ===== Контекстный менеджер =====

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.disconnect()
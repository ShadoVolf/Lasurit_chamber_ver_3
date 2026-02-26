"""
BLSD-20Modbus эмулятор
Имитирует работу реального BLSD-20Modbus контроллера двигателя.
"""

import time
import threading
import random
import logging
from enum import IntEnum
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List, Callable, Union
from queue import Queue, Empty

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class BLSDEmulator:
    """
    Эмулятор BLSD-20Modbus контроллера.
    Полностью имитирует поведение реального устройства с поддержкой всех регистров.
    """

    # Копия enum из реального драйвера
    class MotorStatus(IntEnum):
        STOPPED = 0
        FORWARD = 1
        REVERSE = 2

    class DeviceMode(IntEnum):
        MODBUS = 1
        EXTERNAL = 2

    class Direction(IntEnum):
        FORWARD = 1
        REVERSE = 2

    class RotationMode(IntEnum):
        CONTINUOUS = 1
        OFFSET = 2
        POSITIONING = 3

    class ModbusMode(IntEnum):
        RTU = 1
        ASCII = 2

    @dataclass
    class RegisterMap:
        """Карта регистров устройства"""
        # Системные регистры (только для чтения)
        system_ax: int = 0x424C  # 'BL'
        system_bx: int = 0x5344  # 'SD'
        system_cx: int = 0x2D32  # '-2'
        system_dx: int = 0x304D  # '0M'
        system_ex: int = 0x6F64  # 'od'
        system_fx: int = 0x6275  # 'bu'
        system_pc: int = 0x73  # 's'

        # Coils (1-битные регистры управления)
        coil_start: bool = False
        coil_stop: bool = False
        coil_hard_stop: bool = False
        coil_clear_position: bool = False

        # Input Registers (только для чтения)
        status: int = 0  # 0x3000
        current: int = 0  # 0x3001 (мА)
        speed: int = 0  # 0x3002 (об/мин)
        position: int = 0  # 0x3003-0x3004 (32-bit)
        temp_mcu: int = 300  # 0x3005 (℃ * 10)
        temp_mosfet: int = 300  # 0x3006 (℃ * 10)
        temp_brake: int = 300  # 0x3007 (℃ * 10)
        task_counter: int = 0  # 0x3008

        # Holding Registers (чтение/запись)
        slave_addr: int = 1  # 0x5000
        modbus_type: int = 1  # 0x5001 (1=RTU, 2=ASCII)
        modbus_baud: int = 115200  # 0x5002
        timeout: int = 1000  # 0x5003 (мс)
        mode_device: int = 1  # 0x5004 (1=MODBUS, 2=EXTERNAL)
        mode_user_program: int = 0  # 0x5005
        mode_rotation: int = 1  # 0x5006 (1=CONTINUOUS, 2=OFFSET, 3=POSITIONING)
        mode_ext_in: int = 0  # 0x5007
        position_n: int = 1  # 0x5008
        ref_current: int = 10000  # 0x5009 (мА)
        hold_current: int = 1000  # 0x500A (мА)
        set_speed: int = 1000  # 0x500B (об/мин)
        acceleration: int = 100  # 0x500C
        deceleration: int = 100  # 0x500D
        direction: int = 1  # 0x500E (1=FORWARD, 2=REVERSE)
        n_poles: int = 8  # 0x500F
        use_extern_speed: int = 0  # 0x5010
        offset: int = 0  # 0x5015-0x5016 (32-bit)
        target_position: int = 0  # 0x5017-0x5018 (32-bit)
        position1: int = 0  # 0x5019-0x501A (32-bit)
        position2: int = 10000  # 0x501B-0x501C (32-bit)
        position3: int = 20000  # 0x501D-0x501E (32-bit)
        position4: int = 30000  # 0x501F-0x5020 (32-bit)
        error: int = 0  # 0x5021
        flag_save_ini: int = 0  # 0x5022
        flag_save_program: int = 0  # 0x5023
        flag_restart: int = 0  # 0x5024

        # Identification Registers (только для чтения)
        hw_major: int = 1000  # 0x8001: Тип драйвера (BLSD-20ModBus)
        hw_minor: int = 1  # 0x8002: Версия аппаратной части
        fw_major: int = 1  # 0x8003: Идентификатор ПО
        fw_minor: int = 0  # 0x8004: Версия ПО

        # Внутренние переменные состояния
        is_running: bool = False
        start_time: Optional[float] = None
        last_update_time: Optional[float] = None
        target_speed: int = 0
        actual_speed: int = 0
        acceleration_rate: float = 10.0  # об/мин в секунду

        # Настройки эмуляции
        error_probability: float = 0.01  # 1% вероятность ошибки
        temperature_increase_rate: float = 0.1  # ℃/сек при работе
        temperature_decrease_rate: float = 0.05  # ℃/сек при простое
        max_temperature_mcu: int = 850  # 85.0℃
        max_temperature_mosfet: int = 1050  # 105.0℃
        max_temperature_brake: int = 550  # 55.0℃

        # Для эмуляции плавного движения
        position_increment: int = 0
        movement_start_time: Optional[float] = None

        # Случайные колебания
        noise_current: int = 50  # Разброс тока (мА)
        noise_temperature: int = 5  # Разброс температуры (0.1℃)

        # Сохраненные настройки (имитация EEPROM)
        saved_settings: Dict[str, Any] = field(default_factory=dict)

    def __init__(self, slave_id: int = 1, motor_type: str = 'FL42BLS02',
                 simulation_speed: float = 1.0):
        """
        Инициализация эмулятора.

        Args:
            slave_id: Modbus адрес устройства
            motor_type: Тип двигателя ('FL42BLS02' или 'FL57BLS02')
            simulation_speed: Коэффициент скорости симуляции (1.0 = реальное время)
        """
        self.slave_id = slave_id
        self.motor_type = motor_type
        self.simulation_speed = simulation_speed

        # Инициализация регистров
        self.registers = self.RegisterMap()
        self.registers.n_poles = 8 if motor_type == 'FL42BLS02' else 4

        # Создаем сохраненную копию настроек по умолчанию
        self._save_default_settings()

        # Блокировка для потокобезопасности
        self._lock = threading.RLock()

        # Очередь команд для обработки
        self._command_queue = Queue()

        # Флаг работы эмулятора
        self._is_running = False
        self._update_thread: Optional[threading.Thread] = None
        self._command_thread: Optional[threading.Thread] = None

        # Интервалы обновления (секунды)
        self._update_interval = 0.1  # 100 мс
        self._command_interval = 0.05  # 50 мс

        # Подписчики на события
        self._event_handlers: Dict[str, List[Callable]] = {
            'motor_started': [],
            'motor_stopped': [],
            'error_occurred': [],
            'position_reached': [],
            'temperature_warning': [],
        }

        # Статистика работы
        self._stats = {
            'total_runtime': 0.0,
            'commands_processed': 0,
            'errors_generated': 0,
            'temperature_warnings': 0,
        }

        logger.info(f"BLSD20 эмулятор инициализирован (адрес: {slave_id}, тип: {motor_type})")

    def _save_default_settings(self):
        """Сохранение настроек по умолчанию."""
        self.registers.saved_settings = {
            'slave_addr': self.registers.slave_addr,
            'modbus_type': self.registers.modbus_type,
            'modbus_baud': self.registers.modbus_baud,
            'timeout': self.registers.timeout,
            'mode_device': self.registers.mode_device,
            'mode_rotation': self.registers.mode_rotation,
            'ref_current': self.registers.ref_current,
            'hold_current': self.registers.hold_current,
            'set_speed': self.registers.set_speed,
            'acceleration': self.registers.acceleration,
            'deceleration': self.registers.deceleration,
            'direction': self.registers.direction,
            'n_poles': self.registers.n_poles,
            'position1': self.registers.position1,
            'position2': self.registers.position2,
            'position3': self.registers.position3,
            'position4': self.registers.position4,
        }

    def start(self):
        """Запуск эмулятора."""
        if not self._is_running:
            self._is_running = True

            # Поток обновления состояния
            self._update_thread = threading.Thread(
                target=self._update_loop,
                daemon=True,
                name=f"BLSD20Emulator-Update-{self.slave_id}"
            )

            # Поток обработки команд
            self._command_thread = threading.Thread(
                target=self._command_loop,
                daemon=True,
                name=f"BLSD20Emulator-Command-{self.slave_id}"
            )

            self._update_thread.start()
            self._command_thread.start()

            logger.info(f"BLSD20 эмулятор запущен (адрес: {self.slave_id})")

    def stop(self):
        """Остановка эмулятора."""
        if self._is_running:
            self._is_running = False

            # Останавливаем двигатель
            with self._lock:
                self.registers.is_running = False
                self.registers.actual_speed = 0
                self.registers.target_speed = 0
                self.registers.status = self.MotorStatus.STOPPED

            # Ждем завершения потоков
            if self._update_thread:
                self._update_thread.join(timeout=2.0)
            if self._command_thread:
                self._command_thread.join(timeout=2.0)

            logger.info(f"BLSD20 эмулятор остановлен (адрес: {self.slave_id})")

    def _update_loop(self):
        """Основной цикл обновления состояния."""
        while self._is_running:
            try:
                with self._lock:
                    self._update_state()

                # Спим с учетом коэффициента симуляции
                time.sleep(self._update_interval / self.simulation_speed)

            except Exception as e:
                logger.error(f"Ошибка в цикле обновления: {e}")
                time.sleep(1.0)

    def _command_loop(self):
        """Цикл обработки команд из очереди."""
        while self._is_running:
            try:
                # Обработка команд с таймаутом
                self._process_commands()

                # Спим с учетом коэффициента симуляции
                time.sleep(self._command_interval / self.simulation_speed)

            except Exception as e:
                logger.error(f"Ошибка в цикле команд: {e}")
                time.sleep(1.0)

    def _process_commands(self):
        """Обработка команд из очереди."""
        try:
            # Обрабатываем все команды в очереди
            while True:
                try:
                    command = self._command_queue.get_nowait()
                    self._execute_command(command)
                    self._command_queue.task_done()
                    self._stats['commands_processed'] += 1
                except Empty:
                    break
        except Exception as e:
            logger.error(f"Ошибка при обработке команд: {e}")

    def _execute_command(self, command: Dict[str, Any]):
        """Выполнение команды."""
        cmd_type = command.get('type')

        if cmd_type == 'write_register':
            address = command.get('address')
            value = command.get('value')
            self._process_register_write(address, value)

        elif cmd_type == 'write_coil':
            address = command.get('address')
            value = command.get('value')
            self._process_coil_write(address, value)

        elif cmd_type == 'inject_error':
            error_code = command.get('error_code')
            self.inject_error(error_code)

        elif cmd_type == 'clear_errors':
            self.clear_errors()

    def _update_state(self):
        """Обновление состояния устройства."""
        current_time = time.time()

        # Обновление статистики
        if self.registers.is_running:
            dt = current_time - self.registers.last_update_time if self.registers.last_update_time else 0
            self._stats['total_runtime'] += dt * self.simulation_speed

        # Обновление движения
        self._update_movement(current_time)

        # Обновление температур
        self._update_temperatures(current_time)

        # Обновление тока
        self._update_current()

        # Обновление позиции
        self._update_position(current_time)

        # Проверка достижения позиции
        self._check_position_reached()

        # Проверка перегрева
        self._check_temperature_warnings()

        # Имитация случайных ошибок
        self._simulate_random_errors()

        # Обновление счетчика задач
        self.registers.task_counter += 1
        if self.registers.task_counter > 0xFFFF:
            self.registers.task_counter = 0

        self.registers.last_update_time = current_time

    def _update_movement(self, current_time: float):
        """Обновление состояния движения."""
        if not self.registers.is_running:
            return

        # Плавное изменение скорости
        speed_diff = self.registers.target_speed - self.registers.actual_speed

        if abs(speed_diff) > 0.1:
            # Вычисляем изменение скорости с учетом ускорения/замедления
            acceleration = self.registers.acceleration_rate

            # Если двигаемся к нулю - используем замедление
            if self.registers.target_speed == 0:
                acceleration = self.registers.deceleration * 0.1

            max_change = acceleration * self._update_interval * self.simulation_speed

            if abs(speed_diff) <= max_change:
                self.registers.actual_speed = self.registers.target_speed
            else:
                change = max_change if speed_diff > 0 else -max_change
                self.registers.actual_speed += change

        # Если скорость близка к нулю - останавливаем двигатель
        if self.registers.target_speed == 0 and abs(self.registers.actual_speed) < 1.0:
            self.registers.actual_speed = 0
            self.registers.is_running = False
            self.registers.status = self.MotorStatus.STOPPED
            self._fire_event('motor_stopped', {'reason': 'normal_stop'})

    def _update_temperatures(self, current_time: float):
        """Обновление температур."""
        if self.registers.is_running:
            # Нагрев при работе
            heat_rate = self.registers.temperature_increase_rate

            # Нагрев зависит от нагрузки
            load_factor = abs(
                self.registers.actual_speed) / self.registers.set_speed if self.registers.set_speed > 0 else 0
            load_factor = max(0.1, min(1.0, load_factor))

            self.registers.temp_mcu += int(heat_rate * load_factor * 10 * self._update_interval * self.simulation_speed)
            self.registers.temp_mosfet += int(
                heat_rate * load_factor * 15 * self._update_interval * self.simulation_speed)
            self.registers.temp_brake += int(
                heat_rate * load_factor * 5 * self._update_interval * self.simulation_speed)
        else:
            # Охлаждение в простое
            self.registers.temp_mcu -= int(
                self.registers.temperature_decrease_rate * 10 * self._update_interval * self.simulation_speed)
            self.registers.temp_mosfet -= int(
                self.registers.temperature_decrease_rate * 15 * self._update_interval * self.simulation_speed)
            self.registers.temp_brake -= int(
                self.registers.temperature_decrease_rate * 5 * self._update_interval * self.simulation_speed)

        # Ограничение температур
        self.registers.temp_mcu = max(200, min(self.registers.max_temperature_mcu, self.registers.temp_mcu))
        self.registers.temp_mosfet = max(200, min(self.registers.max_temperature_mosfet, self.registers.temp_mosfet))
        self.registers.temp_brake = max(200, min(self.registers.max_temperature_brake, self.registers.temp_brake))

        # Добавляем случайные колебания
        noise = random.randint(-self.registers.noise_temperature, self.registers.noise_temperature)
        self.registers.temp_mcu = max(200, self.registers.temp_mcu + noise)

    def _update_current(self):
        """Обновление тока."""
        if self.registers.is_running and abs(self.registers.actual_speed) > 0:
            # Ток пропорционален скорости и нагрузке
            base_current = 500  # ток холостого хода
            speed_factor = abs(
                self.registers.actual_speed) / self.registers.set_speed if self.registers.set_speed > 0 else 0.5
            speed_factor = max(0.1, min(1.5, speed_factor))

            # Ток удержания при остановке
            if self.registers.actual_speed == 0:
                current = self.registers.hold_current
            else:
                current = base_current + int(self.registers.ref_current * speed_factor * 0.05)

            # Добавляем случайные колебания
            noise = random.randint(-self.registers.noise_current, self.registers.noise_current)
            self.registers.current = max(0, current + noise)
        else:
            # Минимальный ток в простое
            self.registers.current = random.randint(10, 50)

    def _update_position(self, current_time: float):
        """Обновление позиции."""
        if self.registers.is_running and abs(self.registers.actual_speed) > 0:
            if self.registers.movement_start_time is None:
                self.registers.movement_start_time = current_time

            # Вычисляем изменение позиции
            dt = current_time - self.registers.movement_start_time
            direction = 1 if self.registers.direction == self.Direction.FORWARD else -1

            # Скорость в об/мин, преобразуем в шаги/сек (предполагаем 200 шагов на оборот)
            steps_per_rev = 200
            position_change = int(self.registers.actual_speed * steps_per_rev * dt / 60.0 * direction)

            self.registers.position += position_change

            # Ограничение 32-bit со знаком
            if self.registers.position > 0x7FFFFFFF:
                self.registers.position = 0x7FFFFFFF
            elif self.registers.position < -0x80000000:
                self.registers.position = -0x80000000

            self.registers.movement_start_time = current_time
        else:
            self.registers.movement_start_time = None

    def _check_position_reached(self):
        """Проверка достижения целевой позиции."""
        if (self.registers.mode_rotation == self.RotationMode.POSITIONING and
                self.registers.is_running):

            target_pos = self._get_target_position_by_number(self.registers.position_n)

            if target_pos is not None:
                pos_diff = abs(self.registers.position - target_pos)

                # Допуск 10 шагов
                if pos_diff <= 10:
                    # Останавливаем двигатель
                    self.registers.target_speed = 0
                    self._fire_event('position_reached', {
                        'position': self.registers.position,
                        'target_position': target_pos,
                        'position_number': self.registers.position_n
                    })

    def _check_temperature_warnings(self):
        """Проверка предупреждений о температуре."""
        warnings = []

        if self.registers.temp_mcu > 700:  # 70.0℃
            warnings.append(('MCU', self.registers.temp_mcu / 10.0))

        if self.registers.temp_mosfet > 800:  # 80.0℃
            warnings.append(('MOSFET', self.registers.temp_mosfet / 10.0))

        if self.registers.temp_brake > 400:  # 40.0℃
            warnings.append(('BRAKE', self.registers.temp_brake / 10.0))

        if warnings:
            self._stats['temperature_warnings'] += 1
            self._fire_event('temperature_warning', {'warnings': warnings})

            # Устанавливаем бит перегрева в ошибках
            self.registers.error |= 0x0001  # Бит 0: Перегрев

    def _simulate_random_errors(self):
        """Имитация случайных ошибок."""
        if random.random() < self.registers.error_probability:
            # Выбираем случайную ошибку
            possible_errors = [
                0x0002,  # Перегрузка по току
                0x0004,  # Ошибка связи
                0x0008,  # Ошибка энкодера
                0x0010,  # Ошибка драйвера
                0x0020,  # Ошибка питания
            ]

            error = random.choice(possible_errors)
            self.registers.error |= error
            self._stats['errors_generated'] += 1

            self._fire_event('error_occurred', {
                'error_code': error,
                'error_mask': self.registers.error
            })

    def _get_target_position_by_number(self, position_num: int) -> Optional[int]:
        """Получение целевой позиции по номеру."""
        position_map = {
            1: self.registers.position1,
            2: self.registers.position2,
            3: self.registers.position3,
            4: self.registers.position4,
        }
        return position_map.get(position_num)

    def _fire_event(self, event_name: str, data: Dict[str, Any]):
        """Вызов обработчиков события."""
        handlers = self._event_handlers.get(event_name, [])
        for handler in handlers:
            try:
                handler(data)
            except Exception as e:
                logger.error(f"Ошибка в обработчике события {event_name}: {e}")

    # API для работы с регистрами

    def read_holding_registers(self, address: int, count: int = 1) -> List[int]:
        """Чтение holding регистров."""
        with self._lock:
            result = []
            for i in range(count):
                reg_addr = address + i
                value = self._get_holding_register_value(reg_addr)
                result.append(value)
            return result

    def read_input_registers(self, address: int, count: int = 1) -> List[int]:
        """Чтение input регистров."""
        with self._lock:
            result = []
            for i in range(count):
                reg_addr = address + i
                value = self._get_input_register_value(reg_addr)
                result.append(value)
            return result

    def write_registers(self, address: int, values: List[int]) -> bool:
        """Запись holding регистров."""
        # Добавляем команду в очередь
        for i, value in enumerate(values):
            cmd = {
                'type': 'write_register',
                'address': address + i,
                'value': value & 0xFFFF  # Ограничиваем 16 битами
            }
            self._command_queue.put(cmd)

        return True

    def write_coil(self, address: int, value: bool) -> bool:
        """Запись coil регистра."""
        cmd = {
            'type': 'write_coil',
            'address': address,
            'value': value
        }
        self._command_queue.put(cmd)
        return True

    def _process_register_write(self, address: int, value: int):
        """Обработка записи регистра."""
        with self._lock:
            self._set_holding_register_value(address, value)

    def _process_coil_write(self, address: int, value: bool):
        """Обработка записи coil."""
        with self._lock:
            if address == 0x2000:  # COIL_START
                self._start_motor()
            elif address == 0x2001:  # COIL_STOP
                self._stop_motor()
            elif address == 0x2002:  # COIL_HARD_STOP
                self._emergency_stop()
            elif address == 0x2003:  # COIL_CLEAR_POSITION
                self._clear_position()

    def _start_motor(self):
        """Запуск двигателя."""
        if not self.registers.is_running:
            self.registers.is_running = True
            self.registers.start_time = time.time()
            self.registers.target_speed = self.registers.set_speed
            self.registers.acceleration_rate = self.registers.acceleration * 0.1

            # Устанавливаем статус
            if self.registers.direction == self.Direction.FORWARD:
                self.registers.status = self.MotorStatus.FORWARD
            else:
                self.registers.status = self.MotorStatus.REVERSE

            self._fire_event('motor_started', {
                'speed': self.registers.set_speed,
                'direction': self.registers.direction,
                'mode': self.registers.mode_rotation
            })

    def _stop_motor(self):
        """Остановка двигателя с замедлением."""
        if self.registers.is_running:
            self.registers.target_speed = 0
            self.registers.acceleration_rate = self.registers.deceleration * 0.1

    def _emergency_stop(self):
        """Аварийная остановка."""
        if self.registers.is_running:
            self.registers.is_running = False
            self.registers.target_speed = 0
            self.registers.actual_speed = 0
            self.registers.status = self.MotorStatus.STOPPED

            self._fire_event('motor_stopped', {'reason': 'emergency_stop'})

    def _clear_position(self):
        """Сброс позиции."""
        self.registers.position = 0

    def _get_holding_register_value(self, address: int) -> int:
        """Получение значения holding регистра."""
        # Системные регистры
        if address == 0x7000: return self.registers.system_ax
        if address == 0x7001: return self.registers.system_bx
        if address == 0x7002: return self.registers.system_cx
        if address == 0x7003: return self.registers.system_dx
        if address == 0x7004: return self.registers.system_ex
        if address == 0x7005: return self.registers.system_fx
        if address == 0x7006: return self.registers.system_pc

        # Регистры настройки
        if address == 0x5000: return self.registers.slave_addr
        if address == 0x5001: return self.registers.modbus_type
        if address == 0x5002: return self.registers.modbus_baud
        if address == 0x5003: return self.registers.timeout
        if address == 0x5004: return self.registers.mode_device
        if address == 0x5005: return self.registers.mode_user_program
        if address == 0x5006: return self.registers.mode_rotation
        if address == 0x5007: return self.registers.mode_ext_in
        if address == 0x5008: return self.registers.position_n
        if address == 0x5009: return self.registers.ref_current
        if address == 0x500A: return self.registers.hold_current
        if address == 0x500B: return self.registers.set_speed
        if address == 0x500C: return self.registers.acceleration
        if address == 0x500D: return self.registers.deceleration
        if address == 0x500E: return self.registers.direction
        if address == 0x500F: return self.registers.n_poles
        if address == 0x5010: return self.registers.use_extern_speed

        # 32-битные регистры (младшее слово)
        if address == 0x5015: return self.registers.offset & 0xFFFF
        if address == 0x5016: return (self.registers.offset >> 16) & 0xFFFF
        if address == 0x5017: return self.registers.target_position & 0xFFFF
        if address == 0x5018: return (self.registers.target_position >> 16) & 0xFFFF
        if address == 0x5019: return self.registers.position1 & 0xFFFF
        if address == 0x501A: return (self.registers.position1 >> 16) & 0xFFFF
        if address == 0x501B: return self.registers.position2 & 0xFFFF
        if address == 0x501C: return (self.registers.position2 >> 16) & 0xFFFF
        if address == 0x501D: return self.registers.position3 & 0xFFFF
        if address == 0x501E: return (self.registers.position3 >> 16) & 0xFFFF
        if address == 0x501F: return self.registers.position4 & 0xFFFF
        if address == 0x5020: return (self.registers.position4 >> 16) & 0xFFFF

        if address == 0x5021: return self.registers.error
        if address == 0x5022: return self.registers.flag_save_ini
        if address == 0x5023: return self.registers.flag_save_program
        if address == 0x5024: return self.registers.flag_restart

        return 0  # Неизвестный регистр

    def _get_input_register_value(self, address: int) -> int:
        """Получение значения input регистра."""
        # Регистры состояния
        if address == 0x3000: return self.registers.status
        if address == 0x3001: return self.registers.current
        if address == 0x3002: return abs(self.registers.actual_speed)

        # 32-битная позиция
        if address == 0x3003: return self.registers.position & 0xFFFF
        if address == 0x3004: return (self.registers.position >> 16) & 0xFFFF

        if address == 0x3005: return self.registers.temp_mcu
        if address == 0x3006: return self.registers.temp_mosfet
        if address == 0x3007: return self.registers.temp_brake
        if address == 0x3008: return self.registers.task_counter

        # Регистры идентификации
        if address == 0x8001: return self.registers.hw_major
        if address == 0x8002: return self.registers.hw_minor
        if address == 0x8003: return self.registers.fw_major
        if address == 0x8004: return self.registers.fw_minor

        return 0  # Неизвестный регистр

    def _set_holding_register_value(self, address: int, value: int):
        """Установка значения holding регистра."""
        # Обработка специальных регистров
        if address == 0x500B:  # REG_SET_SPEED
            self.registers.set_speed = max(0, min(4000, value))
            if self.registers.is_running:
                self.registers.target_speed = self.registers.set_speed

        elif address == 0x500C:  # REG_ACCELERATION
            self.registers.acceleration = max(10, min(1000, value))

        elif address == 0x500D:  # REG_DECELERATION
            self.registers.deceleration = max(10, min(1000, value))

        elif address == 0x500E:  # REG_DIRECTION
            if value in [1, 2]:
                self.registers.direction = value
                if self.registers.is_running:
                    if self.registers.direction == self.Direction.FORWARD:
                        self.registers.status = self.MotorStatus.FORWARD
                    else:
                        self.registers.status = self.MotorStatus.REVERSE

        elif address == 0x5009:  # REG_REF_CURRENT
            self.registers.ref_current = max(1000, min(20000, value))

        elif address == 0x500A:  # REG_HOLD_CURRENT
            self.registers.hold_current = max(0, min(1000, value))

        elif address == 0x5004:  # REG_MODE_DEVICE
            if value in [1, 2]:
                self.registers.mode_device = value

        elif address == 0x5006:  # REG_MODE_ROTATION
            if value in [1, 2, 3]:
                self.registers.mode_rotation = value

        # 32-битные регистры
        elif address == 0x5015:  # OFFSET low word
            self.registers.offset = (self.registers.offset & 0xFFFF0000) | (value & 0xFFFF)

        elif address == 0x5016:  # OFFSET high word
            self.registers.offset = (self.registers.offset & 0xFFFF) | ((value & 0xFFFF) << 16)

        elif address == 0x5017:  # TARGET_POSITION low word
            self.registers.target_position = (self.registers.target_position & 0xFFFF0000) | (value & 0xFFFF)

        elif address == 0x5018:  # TARGET_POSITION high word
            self.registers.target_position = (self.registers.target_position & 0xFFFF) | ((value & 0xFFFF) << 16)

        # Регистры позиций
        elif address == 0x5019:  # POSITION1 low word
            self.registers.position1 = (self.registers.position1 & 0xFFFF0000) | (value & 0xFFFF)

        elif address == 0x501A:  # POSITION1 high word
            self.registers.position1 = (self.registers.position1 & 0xFFFF) | ((value & 0xFFFF) << 16)

        elif address == 0x501B:  # POSITION2 low word
            self.registers.position2 = (self.registers.position2 & 0xFFFF0000) | (value & 0xFFFF)

        elif address == 0x501C:  # POSITION2 high word
            self.registers.position2 = (self.registers.position2 & 0xFFFF) | ((value & 0xFFFF) << 16)

        elif address == 0x501D:  # POSITION3 low word
            self.registers.position3 = (self.registers.position3 & 0xFFFF0000) | (value & 0xFFFF)

        elif address == 0x501E:  # POSITION3 high word
            self.registers.position3 = (self.registers.position3 & 0xFFFF) | ((value & 0xFFFF) << 16)

        elif address == 0x501F:  # POSITION4 low word
            self.registers.position4 = (self.registers.position4 & 0xFFFF0000) | (value & 0xFFFF)

        elif address == 0x5020:  # POSITION4 high word
            self.registers.position4 = (self.registers.position4 & 0xFFFF) | ((value & 0xFFFF) << 16)

        # Флаги
        elif address == 0x5022:  # REG_FLAG_SAVE_INI
            if value == 0x37FA:
                self._save_settings()
                self.registers.flag_save_ini = 0

        elif address == 0x5023:  # REG_FLAG_SAVE_PROGRAM
            if value == 0x8426:
                self._save_user_program()
                self.registers.flag_save_program = 0
            elif value == 0x9346:
                self._load_user_program()
                self.registers.flag_save_program = 0

        elif address == 0x5024:  # REG_FLAG_RESTART
            if value == 0x95AF:
                self._restart_device()
                self.registers.flag_restart = 0

        elif address == 0x5021:  # REG_ERROR
            self.registers.error = value & 0xFFFF

        else:
            # Для других регистров просто сохраняем значение
            pass

    def _save_settings(self):
        """Сохранение настроек в EEPROM (эмуляция)."""
        self.registers.saved_settings.update({
            'slave_addr': self.registers.slave_addr,
            'modbus_type': self.registers.modbus_type,
            'modbus_baud': self.registers.modbus_baud,
            'timeout': self.registers.timeout,
            'mode_device': self.registers.mode_device,
            'mode_rotation': self.registers.mode_rotation,
            'ref_current': self.registers.ref_current,
            'hold_current': self.registers.hold_current,
            'set_speed': self.registers.set_speed,
            'acceleration': self.registers.acceleration,
            'deceleration': self.registers.deceleration,
            'direction': self.registers.direction,
        })
        logger.info(f"Настройки сохранены (адрес: {self.slave_id})")

    def _save_user_program(self):
        """Сохранение пользовательской программы (эмуляция)."""
        logger.info(f"Пользовательская программа сохранена (адрес: {self.slave_id})")

    def _load_user_program(self):
        """Загрузка пользовательской программы (эмуляция)."""
        logger.info(f"Пользовательская программа загружена (адрес: {self.slave_id})")

    def _restart_device(self):
        """Перезагрузка устройства (эмуляция)."""
        # Сбрасываем состояние, но сохраняем основные настройки
        old_settings = self.registers.saved_settings.copy()

        # Создаем новый объект регистров
        self.registers = self.RegisterMap()

        # Восстанавливаем настройки
        self.registers.saved_settings = old_settings
        for key, value in old_settings.items():
            if hasattr(self.registers, key):
                setattr(self.registers, key, value)

        # Восстанавливаем тип двигателя
        self.registers.n_poles = 8 if self.motor_type == 'FL42BLS02' else 4

        logger.info(f"Устройство перезагружено (адрес: {self.slave_id})")

    # Публичные методы для управления эмулятором

    def inject_error(self, error_code: int):
        """Имитация ошибки устройства."""
        cmd = {
            'type': 'inject_error',
            'error_code': error_code & 0xFFFF
        }
        self._command_queue.put(cmd)

    def clear_errors(self):
        """Сброс всех ошибок."""
        cmd = {
            'type': 'clear_errors'
        }
        self._command_queue.put(cmd)

    def set_error_probability(self, probability: float):
        """Установка вероятности возникновения ошибок."""
        with self._lock:
            self.registers.error_probability = max(0.0, min(1.0, probability))

    def set_simulation_speed(self, speed: float):
        """Установка коэффициента скорости симуляции."""
        with self._lock:
            self.simulation_speed = max(0.1, min(10.0, speed))

    def reset_statistics(self):
        """Сброс статистики."""
        with self._lock:
            self._stats = {
                'total_runtime': 0.0,
                'commands_processed': 0,
                'errors_generated': 0,
                'temperature_warnings': 0,
            }

    def get_state(self) -> Dict[str, Any]:
        """Получение полного состояния устройства."""
        with self._lock:
            return {
                'motor_status': {
                    'value': self.registers.status,
                    'text': {
                        0: "Остановлен",
                        1: "Вращение вперед",
                        2: "Вращение назад"
                    }.get(self.registers.status, "Неизвестно")
                },
                'current': self.registers.current,
                'speed': self.registers.actual_speed,
                'target_speed': self.registers.set_speed,
                'position': self.registers.position,
                'temperatures': {
                    'mcu': self.registers.temp_mcu / 10.0,
                    'mosfet': self.registers.temp_mosfet / 10.0,
                    'brake': self.registers.temp_brake / 10.0,
                },
                'error_code': self.registers.error,
                'direction': {
                    'value': self.registers.direction,
                    'text': "Вперед" if self.registers.direction == 1 else "Назад"
                },
                'mode_device': {
                    'value': self.registers.mode_device,
                    'text': "MODBUS" if self.registers.mode_device == 1 else "EXTERNAL"
                },
                'mode_rotation': {
                    'value': self.registers.mode_rotation,
                    'text': {
                        1: "Непрерывное",
                        2: "Смещение",
                        3: "Позиционирование"
                    }.get(self.registers.mode_rotation, "Неизвестно")
                },
                'is_running': self.registers.is_running,
                'task_counter': self.registers.task_counter,
                'statistics': self._stats.copy(),
            }

    def get_register_dump(self) -> Dict[str, Any]:
        """Получение дампа всех регистров."""
        with self._lock:
            return {
                'holding_registers': self._get_all_holding_registers(),
                'input_registers': self._get_all_input_registers(),
                'coils': self._get_all_coils(),
                'settings': self.registers.saved_settings.copy(),
            }

    def _get_all_holding_registers(self) -> Dict[str, Any]:
        """Получение всех holding регистров."""
        regs = {}

        # Системные регистры
        system_regs = ['system_ax', 'system_bx', 'system_cx', 'system_dx',
                       'system_ex', 'system_fx', 'system_pc']

        for reg in system_regs:
            value = getattr(self.registers, reg, 0)
            regs[reg] = {
                'value': value,
                'hex': hex(value),
                'ascii': self._value_to_ascii(value)
            }

        # Регистры настройки
        config_regs = [
            ('slave_addr', 'Адрес устройства'),
            ('modbus_type', 'Тип Modbus'),
            ('modbus_baud', 'Скорость Modbus'),
            ('timeout', 'Таймаут'),
            ('mode_device', 'Режим устройства'),
            ('mode_rotation', 'Режим вращения'),
            ('ref_current', 'Ограничение тока'),
            ('hold_current', 'Ток удержания'),
            ('set_speed', 'Установленная скорость'),
            ('acceleration', 'Ускорение'),
            ('deceleration', 'Замедление'),
            ('direction', 'Направление'),
            ('n_poles', 'Количество полюсов'),
        ]

        for reg_name, description in config_regs:
            value = getattr(self.registers, reg_name, 0)
            regs[reg_name] = {
                'value': value,
                'hex': hex(value),
                'description': description
            }

        # 32-битные регистры
        reg32 = [
            ('offset', 'Смещение'),
            ('target_position', 'Целевая позиция'),
            ('position1', 'Позиция 1'),
            ('position2', 'Позиция 2'),
            ('position3', 'Позиция 3'),
            ('position4', 'Позиция 4'),
        ]

        for reg_name, description in reg32:
            value = getattr(self.registers, reg_name, 0)
            regs[reg_name] = {
                'value': value,
                'hex': hex(value),
                'description': description
            }

        return regs

    def _get_all_input_registers(self) -> Dict[str, Any]:
        """Получение всех input регистров."""
        regs = {}

        # Регистры состояния
        status_regs = [
            ('status', 'Статус двигателя'),
            ('current', 'Ток двигателя'),
            ('speed', 'Скорость двигателя'),
            ('position', 'Позиция двигателя'),
            ('temp_mcu', 'Температура MCU'),
            ('temp_mosfet', 'Температура MOSFET'),
            ('temp_brake', 'Температура тормоза'),
            ('task_counter', 'Счетчик задач'),
        ]

        for reg_name, description in status_regs:
            value = getattr(self.registers, reg_name, 0)
            regs[reg_name] = {
                'value': value,
                'hex': hex(value),
                'description': description
            }

        # Регистры идентификации
        id_regs = [
            ('hw_major', 'Тип драйвера'),
            ('hw_minor', 'Версия аппаратной части'),
            ('fw_major', 'Идентификатор ПО'),
            ('fw_minor', 'Версия ПО'),
        ]

        for reg_name, description in id_regs:
            value = getattr(self.registers, reg_name, 0)
            regs[reg_name] = {
                'value': value,
                'hex': hex(value),
                'description': description
            }

        return regs

    def _get_all_coils(self) -> Dict[str, Any]:
        """Получение всех coils."""
        coils = {
            'coil_start': {
                'value': self.registers.coil_start,
                'description': 'Запуск двигателя'
            },
            'coil_stop': {
                'value': self.registers.coil_stop,
                'description': 'Остановка двигателя'
            },
            'coil_hard_stop': {
                'value': self.registers.coil_hard_stop,
                'description': 'Аварийная остановка'
            },
            'coil_clear_position': {
                'value': self.registers.coil_clear_position,
                'description': 'Сброс позиции'
            },
        }
        return coils

    def _value_to_ascii(self, value: int) -> str:
        """Преобразование значения в ASCII строку."""
        try:
            # Пытаемся получить 2 символа из 16-битного значения
            chars = []
            for shift in [8, 0]:
                char_code = (value >> shift) & 0xFF
                if 32 <= char_code <= 126:  # Печатные символы
                    chars.append(chr(char_code))
                else:
                    chars.append('.')
            return ''.join(chars)
        except:
            return ''

    def subscribe_event(self, event_name: str, handler: Callable):
        """Подписка на событие."""
        if event_name in self._event_handlers:
            self._event_handlers[event_name].append(handler)

    def unsubscribe_event(self, event_name: str, handler: Callable):
        """Отписка от события."""
        if event_name in self._event_handlers:
            if handler in self._event_handlers[event_name]:
                self._event_handlers[event_name].remove(handler)

    def get_connection_info(self) -> Dict[str, Any]:
        """Получение информации о подключении."""
        return {
            'mode': 'emulation',
            'slave_id': self.slave_id,
            'motor_type': self.motor_type,
            'simulation_speed': self.simulation_speed,
            'is_running': self._is_running,
            'statistics': self._stats.copy(),
        }
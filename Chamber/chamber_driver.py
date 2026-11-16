# camera_controller.py
import threading
import time
from typing import Optional, Dict, Any, Tuple
from BLSD.client_blsd20 import BLSD20ModbusDriver
from Ports_COM.client import DeviceType
from Ports_COM.Devices_Data import DEVICES_DATA
from RS232_4pin_Rele.Client import RS232RelayDriver
from owen.Client import TRM12Driver, ByteOrder, ControlMode
from tabulate import tabulate

from owen.Temp_Corrector_class import PolynomialCorrector


class CameraController:
    """
    Единый драйвер управления камерой, использующий три устройства:
    1. BLSD-20Modbus (двигатель вентилятора)
    2. TRM12 (терморегулятор)
    3. RS232-4pin-Relay (релейная плата для переключения датчиков)
    """

    def __init__(self, devices_data: Optional[Any] = None):
        self.blsd20 = None
        self.trm12 = None
        self.relay = None
        self.soak_time = 0
        self.connected = False
        self._connection_params = {}

        self.devices_data = devices_data if devices_data is not None else DEVICES_DATA

        # Общая блокировка для составных операций
        self._lock = threading.RLock()

        # Раздельные блокировки по физическим устройствам
        self._lock_blsd = threading.RLock()
        self._lock_trm = threading.RLock()
        self._lock_relay = threading.RLock()

        # Сериализует измерения с переключением реле 3/4.
        # Держится ВСЁ время (включая sleep), иначе get_gradient и
        # get_shaft_temperature переплетаются и читают «чужой» датчик.
        self._lock_measure = threading.RLock()

        # TTL-кэш измерений: (value, timestamp)
        self._gradient_cache = (None, 0.0)
        self._shaft_temp_cache = (None, 0.0)
        self._gradient_cache_ttl = 3.0  # сек
        self._shaft_temp_cache_ttl = 30.0  # сек

        self.corrector_chamber: Optional[PolynomialCorrector] = None
        self.corrector_shaft: Optional[PolynomialCorrector] = None

        # Параметры измерения температуры вала
        self.shaft_stabilization_interval = 2.0
        self.shaft_max_attempts = 15
        self.shaft_initial_delay = 5.0
        self.shaft_final_delay = 20.0

    def __init__OLD(self, devices_data: Optional[Any] = None):
        self.blsd20 = None
        self.trm12 = None
        self.relay = None
        self.soak_time = 0
        self.connected = False
        self._connection_params = {}

        self.devices_data = devices_data if devices_data is not None else DEVICES_DATA

        # Общая блокировка для составных операций (порядок захвата:
        # _lock_blsd -> _lock_trm -> _lock_relay)
        self._lock = threading.RLock()

        # НОВОЕ: кэш измерений. Защищает от блокировки других потоков,
        # когда одно долгое измерение уже идёт.
        self._gradient_cache = (None, 0.0)  # (value, timestamp)
        self._shaft_temp_cache = (None, 0.0)  # (value, timestamp)
        self._gradient_cache_ttl = 3.0  # сек
        self._shaft_temp_cache_ttl = 30.0  # сек

        # Раздельные блокировки по физическим устройствам
        self._lock_blsd = threading.RLock()
        self._lock_trm = threading.RLock()
        self._lock_relay = threading.RLock()

        self.corrector_chamber: Optional[PolynomialCorrector] = None
        self.corrector_shaft: Optional[PolynomialCorrector] = None

        # Параметры измерения температуры вала
        self.shaft_stabilization_interval = 2.0
        self.shaft_max_attempts = 15
        self.shaft_initial_delay = 5.0
        self.shaft_final_delay = 20.0

    def set_shaft_params(self, stabilization_interval: float = None, attempts: int = None,
                         initial_delay: float = None, final_delay: float = None):
        if stabilization_interval is not None:
            self.shaft_stabilization_interval = stabilization_interval
        if attempts is not None:
            self.shaft_max_attempts = attempts
        if initial_delay is not None:
            self.shaft_initial_delay = initial_delay
        if final_delay is not None:
            self.shaft_final_delay = final_delay

    def set_corrector(self, channel: int, corrector: PolynomialCorrector) -> None:
        if channel == 0:
            self.corrector_chamber = corrector
        elif channel == 1:
            self.corrector_shaft = corrector
        else:
            raise ValueError("Канал должен быть 0 или 1")

    # ============ СОЗДАНИЕ/ПОДКЛЮЧЕНИЕ ДРАЙВЕРОВ ============

    def _create_driver(self, device_type: DeviceType) -> Tuple[bool, str]:
        try:
            if device_type == DeviceType.TRM12:
                params = self.devices_data.trm12
                driver_current = TRM12Driver(
                    port=params.com_port,
                    address=params.address,
                    baudrate=params.baudrate,
                    byte_order=ByteOrder.BIG_ENDIAN_SWAP,
                    timeout=params.timeout,
                    retries=3
                )
                self.devices_data.add_device_driver(device_type, driver_current)
                return True, "Драйвер TRM12 создан"

            elif device_type == DeviceType.BLSD20:
                params = self.devices_data.blsd20
                driver = BLSD20ModbusDriver(
                    port=params.com_port,
                    slave_id=params.address,
                    baudrate=params.baudrate,
                    timeout=params.timeout,
                    Motor_Type='FL42BLS02'
                )
                self.devices_data.add_device_driver(device_type, driver)
                return True, "Драйвер BLSD-20 создан"

            elif device_type == DeviceType.RS232_4PIN_RELAY:
                params = self.devices_data.rs232_relay
                driver = RS232RelayDriver(
                    port=params.com_port,
                    baudrate=params.baudrate,
                    timeout=params.timeout,
                    retries=3
                )
                self.devices_data.add_device_driver(device_type, driver)
                return True, "Драйвер RS232-4pin-Relay создан"

            else:
                print(f"Неизвестный тип устройства: {device_type}")
                return False, f"Неизвестный тип устройства: {device_type}"

        except Exception as e:
            return False, f"Ошибка создания драйвера {device_type}: {e}"

    def _connect_device(self, device_type: DeviceType) -> Tuple[bool, str]:
        try:
            driver_current = self.devices_data.get_device_driver(device_type)
            if driver_current is None:
                success, message = self._create_driver(device_type)
                if not success:
                    return False, message
                driver_current = self.devices_data.get_device_driver(device_type)

            if device_type == DeviceType.TRM12:
                if not driver_current.is_connected():
                    if not driver_current.connect():
                        return False, f"Не удалось подключиться к {device_type.value}"
                self.trm12 = driver_current

            elif device_type == DeviceType.BLSD20:
                if not driver_current.connected:
                    if not driver_current.connect():
                        return False, f"Не удалось подключиться к {device_type.value}"
                self.blsd20 = driver_current

            elif device_type == DeviceType.RS232_4PIN_RELAY:
                if not driver_current.is_connected():
                    if not driver_current.connect():
                        return False, f"Не удалось подключиться к {device_type.value}"
                self.relay = driver_current

            self._save_connection_params(device_type)
            return True, f"Успешно подключено к {device_type.value}"

        except Exception as e:
            return False, f"Ошибка подключения к {device_type.value}: {e}"

    # ============ TRM12 ============

    def get_pid_parameters(self, channel: int = 0) -> Optional[Dict[str, Any]]:
        with self._lock_trm:
            try:
                if not self.trm12 or not hasattr(self.trm12, 'is_connected') or not self.trm12.is_connected():
                    print("TRM12 не подключен")
                    return None
                if not hasattr(self.trm12, 'get_pid_parameters'):
                    print("Драйвер TRM12 не поддерживает get_pid_parameters")
                    return None
                return self.trm12.get_pid_parameters(channel)
            except Exception as e:
                print(f"Ошибка получения ПИД-параметров: {e}")
                return None

    def set_pid_parameters(self,
                           P: float = None,
                           I: int = None,
                           D: int = None,
                           deadband: float = None,
                           output_min: float = None,
                           output_max: float = None,
                           channel: int = 0) -> Tuple[bool, str]:
        with self._lock_trm:
            try:
                if not self.trm12 or not hasattr(self.trm12, 'is_connected') or not self.trm12.is_connected():
                    return False, "TRM12 не подключен"
                if not hasattr(self.trm12, 'set_pid_parameters'):
                    return False, "Драйвер TRM12 не поддерживает set_pid_parameters"

                success = self.trm12.set_pid_parameters(
                    P=P, I=I, D=D,
                    deadband=deadband,
                    output_min=output_min,
                    output_max=output_max,
                    channel=channel
                )
                if success:
                    return True, "ПИД-параметры успешно установлены"
                return False, "Ошибка при установке ПИД-параметров (проверьте журнал)"
            except Exception as e:
                return False, f"Ошибка установки ПИД-параметров: {e}"

    def set_temperature(self, temperature: float, channel: int = 0) -> Tuple[bool, str]:
        with self._lock_trm:
            try:
                if not self.trm12 or not hasattr(self.trm12, 'is_connected') or not self.trm12.is_connected():
                    return False, "TRM12 не подключен"
                if not hasattr(self.trm12, 'set_setpoint'):
                    return False, "TRM12 драйвер не поддерживает установку температуры"
                success = self.trm12.set_setpoint(temperature, channel)
                return (success,
                        f"Температура установлена на {temperature}°C" if success
                        else "Ошибка установки температуры")
            except Exception as e:
                return False, f"Ошибка установки температуры: {e}"

    def get_chamber_temperature(self) -> Tuple[Optional[float], str]:
        with self._lock_trm:
            try:
                if not self.trm12 or not self.trm12.is_connected():
                    return None, "TRM12 не подключен"
                temp = self.trm12.read_parameter("PV", channel=0)
                if temp is not None:
                    if self.corrector_chamber:
                        temp = float(self.corrector_chamber.predict(temp))
                    return temp, "Температура камеры получена"
                return None, "Ошибка чтения температуры"
            except Exception as e:
                return None, f"Ошибка получения температуры камеры: {e}"

    def get_chamber_setpoint(self) -> Tuple[Optional[float], str]:
        with self._lock_trm:
            try:
                if not self.trm12 or not hasattr(self.trm12, 'is_connected') or not self.trm12.is_connected():
                    return None, "TRM12 не подключен"
                setpoints = self.trm12.get_setpoints()
                if 'Канал 1' in setpoints:
                    return setpoints['Канал 1'], "Уставка камеры получена"
                return None, "Уставка не найдена"
            except Exception as e:
                return None, f"Ошибка получения уставки камеры: {e}"

    def get_temperature_rate(self, channel: int = 0) -> Optional[float]:
        with self._lock_trm:
            try:
                if not self.trm12 or not self.trm12.is_connected():
                    return None
                return self.trm12.read_parameter("USP", channel=channel)
            except Exception as e:
                print(f"Ошибка чтения скорости нагрева: {e}")
                return None

    def set_temperature_rate(self, rate: float, channel: int = 0) -> Tuple[bool, str]:
        with self._lock_trm:
            try:
                if not self.trm12 or not self.trm12.is_connected():
                    return False, "TRM12 не подключен"
                success = self.trm12.write_parameter("USP", rate, channel=channel)
                return (success,
                        "Скорость нагрева установлена" if success
                        else "Ошибка установки скорости")
            except Exception as e:
                return False, f"Ошибка: {e}"

    def get_oven_status(self) -> Optional[Dict[str, Any]]:
        with self._lock_trm:
            try:
                if not self.trm12 or not hasattr(self.trm12, 'is_connected') or not self.trm12.is_connected():
                    return None
                mode_dice = self.trm12.get_control_mode()
                return mode_dice['name']
            except Exception as e:
                print(f"Ошибка получения статуса ОВЕН: {e}")
                return None

    def get_control_mode(self) -> Optional[Dict[str, Any]]:
        """Дополнительная обёртка для GUI (чтобы не дёргать trm12 напрямую)."""
        with self._lock_trm:
            try:
                if not self.trm12 or not self.trm12.is_connected():
                    return None
                return self.trm12.get_control_mode()
            except Exception as e:
                print(f"Ошибка получения режима TRM12: {e}")
                return None

    def get_device_info_trm12(self) -> Optional[Dict[str, Any]]:
        """Обёртка get_device_info() для TRM12."""
        with self._lock_trm:
            try:
                if not self.trm12 or not self.trm12.is_connected():
                    return None
                return self.trm12.get_device_info()
            except Exception as e:
                print(f"Ошибка get_device_info TRM12: {e}")
                return None

    def trm12_write_parameter(self, name: str, value, channel: int = 0) -> Tuple[bool, str]:
        """Обёртка write_parameter для TRM12 (используется в apply_preset)."""
        with self._lock_trm:
            try:
                if not self.trm12 or not self.trm12.is_connected():
                    return False, "TRM12 не подключен"
                ok = self.trm12.write_parameter(name, value, channel=channel)
                return ok, "OK" if ok else "Ошибка записи"
            except Exception as e:
                return False, f"Ошибка: {e}"

    # ============ BLSD-20 ============

    def set_fan_speed(self, speed: int) -> Tuple[bool, str]:
        with self._lock_blsd:
            try:
                if not self.blsd20 or not hasattr(self.blsd20, 'connected') or not self.blsd20.connected:
                    return False, "BLSD-20 не подключен"
                if not hasattr(self.blsd20, 'set_speed'):
                    return False, "BLSD-20 драйвер не поддерживает установку скорости"
                speed = max(0, min(4000, speed))
                success = self.blsd20.set_speed(speed)
                return (success,
                        f"Скорость установлена на {speed} об/мин" if success
                        else "Ошибка установки скорости")
            except Exception as e:
                return False, f"Ошибка установки скорости вентилятора: {e}"

    def get_fan_speed(self) -> Optional[int]:
        with self._lock_blsd:
            try:
                if not self.blsd20 or not hasattr(self.blsd20, 'connected') or not self.blsd20.connected:
                    return None
                if hasattr(self.blsd20, 'get_speed'):
                    return self.blsd20.get_speed()
                return None
            except Exception as e:
                print(f"Ошибка получения скорости вентилятора: {e}")
                return None

    def get_fan_set_speed(self) -> Optional[int]:
        """Уставка скорости BLSD-20 (регистр SET_SPEED)."""
        with self._lock_blsd:
            try:
                if not self.blsd20 or not self.blsd20.connected:
                    return None
                if hasattr(self.blsd20, 'get_set_speed'):
                    return self.blsd20.get_set_speed()
                return None
            except Exception as e:
                print(f"Ошибка получения уставки скорости: {e}")
                return None

    def get_motor_current(self) -> Optional[float]:
        with self._lock_blsd:
            try:
                if not self.blsd20 or not hasattr(self.blsd20, 'connected') or not self.blsd20.connected:
                    return None
                return self.blsd20.get_current()
            except Exception as e:
                print(f"Ошибка получения тока двигателя: {e}")
                return None

    def get_motor_status(self) -> Tuple[Optional[str], str]:
        with self._lock_blsd:
            try:
                if not self.blsd20 or not hasattr(self.blsd20, 'connected') or not self.blsd20.connected:
                    return None, "BLSD-20 не подключен"
                if not hasattr(self.blsd20, 'get_status'):
                    return None, "BLSD-20 драйвер не поддерживает получение статуса"
                status = self.blsd20.get_status()
                if status is None:
                    return None, "Ошибка чтения статуса"
                status_map = {0: "СТОП", 1: "ВПЕРЕД", 2: "НАЗАД"}
                return status_map.get(status, f"Неизвестный статус: {status}"), "Статус получен"
            except Exception as e:
                return None, f"Ошибка получения статуса двигателя: {e}"

    def get_device_info_blsd20(self) -> Optional[Dict[str, Any]]:
        with self._lock_blsd:
            try:
                if not self.blsd20 or not self.blsd20.connected:
                    return None
                return self.blsd20.get_device_info()
            except Exception as e:
                print(f"Ошибка get_device_info BLSD-20: {e}")
            return None

    # ============ РЕЛЕ ============

    def turn_on_motor_blower(self) -> Tuple[bool, str]:
        with self._lock_relay:
            try:
                if not self.relay or not hasattr(self.relay, 'is_connected') or not self.relay.is_connected():
                    return False, "Релейная плата не подключена"
                if self.relay.open_relay(2):
                    return True, "Вентилятор двигателя включен"
                self.relay.close_relay(2)
                return False, "Ошибка включения вентилятора двигателя"
            except Exception as e:
                return False, f"Ошибка включения вентилятора двигателя: {e}"

    def turn_off_motor_blower(self) -> Tuple[bool, str]:
        with self._lock_relay:
            try:
                if not self.relay or not hasattr(self.relay, 'is_connected') or not self.relay.is_connected():
                    return False, "Релейная плата не подключена"
                if self.relay.close_relay(2):
                    return True, "Вентилятор двигателя выключен"
                return False, "Ошибка выключения вентилятора двигателя"
            except Exception as e:
                return False, f"Ошибка выключения вентилятора двигателя: {e}"

    def turn_on_motor_heating(self) -> Tuple[bool, str]:
        with self._lock_relay:
            try:
                if not self.relay or not hasattr(self.relay, 'is_connected') or not self.relay.is_connected():
                    return False, "Релейная плата не подключена"
                if self.relay.open_relay(1):
                    return True, "Нагрев двигателя включен"
                self.relay.close_relay(1)
                return False, "Ошибка включения нагрева двигателя"
            except Exception as e:
                return False, f"Ошибка включения нагрева двигателя: {e}"

    def turn_off_motor_heating(self) -> Tuple[bool, str]:
        with self._lock_relay:
            try:
                if not self.relay or not hasattr(self.relay, 'is_connected') or not self.relay.is_connected():
                    return False, "Релейная плата не подключена"
                if self.relay.close_relay(1):
                    return True, "Нагрев двигателя выключен"
                return False, "Ошибка выключения нагрева двигателя"
            except Exception as e:
                return False, f"Ошибка выключения нагрева двигателя: {e}"

    # ============ СОСТАВНЫЕ ОПЕРАЦИИ ============

    def turn_on_camera(self) -> Tuple[bool, str]:
        with self._lock_blsd, self._lock_trm, self._lock_relay:
            try:
                if not self.connected:
                    return False, "Устройства не подключены. Сначала подключите устройства."

                if self.blsd20 and hasattr(self.blsd20, 'start_motor'):
                    if not self.blsd20.start_motor():
                        return False, "Ошибка включения двигателя"
                    self.turn_on_motor_blower()

                if self.trm12 and hasattr(self.trm12, 'set_control_mode'):
                    if not self.trm12.set_control_mode(ControlMode.RUN):
                        return False, "Ошибка установки режима работы TRM12"

                return True, "Камера включена"
            except Exception as e:
                return False, f"Ошибка включения камеры: {e}"

    def turn_off_camera(self) -> Tuple[bool, str]:
        with self._lock_blsd, self._lock_trm, self._lock_relay:
            try:
                if not self.connected:
                    return False, "Камера не подключена"

                if self.blsd20 and hasattr(self.blsd20, 'stop_motor'):
                    if not self.blsd20.stop_motor():
                        return False, "Ошибка остановки двигателя"
                    self.turn_off_motor_blower()

                if self.trm12 and hasattr(self.trm12, 'set_control_mode'):
                    if not self.trm12.set_control_mode(ControlMode.MANUAL):
                        return False, "Ошибка переключения TRM12 в ручной режим"

                return True, "Камера выключена"
            except Exception as e:
                return False, f"Ошибка выключения камеры: {e}"

    def emergency_stop(self) -> Tuple[bool, str]:
        with self._lock_blsd, self._lock_trm, self._lock_relay:
            try:
                results = []
                if self.blsd20 and hasattr(self.blsd20, 'connected') and self.blsd20.connected:
                    if hasattr(self.blsd20, 'emergency_stop'):
                        motor_stopped = self.blsd20.emergency_stop()
                        results.append(f"Двигатель: {'остановлен' if motor_stopped else 'ошибка'}")
                    else:
                        results.append("Двигатель: функция emergency_stop не поддерживается")

                if self.relay and hasattr(self.relay, 'is_connected') and self.relay.is_connected():
                    success, _ = self.turn_off_motor_heating()
                    results.append(f"Нагрев: {'выключен' if success else 'ошибка'}")

                if self.trm12 and hasattr(self.trm12, 'is_connected') and self.trm12.is_connected():
                    if hasattr(self.trm12, 'set_control_mode'):
                        oven_stopped = self.trm12.set_control_mode(ControlMode.MANUAL)
                        results.append(f"ОВЕН: {'переведен в ручной режим' if oven_stopped else 'ошибка'}")
                    else:
                        results.append("ОВЕН: функция set_control_mode не поддерживается")

                return True, "Аварийная остановка выполнена: " + ", ".join(results)
            except Exception as e:
                return False, f"Ошибка аварийной остановки: {e}"

    # ============ ГРАДИЕНТ И ТЕМПЕРАТУРА ВАЛА (sleep вне lock) ============

    def get_gradient(self) -> Tuple[Optional[float], str]:
        """
        Градиент = T_камеры − T_внутреннего датчика.

        Внутренний датчик — это второй вход TRM12 (channel=1),
        который через реле 3 и 4 переключается между двумя
        физическими источниками:
          * реле 3,4 РАЗОМКНУТЫ → ко второму входу подключён ДАТЧИК ВАЛА
          * реле 3,4 ЗАМКНУТЫ   → ко второму входу подключён ДАТЧИК КАМЕРЫ

        Измерение градиента требует именно ЗАМКНУТЫХ реле 3,4.
        """
        # --- Быстрая проверка кэша (без захвата _lock_measure) ---
        now = time.time()
        if (self._gradient_cache[0] is not None
                and (now - self._gradient_cache[1]) < self._gradient_cache_ttl):
            return self._gradient_cache[0], "Градиент из кэша"

        with self._lock_measure:
            # Повторная проверка: пока ждали lock, кто-то мог уже измерить
            now = time.time()
            if (self._gradient_cache[0] is not None
                    and (now - self._gradient_cache[1]) < self._gradient_cache_ttl):
                return self._gradient_cache[0], "Градиент из кэша"

            # 1. Температура камеры (channel=0 — отдельный датчик, реле не влияют)
            temp_chamber, msg = self.get_chamber_temperature()
            if temp_chamber is None:
                return None, f"Ошибка получения температуры камеры: {msg}"

            # 2. Замыкаем реле 3,4 → второй вход на датчик камеры
            with self._lock_relay:
                try:
                    if not self.relay or not self.relay.is_connected():
                        return None, "Релейная плата не подключена"
                    if not self.relay.close_relay(3) or not self.relay.close_relay(4):
                        return None, "Ошибка включения реле"
                except Exception as e:
                    return None, f"Ошибка управления реле: {e}"

            # 3. Стабилизация — ОБЯЗАТЕЛЬНО внутри _lock_measure,
            #    иначе другой поток успеет разомкнуть реле и мы прочитаем вал.
            time.sleep(2)

            # 4. Читаем channel=1
            with self._lock_trm:
                try:
                    if not self.trm12 or not self.trm12.is_connected():
                        return None, "TRM12 не подключен"
                    raw_inside = self.trm12.read_parameter("PV", channel=1)
                except Exception as e:
                    return None, f"Ошибка чтения внутреннего датчика: {e}"

            if raw_inside is None:
                return None, "Ошибка чтения внутреннего датчика"

            if self.corrector_shaft:
                try:
                    temp_inside = float(self.corrector_shaft.predict(raw_inside))
                except Exception:
                    temp_inside = raw_inside
            else:
                temp_inside = raw_inside

            gradient = temp_chamber - temp_inside
            self._gradient_cache = (gradient, time.time())
            return gradient, f"Градиент: {gradient:.2f}°C"

    def get_gradient_old(self) -> Tuple[Optional[float], str]:
        # 1. Температура камеры (внутри get_chamber_temperature уже есть _lock_trm)
        temp_chamber, msg = self.get_chamber_temperature()
        if temp_chamber is None:
            return None, f"Ошибка получения температуры камеры: {msg}"

        # 2. Замыкаем реле — под _lock_relay, быстро
        with self._lock_relay:
            try:
                if not self.relay or not self.relay.is_connected():
                    return None, "Релейная плата не подключена"
                if not self.relay.close_relay(3) or not self.relay.close_relay(4):
                    return None, "Ошибка включения реле"
            except Exception as e:
                return None, f"Ошибка управления реле: {e}"

        # 3. Стабилизация — ВНЕ любых блокировок
        time.sleep(2)

        # 4. Читаем внутренний датчик — под _lock_trm
        with self._lock_trm:
            try:
                if not self.trm12 or not self.trm12.is_connected():
                    return None, "TRM12 не подключен"
                raw_inside = self.trm12.read_parameter("PV", channel=1)
            except Exception as e:
                return None, f"Ошибка чтения внутреннего датчика: {e}"

        if raw_inside is None:
            return None, "Ошибка чтения внутреннего датчика"

        if self.corrector_shaft:
            try:
                temp_inside = float(self.corrector_shaft.predict(raw_inside))
            except Exception:
                temp_inside = raw_inside
        else:
            temp_inside = raw_inside

        gradient = temp_chamber - temp_inside
        return gradient, f"Градиент: {gradient:.2f}°C"

    def get_shaft_temperature(self) -> Tuple[Optional[float], str]:
        """
        Температура вала. Измеряется вторым входом TRM12 (channel=1)
        при РАЗОМКНУТЫХ реле 3 и 4.
        """
        # --- Быстрая проверка кэша ---
        now = time.time()
        if (self._shaft_temp_cache[0] is not None
                and (now - self._shaft_temp_cache[1]) < self._shaft_temp_cache_ttl):
            return self._shaft_temp_cache[0], "Температура вала из кэша"

        with self._lock_measure:
            # Повторная проверка после захвата lock
            now = time.time()
            if (self._shaft_temp_cache[0] is not None
                    and (now - self._shaft_temp_cache[1]) < self._shaft_temp_cache_ttl):
                return self._shaft_temp_cache[0], "Температура вала из кэша"

            # 1. РАЗМЫКАЕМ реле 3,4 → второй вход на датчик вала
            with self._lock_relay:
                try:
                    if not self.relay or not hasattr(self.relay, 'is_connected') or not self.relay.is_connected():
                        return None, "Релейная плата не подключена"
                    if not self.relay.open_relay(3):
                        return None, "Ошибка включения реле 3"
                    if not self.relay.open_relay(4):
                        self.relay.close_relay(3)
                        return None, "Ошибка включения реле 4"
                except Exception as e:
                    try:
                        self.relay.close_relay(3)
                        self.relay.close_relay(4)
                    except Exception:
                        pass
                    return None, f"Ошибка управления реле: {e}"

            # 2. Начальная задержка — внутри _lock_measure
            time.sleep(self.shaft_initial_delay)

            max_attempts = self.shaft_max_attempts
            attempt = 0
            prev_temp = None
            stable_temp = None
            current_temp = None

            try:
                while attempt < max_attempts:
                    with self._lock_trm:
                        if not self.trm12 or not self.trm12.is_connected():
                            raise RuntimeError("TRM12 не подключен")
                        raw_temp = self.trm12.read_parameter("PV", channel=1)

                    if raw_temp is None:
                        raise RuntimeError("Ошибка чтения температуры вала")

                    if self.corrector_shaft:
                        try:
                            current_temp = float(self.corrector_shaft.predict(raw_temp))
                        except Exception:
                            current_temp = raw_temp
                    else:
                        current_temp = raw_temp

                    if prev_temp is not None:
                        delta = abs(current_temp - prev_temp)
                        print(f"Попытка {attempt + 1}:  {current_temp:.2f}°C {delta}")
                        if delta < 0.2:
                            stable_temp = current_temp
                            print(f"Попытка {attempt + 1}: окончательное значение {stable_temp:.2f}°C")
                            break
                    else:
                        print(f"Попытка {attempt + 1}: первое измерение {current_temp:.2f}°C")

                    prev_temp = current_temp
                    attempt += 1
                    if attempt < max_attempts:
                        time.sleep(self.shaft_stabilization_interval)

            except Exception as e:
                with self._lock_relay:
                    try:
                        self.relay.close_relay(3)
                        self.relay.close_relay(4)
                    except Exception:
                        pass
                return None, f"Ошибка получения температуры вала: {e}"

            if stable_temp is None:
                stable_temp = current_temp if current_temp is not None else prev_temp

            # 3. ЗАМЫКАЕМ реле 3,4 обратно — внутри _lock_measure,
            #    чтобы никто не прочитал channel=1 в «промежуточном» состоянии.
            with self._lock_relay:
                try:
                    self.relay.close_relay(3)
                    self.relay.close_relay(4)
                except Exception:
                    pass

            # 4. Финальная пауза — тоже внутри _lock_measure,
            #    чтобы следующее измерение началось после того, как TRM12
            #    отработает переключение второго входа.
            time.sleep(self.shaft_final_delay)

            if stable_temp is not None:
                self._shaft_temp_cache = (stable_temp, time.time())
            return stable_temp, "Температура вала получена"

    def get_shaft_temperature_old(self) -> Tuple[Optional[float], str]:
        # 1. Открываем реле 3 и 4
        with self._lock_relay:
            try:
                if not self.relay or not hasattr(self.relay, 'is_connected') or not self.relay.is_connected():
                    return None, "Релейная плата не подключена"
                if not self.relay.open_relay(3):
                    return None, "Ошибка включения реле 3"
                if not self.relay.open_relay(4):
                    self.relay.close_relay(3)
                    return None, "Ошибка включения реле 4"
            except Exception as e:
                try:
                    self.relay.close_relay(3)
                    self.relay.close_relay(4)
                except Exception:
                    pass
                return None, f"Ошибка управления реле: {e}"

        # 2. Начальная задержка — ВНЕ блокировок
        time.sleep(self.shaft_initial_delay)

        max_attempts = self.shaft_max_attempts
        attempt = 0
        prev_temp = None
        stable_temp = None
        current_temp = None

        try:
            while attempt < max_attempts:
                with self._lock_trm:
                    if not self.trm12 or not self.trm12.is_connected():
                        raise RuntimeError("TRM12 не подключен")
                    raw_temp = self.trm12.read_parameter("PV", channel=1)

                if raw_temp is None:
                    raise RuntimeError("Ошибка чтения температуры вала")

                if self.corrector_shaft:
                    try:
                        current_temp = float(self.corrector_shaft.predict(raw_temp))
                    except Exception:
                        current_temp = raw_temp
                else:
                    current_temp = raw_temp

                if prev_temp is not None:
                    delta = abs(current_temp - prev_temp)
                    print(f"Попытка {attempt + 1}:  {current_temp:.2f}°C {delta}")
                    if delta < 0.2:
                        stable_temp = current_temp
                        print(f"Попытка {attempt + 1}: окончательное значение {stable_temp:.2f}°C")
                        break
                else:
                    print(f"Попытка {attempt + 1}: первое измерение {current_temp:.2f}°C")

                prev_temp = current_temp
                attempt += 1
                if attempt < max_attempts:
                    time.sleep(self.shaft_stabilization_interval)

        except Exception as e:
            with self._lock_relay:
                try:
                    self.relay.close_relay(3)
                    self.relay.close_relay(4)
                except Exception:
                    pass
            return None, f"Ошибка получения температуры вала: {e}"

        if stable_temp is None:
            stable_temp = current_temp if current_temp is not None else prev_temp

        with self._lock_relay:
            try:
                self.relay.close_relay(3)
                self.relay.close_relay(4)
            except Exception:
                pass

        time.sleep(self.shaft_final_delay)

        return stable_temp, "Температура вала получена"

    # ============ ПОДКЛЮЧЕНИЕ / ОТКЛЮЧЕНИЕ ============

    def _save_connection_params(self, device_type: DeviceType):
        if device_type == DeviceType.TRM12:
            params = self.devices_data.trm12
            self._connection_params['trm12'] = {
                'com_port': params.com_port, 'baudrate': params.baudrate, 'address': params.address
            }
        elif device_type == DeviceType.BLSD20:
            params = self.devices_data.blsd20
            self._connection_params['blsd20'] = {
                'com_port': params.com_port, 'baudrate': params.baudrate, 'address': params.address
            }
        elif device_type == DeviceType.RS232_4PIN_RELAY:
            params = self.devices_data.rs232_relay
            self._connection_params['relay'] = {
                'com_port': params.com_port, 'baudrate': params.baudrate
            }

    def _check_connection_params_changed(self, device_type: DeviceType) -> bool:
        try:
            if device_type == DeviceType.TRM12:
                params = self.devices_data.trm12
                old = self._connection_params.get('trm12', {})
                return (old.get('com_port') != params.com_port or
                        old.get('baudrate') != params.baudrate or
                        old.get('address') != params.address)
            elif device_type == DeviceType.BLSD20:
                params = self.devices_data.blsd20
                old = self._connection_params.get('blsd20', {})
                return (old.get('com_port') != params.com_port or
                        old.get('baudrate') != params.baudrate or
                        old.get('address') != params.address)
            elif device_type == DeviceType.RS232_4PIN_RELAY:
                params = self.devices_data.rs232_relay
                old = self._connection_params.get('relay', {})
                return (old.get('com_port') != params.com_port or
                        old.get('baudrate') != params.baudrate)
            return False
        except Exception:
            return True

    def reconnect_device(self, device_type: DeviceType) -> Tuple[bool, str]:
        with self._lock_blsd, self._lock_trm, self._lock_relay:
            try:
                if device_type == DeviceType.TRM12 and self.trm12:
                    self.trm12.disconnect()
                    self.trm12 = None
                elif device_type == DeviceType.BLSD20 and self.blsd20:
                    self.blsd20.disconnect()
                    self.blsd20 = None
                elif device_type == DeviceType.RS232_4PIN_RELAY and self.relay:
                    self.relay.disconnect()
                    self.relay = None

                if hasattr(self.devices_data, 'device_drivers_dict'):
                    self.devices_data.device_drivers_dict[device_type] = None

                success, message = self._create_driver(device_type)
                if not success:
                    return False, message
                return self._connect_device(device_type)
            except Exception as e:
                return False, f"Ошибка переподключения к {device_type.value}: {e}"

    def connect_all(self) -> Tuple[bool, Dict[str, str]]:
        with self._lock_blsd, self._lock_trm, self._lock_relay:
            results = {}
            overall_success = True
            for key, dev_type in (('TRM12', DeviceType.TRM12),
                                  ('BLSD20', DeviceType.BLSD20),
                                  ('Relay', DeviceType.RS232_4PIN_RELAY)):
                success, message = self._connect_device(dev_type)
                results[key] = message
                if not success:
                    overall_success = False
            self.connected = overall_success
            return overall_success, results

    def disconnect_all(self) -> Dict[str, str]:
        with self._lock_blsd, self._lock_trm, self._lock_relay:
            results = {}
            if self.trm12 and hasattr(self.trm12, 'is_connected') and self.trm12.is_connected():
                self.trm12.disconnect()
                results['TRM12'] = "Отключено"
            if self.blsd20 and hasattr(self.blsd20, 'connected') and self.blsd20.connected:
                self.blsd20.disconnect()
                results['BLSD20'] = "Отключено"
            if self.relay and hasattr(self.relay, 'is_connected') and self.relay.is_connected():
                self.relay.disconnect()
                results['Relay'] = "Отключено"
            self.connected = False
            return results

    def check_connection_status(self) -> Dict[str, Any]:
        with self._lock_blsd, self._lock_trm, self._lock_relay:
            status = {'overall_connected': self.connected, 'devices': {}}
            status['devices']['TRM12'] = {
                'driver_exists': self.trm12 is not None,
                'connected': (self.trm12.is_connected()
                              if self.trm12 and hasattr(self.trm12, 'is_connected') else False),
                'params_changed': self._check_connection_params_changed(DeviceType.TRM12)
            }
            status['devices']['BLSD20'] = {
                'driver_exists': self.blsd20 is not None,
                'connected': self.blsd20.connected if self.blsd20 else False,
                'params_changed': self._check_connection_params_changed(DeviceType.BLSD20)
            }
            status['devices']['Relay'] = {
                'driver_exists': self.relay is not None,
                'connected': (self.relay.is_connected()
                              if self.relay and hasattr(self.relay, 'is_connected') else False),
                'params_changed': self._check_connection_params_changed(DeviceType.RS232_4PIN_RELAY)
            }
            return status

    def auto_reconnect_if_needed(self) -> Dict[str, str]:
        results = {}
        for device_type in [DeviceType.TRM12, DeviceType.BLSD20, DeviceType.RS232_4PIN_RELAY]:
            device_name = device_type.value
            if self._check_connection_params_changed(device_type):
                _, message = self.reconnect_device(device_type)
                results[device_name] = f"Переподключено: {message}"
            else:
                results[device_name] = "Переподключение не требуется"
        return results

    def connect_and_initialize(self) -> Tuple[bool, Dict[str, str]]:
        with self._lock_blsd, self._lock_trm, self._lock_relay:
            results = {}
            overall_success = True
            connection_table = []
            info_table = []

            devices = [
                ('TRM12', DeviceType.TRM12, 'Терморегулятор'),
                ('BLSD20', DeviceType.BLSD20, 'Двигатель BLSD-20'),
                ('Relay', DeviceType.RS232_4PIN_RELAY, 'Релейная плата')
            ]
            for key, device_type, description in devices:
                success, message = self._connect_device(device_type)
                results[key] = message
                connection_table.append(
                    [description, "✓" if success else "✗",
                     "Успешно" if success else "Ошибка", message]
                )
                if not success:
                    overall_success = False

            self.connected = overall_success

            if overall_success:
                try:
                    temp, _ = self.get_chamber_temperature()
                    if temp is not None:
                        info_table.append(["Температура камеры", f"{temp:.2f}°C"])
                    if self.trm12:
                        info = self.trm12.get_device_info()
                        if info:
                            info_table.append(["Информация TRM12", info])
                    if self.blsd20:
                        st = self.blsd20.get_status()
                        if st is not None:
                            info_table.append(["Статус двигателя", str(st)])
                except Exception as e:
                    info_table.append(["Ошибка чтения данных", str(e)])

            print("\n" + "=" * 60)
            print("РЕЗУЛЬТАТЫ ПОДКЛЮЧЕНИЯ УСТРОЙСТВ".center(60))
            print("=" * 60)
            headers = ["Устройство", "Статус", "Результат", "Сообщение"]
            print(tabulate(connection_table, headers=headers, tablefmt="grid", stralign="left"))
            if info_table:
                print("\n" + "-" * 40)
                print("СВЕДЕНИЯ О СИСТЕМЕ".center(40))
                print("-" * 40)
                print(tabulate(info_table, tablefmt="simple", stralign="left"))
            print("\n" + "=" * 60)
            if overall_success:
                print("\033[92m✓ ВСЕ УСТРОЙСТВА УСПЕШНО ПОДКЛЮЧЕНЫ\033[0m".center(60))
            else:
                print("\033[91m✗ ОШИБКА ПОДКЛЮЧЕНИЯ УСТРОЙСТВ\033[0m".center(60))
            print("=" * 60)

            return overall_success, results

    def __enter__(self):
        self.connect_all()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.disconnect_all()


CAMERA_CONTROLLER = CameraController()


def get_camera_controller() -> CameraController:
    return CAMERA_CONTROLLER


def initialize_camera_system() -> Tuple[bool, Dict[str, str]]:
    return CAMERA_CONTROLLER.connect_all()


def shutdown_camera_system() -> Dict[str, str]:
    return CAMERA_CONTROLLER.disconnect_all()
# camera_controller.py
import threading
import time
from typing import Optional, Dict, Any, Tuple
from BLSD.client_blsd20 import BLSD20ModbusDriver
from Ports_COM.client import DeviceType
from Ports_COM.Devices_Data import DEVICES_DATA  # Добавлен импорт
from RS232_4pin_Rele.Client import RS232RelayDriver
from owen.Client import TRM12Driver, ByteOrder, ControlMode
from tabulate import tabulate

from owen.Temp_Corrector_class import PolynomialCorrector


# Класс для управления температурной камерой
class CameraController:
    """
    Единый драйвер управления камерой, использующий три устройства:
    1. BLSD-20Modbus (двигатель вентилятора)
    2. TRM12 (терморегулятор)
    3. RS232-4pin-Relay (релейная плата для переключения датчиков)
    """

    def __init__(self, devices_data: Optional[Any] = None):
        """Инициализация контроллера камеры"""
        self.blsd20 = None
        self.trm12 = None
        self.relay = None
        self.soak_time = 0  # Время выдержки на температуре
        self.connected = False
        self._connection_params = {}

        # Используем переданный объект DEVICES_DATA или импортированный по умолчанию
        self.devices_data = devices_data if devices_data is not None else DEVICES_DATA

        self._lock = threading.RLock()  # блокировка для синхронизации

        self.corrector_chamber: Optional[PolynomialCorrector] = None  # канал 0 (камера)
        self.corrector_shaft: Optional[PolynomialCorrector] = None  # канал 1 (вал)

        # Параметры измерения температуры вала
        self.shaft_stabilization_interval = 2.0  # интервал между попытками (сек)
        self.shaft_max_attempts = 15  # максимальное количество попыток
        self.shaft_initial_delay = 5.0  # задержка после переключения реле
        self.shaft_final_delay = 20.0

    def set_shaft_params(self, stabilization_interval: float = None, attempts: int = None,
                         initial_delay: float = None, final_delay: float = None):
        """Установить параметры измерения температуры вала"""
        if stabilization_interval is not None:
            self.shaft_stabilization_interval = stabilization_interval
        if attempts is not None:
            self.shaft_max_attempts = attempts
        if initial_delay is not None:
            self.shaft_initial_delay = initial_delay
        if final_delay is not None:
            self.shaft_final_delay = final_delay

    def set_corrector(self, channel: int, corrector: PolynomialCorrector) -> None:
        """Установить корректор для указанного канала (0 – камера, 1 – вал)"""
        if channel == 0:
            self.corrector_chamber = corrector
        elif channel == 1:
            self.corrector_shaft = corrector
        else:
            raise ValueError("Канал должен быть 0 или 1")

    def _create_driver(self, device_type: DeviceType) -> Tuple[bool, str]:
        """
        Создание драйвера устройства с текущими параметрами подключения

        Args:
            device_type: Тип устройства

        Returns:
            Tuple[bool, str]: (Успех создания, Сообщение об ошибке)
        """
        print('Create', device_type)
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
            print(e)
            return False, f"Ошибка создания драйвера {device_type}: {e}"

    def _connect_device(self, device_type: DeviceType) -> Tuple[bool, str]:
        """
        Подключение к устройству с сохранением драйвера в DEVICES_DATA

        Args:
            device_type: Тип устройства

        Returns:
            Tuple[bool, str]: (Успех подключения, Сообщение)
        """
        try:
            # Получаем или создаем драйвер
            driver_current = self.devices_data.get_device_driver(device_type)
            if driver_current is None:
                # Создаем новый драйвер
                success, message = self._create_driver(device_type)
                if not success:
                    return False, message
                driver_current = self.devices_data.get_device_driver(device_type)

            # Проверяем подключение
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

            # Сохраняем параметры подключения для проверки изменений
            self._save_connection_params(device_type)
            return True, f"Успешно подключено к {device_type.value}"

        except Exception as e:
            print('Error', e)
            return False, f"Ошибка подключения к {device_type.value}: {e}"

    def get_pid_parameters(self, channel: int = 0) -> Optional[Dict[str, Any]]:
        """
        Получить параметры ПИД-регулятора для указанного канала.

        Args:
            channel: Номер канала (0 или 1)

        Returns:
            Optional[Dict]: Словарь с параметрами или None при ошибке.
            Словарь содержит ключи: P, I, D, deadband, output_min, output_max, hysteresis.
        """
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
        """
        Установить параметры ПИД-регулятора для указанного канала.

        Args:
            P: Пропорциональная составляющая
            I: Интегральная постоянная
            D: Дифференциальная постоянная
            deadband: Зона нечувствительности
            output_min: Нижний предел выходной мощности
            output_max: Верхний предел выходной мощности
            channel: Номер канала (0 или 1)

        Returns:
            Tuple[bool, str]: (Успех операции, Сообщение)
        """
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
            else:
                return False, "Ошибка при установке ПИД-параметров (проверьте журнал)"
        except Exception as e:
            return False, f"Ошибка установки ПИД-параметров: {e}"

    def _save_connection_params(self, device_type: DeviceType):
        """
        Сохранение текущих параметров подключения для отслеживания изменений

        Args:
            device_type: Тип устройства
        """
        if device_type == DeviceType.TRM12:
            params = self.devices_data.trm12
            self._connection_params['trm12'] = {
                'com_port': params.com_port,
                'baudrate': params.baudrate,
                'address': params.address
            }
        elif device_type == DeviceType.BLSD20:
            params = self.devices_data.blsd20
            self._connection_params['blsd20'] = {
                'com_port': params.com_port,
                'baudrate': params.baudrate,
                'address': params.address
            }
        elif device_type == DeviceType.RS232_4PIN_RELAY:
            params = self.devices_data.rs232_relay
            self._connection_params['relay'] = {
                'com_port': params.com_port,
                'baudrate': params.baudrate
            }

    def _check_connection_params_changed(self, device_type: DeviceType) -> bool:
        """
        Проверка изменения параметров подключения

        Args:
            device_type: Тип устройства

        Returns:
            bool: True если параметры изменились
        """
        try:
            if device_type == DeviceType.TRM12:
                params = self.devices_data.trm12
                old_params = self._connection_params.get('trm12', {})
                return (old_params.get('com_port') != params.com_port or
                        old_params.get('baudrate') != params.baudrate or
                        old_params.get('address') != params.address)

            elif device_type == DeviceType.BLSD20:
                params = self.devices_data.blsd20
                old_params = self._connection_params.get('blsd20', {})
                return (old_params.get('com_port') != params.com_port or
                        old_params.get('baudrate') != params.baudrate or
                        old_params.get('address') != params.address)

            elif device_type == DeviceType.RS232_4PIN_RELAY:
                params = self.devices_data.rs232_relay
                old_params = self._connection_params.get('relay', {})
                return (old_params.get('com_port') != params.com_port or
                        old_params.get('baudrate') != params.baudrate)

            return False
        except:
            return True

    def reconnect_device(self, device_type: DeviceType) -> Tuple[bool, str]:
        """
        Принудительное переподключение к устройству с обновлением драйвера

        Args:
            device_type: Тип устройства

        Returns:
            Tuple[bool, str]: (Успех, Сообщение)
        """
        try:
            # Отключаем если подключено
            if device_type == DeviceType.TRM12 and self.trm12:
                self.trm12.disconnect()
                self.trm12 = None
            elif device_type == DeviceType.BLSD20 and self.blsd20:
                self.blsd20.disconnect()
                self.blsd20 = None
            elif device_type == DeviceType.RS232_4PIN_RELAY and self.relay:
                self.relay.disconnect()
                self.relay = None

            # Удаляем старый драйвер
            if hasattr(self.devices_data, 'device_drivers_dict'):
                self.devices_data.device_drivers_dict[device_type] = None

            # Создаем новый драйвер
            success, message = self._create_driver(device_type)
            if not success:
                return False, message

            # Подключаемся
            return self._connect_device(device_type)

        except Exception as e:
            return False, f"Ошибка переподключения к {device_type.value}: {e}"

    def connect_all(self) -> Tuple[bool, Dict[str, str]]:
        """
        Подключение ко всем устройствам с автоматическим созданием драйверов

        Returns:
            Tuple[bool, Dict[str, str]]: (Общий успех, Результаты по устройствам)
        """
        results = {}
        overall_success = True

        # Подключаемся к TRM12
        success, message = self._connect_device(DeviceType.TRM12)
        results['TRM12'] = message
        if not success:
            overall_success = False

        # Подключаемся к BLSD-20
        success, message = self._connect_device(DeviceType.BLSD20)
        results['BLSD20'] = message
        if not success:
            overall_success = False

        # Подключаемся к релейной плате
        success, message = self._connect_device(DeviceType.RS232_4PIN_RELAY)
        results['Relay'] = message
        if not success:
            overall_success = False

        self.connected = overall_success
        return overall_success, results

    def disconnect_all(self) -> Dict[str, str]:
        """
        Отключение от всех устройств

        Returns:
            Dict[str, str]: Результаты отключения по устройствам
        """
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
        """
        Проверка статуса подключения всех устройств

        Returns:
            Dict[str, Any]: Статус подключения
        """
        status = {
            'overall_connected': self.connected,
            'devices': {}
        }

        # Проверяем TRM12
        trm12_status = {
            'driver_exists': self.trm12 is not None,
            'connected': self.trm12.is_connected() if self.trm12 and hasattr(self.trm12, 'is_connected') else False,
            'params_changed': self._check_connection_params_changed(DeviceType.TRM12)
        }
        status['devices']['TRM12'] = trm12_status

        # Проверяем BLSD-20
        blsd20_status = {
            'driver_exists': self.blsd20 is not None,
            'connected': self.blsd20.connected if self.blsd20 else False,
            'params_changed': self._check_connection_params_changed(DeviceType.BLSD20)
        }
        status['devices']['BLSD20'] = blsd20_status

        # Проверяем релейную плату
        relay_status = {
            'driver_exists': self.relay is not None,
            'connected': self.relay.is_connected() if self.relay and hasattr(self.relay, 'is_connected') else False,
            'params_changed': self._check_connection_params_changed(DeviceType.RS232_4PIN_RELAY)
        }
        status['devices']['Relay'] = relay_status

        return status

    def auto_reconnect_if_needed(self) -> Dict[str, str]:
        """
        Автоматическое переподключение устройств при необходимости

        Returns:
            Dict[str, str]: Результаты переподключения
        """
        results = {}

        # Проверяем каждое устройство
        for device_type in [DeviceType.TRM12, DeviceType.BLSD20, DeviceType.RS232_4PIN_RELAY]:
            device_name = device_type.value

            # Проверяем нужно ли переподключение
            if self._check_connection_params_changed(device_type):
                success, message = self.reconnect_device(device_type)
                results[device_name] = f"Переподключено: {message}"
            else:
                results[device_name] = "Переподключение не требуется"

        return results

    # ============ ОСНОВНЫЕ ФУНКЦИИ УПРАВЛЕНИЯ ============
    def turn_on_camera(self) -> Tuple[bool, str]:
        """
        Включить камеру (Включить двигатель, переключить oven в режим работы)

        Returns:
            Tuple[bool, str]: (Успех, Сообщение)
        """
        try:
            # Проверяем подключение
            if not self.connected:
                return False, "Устройства не подключены. Сначала подключите устройства."

            # Включаем двигатель
            if self.blsd20 and hasattr(self.blsd20, 'start_motor'):
                if not self.blsd20.start_motor():
                    return False, "Ошибка включения двигателя"

            # Устанавливаем режим автоматического регулирования для TRM12
            if self.trm12 and hasattr(self.trm12, 'set_control_mode'):
                if not self.trm12.set_control_mode(ControlMode.RUN):
                    return False, "Ошибка установки режима работы TRM12"

            return True, "Камера включена"

        except Exception as e:
            return False, f"Ошибка включения камеры: {e}"

    def turn_off_camera(self) -> Tuple[bool, str]:
        """
        Выключить камеру

        Returns:
            Tuple[bool, str]: (Успех, Сообщение)
        """
        try:
            # Проверяем подключение
            if not self.connected:
                return False, "Камера не подключена"

            # Останавливаем двигатель с замедлением
            if self.blsd20 and hasattr(self.blsd20, 'stop_motor'):
                if not self.blsd20.stop_motor():
                    return False, "Ошибка остановки двигателя"

            # Переводим TRM12 в ручной режим
            if self.trm12 and hasattr(self.trm12, 'set_control_mode'):
                if not self.trm12.set_control_mode(ControlMode.MANUAL):
                    return False, "Ошибка переключения TRM12 в ручной режим"

            return True, "Камера выключена"

        except Exception as e:
            return False, f"Ошибка выключения камеры: {e}"

    def set_temperature(self, temperature: float, channel: int = 0) -> Tuple[bool, str]:
        """
        Задать температуру

        Args:
            temperature: Температура в градусах
            channel: Номер канала (0 или 1)

        Returns:
            Tuple[bool, str]: (Успех, Сообщение)
        """
        try:
            if not self.trm12 or not hasattr(self.trm12, 'is_connected') or not self.trm12.is_connected():
                return False, "TRM12 не подключен"

            if not hasattr(self.trm12, 'set_setpoint'):
                return False, "TRM12 драйвер не поддерживает установку температуры"

            success = self.trm12.set_setpoint(temperature, channel)
            return success, f"Температура установлена на {temperature}°C" if success else "Ошибка установки температуры"
        except Exception as e:
            return False, f"Ошибка установки температуры: {e}"

    def set_fan_speed(self, speed: int) -> Tuple[bool, str]:
        """
        Задать скорость вентилятора (0-4000 об/мин)

        Args:
            speed: Скорость в об/мин

        Returns:
            Tuple[bool, str]: (Успех, Сообщение)
        """
        try:
            if not self.blsd20 or not hasattr(self.blsd20, 'connected') or not self.blsd20.connected:
                return False, "BLSD-20 не подключен"

            if not hasattr(self.blsd20, 'set_speed'):
                return False, "BLSD-20 драйвер не поддерживает установку скорости"

            speed = max(0, min(4000, speed))
            success = self.blsd20.set_speed(speed)
            return success, f"Скорость установлена на {speed} об/мин" if success else "Ошибка установки скорости"
        except Exception as e:
            return False, f"Ошибка установки скорости вентилятора: {e}"



    def get_chamber_temperature(self) -> Tuple[Optional[float], str]:
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

    # Возвращает температуру уставки первого канала регулятора

    def get_chamber_setpoint(self) -> Tuple[Optional[float], str]:
        """
        Получить уставку температуры камеры

        Returns:
            Tuple[Optional[float], str]: (Уставка, Сообщение)
        """
        try:
            if not self.trm12 or not hasattr(self.trm12, 'is_connected') or not self.trm12.is_connected():
                return None, "TRM12 не подключен"

            setpoints = self.trm12.get_setpoints()

            # Ищем уставку камеры (предполагаем, что это Канал 1 или Канал 0)
            if 'Канал 1' in setpoints:
                return setpoints['Канал 1'], "Уставка камеры получена"
            else:
                return None, "Уставка не найдена"
        except Exception as e:
            return None, f"Ошибка получения уставки камеры: {e}"

    def get_shaft_temperature(self) -> Tuple[Optional[float], str]:
        with self._lock:
            try:
                if not self.trm12 or not hasattr(self.trm12, 'is_connected') or not self.trm12.is_connected():
                    return None, "TRM12 не подключен"
                if not self.relay or not hasattr(self.relay, 'is_connected') or not self.relay.is_connected():
                    return None, "Релейная плата не подключена"
                '''
                # Логирование текущих температур (опционально)
                temp_0 = self.trm12.read_parameter("PV", channel=0)
                temp_1 = self.trm12.read_parameter("PV", channel=1)
                '''
                # Переключаем реле для подключения датчика вала (open = разомкнуть)
                if not self.relay.open_relay(3):
                    return None, "Ошибка включения реле 3"
                if not self.relay.open_relay(4):
                    self.relay.close_relay(3)  # откат
                    return None, "Ошибка включения реле 4"

                # Начальная задержка стабилизации
                time.sleep(self.shaft_initial_delay)

                # Цикл измерения с контролем стабильности
                max_attempts = self.shaft_max_attempts
                attempt = 0
                prev_temp = None
                stable_temp = None
                current_temp = None
                while attempt < max_attempts:
                    raw_temp = self.trm12.read_parameter("PV", channel=1)
                    if raw_temp is None:
                        self.relay.close_relay(3)
                        self.relay.close_relay(4)
                        return None, "Ошибка чтения температуры вала"
                    if self.corrector_shaft:
                        current_temp = float(self.corrector_shaft.predict(raw_temp))
                    else:
                        current_temp = raw_temp
                    if prev_temp is not None:
                        delta = abs(current_temp - prev_temp)
                        print(f"Попытка {attempt + 1}:  {current_temp:.2f}°C {delta}" )
                        if delta < 0.2:
                            stable_temp = current_temp
                            print(f"Попытка {attempt + 1}: окончательное значение {stable_temp:.2f}°C")
                            break
                    else:
                        print(f"Попытка {attempt + 1}: первое измерение {current_temp:.2f}°C")

                    prev_temp = current_temp
                    attempt += 1
                    if attempt < max_attempts:
                        time.sleep(self.shaft_stabilization_interval)  # используем новый атрибут


                if stable_temp is None:
                    stable_temp = current_temp if current_temp is not None else prev_temp

                self.relay.close_relay(3)
                self.relay.close_relay(4)
                time.sleep(self.shaft_final_delay)  # используем новый атрибут

                return stable_temp, "Температура вала получена"

            except Exception as e:
                # аварийное отключение реле
                try:
                    self.relay.close_relay(3)
                    self.relay.close_relay(4)
                except:
                    pass
                return None, f"Ошибка получения температуры вала: {e}"


    def get_temperature_rate(self, channel: int = 0) -> Optional[float]:
        """Получить текущую скорость изменения уставки (USP)."""
        try:
            if not self.trm12 or not self.trm12.is_connected():
                return None
            return self.trm12.read_parameter("USP", channel=channel)
        except Exception as e:
            print(f"Ошибка чтения скорости нагрева: {e}")
            return None

    def set_temperature_rate(self, rate: float, channel: int = 0) -> Tuple[bool, str]:
        """Установить скорость изменения уставки (USP)."""
        try:
            if not self.trm12 or not self.trm12.is_connected():
                return False, "TRM12 не подключен"
            success = self.trm12.write_parameter("USP", rate, channel=channel)
            return success, "Скорость нагрева установлена" if success else "Ошибка установки скорости"
        except Exception as e:
            return False, f"Ошибка: {e}"

    def turn_on_motor_heating(self) -> Tuple[bool, str]:
        """
        Включить нагрев двигателя (включить реле 1 и реле 2)

        Returns:
            Tuple[bool, str]: (Успех, Сообщение)
        """
        try:
            if not self.relay or not hasattr(self.relay, 'is_connected') or not self.relay.is_connected():
                return False, "Релейная плата не подключена"

            # Включаем реле 1 и реле 2
            success1 = self.relay.open_relay(1)
            success2 = self.relay.open_relay(2)
            if success1 and success2:
                return True, "Нагрев двигателя включен"
            else:
                # Если одно из реле не включилось, выключаем оба для безопасности
                self.relay.close_relay(1)
                self.relay.close_relay(2)
                return False, "Ошибка включения нагрева двигателя"
        except Exception as e:
            return False, f"Ошибка включения нагрева двигателя: {e}"

    def turn_off_motor_heating(self) -> Tuple[bool, str]:
        """
        Выключить нагрев двигателя (выключить реле 1 и реле 2)

        Returns:
            Tuple[bool, str]: (Успех, Сообщение)
        """
        try:
            if not self.relay or not hasattr(self.relay, 'is_connected') or not self.relay.is_connected():
                return False, "Релейная плата не подключена"

            # Выключаем реле 1 и реле 2
            success1 = self.relay.close_relay(1)
            success2 = self.relay.close_relay(2)
            if success1 and success2:
                return True, "Нагрев двигателя выключен"
            else:
                return False, "Ошибка выключения нагрева двигателя"
        except Exception as e:
            return False, f"Ошибка выключения нагрева двигателя: {e}"

    def get_motor_status(self) -> Tuple[Optional[str], str]:
        """
        Получить статус двигателя

        Returns:
            Tuple[Optional[str], str]: (Статус или None, Сообщение)
        """
        try:
            if not self.blsd20 or not hasattr(self.blsd20, 'connected') or not self.blsd20.connected:
                return None, "BLSD-20 не подключен"

            if not hasattr(self.blsd20, 'get_status'):
                return None, "BLSD-20 драйвер не поддерживает получение статуса"

            status = self.blsd20.get_status()
            if status is None:
                return None, "Ошибка чтения статуса"

            status_map = {
                0: "СТОП",
                1: "ВПЕРЕД",
                2: "НАЗАД"
            }

            status_text = status_map.get(status, f"Неизвестный статус: {status}")
            return status_text, "Статус получен"
        except Exception as e:
            return None, f"Ошибка получения статуса двигателя: {e}"

    def heat_pulse(self, duration: float = 5.0) -> Tuple[bool, str]:
        """
        Импульс нагрева - включить нагрев двигателя на заданное время

        Args:
            duration: Длительность импульса в секундах

        Returns:
            Tuple[bool, str]: (Успех, Сообщение)
        """
        try:
            if not self.relay or not hasattr(self.relay, 'is_connected') or not self.relay.is_connected():
                return False, "Релейная плата не подключена"

            # Включаем нагрев
            success, message = self.turn_on_motor_heating()
            if not success:
                return False, message

            # Ждем указанное время
            time.sleep(duration)

            # Выключаем нагрев
            success, message = self.turn_off_motor_heating()
            return success, "Импульс нагрева выполнен" if success else message

        except Exception as e:
            # Пытаемся выключить нагрев в любом случае
            self.turn_off_motor_heating()
            return False, f"Ошибка импульса нагрева: {e}"

    def emergency_stop(self) -> Tuple[bool, str]:
        """
        Аварийная остановка всей системы камеры

        Returns:
            Tuple[bool, str]: (Успех, Сообщение)
        """
        try:
            results = []

            # Аварийная остановка двигателя
            if self.blsd20 and hasattr(self.blsd20, 'connected') and self.blsd20.connected:
                if hasattr(self.blsd20, 'emergency_stop'):
                    motor_stopped = self.blsd20.emergency_stop()
                    results.append(f"Двигатель: {'остановлен' if motor_stopped else 'ошибка'}")
                else:
                    results.append("Двигатель: функция emergency_stop не поддерживается")

            # Выключаем нагрев двигателя
            if self.relay and hasattr(self.relay, 'is_connected') and self.relay.is_connected():
                success, _ = self.turn_off_motor_heating()
                results.append(f"Нагрев: {'выключен' if success else 'ошибка'}")

            # Переводим ОВЕН в ручной режим
            if self.trm12 and hasattr(self.trm12, 'is_connected') and self.trm12.is_connected():
                if hasattr(self.trm12, 'set_control_mode'):
                    oven_stopped = self.trm12.set_control_mode(ControlMode.MANUAL)
                    results.append(f"ОВЕН: {'переведен в ручной режим' if oven_stopped else 'ошибка'}")
                else:
                    results.append("ОВЕН: функция set_control_mode не поддерживается")

            message = "Аварийная остановка выполнена: " + ", ".join(results)
            return True, message

        except Exception as e:
            return False, f"Ошибка аварийной остановки: {e}"

    def get_fan_speed(self) -> Optional[int]:
        """
        Получить скорость вентилятора

        Returns:
            Optional[int]: Скорость в об/мин или None при ошибке
        """
        try:
            if not self.blsd20 or not hasattr(self.blsd20, 'connected') or not self.blsd20.connected:
                return None

            if hasattr(self.blsd20, 'get_speed'):
                speed = self.blsd20.get_speed()
                return speed
            else:
                return None
        except Exception as e:
            print(f"Ошибка получения скорости вентилятора: {e}")
            return None

    def get_motor_current(self) -> Optional[float]:
        """
        Получить ток двигателя

        Returns:
            Optional[float]: Ток в мА или None при ошибке
        """
        try:
            if not self.blsd20 or not hasattr(self.blsd20, 'connected') or not self.blsd20.connected:
                return None

            cur = self.blsd20.get_current()
            if cur is not None:
                return cur
            else:
                return None
        except Exception as e:
            print(f"Ошибка получения тока двигателя: {e}")
            return None

    def get_oven_status(self) -> Optional[Dict[str, Any]]:
        """
        Получить статус терморегулятора (ОВЕН)

        Returns:
            Optional[Dict]: Статус ОВЕН или None при ошибке
        """
        try:
            if not self.trm12 or not hasattr(self.trm12, 'is_connected') or not self.trm12.is_connected():
                return None

            # Получаем режим управления
            mode_dice = self.trm12.get_control_mode()
            return mode_dice['name']
        except Exception as e:
            print(f"Ошибка получения статуса ОВЕН: {e}")
            return None

    def get_gradient(self) -> Tuple[Optional[float], str]:
        with self._lock:
            try:
                if not self.connected:
                    return None, "Устройства не подключены"

                temp_chamber, msg = self.get_chamber_temperature()
                if temp_chamber is None:
                    return None, f"Ошибка получения температуры камеры: {msg}"

                # Подключаем внутренний датчик (замыкаем реле 3 и 4)
                if not self.relay.close_relay(3) or not self.relay.close_relay(4):
                    return None, "Ошибка включения реле"

                time.sleep(2)  # стабилизация

                raw_inside = self.trm12.read_parameter("PV", channel=1)
                if raw_inside is None:
                    return None, "Ошибка чтения внутреннего датчика"
                temp_inside = raw_inside
                if self.corrector_shaft:
                    temp_inside = float(self.corrector_shaft.predict(raw_inside))
                else:
                    temp_inside = raw_inside

                # Реле остаются замкнутыми (штатное состояние для градиента)
                gradient = temp_chamber - temp_inside
                return gradient, f"Градиент: {gradient:.2f}°C"
            except Exception as e:
                return None, f"Ошибка измерения градиента: {e}"



    def connect_and_initialize(self) -> Tuple[bool, Dict[str, str]]:
        """
        Подключение ко всем устройствам без их активации (без включения двигателя и терморегулятора)

        Returns:
            Tuple[bool, Dict[str, str]]: (Общий успех, Результаты по устройствам)
        """
        results = {}
        overall_success = True

        # Данные для таблиц
        connection_table = []
        info_table = []

        # Подключаемся к устройствам
        devices = [
            ('TRM12', DeviceType.TRM12, 'Терморегулятор'),
            ('BLSD20', DeviceType.BLSD20, 'Двигатель BLSD-20'),
            ('Relay', DeviceType.RS232_4PIN_RELAY, 'Релейная плата')
        ]

        for key, device_type, description in devices:
            success, message = self._connect_device(device_type)
            results[key] = message

            status_icon = "✓" if success else "✗"
            status_text = "Успешно" if success else "Ошибка"
            connection_table.append([description, status_icon, status_text, message])

            if not success:
                overall_success = False

        # Устанавливаем флаг подключения
        self.connected = overall_success

        # Получаем дополнительную информацию
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
                    status = self.blsd20.get_status()
                    if status is not None:
                        info_table.append(["Статус двигателя", str(status)])

            except Exception as e:
                info_table.append(["Ошибка чтения данных", str(e)])

        # Выводим таблицы
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

        # Итоговый статус
        print("\n" + "=" * 60)
        if overall_success:
            print("\033[92m✓ ВСЕ УСТРОЙСТВА УСПЕШНО ПОДКЛЮЧЕНЫ\033[0m".center(60))
        else:
            print("\033[91m✗ ОШИБКА ПОДКЛЮЧЕНИЯ УСТРОЙСТВ\033[0m".center(60))
        print("=" * 60)

        return overall_success, results

    # Контекстный менеджер для безопасного управления
    def __enter__(self):
        self.connect_all()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.disconnect_all()


# Создаем глобальный экземпляр контроллера
CAMERA_CONTROLLER = CameraController()


# Функции для удобного доступа из других модулей
def get_camera_controller() -> CameraController:
    """Получить глобальный экземпляр контроллера камеры"""
    return CAMERA_CONTROLLER


def initialize_camera_system() -> Tuple[bool, Dict[str, str]]:
    """Инициализировать всю систему камеры"""
    return CAMERA_CONTROLLER.connect_all()


def shutdown_camera_system() -> Dict[str, str]:
    """Выключить всю систему камеры"""
    return CAMERA_CONTROLLER.disconnect_all()

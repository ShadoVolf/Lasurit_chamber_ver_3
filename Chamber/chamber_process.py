import time
import threading
from typing import Optional
from datetime import datetime

from Chamber.chamber_data import ChamberData, ProcessStatus
from Chamber.chamber_driver import CameraController
from Chamber.temperature_program import TemperatureProgram


class ChamberProcess:
    """
    Управление процессом нагрева/выдержки камеры в отдельном потоке.
    """

    def __init__(self, camera_controller: CameraController):
        self._current_setpoint = None
        self.camera = camera_controller
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._lock = threading.Lock()
        self.data = ChamberData()
        self._target_temp = 0.0
        self._hold_minutes = 0.0

        # Параметры алгоритма (можно вынести в настройки)
        self.epsilon_reach = 0.2           # допуск при выходе на температуру
        self.epsilon_stable = 0.1          # допуск стабильности
        self.stability_interval = 5         # интервал проверки стабильности (сек)
        self.pid_adjust_interval = 120      # интервал увеличения PID.I (сек)
        self.setpoint_adjust_interval = 200 # интервал коррекции уставки (сек)
        self.update_interval = 1.0          # интервал обновления данных (сек)

        # Новые параметры коррекции уставки
        self.max_correction = 0.1  # максимальное изменение уставки за одну коррекцию (°C)
        self.correction_cooldown = 30  # минимальный интервал между коррекциями уставки (сек)

        # Параметры измерения вала
        self.shaft_stabilization_interval = 2.0
        self.shaft_max_attempts = 15
        self.shaft_final_delay = 20.0
        # Параметр для GUI (интервал обновления температуры)
        self.shaft_temp_update_interval = 60.0

        self._heating_rate = 20.0

        # Параметры управления вентилятором по градиенту
        self.target_gradient = 2.0  # целевое значение градиента (°C)
        self.fan_adjust_interval = 30.0  # интервал коррекции скорости (сек)
        self.current_fan_speed = 1000  # текущая скорость вентилятора
        self.min_fan_speed = 500
        self.max_fan_speed = 3500
        self.last_fan_adjust_time = 0

        # Параметры нагрева вала
        self.temp_threshold_for_shaft_heating = 50.0
        self.shaft_min_temp_for_heating = 20.0
        self.shaft_heating_duration = 5.0
        self.shaft_heating_repetitions = 3
        self.shaft_heating_interval = 60.0

        # Состояние нагрева вала (серия)
        self.shaft_heating_active = False  # идёт ли серия нагревов
        self.shaft_heating_phase = None  # "heating" или "pause"
        self.shaft_heating_cycles_left = 0  # сколько циклов осталось
        self.shaft_phase_end_time = 0  # время окончания текущей фазы

        # Время последней полной проверки температуры вала (интервал shaft_temp_update_interval)
        self.last_shaft_check_time = 0

        # Кэш температуры вала (последнее измеренное значение)
        self.last_shaft_temp = None
        self.last_shaft_temp_time = 0

        self.program: Optional[TemperatureProgram] = None
        self.current_step_index: int = -1

        self.fan_control_enabled = True
        self.shaft_check_enabled = True

    def start_program(self, program: TemperatureProgram):
        """Запуск многоступенчатой программы."""
        if self.is_running():
            raise RuntimeError("Процесс уже запущен")
        self.program = program
        self.current_step_index = 0
        self._stop_event.clear()

        # Применяем предустановки PID и скорости нагрева (как в start_process)
        self.apply_preset()

        # Установка начальной скорости вентилятора (1000 об/мин)
        self.current_fan_speed = 1000
        self.camera.set_fan_speed(1000)

        # Устанавливаем уставку для первой ступени и включаем камеру
        first_step = program.steps[0]
        self.camera.set_temperature(first_step['temperature'], channel=0)
        self.camera.turn_on_camera()

        self._log(f"Запуск программы из {len(program.steps)} ступеней")

        self._thread = threading.Thread(target=self._program_loop, daemon=True)
        self._thread.start()

    def _program_loop(self):
        """Цикл выполнения многоступенчатой программы."""
        try:
            for idx, step in enumerate(self.program.steps):
                if self._stop_event.is_set():
                    break
                self.current_step_index = idx
                target = step['temperature']
                rate = step['rate']
                hold = step['hold_time'] * 60  # в секунды

                self._log(
                    f"Ступень {idx + 1}/{len(self.program.steps)}: цель {target}°C, скорость {rate}°C/мин, выдержка {hold / 60} мин")

                # Установить скорость нагрева, если отличается
                current_rate = self.get_heating_rate()
                if abs(current_rate - rate) > 0.01:
                    self.set_heating_rate(rate)

                # Установить уставку
                self.camera.set_temperature(target, channel=0)
                self._update_data(current_setpoint=target, target_temp=target, process_status=ProcessStatus.HEATING)

                # Ожидание достижения
                if not self._wait_for_target(target):
                    self._update_data(process_status=ProcessStatus.ERROR)
                    self._log("Ошибка: не удалось достичь целевой температуры")
                    break

                # Стабилизация
                self._update_data(process_status=ProcessStatus.STABILIZING)
                if not self._stabilize_temperature(target):
                    self._update_data(process_status=ProcessStatus.ERROR)
                    self._log("Ошибка стабилизации")
                    break

                # Выдержка
                self._update_data(process_status=ProcessStatus.HOLDING)
                self._hold_temperature(target, hold)

                if self._stop_event.is_set():
                    break

            else:
                # Цикл завершился без break – все ступени выполнены
                self._update_data(process_status=ProcessStatus.COMPLETED)
                self._log("Программа успешно завершена")
        except Exception as e:
            self._log(f"Ошибка в цикле программы: {e}")
            self._update_data(process_status=ProcessStatus.ERROR)
        finally:
            self.camera.turn_off_camera()

    def set_heating_rate(self, rate: float):
        """Установить скорость нагрева (USP) в терморегуляторе и сохранить."""
        if self.camera:
            self.camera.set_temperature_rate(rate, channel=0)
        self._heating_rate = rate  # сохраняем

    def get_heating_rate(self) -> float:
        """Получить текущую скорость нагрева из устройства или сохранённое значение."""
        if self.camera and self.camera.trm12:
            rate = self.camera.get_temperature_rate(channel=0)
            if rate is not None:
                self._heating_rate = rate
                return rate
        return self._heating_rate

    def _get_shaft_temp_cached(self):
        """Возвращает последнее измерение температуры вала, обновляя при необходимости, если нагрев не активен."""
        now = time.time()
        # Если нагрев активен, не измеряем, возвращаем старое значение
        if self.shaft_heating_active:
            return self.last_shaft_temp

        if self.last_shaft_temp is None or now - self.last_shaft_temp_time > self.shaft_temp_update_interval:
            shaft_temp, msg = self.camera.get_shaft_temperature()
            if shaft_temp is not None:
                self.last_shaft_temp = shaft_temp
                self.last_shaft_temp_time = now
            else:
                self._log(f"Ошибка измерения вала: {msg}")
        return self.last_shaft_temp

    def _check_and_heat_shaft(self, current_temp):
        """
        Периодическая проверка температуры вала и запуск серии нагревов.
        Вызывается из основного цикла, но реальное измерение происходит
        не чаще чем shaft_temp_update_interval.
        """
        if self.shaft_heating_active:
            # Если серия уже идёт, не инициируем новую проверку
            return
        if not self.shaft_check_enabled:
            return

        now = time.time()
        # Проверяем, наступило ли время для нового измерения


        if now - self.last_shaft_check_time < self.shaft_temp_update_interval:
            return

        # Проверяем температуру камеры
        if current_temp >= self.temp_threshold_for_shaft_heating:

            # Температура камеры выше порога – не проверяем вал
            self.last_shaft_check_time = now
            return
        self._log(
            f"DEBUG: shaft_temp_update_interval={self.shaft_temp_update_interval}, last_check={self.last_shaft_check_time}, now={now}")
        # Получаем свежее измерение температуры вала
        shaft_temp, msg = self.camera.get_shaft_temperature()
        if shaft_temp is None:
            self._log(f"Не удалось получить температуру вала: {msg}")
            self.last_shaft_check_time = now
            return

        # Обновляем кэш
        self.last_shaft_temp = shaft_temp
        self.last_shaft_temp_time = now
        self.last_shaft_check_time = now

        # Проверяем температуру вала
        if shaft_temp >= self.shaft_min_temp_for_heating:
            # Температура вала достаточна – ничего не делаем
            return

        # Запускаем серию нагревов
        self._log(f"Температура вала {shaft_temp:.1f}°C ниже порога {self.shaft_min_temp_for_heating}°C. "
                  f"Запуск серии нагревов ({self.shaft_heating_repetitions} циклов по {self.shaft_heating_duration} сек, "
                  f"пауза {self.shaft_heating_interval} сек)")
        self.shaft_heating_active = True
        self.shaft_heating_cycles_left = self.shaft_heating_repetitions
        self.shaft_heating_phase = "heating"
        self.shaft_phase_end_time = now + self.shaft_heating_duration
        self.camera.turn_on_motor_heating()

    def _manage_shaft_heating_series(self):
        """
        Управляет фазами текущей серии нагревов (включение/пауза).
        Вызывается на каждой итерации основного цикла.
        """
        if not self.shaft_heating_active:
            return
        if not self.shaft_check_enabled:
            return

        now = time.time()

        if self.shaft_heating_phase == "heating":
            if now >= self.shaft_phase_end_time:
                # Завершаем текущий нагрев
                self.camera.turn_off_motor_heating()
                self.shaft_heating_cycles_left -= 1
                if self.shaft_heating_cycles_left > 0:
                    # Переходим в паузу
                    self.shaft_heating_phase = "pause"
                    self.shaft_phase_end_time = now + self.shaft_heating_interval
                    self._log(f"Нагрев вала завершён, пауза {self.shaft_heating_interval} сек "
                              f"(осталось {self.shaft_heating_cycles_left} циклов)")
                else:
                    # Серия завершена
                    self.shaft_heating_active = False
                    self.shaft_heating_phase = None
                    self.shaft_heating_cycles_left = 0
                    self._log("Серия нагревов вала полностью завершена")

        elif self.shaft_heating_phase == "pause":
            if now >= self.shaft_phase_end_time:
                # Завершаем паузу, начинаем следующий нагрев
                self.shaft_heating_phase = "heating"
                self.shaft_phase_end_time = now + self.shaft_heating_duration
                self.camera.turn_on_motor_heating()
                self._log(f"Пауза завершена, следующий нагрев на {self.shaft_heating_duration} сек")



    def _reset_shaft_heating(self):
        """Полностью сбрасывает состояние нагрева вала (выключает, если активно)."""
        if self.shaft_heating_active:
            self.camera.turn_off_motor_heating()
        self.shaft_heating_active = False
        self.shaft_heating_phase = None
        self.shaft_heating_cycles_left = 0
        self.shaft_phase_end_time = 0
        # НЕ сбрасываем last_shaft_check_time – интервал проверок сохраняется

    def update_algorithm_params(self, params: dict):
        """
        Обновить параметры алгоритма из словаря.
        Поддерживаемые ключи: epsilon_reach, epsilon_stable, stability_interval,
        pid_adjust_interval, setpoint_adjust_interval, update_interval,
        heating_rate, max_correction, correction_cooldown,
        shaft_stabilization_interval, shaft_max_attempts,
        shaft_final_delay, shaft_temp_update_interval.
        """
        # Обновляем основные параметры
        if "epsilon_reach" in params:
            self.epsilon_reach = params["epsilon_reach"]
        if "epsilon_stable" in params:
            self.epsilon_stable = params["epsilon_stable"]
        if "stability_interval" in params:
            self.stability_interval = int(params["stability_interval"])
        if "pid_adjust_interval" in params:
            self.pid_adjust_interval = int(params["pid_adjust_interval"])
        if "setpoint_adjust_interval" in params:
            self.setpoint_adjust_interval = int(params["setpoint_adjust_interval"])
        if "update_interval" in params:
            self.update_interval = params["update_interval"]
        if "max_correction" in params:
            self.max_correction = params["max_correction"]
        if "correction_cooldown" in params:
            self.correction_cooldown = int(params["correction_cooldown"])
        if "heating_rate" in params:
            self.set_heating_rate(params["heating_rate"])
        if "target_gradient" in params:
            self.target_gradient = params["target_gradient"]
        if "fan_adjust_interval" in params:
            self.fan_adjust_interval = params["fan_adjust_interval"]
        if "temp_threshold_for_shaft_heating" in params:
            self.temp_threshold_for_shaft_heating = params["temp_threshold_for_shaft_heating"]
        if "shaft_min_temp_for_heating" in params:
            self.shaft_min_temp_for_heating = params["shaft_min_temp_for_heating"]
        if "shaft_heating_duration" in params:
            self.shaft_heating_duration = params["shaft_heating_duration"]
        if "shaft_heating_repetitions" in params:
            self.shaft_heating_repetitions = int(params["shaft_heating_repetitions"])
        if "shaft_heating_interval" in params:
            self.shaft_heating_interval = params["shaft_heating_interval"]

        # Обновляем параметры измерения вала
        shaft_params = {}
        if "shaft_stabilization_interval" in params:
            shaft_params["stabilization_interval"] = params["shaft_stabilization_interval"]
        if "shaft_max_attempts" in params:
            shaft_params["attempts"] = int(params["shaft_max_attempts"])
        if "shaft_final_delay" in params:
            shaft_params["final_delay"] = params["shaft_final_delay"]
        if "shaft_temp_update_interval" in params:
            shaft_params["temp_update_interval"] = params["shaft_temp_update_interval"]
        if shaft_params:
            self.update_shaft_params(**shaft_params)
        if "fan_control_enabled" in params:
            self.fan_control_enabled = params["fan_control_enabled"]
        if "shaft_check_enabled" in params:
            self.shaft_check_enabled = params["shaft_check_enabled"]
            # При отключении проверки вала сбрасываем активный нагрев
            if not self.shaft_check_enabled:
                self._reset_shaft_heating()

    def _adjust_fan_speed(self):
        """Корректирует скорость вентилятора на основе модуля текущего градиента."""
        if not self.camera:
            return
        if not self.fan_control_enabled:
            return

        grad, msg = self.camera.get_gradient()
        if grad is None:
            self._log(f"Не удалось получить градиент: {msg}")
            return

        abs_grad = abs(grad)  # используем модуль
        new_speed = self.current_fan_speed

        if abs_grad > self.target_gradient:
            new_speed = min(self.current_fan_speed + 100, self.max_fan_speed)
            self._log(f"Градиент {abs_grad:.2f} > {self.target_gradient}, увеличение скорости до {new_speed}")
        elif abs_grad < self.target_gradient:
            new_speed = max(self.current_fan_speed - 100, self.min_fan_speed)
            self._log(f"Градиент {abs_grad:.2f} < {self.target_gradient}, уменьшение скорости до {new_speed}")

        if new_speed != self.current_fan_speed:
            success, msg = self.camera.set_fan_speed(new_speed)
            if success:
                self.current_fan_speed = new_speed
                self._log(f"Скорость вентилятора изменена на {new_speed}")
            else:
                self._log(f"Ошибка установки скорости: {msg}")


    def update_shaft_params(self, stabilization_interval: float = None, attempts: int = None,
                            final_delay: float = None, temp_update_interval: float = None):
        """Обновить параметры измерения вала в CameraController и сохранить локально."""
        if stabilization_interval is not None:
            self.shaft_stabilization_interval = stabilization_interval
        if attempts is not None:
            self.shaft_max_attempts = attempts
        if final_delay is not None:
            self.shaft_final_delay = final_delay
        if temp_update_interval is not None:
            self.shaft_temp_update_interval = temp_update_interval

        if self.camera:
            self.camera.set_shaft_params(
                stabilization_interval=stabilization_interval,
                attempts=attempts,
                final_delay=final_delay
            )

    @staticmethod
    def _log(message: str):
        """Вывод сообщения в консоль с временной меткой"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{timestamp}] {message}")

    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def start_process(self, target_temp: float, hold_minutes: float):
        """Запуск процесса нагрева и выдержки"""
        if self.is_running():
            raise RuntimeError("Процесс уже запущен")

        # Применяем предустановки PID и скорости нагрева
        self.apply_preset()  # добавлено

        self._target_temp = target_temp
        self._current_setpoint = target_temp
        self._hold_minutes = hold_minutes
        self._stop_event.clear()

        self._log(f"Запуск процесса: цель {target_temp}°C, выдержка {hold_minutes} мин")
        self.camera.set_temperature(target_temp, channel=0)
        self.camera.turn_on_camera()

        # Установка начальной скорости вентилятора 1000
        self.current_fan_speed = 1000
        self.camera.set_fan_speed(1000)
        self._log("Скорость вентилятора установлена на 1000 об/мин")

        self._thread = threading.Thread(target=self._process_loop, daemon=True)
        self._thread.start()

    def stop_process(self):
        self._log("Остановка процесса по запросу")
        self._stop_event.set()
        self._reset_shaft_heating()  # выключит нагрев, если активен
        if self._thread:
            self._thread.join(timeout=5)
        self._thread = None
        self.camera.turn_off_camera()
        with self._lock:
            self.data.process_status = ProcessStatus.STOPPED
        self._log("Процесс остановлен")

    def get_data(self) -> ChamberData:
        """Получить копию текущих данных (потокобезопасно)"""
        with self._lock:
            import copy
            return copy.deepcopy(self.data)

    def _update_data(self, **kwargs):
        """Обновить поля данных (потокобезопасно)"""
        with self._lock:
            for key, value in kwargs.items():
                if hasattr(self.data, key):
                    setattr(self.data, key, value)


    def _read_sensors(self):
        """Чтение текущих показаний с устройств"""
        temp, _ = self.camera.get_chamber_temperature()
        grad, _ = self.camera.get_gradient()
        speed = self.camera.get_fan_speed()
        current = self.camera.get_motor_current()
        pid = self.camera.get_pid_parameters(channel=0)
        return {
            'current_temp': temp if temp is not None else 0.0,
            'gradient': grad if grad is not None else 0.0,
            'fan_speed': speed if speed is not None else 0,
            'motor_current': current if current is not None else 0.0,
            'p_value': pid.get('P', 0.0),
            'i_value': pid.get('I', 0),
            'd_value': pid.get('D', 0),
        }

    def _process_loop(self):
        """Основной цикл процесса (выполняется в фоновом потоке)"""
        target = self._target_temp
        hold_seconds = self._hold_minutes * 60
        start_time = time.time()
        self.data.current_setpoint = target

        # Этап 1: Выход на температуру
        self._update_data(process_status=ProcessStatus.HEATING, target_temp=target)
        self._log(f"Этап НАГРЕВ: целевая температура {target}°C")
        if not self._wait_for_target(target):
            self._update_data(process_status=ProcessStatus.ERROR)
            self._log("Ошибка: не удалось достичь целевой температуры")
            self.camera.turn_off_camera()
            return
        self._log("Целевая температура достигнута")

        # Этап 2: Стабилизация
        self._update_data(process_status=ProcessStatus.STABILIZING)
        self._log("Этап СТАБИЛИЗАЦИЯ")
        if not self._stabilize_temperature(target):
            self._update_data(process_status=ProcessStatus.ERROR)
            self._log("Ошибка: не удалось стабилизировать температуру")
            self.camera.turn_off_camera()
            return
        self._log("Температура стабилизирована")

        # Этап 3: Выдержка
        self._update_data(process_status=ProcessStatus.HOLDING)
        self._log(f"Этап ВЫДЕРЖКА: {self._hold_minutes} мин")
        self._hold_temperature(target, hold_seconds)

        # Завершение
        self._update_data(process_status=ProcessStatus.COMPLETED)
        self._log("Процесс завершён успешно")
        self.camera.turn_off_camera()

    def _wait_for_target(self, target: float) -> bool:
        timeout = 3600
        start = time.time()
        while not self._stop_event.is_set() and (time.time() - start) < timeout:
            sensors = self._read_sensors()
            # Проверка и запуск нагрева вала (с учётом интервала)
            self._check_and_heat_shaft(sensors['current_temp'])
            # Управление активной серией нагрева
            self._manage_shaft_heating_series()

            self._update_data(**sensors)
            current = sensors['current_temp']
            diff = abs(current - target)
            self._log(f"НАГРЕВ: T={current:.2f}°C, цель={target:.2f}°C, разница={diff:.2f}°C")
            if diff <= self.epsilon_reach:
                return True
            time.sleep(self.update_interval)
        return False


    def _stabilize_temperature(self, target: float) -> bool:
        """
        Стабилизация температуры с учётом отклонения от целевой.
        Использует настраиваемые параметры max_correction и correction_cooldown.
        """
        timeout = 1800  # 30 минут максимум
        start = time.time()
        stable_count = 0
        prev_temp = None
        last_correction_time = 0  # время последней коррекции уставки
        last_i_adjust_time = 0  # время последней коррекции I

        while not self._stop_event.is_set() and (time.time() - start) < timeout:
            sensors = self._read_sensors()
            current = sensors['current_temp']
            self._update_data(**sensors)
            # Управление нагревом вала
            self._check_and_heat_shaft(current)
            self._manage_shaft_heating_series()

            # Регулировка скорости вентилятора по градиенту
            now = time.time()
            if now - self.last_fan_adjust_time >= self.fan_adjust_interval:
                self._adjust_fan_speed()
                self.last_fan_adjust_time = now

            diff_from_target = abs(current - target)

            if prev_temp is not None:
                delta = abs(current - prev_temp)
                if delta <= self.epsilon_stable:
                    stable_count += 1
                else:
                    stable_count = 0

                self._log(f"СТАБИЛИЗАЦИЯ: T={current:.2f}°C, цель={target:.2f}°C, "
                          f"разница={diff_from_target:.2f}°C, стабильность={stable_count}/5")

                if stable_count >= 5 and diff_from_target < 0.1:
                    return True

                # Коррекция уставки, если температура стабильна, но отклонение > 0.2
                now = time.time()
                if (delta <= self.epsilon_stable and diff_from_target > 0.2
                        and (now - last_correction_time) >= self.correction_cooldown):
                    correction = target - current
                    # Ограничиваем изменение уставки
                    correction = max(min(correction, self.max_correction), -self.max_correction)
                    new_setpoint = self._current_setpoint + correction
                    new_setpoint = round(new_setpoint, 1)

                    self.camera.set_temperature(new_setpoint, channel=0)
                    self._current_setpoint = new_setpoint
                    self._update_data(current_setpoint=new_setpoint)
                    last_correction_time = now
                    self._log(f"Коррекция уставки: {self._current_setpoint:.2f}°C (изменение {correction:+.2f}°C)")

                # Коррекция интегральной составляющей PID
                if (now - last_i_adjust_time) >= self.pid_adjust_interval:
                    current_i = self.data.i_value
                    if current_i is not None and current_i < 10:
                        new_i = min(current_i + 3, 10)
                        self.camera.set_pid_parameters(I=new_i, channel=0)
                        self._update_data(i_value=new_i)
                        last_i_adjust_time = now
                        self._log(f"Увеличение PID.I: {current_i} -> {new_i}")

            prev_temp = current
            time.sleep(self.stability_interval)

        return False



    def _hold_temperature(self, target: float, duration: float):
        """Выдержка температуры в течение заданного времени"""
        start_hold = time.time()
        last_correction = time.time()

        while not self._stop_event.is_set() and (time.time() - start_hold) < duration:
            elapsed = time.time() - start_hold
            remaining = duration - elapsed
            sensors = self._read_sensors()
            current = sensors['current_temp']
            self._update_data(**sensors, hold_remaining=remaining)
            # Управление нагревом вала
            self._check_and_heat_shaft(current)
            self._manage_shaft_heating_series()

            diff = abs(current - target)
            self._log(f"ВЫДЕРЖКА: T={current:.2f}°C, цель={target:.2f}°C, "
                      f"разница={diff:.2f}°C, осталось={remaining/60:.1f} мин")

            # Коррекция уставки при отклонении (каждые 30 сек)
            if time.time() - last_correction >= 30:
                if abs(current - target) > 0.1:
                    new_sp = target - (current - target)
                    self.camera.set_temperature(new_sp, channel=0)
                    self._update_data(current_setpoint=new_sp)  # <-- добавить
                    self._log(f"Коррекция уставки во время выдержки: новая уставка {new_sp:.2f}°C")
                last_correction = time.time()

            time.sleep(self.update_interval)

    def apply_preset(self):
        """Установка рекомендуемых параметров PID и скорости нагрева для начала работы"""
        self.camera.set_pid_parameters(P=0.5, I=3, D=200, deadband=0.0,
                                       output_min=0.0, output_max=100.0, channel=0)
        # Устанавливаем скорость нагрева (USP)
        self.set_heating_rate(self._heating_rate)
        # Другие параметры, если доступны
        if hasattr(self.camera.trm12, 'write_parameter'):
            self.camera.trm12.write_parameter("DB.D", 0.05, channel=0)  # минимальный ход
            self.camera.trm12.write_parameter("U.NOT", 5, channel=0)  # полное время хода
            self.camera.trm12.write_parameter("U.GAP", 5, channel=0)  # выборка люфта
            self.camera.trm12.write_parameter("UR.EU", 0.5, channel=0)  # время реверса


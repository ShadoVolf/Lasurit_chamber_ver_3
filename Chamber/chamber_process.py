import json
import os
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

        self._last_fan_ensure_time = 0
        self.FAN_ENSURE_INTERVAL = 5  # проверять не чаще чем раз в 5 секунд

        self._shaft_heating_repetitions_current = self.shaft_heating_repetitions
        self._shaft_heating_interval_current = self.shaft_heating_interval

        self._program_file: Optional[str] = None  # путь к файлу программы (если запущена из файла)
        self.auto_apply_pid: bool = True  # брать из конфига
        self._temp_pid_file = "temp_pid.json"  # файл для ручного режима

    def _ensure_fan_running(self):
        """Проверяет, работает ли вентилятор, и перезапускает при остановке."""
        if not self.is_running() or not self.fan_control_enabled:
            return

        now = time.time()
        if now - self._last_fan_ensure_time < self.FAN_ENSURE_INTERVAL:
            return
        self._last_fan_ensure_time = now

        # Проверяем состояние двигателя
        if self.camera.blsd20 and self.camera.blsd20.connected:
            status = self.camera.blsd20.get_status()
            if status == self.camera.blsd20.MotorStatus.STOPPED:
                self._log("ВНИМАНИЕ: вентилятор остановлен. Выполняется повторный запуск...")
                # Убедимся, что скорость установлена
                self.camera.blsd20.set_speed(self.current_fan_speed)
                self.camera.blsd20.start_motor()
                self._log(f"Вентилятор перезапущен со скоростью {self.current_fan_speed} об/мин")


    def start_program_1(self, program: TemperatureProgram):
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
        self._current_setpoint = first_step['temperature']
        self._log(f"Запуск программы из {len(program.steps)} ступеней")

        self._thread = threading.Thread(target=self._program_loop, daemon=True)
        self._thread.start()

    def start_program(self, program: TemperatureProgram, program_file: Optional[str] = None):
        """Запуск программы с возможным путём к файлу."""
        if self.is_running():
            raise RuntimeError("Процесс уже запущен")
        self._program = program
        self._program_file = program_file
        self.current_step_index = 0
        self._stop_event.clear()

        self.apply_preset()
        self.current_fan_speed = 1000
        self.camera.set_fan_speed(1000)
        first_step = program.steps[0]
        self.camera.set_temperature(first_step['temperature'], channel=0)
        self.camera.turn_on_camera()
        self._log(f"Запуск программы из {len(program.steps)} ступеней")
        self._thread = threading.Thread(target=self._program_loop, daemon=True)
        self._thread.start()

    def _apply_pid_for_target(self, target_temp: float):
        """Загрузить PID из temp_pid.json для целевой температуры и применить."""
        if not os.path.exists(self._temp_pid_file):
            return
        try:
            with open(self._temp_pid_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            # ключ – температура как строка (чтобы избежать проблем с float)
            key = str(target_temp)
            if key in data:
                pid = data[key]
                self.camera.set_pid_parameters(
                    P=pid.get('p'),
                    I=pid.get('i'),
                    D=pid.get('d'),
                    channel=0
                )
                self._log(
                    f"Применены сохранённые PID для температуры {target_temp}°C: P={pid['p']}, I={pid['i']}, D={pid['d']}")
        except Exception as e:
            self._log(f"Ошибка загрузки PID из файла: {e}")

    def _apply_pid_from_step(self, step: dict):
        """Применить PID из ступени программы, если они есть и включена авто-применение."""
        if not self.auto_apply_pid:
            return
        p = step.get('pid_p')
        i = step.get('pid_i')
        d = step.get('pid_d')
        if p is not None and i is not None and d is not None:
            self.camera.set_pid_parameters(P=p, I=i, D=d, channel=0)
            self._log(f"Применены PID из ступени: P={p}, I={i}, D={d}")

    def _save_current_pid(self):
        """Сохранить текущие PID в зависимости от контекста."""
        pid = self.camera.get_pid_parameters(channel=0)
        if not pid:
            return
        p = pid.get('P')
        i = pid.get('I')
        d = pid.get('D')
        if p is None or i is None or d is None:
            return

        if self._program is None:
            # Ручной режим – сохраняем в temp_pid.json
            self._save_pid_to_temp_file(self._target_temp, p, i, d)
        elif self._program_file is not None:
            # Программа из файла – обновляем ступень в памяти
            if 0 <= self.current_step_index < len(self._program.steps):
                self._program.update_step_pid(self.current_step_index, p, i, d)
                self._log(f"PID ступени {self.current_step_index + 1} обновлены в памяти")
        # Если программа временная (без файла) – ничего не сохраняем

    def _save_pid_to_temp_file(self, target: float, p: float, i: int, d: int):
        """Сохранить PID для ручного режима в temp_pid.json (замена по ключу)."""
        try:
            data = {}
            if os.path.exists(self._temp_pid_file):
                with open(self._temp_pid_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
            key = str(round(target, 1))  # ключ – температура с одним знаком
            data[key] = {
                'p': p,
                'i': i,
                'd': d,
                'timestamp': time.time()
            }
            with open(self._temp_pid_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            self._log(f"PID для температуры {target}°C сохранены в {self._temp_pid_file}")
        except Exception as e:
            self._log(f"Ошибка сохранения PID в файл: {e}")



    def _program_loop_1(self):
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
                self._current_setpoint = target
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

    def _program_loop(self):
        """Цикл выполнения программы с применением PID на каждой ступени."""
        try:
            for idx, step in enumerate(self._program.steps):
                if self._stop_event.is_set():
                    break
                self.current_step_index = idx
                target = step['temperature']
                rate = step['rate']
                hold = step['hold_time'] * 60

                # Применить PID из ступени, если есть
                self._apply_pid_from_step(step)

                self._log(f"Ступень {idx + 1}: цель {target}°C, скорость {rate}°C/мин, выдержка {hold / 60} мин")
                # Установка скорости нагрева
                current_rate = self.get_heating_rate()
                if abs(current_rate - rate) > 0.01:
                    self.set_heating_rate(rate)

                self.camera.set_temperature(target, channel=0)
                self._current_setpoint = target
                self._update_data(current_setpoint=target, target_temp=target, process_status=ProcessStatus.HEATING)

                if not self._wait_for_target(target):
                    self._update_data(process_status=ProcessStatus.ERROR)
                    break

                self._update_data(process_status=ProcessStatus.STABILIZING)
                if not self._stabilize_temperature(target):
                    self._update_data(process_status=ProcessStatus.ERROR)
                    break

                # После стабилизации сохраняем PID (если нужно)
                self._save_current_pid()

                self._update_data(process_status=ProcessStatus.HOLDING)
                self._hold_temperature(target, hold)

                if self._stop_event.is_set():
                    break
            else:
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
        if shaft_temp < self.shaft_min_temp_for_heating:
            # Коррекция параметров в зависимости от температуры камеры (база -60°C)
            # На каждые 10°C выше -60 уменьшаем repetitions на 1 и увеличиваем interval на 1 с
            base_temp = -60.0
            delta = current_temp - base_temp
            steps = int(delta // 10) if delta > 0 else 0
            self._shaft_heating_repetitions_current = max(1, self.shaft_heating_repetitions - steps)
            self._shaft_heating_interval_current = self.shaft_heating_interval + steps
            self._log(
                f"Коррекция нагрева вала: repetitions={self._shaft_heating_repetitions_current}, interval={self._shaft_heating_interval_current}с")
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
                    self.shaft_phase_end_time = now + self._shaft_heating_interval_current
                    self._log(f"Нагрев вала завершён, пауза {self._shaft_heating_interval_current} сек "
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

    def _manage_shaft_heating_series_1(self):
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
        if "shaft_heating_repetitions" in params:
            self.shaft_heating_repetitions = int(params["shaft_heating_repetitions"])
            self._shaft_heating_repetitions_current = self.shaft_heating_repetitions
        if "shaft_heating_interval" in params:
            self.shaft_heating_interval = params["shaft_heating_interval"]
            self._shaft_heating_interval_current = self.shaft_heating_interval
        if "auto_apply_pid" in params:
            self.auto_apply_pid = params["auto_apply_pid"]


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
        """Запуск ручного режима (одна цель)."""
        if self.is_running():
            raise RuntimeError("Процесс уже запущен")
        self._program = None
        self._program_file = None
        self._target_temp = target_temp
        self._hold_minutes = hold_minutes
        self._stop_event.clear()

        # Применить PID из файла, если включена авто-применение
        if self.auto_apply_pid:
            self._apply_pid_for_target(target_temp)

        self._log(f"Запуск ручного режима: цель {target_temp}°C, выдержка {hold_minutes} мин")
        self.camera.set_temperature(target_temp, channel=0)
        self.camera.turn_on_camera()
        self.current_fan_speed = 1000
        self.camera.set_fan_speed(1000)
        self._thread = threading.Thread(target=self._process_loop, daemon=True)
        self._thread.start()

    def start_process_1(self, target_temp: float, hold_minutes: float):
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
            self._ensure_fan_running()
            current = sensors['current_temp']
            diff = abs(current - target)
            self._log(f"НАГРЕВ: T={current:.2f}°C, цель={target:.2f}°C, разница={diff:.2f}°C")
            if diff <= self.epsilon_reach:
                return True
            time.sleep(self.update_interval)
        return False


    def _stabilize_temperature(self, target: float) -> bool:
        """
        Многоэтапная стабилизация температуры:
        1. Установка начальных PID (P=5, I=10) и ожидание стабилизации.
        2. Если температура не в допуске – подбор P (шаг 0.5 до 1.5) с ожиданием стабилизации.
        3. Если не помогло – подбор I (шаг 1 до 7) с ожиданием стабилизации.
        4. Если не помогло – коррекция уставки прибора (шаг max_correction) до попадания в допуск.
        5. После попадания в допуск – дополнительная стабилизация.
        6. Если включена регулировка вентилятора – подбор скорости для достижения целевого градиента
           с ожиданием стабилизации после каждого изменения.
        7. После подбора скорости – повторная проверка температуры и при необходимости коррекция уставки.
        8. Финальная стабилизация и сохранение результатов в JSON.
        """
        # --- Шаг 1: Установка начальных PID и ожидание стабилизации ---
        self._log("Установка начальных PID: P=5, I=10")
        self.camera.set_pid_parameters(P=5.0, I=10, channel=0)
        if not self._wait_for_stabilization(timeout=1800):
            self._log("Ошибка: не удалось достичь стабилизации после установки PID")
            self._update_data(process_status=ProcessStatus.ERROR)
            self._log("Ошибка: не удалось стабилизировать температуру")
            self.camera.turn_off_camera()
            return False

        # Текущая температура после стабилизации
        sensors = self._read_sensors()
        current_temp = sensors['current_temp']
        diff = abs(current_temp - target)

        # Если уже в допуске – сразу переходим к вентилятору
        if diff <= self.epsilon_reach:
            self._log(f"Температура в допуске с начальными PID: {current_temp:.2f}°C")
        else:
            self._log(
                f"Температура {current_temp:.2f}°C, отклонение {diff:.2f}°C > {self.epsilon_reach}. Начинаем подбор P.")

            # --- Шаг 2: Подбор P ---
            p_value = 5.0
            while p_value > 1.5 and diff > self.epsilon_reach and not self._stop_event.is_set():
                p_value = max(1.5, p_value - 0.5)
                self._log(f"Установка P = {p_value:.2f}")
                self.camera.set_pid_parameters(P=p_value, channel=0)
                if not self._wait_for_stabilization(timeout=600):
                    self._log("Ошибка стабилизации после изменения P")
                    return False
                sensors = self._read_sensors()
                current_temp = sensors['current_temp']
                diff = abs(current_temp - target)
                self._log(f"После P={p_value:.2f} температура {current_temp:.2f}°C, отклонение {diff:.2f}°C")

            if diff <= self.epsilon_reach:
                self._log("Температура в допуске после подбора P")
            else:
                self._log("P достигло минимума, но отклонение всё ещё велико. Начинаем подбор I.")

                # --- Шаг 3: Подбор I (исправлено зацикливание) ---
                i_value = 10
                while i_value > 7 and diff > self.epsilon_reach and not self._stop_event.is_set():
                    i_value -= 1
                    self._log(f"Установка I = {i_value}")
                    self.camera.set_pid_parameters(I=i_value, channel=0)
                    if not self._wait_for_stabilization(timeout=600):
                        self._log("Ошибка стабилизации после изменения I")
                        return False
                    sensors = self._read_sensors()
                    current_temp = sensors['current_temp']
                    diff = abs(current_temp - target)
                    self._log(f"После I={i_value} температура {current_temp:.2f}°C, отклонение {diff:.2f}°C")

                if diff <= self.epsilon_reach:
                    self._log("Температура в допуске после подбора I")
                else:
                    self._log("I достигло минимума, начинаем коррекцию уставки.")

                    # --- Шаг 4: Коррекция уставки прибора ---
                    if not self._correct_setpoint_stepwise(target, current_temp):
                        self._log("Не удалось достичь допуска после коррекции уставки")
                        return False
                    '''
                    if self._current_setpoint is None:  # <-- ЗАЩИТА
                        self._current_setpoint = target
                        self._log(f"Предупреждение: _current_setpoint был None, установлен в {target}")
                    max_attempts = 20
                    attempt = 0
                    while diff > self.epsilon_reach and attempt < max_attempts and not self._stop_event.is_set():
                        # Вычисляем корректировку, ограниченную max_correction
                        error = target - current_temp
                        correction = max(-self.max_correction, min(self.max_correction, error))
                        new_setpoint = self._current_setpoint + correction
                        self._log(
                            f"Коррекция уставки: {self._current_setpoint:.2f} -> {new_setpoint:.2f} (error={error:.3f}, correction={correction:.3f})")
                        self.camera.set_temperature(new_setpoint, channel=0)
                        self._current_setpoint = new_setpoint
                        self._update_data(current_setpoint=new_setpoint)
                        self._update_data(current_setpoint=new_setpoint)

                        if not self._wait_for_stabilization(timeout=600):
                            self._log("Ошибка стабилизации после коррекции уставки")
                            return False

                        sensors = self._read_sensors()
                        current_temp = sensors['current_temp']
                        diff = abs(current_temp - target)
                        attempt += 1
                        self._log(f"После коррекции уставки температура {current_temp:.2f}°C, отклонение {diff:.2f}°C")

                    if diff <= self.epsilon_reach:
                        self._log("Температура в допуске после коррекции уставки")
                    else:
                        self._log("Не удалось достичь допуска после всех коррекций")
                        return False
                    '''
        # --- Шаг 5: Дополнительная стабилизация после достижения допуска ---
        self._log("Ожидание финальной стабилизации перед регулировкой вентилятора")
        if not self._wait_for_stabilization(timeout=600):
            self._log("Ошибка финальной стабилизации")
            return False

        # --- Шаг 5.5: Предварительная корректировка скорости вентилятора ---
        if self.fan_control_enabled and self.current_fan_speed < 2500:
            self._log("Предварительная корректировка: увеличиваем скорость на 1000 об/мин")
            old_speed = self.current_fan_speed
            new_speed = old_speed + 1000
            success, msg = self.camera.set_fan_speed(new_speed)
            if success:
                self.current_fan_speed = new_speed
                # Ждём стабилизации
                if self._wait_for_stabilization(timeout=600):
                    grad_before = None
                    grad_after = None
                    # Измеряем градиент до изменения (старое значение уже было)
                    grad_before, _ = self.camera.get_gradient()
                    # Измеряем после
                    grad_after, _ = self.camera.get_gradient()
                    if grad_before is not None and grad_after is not None:
                        delta_grad = abs(grad_after - grad_before)
                        self._log(f"Изменение градиента после увеличения скорости: {delta_grad:.2f}°C")
                        if delta_grad <= 0.2:
                            self._log("Изменение незначительное, возвращаем исходную скорость и пропускаем подбор")
                            # Возвращаем старую скорость
                            self.camera.set_fan_speed(old_speed)
                            self.current_fan_speed = old_speed
                            # Пропускаем основной подбор (идём дальше)
                        else:
                            self._log("Изменение существенное, продолжаем подбор с новой скоростью")
                            # Оставляем увеличенную скорость и переходим к основному подбору
                    else:
                        self._log("Не удалось измерить градиент, продолжаем без предкоррекции")
                else:
                    self._log("Стабилизация после увеличения скорости не удалась, возврат")
                    self.camera.set_fan_speed(old_speed)
                    self.current_fan_speed = old_speed
            else:
                self._log(f"Не удалось увеличить скорость: {msg}")


        # --- Шаг 6: Регулировка скорости вентилятора (если включена) ---
        if self.fan_control_enabled:
            self._log("Начинаем подбор скорости вентилятора для достижения целевого градиента")
            grad, _ = self.camera.get_gradient()
            if grad is None:
                self._log("Не удалось измерить градиент, пропускаем регулировку вентилятора")
            else:
                abs_grad = abs(grad)
                max_fan_attempts = 20
                fan_attempt = 0
                # Будем подбирать, пока градиент не войдёт в диапазон ±0.5 от target_gradient
                while abs(
                        abs_grad - self.target_gradient) > 0.5 and fan_attempt < max_fan_attempts and not self._stop_event.is_set():
                    if abs_grad > self.target_gradient:
                        new_speed = min(self.current_fan_speed + 100, self.max_fan_speed)
                        self._log(
                            f"Градиент {abs_grad:.2f} > {self.target_gradient}, увеличиваем скорость до {new_speed}")
                    else:
                        new_speed = max(self.current_fan_speed - 100, self.min_fan_speed)
                        self._log(
                            f"Градиент {abs_grad:.2f} < {self.target_gradient}, уменьшаем скорость до {new_speed}")

                    success, msg = self.camera.set_fan_speed(new_speed)
                    if not success:
                        self._log(f"Ошибка установки скорости: {msg}")
                        break
                    self.current_fan_speed = new_speed

                    # Ждём стабилизации температуры после изменения скорости
                    if not self._wait_for_stabilization(timeout=600):
                        self._log("Ошибка стабилизации после изменения скорости вентилятора")
                        return False

                    grad, _ = self.camera.get_gradient()
                    if grad is None:
                        self._log("Не удалось измерить градиент, прекращаем подбор")
                        break
                    abs_grad = abs(grad)
                    fan_attempt += 1
                    self._log(f"После изменения скорости градиент = {abs_grad:.2f}°C")

                if abs(abs_grad - self.target_gradient) <= 0.5:
                    self._log(f"Градиент достиг целевого диапазона: {abs_grad:.2f}°C")
                else:
                    self._log("Не удалось точно настроить градиент, продолжаем с текущим")

            # --- Шаг 7: После регулировки вентилятора проверяем температуру и при необходимости корректируем уставку ---
            sensors = self._read_sensors()
            current_temp = sensors['current_temp']
            if not self._correct_setpoint_stepwise(target, current_temp):
                self._log("Не удалось вернуть температуру в допуск после регулировки вентилятора")
                return False
            '''
            diff = abs(current_temp - target)
            if diff > self.epsilon_reach:
                self._log(
                    f"После регулировки вентилятора температура отклонилась: {current_temp:.2f}°C, отклонение {diff:.2f}°C. Повторная коррекция уставки.")
                # Повторяем коррекцию уставки (аналогично шагу 4)
                max_attempts = 10
                attempt = 0
                while diff > self.epsilon_reach and attempt < max_attempts and not self._stop_event.is_set():
                    error = target - current_temp
                    correction = max(-self.max_correction, min(self.max_correction, error))
                    new_setpoint = self._current_setpoint + correction
                    self._log(f"Повторная коррекция уставки: {self._current_setpoint:.2f} -> {new_setpoint:.2f}")
                    self.camera.set_temperature(new_setpoint, channel=0)
                    self._current_setpoint = new_setpoint
                    self._update_data(current_setpoint=new_setpoint)

                    if not self._wait_for_stabilization(timeout=600):
                        self._log("Ошибка стабилизации после повторной коррекции уставки")
                        return False

                    sensors = self._read_sensors()
                    current_temp = sensors['current_temp']
                    diff = abs(current_temp - target)
                    attempt += 1

                if diff <= self.epsilon_reach:
                    self._log("Температура снова в допуске после повторной коррекции")
                else:
                    self._log("Не удалось вернуть температуру в допуск после регулировки вентилятора")
                    return False
                '''

        # --- Шаг 8: Финальная стабилизация и сохранение результатов ---
        self._log("Финальная стабилизация перед выдержкой")
        if not self._wait_for_stabilization(timeout=600):
            self._log("Ошибка финальной стабилизации")
            return False

        # Сохраняем результаты
        self._save_stabilization_results(target)
        self._save_current_pid()
        return True

    def _wait_for_stabilization(self, timeout: float = 1800) -> bool:
        """
        Ожидает, пока температура не станет стабильной в течение заданного числа интервалов.
        Критерий: изменение температуры за stability_interval не превышает epsilon_stable,
        и таких отсчётов подряд не менее 5.
        Возвращает True, если стабилизация достигнута, иначе False.
        """
        start = time.time()
        stable_count = 0
        prev_temp = None
        required_stable = 5  # количество последовательных стабильных измерений

        while not self._stop_event.is_set() and (time.time() - start) < timeout:
            sensors = self._read_sensors()
            current_temp = sensors['current_temp']
            self._update_data(**sensors)
            self._ensure_fan_running()
            self._check_and_heat_shaft(current_temp)
            self._manage_shaft_heating_series()

            if prev_temp is not None:
                delta = abs(current_temp - prev_temp)
                if delta <= self.epsilon_stable:
                    stable_count += 1
                    self._log(f"СТАБИЛИЗАЦИЯ: T={current_temp:.2f}°C, стабильность {stable_count}/{required_stable}")
                    if stable_count >= required_stable:
                        return True
                else:
                    stable_count = 0
                    self._log(
                        f"СТАБИЛИЗАЦИЯ: T={current_temp:.2f}°C, изменение {delta:.2f} > {self.epsilon_stable}, сброс счётчика")
            else:
                self._log(f"СТАБИЛИЗАЦИЯ: первое измерение T={current_temp:.2f}°C")

            prev_temp = current_temp
            time.sleep(self.stability_interval)

        self._log("Таймаут или остановка при ожидании стабилизации")
        return False

    def _save_stabilization_results(self, target_temp: float):
        """
        Сохраняет итоговые параметры стабилизации в JSON-файл.
        Файл: stabilization_results.json (в рабочей директории)
        Добавляет запись в массив.
        """
        sensors = self._read_sensors()
        result = {
            "timestamp": datetime.now().isoformat(),
            "step_index": self.current_step_index if self.program and self.current_step_index is not None else -1,
            "target_temperature": target_temp,
            "final_temperature": sensors['current_temp'],
            "final_p": sensors['p_value'],
            "final_i": sensors['i_value'],
            "final_setpoint": self._current_setpoint,
            "final_fan_speed": self.current_fan_speed,
            "gradient": sensors['gradient']
        }
        filename = "stabilization_results.json"
        try:
            if os.path.exists(filename):
                with open(filename, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    if not isinstance(data, list):
                        data = [data]  # на случай, если был одиночный объект
            else:
                data = []
            data.append(result)
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=4, ensure_ascii=False)
            self._log(
                f"Результаты стабилизации ступени {self.current_step_index + 1 if self.current_step_index is not None else ''} сохранены в {filename}")
        except Exception as e:
            self._log(f"Ошибка сохранения результатов стабилизации: {e}")

    def _correct_setpoint_stepwise(self, target: float, current_temp: float) -> bool:
        """
        Выполняет пошаговую коррекцию уставки в зависимости от отклонения.
        Возвращает True, если после коррекции температура вошла в допуск.
        """
        error = target - current_temp
        abs_error = abs(error)
        max_step = self.max_correction

        # Определяем начальный шаг в зависимости от величины ошибки
        if abs_error >= 0.5:
            first_step = 0.5
        elif abs_error >= 0.3:
            first_step = 0.3
        else:
            first_step = 0.0  # коррекция не требуется

        # Применяем первый шаг, если он больше нуля
        if first_step > 0:
            correction = first_step if error > 0 else -first_step
            new_setpoint = self._current_setpoint + correction
            self._log(f"Коррекция уставки (первый шаг): {self._current_setpoint:.2f} -> {new_setpoint:.2f}")
            self.camera.set_temperature(new_setpoint, channel=0)
            self._current_setpoint = new_setpoint
            self._update_data(current_setpoint=new_setpoint)

            if not self._wait_for_stabilization(timeout=600):
                self._log("Ошибка стабилизации после первого шага коррекции")
                return False

            # Обновляем текущую температуру после стабилизации
            sensors = self._read_sensors()
            current_temp = sensors['current_temp']
            error = target - current_temp
            abs_error = abs(error)

        # Добираем остаток максимальными шагами
        max_attempts = 20
        attempt = 0
        while abs_error > self.epsilon_reach and attempt < max_attempts and not self._stop_event.is_set():
            # Ограничиваем шаг max_correction
            step = max_step if error > 0 else -max_step
            # Но не превышаем оставшуюся ошибку
            if abs(step) > abs_error:
                step = error  # последний шаг точно в цель
            new_setpoint = self._current_setpoint + step
            self._log(f"Коррекция уставки (шаг {attempt + 1}): {self._current_setpoint:.2f} -> {new_setpoint:.2f}")
            self.camera.set_temperature(new_setpoint, channel=0)
            self._current_setpoint = new_setpoint
            self._update_data(current_setpoint=new_setpoint)

            if not self._wait_for_stabilization(timeout=600):
                self._log("Ошибка стабилизации при доборе")
                return False

            sensors = self._read_sensors()
            current_temp = sensors['current_temp']
            error = target - current_temp
            abs_error = abs(error)
            attempt += 1

        return abs_error <= self.epsilon_reach

    def _hold_temperature(self, target: float, duration: float):
        """
        Выдержка температуры в течение заданного времени.
        Целевая температура – пользовательская уставка target.
        Коррекция уставки прибора производится пошагово с шагом не более max_correction,
        с ожиданием стабилизации после каждого шага.
        """
        start_hold = time.time()
        last_correction_time = 0
        user_target = target



        while not self._stop_event.is_set() and (time.time() - start_hold) < duration:
            elapsed = time.time() - start_hold
            remaining = duration - elapsed
            sensors = self._read_sensors()
            current = sensors['current_temp']
            self._update_data(**sensors, hold_remaining=remaining)
            self._ensure_fan_running()
            self._check_and_heat_shaft(current)
            self._manage_shaft_heating_series()

            diff = abs(current - user_target)
            self._log(f"ВЫДЕРЖКА: T={current:.2f}°C, цель={user_target:.2f}°C, "
                      f"разница={diff:.2f}°C, осталось={remaining / 60:.1f} мин")

            now = time.time()

            # Коррекция выполняется не чаще чем correction_cooldown
            if now - last_correction_time >= self.correction_cooldown and diff > self.epsilon_reach:
                self._correct_setpoint_stepwise(user_target, current)
                last_correction_time = time.time()
            '''
            if now - last_correction_time >= 30 and diff > self.epsilon_reach:
                error = user_target - current
                remaining_error = error

                # Пошаговая коррекция, если ошибка больше допустимого шага
                while abs(remaining_error) > self.max_correction and not self._stop_event.is_set():
                    step = self.max_correction if remaining_error > 0 else -self.max_correction
                    new_setpoint = self._current_setpoint + step
                    self._log(f"Коррекция уставки (шаг): {self._current_setpoint:.2f} -> {new_setpoint:.2f}")
                    self.camera.set_temperature(new_setpoint, channel=0)
                    self._current_setpoint = new_setpoint
                    self._update_data(current_setpoint=new_setpoint)  # <-- ОБНОВЛЕНИЕ

                    if not self._wait_for_stabilization(timeout=600):
                        self._log("Ошибка стабилизации после шага коррекции")
                        break

                    sensors = self._read_sensors()
                    current = sensors['current_temp']
                    remaining_error = user_target - current

                # Финальный шаг (оставшаяся ошибка ≤ max_correction)
                if abs(remaining_error) > 0 and not self._stop_event.is_set():
                    new_setpoint = self._current_setpoint + remaining_error
                    self._log(f"Коррекция уставки (финал): {self._current_setpoint:.2f} -> {new_setpoint:.2f}")
                    self.camera.set_temperature(new_setpoint, channel=0)
                    self._current_setpoint = new_setpoint
                    self._update_data(current_setpoint=new_setpoint)  # <-- ОБНОВЛЕНИЕ

                    self._wait_for_stabilization(timeout=600)
                
                last_correction_time = time.time()
            '''
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


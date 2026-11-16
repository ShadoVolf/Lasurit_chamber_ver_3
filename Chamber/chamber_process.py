import json
import os
import time
import threading
from collections import deque
from typing import Optional
from datetime import datetime

from Chamber.chamber_data import ChamberData, ProcessStatus
from Chamber.chamber_driver import CameraController
from Chamber.temperature_program import TemperatureProgram
from Chamber.chamber_logger import get_logger


class ChamberProcess:
    """
    Управление процессом нагрева/выдержки камеры в отдельном потоке.
    """

    def __init__(self, camera_controller: CameraController):
        self._current_setpoint = None
        self.camera = camera_controller
        self.logger = get_logger()
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

        self._program: Optional[TemperatureProgram] = None
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
        self.temp_program_pid_file = "temp_program_pid.json"

        # Таймауты стабилизации (сек)
        self.stabilization_timeout_default = 1800  # 30 мин — полный подбор
        self.stabilization_timeout_saved = 900  # 15 мин — с сохранёнными PID
        # Параметры упрощённого критерия (в 3 раза мягче основного)
        self.epsilon_stable_simplified_multiplier = 3.0
        self.epsilon_stable_simplified = self.epsilon_stable * self.epsilon_stable_simplified_multiplier
        self.required_stable_simplified = 3

        self.epsilon_reach = 0.2  # финальная стабилизация (было)
        self.epsilon_reach_approach = 2.0  # грубый выход на режим — новый параметр

        self.FAN_MIN_RUNNING_SPEED = 50  # об/мин — ниже считаем «стоит»
        self._last_fan_ensure_time = 0
        # --- Флаг «Пред. выдержка» ---
        self.pre_hold_enabled = False  # отсчёт выдержки с первичной стабилизации
        self._pre_hold_start_time = None  # момент окончания первичной стабилизации
        self._current_hold_seconds = 0.0  # длительность текущей выдержки (для GUI)

        self.min_p_value = 1.5

        # История для предсказания (используется в smart_hold_temperature и detect_load_change)
        self._temp_history = deque(maxlen=10)
        self._time_history = deque(maxlen=10)

        # === Параметры умного подхода к температуре ===
        self.smart_approach_enabled = True  # Включение умного подхода
        self.deceleration_zone = 2.0  # Зона начального торможения (°C)
        self.fine_zone = 0.5  # Зона точной настройки (°C)
        self.braking_factor = 0.7  # Коэффициент торможения (0.5-0.9)
        self.prediction_horizon = 10.0  # Горизонт предсказания (секунды)

        # === Параметры адаптивной стабилизации (Вариант 2) ===
        self.adaptive_stabilization_enabled = True  # Включение адаптивной стабилизации
        self.base_p = 8.0  # Базовый P коэффициент
        self.base_i = 15  # Базовый I коэффициент
        self.base_d = 50  # Базовый D коэффициент
        self.temp_range = 200  # Диапазон температур для масштабирования

        # === Параметры интеллектуального удержания (Вариант 3) ===
        self.smart_hold_enabled = True  # Включение интеллектуального удержания
        self.kp_adaptive = 0.5  # Пропорциональный коэффициент для адаптивной коррекции
        self.ki_adaptive = 0.01  # Интегральный коэффициент
        self.kd_adaptive = 2.0  # Дифференциальный коэффициент

        # === Параметры адаптивного управления нагрузкой (Вариант 4) ===
        self.load_adaptation_enabled = True  # Включение адаптации к нагрузке
        self.velocity_change_threshold = 0.5  # Порог изменения скорости для обнаружения нагрузки
        self.load_adaptation_factor_p = 1.5  # Множитель P при изменении нагрузки
        self.load_adaptation_factor_i = 0.8  # Множитель I при изменении нагрузки
        self.load_adaptation_factor_d = 1.3  # Множитель D при изменении нагрузки

    def _load_pid_for_step(self, step_index: int, target_temp: float) -> Optional[dict]:
        """
        Возвращает словарь с PID, setpoint и fan_speed для ступени step_index.
        Приоритет:
          1. Если программа загружена из файла – данные из ступени (уже в self._program.steps).
          2. Если программа временная – данные из temp_program_pid.json (по индексу).
          3. Данные из temp_pid.json (ручной режим) по целевой температуре.
        Возвращает None, если ничего не найдено.
        """
        if self._program is None:
            return None

        step = self._program.steps[step_index]

        # 1. Проверяем, есть ли PID в текущей ступени (из загруженного файла или ранее сохранённые)
        if 'pid_p' in step and 'pid_i' in step and 'pid_d' in step:
            return {
                'p': step['pid_p'],
                'i': step['pid_i'],
                'd': step['pid_d'],
                'setpoint': step.get('setpoint'),
                'fan_speed': step.get('fan_speed')
            }

        # 2. Если программа временная – пытаемся загрузить из temp_program_pid.json
        if self._program_file is None:
            saved_steps = self._safe_load_json(self.temp_program_pid_file, default=None)
            if isinstance(saved_steps, list) and step_index < len(saved_steps):
                saved = saved_steps[step_index]
                if isinstance(saved, dict) and 'pid_p' in saved and 'pid_i' in saved and 'pid_d' in saved:
                    return {
                        'p': saved['pid_p'],
                        'i': saved['pid_i'],
                        'd': saved['pid_d'],
                        'setpoint': saved.get('setpoint'),
                        'fan_speed': saved.get('fan_speed')
                    }

        # 3. Пытаемся загрузить из temp_pid.json по температуре
        data = self._safe_load_json(self._temp_pid_file, default=None)
        if isinstance(data, dict):
            key = str(round(target_temp, 1))
            if key in data and isinstance(data[key], dict):
                pid = data[key]
                if 'p' in pid and 'i' in pid and 'd' in pid:
                    return {
                        'p': pid['p'],
                        'i': pid['i'],
                        'd': pid['d'],
                        'setpoint': pid.get('setpoint'),
                        'fan_speed': pid.get('fan_speed')
                    }

        return None


    def _load_pid_for_step_1(self, step_index: int, target_temp: float) -> Optional[dict]:
        """
        Возвращает словарь с PID, setpoint и fan_speed для ступени step_index.
        Приоритет:
          1. Если программа загружена из файла – данные из ступени (уже в self._program.steps).
          2. Если программа временная – данные из temp_program_pid.json (по индексу).
          3. Данные из temp_pid.json (ручной режим) по целевой температуре.
        Возвращает None, если ничего не найдено.
        """
        if self._program is None:
            return None

        step = self._program.steps[step_index]

        # 1. Проверяем, есть ли PID в текущей ступени (из загруженного файла или ранее сохранённые)
        if 'pid_p' in step and 'pid_i' in step and 'pid_d' in step:
            return {
                'p': step['pid_p'],
                'i': step['pid_i'],
                'd': step['pid_d'],
                'setpoint': step.get('setpoint'),
                'fan_speed': step.get('fan_speed')
            }

        # 2. Если программа временная – пытаемся загрузить из temp_program_pid.json
        if self._program_file is None and os.path.exists(self.temp_program_pid_file):
            try:
                with open(self.temp_program_pid_file, 'r', encoding='utf-8') as f:
                    saved_steps = json.load(f)
                if step_index < len(saved_steps):
                    saved = saved_steps[step_index]
                    if 'pid_p' in saved and 'pid_i' in saved and 'pid_d' in saved:
                        return {
                            'p': saved['pid_p'],
                            'i': saved['pid_i'],
                            'd': saved['pid_d'],
                            'setpoint': saved.get('setpoint'),
                            'fan_speed': saved.get('fan_speed')
                        }
            except Exception as e:
                self._log(f"Ошибка загрузки {self.temp_program_pid_file}: {e}")

        # 3. Пытаемся загрузить из temp_pid.json по температуре
        if os.path.exists(self._temp_pid_file):
            try:
                with open(self._temp_pid_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                key = str(round(target_temp, 1))
                if key in data:
                    pid = data[key]
                    return {
                        'p': pid['p'],
                        'i': pid['i'],
                        'd': pid['d'],
                        'setpoint': pid.get('setpoint'),
                        'fan_speed': pid.get('fan_speed')
                    }
            except Exception as e:
                self._log(f"Ошибка загрузки {self._temp_pid_file}: {e}")

        return None

    def _ensure_fan_running(self):
        """
        Проверяет состояние вентилятора и перезапускает при остановке.

        Признаки остановки (любой из):
          * get_speed() < FAN_MIN_RUNNING_SPEED;
          * get_status() == 0 (СТОП);
          * оба чтения вернули None (нет ответа от BLSD-20).

        При ошибке записи/запуска _last_fan_ensure_time сбрасывается в 0,
        чтобы следующая попытка была сразу.
        """
        if not self.is_running():
            return

        now = time.time()
        if now - self._last_fan_ensure_time < self.FAN_ENSURE_INTERVAL:
            return
        self._last_fan_ensure_time = now

        if not (self.camera.blsd20 and getattr(self.camera.blsd20, 'connected', False)):
            self._log("Вентилятор: BLSD-20 не подключён — проверка пропущена",
                      level="WARNING")
            return

        actual_speed = None
        status_val = None
        read_failed = False

        try:
            actual_speed = self.camera.get_fan_speed()
        except Exception as e:
            self._log(f"Ошибка чтения оборотов вентилятора: {e}", level="ERROR")

        try:
            status_raw = self.camera.blsd20.get_status()
            try:
                status_val = int(status_raw) if status_raw is not None else None
            except (TypeError, ValueError):
                status_val = None
        except Exception as e:
            self._log(f"Ошибка чтения статуса вентилятора: {e}", level="ERROR")

        if actual_speed is None and status_val is None:
            read_failed = True

        self._log(
            f"Проверка вентилятора: факт. обороты={actual_speed}, "
            f"статус={status_val}, уставка={self.current_fan_speed}",
            level="DEBUG"
        )

        threshold = getattr(self, 'FAN_MIN_RUNNING_SPEED', 50)
        reasons = []
        if actual_speed is not None and actual_speed < threshold:
            reasons.append(f"обороты {actual_speed} < {threshold}")
        if status_val == 0:
            reasons.append("статус = СТОП")
        if read_failed:
            reasons.append("нет ответа от BLSD-20 (оба чтения None)")

        if not reasons:
            return

        self._log(
            f"ВНИМАНИЕ: вентилятор остановлен/нет связи ({', '.join(reasons)}). "
            f"Перезапуск на {self.current_fan_speed} об/мин...",
            level="WARNING"
        )

        ok_speed, msg = self.camera.set_fan_speed(self.current_fan_speed)
        if not ok_speed:
            self._log(f"Не удалось установить скорость: {msg}", level="ERROR")
            self._last_fan_ensure_time = 0
            return

        try:
            ok_start = self.camera.blsd20.start_motor()
        except Exception as e:
            self._log(f"Исключение при запуске двигателя: {e}", level="ERROR")
            self._last_fan_ensure_time = 0
            return

        if not ok_start:
            self._log("start_motor() вернул False", level="ERROR")
            self._last_fan_ensure_time = 0
            return

        time.sleep(1.5)

        try:
            new_speed = self.camera.get_fan_speed()
        except Exception:
            new_speed = None

        if new_speed is None or new_speed < threshold:
            self._log(
                f"Вентилятор НЕ раскрутился (speed={new_speed}). Будет повторная попытка.",
                level="ERROR"
            )
            self._last_fan_ensure_time = 0
            return

        self._log(f"Вентилятор перезапущен. Фактические обороты: {new_speed}")

    def _ensure_fan_running_old(self):
        """
        Проверяет состояние вентилятора и перезапускает при остановке.

        Признаки остановки (любой из):
          * get_speed() < FAN_MIN_RUNNING_SPEED (фактические обороты);
          * get_status() == 0 (СТОП).

        При ошибке записи/запуска _last_fan_ensure_time сбрасывается в 0,
        чтобы следующая попытка была не через 5 секунд, а сразу.
        """

        #self._log('Проверка скорости вентилятора', 'INFO')
        #self._log(str(self.is_running()),"INFO")
        if not self.is_running():
            return

        now = time.time()
        #self._log(str(now), 'INFO')
        if now - self._last_fan_ensure_time < self.FAN_ENSURE_INTERVAL:
            return
        self._last_fan_ensure_time = now

        if not (self.camera.blsd20 and getattr(self.camera.blsd20, 'connected', False)):
            self._log("Вентилятор: BLSD-20 не подключён — проверка пропущена",
                      level="WARNING")
            return

        # --- Чтение фактических оборотов и статуса ---
        status_raw = ""
        try:
            actual_speed = self.camera.blsd20.get_speed()
        except Exception as e:
            actual_speed = None
            self._log(f"Ошибка чтения оборотов вентилятора: {e}", level="ERROR")

        try:
            status_raw = self.camera.blsd20.get_status()
        except Exception as e:
            status_raw = None
            self._log(f"Ошибка чтения статуса вентилятора: {e}", level="ERROR")

        try:
            status_val = int(status_raw) if status_raw is not None else None
        except (TypeError, ValueError):
            status_val = None

        # --- Диагностика: пишем состояние при каждой проверке ---
        self._log(
            f"Проверка вентилятора: факт. обороты={actual_speed}, "
            f"статус={status_val}, уставка={self.current_fan_speed}",
            level="DEBUG"
        )

        # --- Решение: стоит ли вентилятор ---
        threshold = getattr(self, 'FAN_MIN_RUNNING_SPEED', 50)
        reasons = []
        if actual_speed is not None and actual_speed < threshold:
            reasons.append(f"обороты {actual_speed} < {threshold}")
        if status_val == 0:
            reasons.append("статус = СТОП")

        if not reasons:
            return

        # --- Перезапуск ---
        self._log(
            f"ВНИМАНИЕ: вентилятор остановлен ({', '.join(reasons)}). "
            f"Перезапуск на {self.current_fan_speed} об/мин...",
            level="WARNING"
        )

        ok_speed, msg = self.camera.set_fan_speed(self.current_fan_speed)
        if not ok_speed:
            self._log(f"Не удалось установить скорость: {msg}", level="ERROR")
            self._last_fan_ensure_time = 0  # ← повторим на следующей итерации
            return

        try:
            ok_start = self.camera.blsd20.start_motor()
        except Exception as e:
            self._log(f"Исключение при запуске двигателя: {e}", level="ERROR")
            self._last_fan_ensure_time = 0
            return

        if not ok_start:
            self._log("start_motor() вернул False", level="ERROR")
            self._last_fan_ensure_time = 0
            return

        time.sleep(1.5)

        try:
            new_speed = self.camera.blsd20.get_speed()
        except Exception:
            new_speed = None

        if new_speed is None or new_speed < threshold:
            self._log(
                f"Вентилятор НЕ раскрутился (speed={new_speed}). "
                f"Будет повторная попытка.",
                level="ERROR"
            )
            self._last_fan_ensure_time = 0
            return

        self._log(f"Вентилятор перезапущен. Фактические обороты: {new_speed}")

    def start_program(self, program: TemperatureProgram, program_file: Optional[str] = None):
        """Запуск программы с возможным путём к файлу."""
        if self.is_running():
            raise RuntimeError("Процесс уже запущен")

        self._program = program
        self._program_file = program_file
        self.current_step_index = 0
        self._stop_event.clear()

        # Если программа временная (нет файла) и существует временный файл программы,
        # загружаем из него ступени и заменяем ими текущую программу.
        if program_file is None:
            saved_steps = self._safe_load_json(self.temp_program_pid_file, default=None)
            if isinstance(saved_steps, list) and saved_steps:
                self._program.steps = saved_steps
                self._log(
                    f"Загружена программа из {self.temp_program_pid_file} "
                    f"({len(saved_steps)} ступеней)"
                )

        # --- НОВЫЙ БЛОК: сохраняем программу во временный файл при запуске
        #     (для временных программ) ---
        if program_file is None:
            try:
                tmp = self.temp_program_pid_file + ".tmp"
                with open(tmp, 'w', encoding='utf-8') as f:
                    json.dump(self._program.steps, f, indent=2, ensure_ascii=False)
                os.replace(tmp, self.temp_program_pid_file)
                self._log(f"Программа сохранена в {self.temp_program_pid_file}")
            except Exception as e:
                self._log(f"Ошибка сохранения программы во временный файл: {e}")

        self.apply_preset()

        first_step = program.steps[0]
        default_fan = self._get_default_fan_speed(first_step['temperature'])
        self.current_fan_speed = default_fan
        self.camera.set_fan_speed(default_fan)
        self._log(f"Скорость вентилятора по умолчанию: {default_fan} об/мин "
                  f"(цель {first_step['temperature']}°C)")

        self.camera.set_temperature(first_step['temperature'], channel=0)
        self.camera.turn_on_camera()
        self._log(f"Запуск программы из {len(program.steps)} ступеней")

        self._thread = threading.Thread(target=self._program_loop, daemon=True)
        self._thread.start()


    def _apply_pid_for_target(self, target_temp: float) -> bool:
        """Загрузить PID из temp_pid.json для целевой температуры и применить.
        Возвращает True только если данные найдены И успешно применены."""
        if not os.path.exists(self._temp_pid_file):
            return False
        try:
            with open(self._temp_pid_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            key = str(round(target_temp, 1))
            if key not in data:
                return False

            pid = data[key]
            ok, msg = self.camera.set_pid_parameters(
                P=pid.get('p'), I=pid.get('i'), D=pid.get('d'), channel=0
            )
            if not ok:
                self._log(f"Не удалось применить сохранённые PID: {msg}", level="ERROR")
                return False

            if pid.get('setpoint') is not None:
                ok, msg = self.camera.set_temperature(pid['setpoint'], channel=0)
                if not ok:
                    self._log(f"Не удалось применить сохранённую уставку: {msg}",
                              level="ERROR")
                    return False
                self._current_setpoint = pid['setpoint']
                self._update_data(current_setpoint=self._current_setpoint)

            if pid.get('fan_speed') is not None:
                self.camera.set_fan_speed(pid['fan_speed'])
                self.current_fan_speed = pid['fan_speed']

            self._log(
                f"Применены сохранённые PID для T={target_temp}°C: "
                f"P={pid['p']}, I={pid['i']}, D={pid['d']}, "
                f"setpoint={pid.get('setpoint')}, fan_speed={pid.get('fan_speed')}"
            )
            return True
        except Exception as e:
            self._log(f"Ошибка загрузки PID из файла: {e}", level="ERROR")
            return False




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
        # Применяем сохранённую уставку
        setpoint = step.get('setpoint')
        if setpoint is not None:
            self.camera.set_temperature(setpoint, channel=0)
            self._current_setpoint = setpoint
            self._update_data(current_setpoint=self._current_setpoint)
            self._log(f"Установлена уставка из ступени: {setpoint}°C")
        # Применяем сохранённую скорость вентилятора
        fan_speed = step.get('fan_speed')
        if fan_speed is not None:
            self.camera.set_fan_speed(fan_speed)
            self.current_fan_speed = fan_speed
            self._log(f"Установлена скорость вентилятора из ступени: {fan_speed} об/мин")


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
            return

        # Обновляем ступень в памяти
        if 0 <= self.current_step_index < len(self._program.steps):
            step = self._program.steps[self.current_step_index]
            step['pid_p'] = round(p, 2)
            step['pid_i'] = int(i)
            step['pid_d'] = int(d)
            step['setpoint'] = self._current_setpoint
            step['fan_speed'] = self.current_fan_speed

            # Если программа из файла – сохраняем в этот файл
            if self._program_file is not None:
                try:
                    with open(self._program_file, 'w', encoding='utf-8') as f:
                        json.dump(self._program.steps, f, indent=2, ensure_ascii=False)
                    self._log(f"PID ступени {self.current_step_index + 1} сохранены в {self._program_file}")
                except Exception as e:
                    self._log(f"Ошибка сохранения в файл программы: {e}")
            else:
                # Временная программа – сохраняем в temp_program_pid.json
                try:
                    with open(self.temp_program_pid_file, 'w', encoding='utf-8') as f:
                        json.dump(self._program.steps, f, indent=2, ensure_ascii=False)
                    self._log(f"PID временной программы сохранены в {self.temp_program_pid_file}")
                except Exception as e:
                    self._log(f"Ошибка сохранения во временный файл: {e}")

    def _safe_load_json(self, path: str, default):
        """Читает JSON; при пустом/битом файле возвращает default."""
        if not os.path.exists(path):
            return default
        try:
            if os.path.getsize(path) == 0:
                return default
            with open(path, 'r', encoding='utf-8') as f:
                content = f.read().strip()
            if not content:
                return default
            return json.loads(content)
        except (json.JSONDecodeError, OSError) as e:
            self._log(f"Повреждён JSON в {path}: {e}. Использую значение по умолчанию.")
            return default

    def _save_pid_to_temp_file(self, target: float, p: float, i: int, d: int):
        try:
            data = self._safe_load_json(self._temp_pid_file, default={})
            if not isinstance(data, dict):
                data = {}

            key = str(round(target, 1))
            data[key] = {
                'p': p,
                'i': i,
                'd': d,
                'setpoint': self._current_setpoint,
                'fan_speed': self.current_fan_speed,
                'timestamp': time.time()
            }
            # атомарная запись — сначала во временный файл, потом замена
            tmp = self._temp_pid_file + ".tmp"
            with open(tmp, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            os.replace(tmp, self._temp_pid_file)
            self._log(f"PID для температуры {target}°C сохранены в {self._temp_pid_file}")
        except Exception as e:
            self._log(f"Ошибка сохранения PID в файл: {e}")


    def _save_pid_to_temp_file_1(self, target: float, p: float, i: int, d: int):
        """Сохранить PID для ручного режима в temp_pid.json (замена по ключу)."""
        try:
            data = {}
            if os.path.exists(self._temp_pid_file):
                with open(self._temp_pid_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
            key = str(round(target, 1))
            data[key] = {
                'p': p,
                'i': i,
                'd': d,
                'setpoint': self._current_setpoint,  # добавлено
                'fan_speed': self.current_fan_speed,  # добавлено
                'timestamp': time.time()
            }
            with open(self._temp_pid_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            self._log(f"PID для температуры {target}°C сохранены в {self._temp_pid_file}")
        except Exception as e:
            self._log(f"Ошибка сохранения PID в файл: {e}")

    def _program_loop(self):
        """Цикл выполнения программы с применением PID на этапе стабилизации."""
        try:
            for idx, step in enumerate(self._program.steps):
                if self._stop_event.is_set():
                    break
                self.current_step_index = idx
                target = step['temperature']
                rate = step['rate']
                hold = step['hold_time'] * 60

                # Сброс/инициализация данных выдержки для текущей ступени
                self._pre_hold_start_time = None
                self._current_hold_seconds = hold

                # 1. Устанавливаем PID по умолчанию для нагрева
                self.apply_preset()

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
                self._log(f"Этап СТАБИЛИЗАЦИЯ (ступень {idx + 1}, цель {target}°C)")
                if not (self._adaptive_stabilize_temperature(target) if self.adaptive_stabilization_enabled else self._stabilize_temperature(target)):  # здесь будут применены сохранённые PID
                    self._update_data(process_status=ProcessStatus.ERROR)
                    break

                self._save_current_pid()  # сохраняем итоговые PID ступени

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

    def _get_default_fan_speed(self, target_temp: float) -> int:
        """
        Скорость вентилятора по умолчанию в зависимости от целевой температуры:
          * target <= +25 °C  → 1000 об/мин
          * +25 < target <= +60 → 1500 об/мин
          * target > +60       → 2000 об/мин
        """
        try:
            t = float(target_temp)
        except (TypeError, ValueError):
            return 1000
        if t <= 25.0:
            return 1000
        if t <= 60.0:
            return 1500
        return 2000

    def get_heating_rate(self) -> float:
        """Получить текущую скорость нагрева из устройства или сохранённое значение."""
        if self.camera and self.camera.trm12:
            rate = self.camera.get_temperature_rate(channel=0)
            if rate is not None:
                self._heating_rate = rate
                return rate
        return self._heating_rate

    def _get_shaft_temp_cached(self):
        """Возвращает последнее измерение температуры вала.
        TTL-кэш живёт в CameraController (_shaft_temp_cache_ttl)."""
        # Если идёт серия нагревов, не инициируем новое измерение
        if self.shaft_heating_active:
            return self.last_shaft_temp

        shaft_temp, msg = self.camera.get_shaft_temperature()
        if shaft_temp is not None:
            self.last_shaft_temp = shaft_temp
            self.last_shaft_temp_time = time.time()
        else:
            self._log(f"Ошибка измерения вала: {msg}")
        return self.last_shaft_temp

    def _get_shaft_temp_cached_old(self):
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
            self.epsilon_stable_simplified = self.epsilon_stable * self.epsilon_stable_simplified_multiplier
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
        # --- Таймауты стабилизации ---
        if "stabilization_timeout_default" in params:
            self.stabilization_timeout_default = float(params["stabilization_timeout_default"])
        if "stabilization_timeout_saved" in params:
            self.stabilization_timeout_saved = float(params["stabilization_timeout_saved"])

        # --- Упрощённый критерий стабилизации ---
        if "epsilon_stable_simplified_multiplier" in params:
            self.epsilon_stable_simplified_multiplier = float(
                params["epsilon_stable_simplified_multiplier"]
            )
            self.epsilon_stable_simplified = self.epsilon_stable * self.epsilon_stable_simplified_multiplier
        if "required_stable_simplified" in params:
            self.required_stable_simplified = int(params["required_stable_simplified"])

        # --- Выход на режим ---
        if "epsilon_reach_approach" in params:
            self.epsilon_reach_approach = float(params["epsilon_reach_approach"])

        # --- Вентилятор ---
        if "FAN_MIN_RUNNING_SPEED" in params:
            self.FAN_MIN_RUNNING_SPEED = float(params["FAN_MIN_RUNNING_SPEED"])

        if "pre_hold_enabled" in params:
            self.pre_hold_enabled = bool(params["pre_hold_enabled"])

        # === Параметры умного подхода ===
        if "smart_approach_enabled" in params:
            self.smart_approach_enabled = bool(params["smart_approach_enabled"])
        if "deceleration_zone" in params:
            self.deceleration_zone = float(params["deceleration_zone"])
        if "fine_zone" in params:
            self.fine_zone = float(params["fine_zone"])
        if "braking_factor" in params:
            self.braking_factor = float(params["braking_factor"])
        if "prediction_horizon" in params:
            self.prediction_horizon = float(params["prediction_horizon"])

        # === Параметры адаптивной стабилизации ===
        if "adaptive_stabilization_enabled" in params:
            self.adaptive_stabilization_enabled = bool(params["adaptive_stabilization_enabled"])
        if "base_p" in params:
            self.base_p = float(params["base_p"])
        if "base_i" in params:
            self.base_i = float(params["base_i"])
        if "base_d" in params:
            self.base_d = float(params["base_d"])
        if "temp_range" in params:
            self.temp_range = float(params["temp_range"])

        # === Параметры интеллектуального удержания ===
        if "smart_hold_enabled" in params:
            self.smart_hold_enabled = bool(params["smart_hold_enabled"])
        if "kp_adaptive" in params:
            self.kp_adaptive = float(params["kp_adaptive"])
        if "ki_adaptive" in params:
            self.ki_adaptive = float(params["ki_adaptive"])
        if "kd_adaptive" in params:
            self.kd_adaptive = float(params["kd_adaptive"])

        # === Параметры адаптивного управления нагрузкой ===
        if "load_adaptation_enabled" in params:
            self.load_adaptation_enabled = bool(params["load_adaptation_enabled"])
        if "velocity_change_threshold" in params:
            self.velocity_change_threshold = float(params["velocity_change_threshold"])
        if "load_adaptation_factor_p" in params:
            self.load_adaptation_factor_p = float(params["load_adaptation_factor_p"])
        if "load_adaptation_factor_i" in params:
            self.load_adaptation_factor_i = float(params["load_adaptation_factor_i"])
        if "load_adaptation_factor_d" in params:
            self.load_adaptation_factor_d = float(params["load_adaptation_factor_d"])

        if "min_p_value" in params:
            val = float(params["min_p_value"])
            self.min_p_value = max(0.1, val)  # защита от 0 и отрицательных


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
    '''
    @staticmethod
    def _log(message: str):
        """Вывод сообщения в консоль с временной меткой"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{timestamp}] {message}")
   '''

    def _log(self, message: str, level: str = "INFO"):
        """Вывод сообщения в лог (консоль + файл)"""
        self.logger.log(message, level)


    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def start_process(self, target_temp: float, hold_minutes: float):
        """Запуск ручного режима (одна цель) с PID по умолчанию."""
        if self.is_running():
            raise RuntimeError("Процесс уже запущен")

        self._program = None
        self._program_file = None
        self._target_temp = target_temp
        self._update_data(current_setpoint=self._current_setpoint)
        self._hold_minutes = hold_minutes
        self._stop_event.clear()

        # Устанавливаем PID по умолчанию (вместо загрузки из файла)
        self.apply_preset()

        self._log(f"Запуск ручного режима: цель {target_temp}°C, выдержка {hold_minutes} мин")
        self.camera.set_temperature(target_temp, channel=0)
        self.camera.turn_on_camera()
        default_fan = self._get_default_fan_speed(target_temp)
        self.current_fan_speed = default_fan
        self.camera.set_fan_speed(default_fan)
        self._log(f"Скорость вентилятора по умолчанию: {default_fan} об/мин "
                  f"(цель {target_temp}°C)")
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
        self._pre_hold_start_time = None
        self._current_hold_seconds = 0.0
        with self._lock:
            self.data.process_status = ProcessStatus.STOPPED
        self._log("Процесс остановлен")

    def get_data(self) -> ChamberData:
        """Получить копию текущих данных (потокобезопасно)"""
        with self._lock:
            import copy
            return copy.deepcopy(self.data)

    def _update_data_old(self, **kwargs):
        """Обновить поля данных (потокобезопасно)"""
        with self._lock:
            for key, value in kwargs.items():
                if hasattr(self.data, key):
                    setattr(self.data, key, value)

    def _update_data(self, **kwargs):
        with self._lock:
            for key, value in kwargs.items():
                if value is None:
                    continue  # не перезаписываем нулём/None
                if hasattr(self.data, key):
                    setattr(self.data, key, value)

    def _read_sensors(self):
        """Чтение текущих показаний с устройств.
        Если какой-то датчик не отвечает — НЕ подменяем значение нулём,
        а оставляем None, чтобы вызывающий код мог отличить сбой от реального нуля.
        """
        temp, _ = self.camera.get_chamber_temperature()
        grad, _ = self.camera.get_gradient()
        speed = self.camera.get_fan_speed()
        current = self.camera.get_motor_current()
        pid = self.camera.get_pid_parameters(channel=0) or {}
        return {
            'current_temp': temp,  # может быть None
            'gradient': grad,  # может быть None
            'fan_speed': speed,  # может быть None
            'motor_current': current if current is not None else 0.0,
            'p_value': pid.get('P', 0.0),
            'i_value': pid.get('I', 0),
            'd_value': pid.get('D', 0),
        }


    def _read_sensors_old(self):
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
        # self.data.current_setpoint = target
        self._update_data(current_setpoint=target)
        # Сброс/инициализация данных выдержки
        self._pre_hold_start_time = None
        self._current_hold_seconds = self._hold_minutes * 60
        # Этап 1: Выход на температуру
        self._update_data(process_status=ProcessStatus.HEATING, target_temp=target)
        self._log(f"Этап НАГРЕВ: целевая температура {target}°C")
        if not self._smart_wait_for_target(target):
            self._update_data(process_status=ProcessStatus.ERROR)
            self._log("Ошибка: не удалось достичь целевой температуры")
            self.camera.turn_off_camera()
            return
        self._log("Целевая температура достигнута")

        # Этап 2: Стабилизация
        self._update_data(process_status=ProcessStatus.STABILIZING)
        self._log("Этап СТАБИЛИЗАЦИЯ")
        if not (self._adaptive_stabilize_temperature(target) if self.adaptive_stabilization_enabled else self._stabilize_temperature(target)):
            self._update_data(process_status=ProcessStatus.ERROR)
            self._log("Ошибка: не удалось стабилизировать температуру")
            self.camera.turn_off_camera()
            return
        self._log("Температура стабилизирована")

        # Этап 3: Выдержка
        self._update_data(process_status=ProcessStatus.HOLDING)
        self._log(f"Этап ВЫДЕРЖКА: {self._hold_minutes} мин")
        (self._smart_hold_temperature(target, hold_seconds) if self.smart_hold_enabled else self._hold_temperature(target, hold_seconds))

        # Завершение
        self._update_data(process_status=ProcessStatus.COMPLETED)
        self._log("Процесс завершён успешно")
        self.camera.turn_off_camera()

    def _wait_for_target(self, target: float) -> bool:
        """
        Ожидание пересечения целевой температуры.

        Триггер срабатывает, когда температура переходит с одной стороны уставки
        на другую: (prev - target) и (current - target) имеют разные знаки
        (или один из них равен нулю). Работает и при нагреве, и при охлаждении.

        На время выхода на режим нагрев вала работает штатно — никаких
        отключений, потому что нам важен только факт пересечения уставки.
        """
        timeout = 3600
        start = time.time()
        prev_temp = None

        while not self._stop_event.is_set() and (time.time() - start) < timeout:
            sensors = self._read_sensors()
            self._update_data(**sensors)
            self._ensure_fan_running()
            self._check_and_heat_shaft(sensors['current_temp'])
            self._manage_shaft_heating_series()

            current = sensors['current_temp']
            self._log(
                f"НАГРЕВ: T={current:.2f}°C, цель={target:.2f}°C, "
                f"разница={abs(current - target):.2f}°C"
            )

            if prev_temp is not None:
                prev_diff = prev_temp - target
                curr_diff = current - target
                # Пересечение: знаки разные, или один из них ноль
                if prev_diff * curr_diff <= 0:
                    self._log(
                        f"Пересечение целевой температуры: "
                        f"{prev_temp:.2f}°C → {current:.2f}°C "
                        f"(цель {target:.2f}°C). Переход к стабилизации."
                    )
                    return True

            prev_temp = current
            time.sleep(self.update_interval)

        self._log("Таймаут или остановка при ожидании пересечения температуры")
        self._log("Таймаут иди остановка при ожидании пересечения температуры")
        return False

    def _smart_wait_for_target(self, target: float) -> bool:
        """
        Умное ожидание достижения целевой температуры с предсказанием и плавным подходом.
        
        Использует линейную экстраполяцию для предсказания момента достижения целевой температуры
        и плавного торможения перед ней, чтобы избежать перерегулирования.
        """
        if not self.smart_approach_enabled:
            return self._wait_for_target(target)

        timeout = 3600
        start = time.time()
        prev_temp = None
        prev_time = time.time()
        velocity_history = deque(maxlen=5)

        while not self._stop_event.is_set() and (time.time() - start) < timeout:
            sensors = self._read_sensors()
            current = sensors['current_temp']
            current_time = time.time()

            self._update_data(**sensors)
            self._ensure_fan_running()
            self._check_and_heat_shaft(current)
            self._manage_shaft_heating_series()

            # Вычисляем скорость изменения температуры
            if prev_temp is not None and (current_time - prev_time) > 0:
                velocity = (current - prev_temp) / (current_time - prev_time)
                velocity_history.append(velocity)

            # Обновляем историю для обнаружения изменения нагрузки
            self._temp_history.append(current)
            self._time_history.append(current_time)

            prev_temp = current
            prev_time = current_time

            # Проверяем изменение нагрузки
            if self._detect_load_change(current, avg_velocity if velocity_history else 0):
                self._adapt_to_load_change(target)

            # Средняя скорость за последние N измерений
            avg_velocity = sum(velocity_history) / len(velocity_history) if velocity_history else 0

            # Предсказываем температуру через prediction_horizon секунд
            if avg_velocity != 0:
                predicted_temp = current + avg_velocity * self.prediction_horizon
            else:
                predicted_temp = current

            self._log(
                f"НАГРЕВ: T={current:.2f}°C, цель={target:.2f}°C, "
                f"скорость={avg_velocity:.2f}°C/с, предск={predicted_temp:.2f}°C"
            )

            diff = abs(current - target)

            # Зона торможения
            if diff < self.deceleration_zone and avg_velocity > 0.05:
                lookahead_temp = current + avg_velocity * 2

                if lookahead_temp > target:
                    new_setpoint = target - (lookahead_temp - target) * self.braking_factor
                    new_setpoint = max(new_setpoint, target - 1.0)
                    self.camera.set_temperature(new_setpoint, channel=0)
                    self._current_setpoint = new_setpoint
                    self._update_data(current_setpoint=new_setpoint)
                    self._log(f"Торможение: setpoint = {new_setpoint:.2f}°C")

            # Зона точной настройки
            if diff < self.fine_zone:
                self._log(f"Достигнута зона точной настройки ({diff:.2f} < {self.fine_zone:.2f})")
                return True

            # Проверка пересечения (fallback)
            if prev_temp is not None:
                prev_diff = prev_temp - target
                curr_diff = current - target

                if prev_diff * curr_diff <= 0 and diff < 1.0:
                    self._log(f"Пересечение целевой температуры: {prev_temp:.2f} → {current:.2f}°C")
                    return True

            time.sleep(self.update_interval)

        self._log("Таймаут иди остановка при ожидании пересечения температуры")
        return False


    def _stabilize_temperature(self, target: float) -> bool:
        """
        Стабилизация температуры.

        Последовательность:
        1. Устанавливаем СТАНДАРТНЫЕ PID (P=5, I=10), уставку = target.
           На время стабилизации ОТКЛЮЧАЕМ проверку температуры вала.
        2. Ждём УПРОЩЁННУЮ стабилизацию
           (epsilon_stable × 3, required = 3, timeout = stabilization_timeout_default).
        3. Если упрощённая стабилизация ДОСТИГНУТА:
           a. Пытаемся применить СОХРАНЁННЫЕ PID (temp_pid.json / ступень /
              temp_program_pid.json).
           b. Если сохранённые есть — применяем и ждём ПОЛНУЮ стабилизацию
              с ними (timeout = stabilization_timeout_saved), затем при
              необходимости корректируем уставку.
           c. Если сохранённых нет — ПОЛНЫЙ ПОДБОР (P, I, коррекция уставки).
        4. Если упрощённая стабилизация НЕ достигнута за отведённое время
           — ПОЛНЫЙ ПОДБОР.
        5. Финальная стабилизация, регулировка вентилятора, сохранение.
        """
        # --- Отключаем проверку вала на всё время стабилизации ---
        prev_shaft_check_enabled = self.shaft_check_enabled
        self.shaft_check_enabled = False
        self._reset_shaft_heating()

        try:
            # ============ ШАГ 1: Стандартные PID + уставка ============
            self._log("Установка стандартных PID: P=5, I=10, уставка = target")
            self.camera.set_pid_parameters(P=5.0, I=10, channel=0)
            self.camera.set_temperature(target, channel=0)
            self._current_setpoint = target
            self._update_data(current_setpoint=target)

            default_fan = self._get_default_fan_speed(target)
            self.current_fan_speed = default_fan
            self.camera.set_fan_speed(default_fan)
            self._log(f"Скорость вентилятора по умолчанию: {default_fan} об/мин "
                      f"(цель {target}°C)")

            # ============ ШАГ 2: Упрощённая стабилизация ============
            self._log(
                f"Ожидание УПРОЩЁННОЙ стабилизации "
                f"(eps={self.epsilon_stable_simplified:.2f}, "
                f"required={self.required_stable_simplified}, "
                f"timeout={self.stabilization_timeout_default}s)"
            )
            simplified_ok = self._wait_for_stabilization(
                timeout=self.stabilization_timeout_default,
                epsilon_stable=self.epsilon_stable_simplified,
                required_stable=self.required_stable_simplified
            )
            # === Флаг «Пред. выдержка»: старт отсчёта после первичной стабилизации ===
            if simplified_ok and self.pre_hold_enabled and self._pre_hold_start_time is None:
                self._pre_hold_start_time = time.time()
                self._log(
                    "Флаг 'Пред. выдержка' активен: отсчёт времени выдержки "
                    "начат после первичной (упрощённой) стабилизации."
                )

            tuning_done = False

            if simplified_ok:
                self._log("Упрощённая стабилизация достигнута. "
                          "Попытка загрузить сохранённые PID.")

                # ============ ШАГ 3: Загрузка сохранённых PID ============
                saved_applied = False

                if self._program is None:
                    # Ручной режим — temp_pid.json
                    if self._apply_pid_for_target(target):
                        self._log("Применены сохранённые PID из temp_pid.json")
                        saved_applied = True
                    else:
                        self._log("Сохранённых PID для ручного режима не найдено.")
                else:
                    # Программный режим — ступень / temp_program_pid.json
                    pid_data = self._load_pid_for_step(self.current_step_index, target)
                    if pid_data is not None:
                        ok, msg = self.camera.set_pid_parameters(
                            P=pid_data['p'], I=pid_data['i'], D=pid_data['d'], channel=0
                        )
                        if ok:
                            if pid_data.get('setpoint') is not None:
                                self.camera.set_temperature(pid_data['setpoint'], channel=0)
                                self._current_setpoint = pid_data['setpoint']
                                self._update_data(current_setpoint=self._current_setpoint)
                            if pid_data.get('fan_speed') is not None:
                                self.camera.set_fan_speed(pid_data['fan_speed'])
                                self.current_fan_speed = pid_data['fan_speed']
                            saved_applied = True
                            self._log("Применены сохранённые PID из программы")
                        else:
                            self._log(
                                f"Не удалось применить сохранённые PID: {msg}",
                                level="ERROR"
                            )
                    else:
                        self._log("Сохранённых PID для ступени не найдено.")

                if saved_applied:
                    # ============ ШАГ 3b: Полная стабилизация с сохранёнными PID ============
                    self._log(
                        f"Ожидание ПОЛНОЙ стабилизации с сохранёнными PID "
                        f"(макс. {self.stabilization_timeout_saved / 60:.0f} мин)"
                    )
                    if self._wait_for_stabilization(timeout=self.stabilization_timeout_saved):
                        sensors = self._read_sensors()
                        current_temp = sensors['current_temp']
                        diff = abs(current_temp - target)

                        if diff <= self.epsilon_reach:
                            self._log(
                                f"Температура в допуске: {current_temp:.2f}°C "
                                f"(отклонение {diff:.2f}°C)"
                            )
                            tuning_done = True
                        else:
                            self._log(
                                f"Температура {current_temp:.2f}°C, "
                                f"отклонение {diff:.2f}°C. Коррекция уставки."
                            )
                            if self._correct_setpoint_stepwise(target, current_temp):
                                self._log("Коррекция уставки выполнена успешно")
                                tuning_done = True
                            else:
                                self._log(
                                    "Коррекция уставки не удалась. "
                                    "Переход к полному подбору."
                                )
                    else:
                        self._log(
                            "Полная стабилизация с сохранёнными PID не удалась "
                            "за отведённое время. Переход к полному подбору."
                        )
                else:
                    self._log("Сохранённых PID нет. Запуск полного подбора.")
            else:
                self._log(
                    "Упрощённая стабилизация НЕ достигнута за отведённое время. "
                    "Запуск полного подбора."
                )

            # ============ ШАГ 4: Полный подбор ============
            if not tuning_done:
                self._log("Возврат к стандартным PID и целевой уставке. Полный подбор.")
                self.camera.set_pid_parameters(P=5.0, I=10, channel=0)
                self.camera.set_temperature(target, channel=0)
                self._current_setpoint = target
                self._update_data(current_setpoint=target)

                default_fan = self._get_default_fan_speed(target)
                self.current_fan_speed = default_fan
                self.camera.set_fan_speed(default_fan)

                if not self._wait_for_stabilization(timeout=self.stabilization_timeout_default):
                    self._log("Ошибка стабилизации перед полным подбором")
                    self._update_data(process_status=ProcessStatus.ERROR)
                    self.camera.turn_off_camera()
                    return False

                sensors = self._read_sensors()
                current_temp = sensors['current_temp']
                diff = abs(current_temp - target)

                # --- Подбор P ---
                p_value = 5.0
                while (p_value > self.min_p_value and diff > self.epsilon_reach
                       and not self._stop_event.is_set()):
                    p_value = max(self.min_p_value, p_value - 0.5)
                    self._log(f"Установка P = {p_value:.2f}")
                    self.camera.set_pid_parameters(P=p_value, channel=0)
                    if not self._wait_for_stabilization(timeout=600):
                        self._log("Ошибка стабилизации после изменения P")
                        return False
                    sensors = self._read_sensors()
                    current_temp = sensors['current_temp']
                    diff = abs(current_temp - target)
                    self._log(f"После P={p_value:.2f} T={current_temp:.2f}°C, "
                              f"отклонение {diff:.2f}°C")

                if diff <= self.epsilon_reach:
                    self._log("Температура в допуске после подбора P")
                else:
                    self._log("P достигло минимума. Начинаем подбор I.")

                    # --- Подбор I ---
                    i_value = 10
                    while (i_value > 7 and diff > self.epsilon_reach
                           and not self._stop_event.is_set()):
                        i_value -= 1
                        self._log(f"Установка I = {i_value}")
                        self.camera.set_pid_parameters(I=i_value, channel=0)
                        if not self._wait_for_stabilization(timeout=600):
                            self._log("Ошибка стабилизации после изменения I")
                            return False
                        sensors = self._read_sensors()
                        current_temp = sensors['current_temp']
                        diff = abs(current_temp - target)
                        self._log(f"После I={i_value} T={current_temp:.2f}°C, "
                                  f"отклонение {diff:.2f}°C")

                    if diff <= self.epsilon_reach:
                        self._log("Температура в допуске после подбора I")
                    else:
                        self._log("I достигло минимума. Коррекция уставки.")

                        # --- Коррекция уставки ---
                        if not self._correct_setpoint_stepwise(target, current_temp):
                            self._log("Не удалось достичь допуска после коррекции уставки")
                            return False

            # ============ ШАГ 5: Финальная стабилизация перед вентилятором ============
            self._log("Ожидание финальной стабилизации перед регулировкой вентилятора")
            if not self._wait_for_stabilization(timeout=600):
                self._log("Ошибка финальной стабилизации")
                return False

            # ============ ШАГ 6: Предварительная корректировка вентилятора ============
            skip_main_fan_adjustment = False

            if self.fan_control_enabled and self.current_fan_speed < 2500:
                self._log("Предварительная корректировка: +1000 об/мин")

                grad_before_raw, msg = self.camera.get_gradient()
                if grad_before_raw is None:
                    self._log(f"Не удалось измерить градиент до изменения: {msg}. "
                              f"Пропускаем предкоррекцию.")
                else:
                    abs_grad_before = abs(grad_before_raw)
                    old_speed = self.current_fan_speed
                    new_speed = old_speed + 1000

                    success, msg = self.camera.set_fan_speed(new_speed)
                    if not success:
                        self._log(f"Не удалось увеличить скорость: {msg}. "
                                  f"Продолжаем без предкоррекции.")
                    else:
                        self.current_fan_speed = new_speed
                        self._log(f"Скорость увеличена до {new_speed}, "
                                  f"ожидание стабилизации...")

                        if not self._wait_for_stabilization(timeout=600):
                            self._log("Стабилизация после увеличения скорости "
                                      "не удалась, возвращаем исходную скорость.")
                            self.camera.set_fan_speed(old_speed)
                            self.current_fan_speed = old_speed
                        else:
                            grad_after_raw, msg = self.camera.get_gradient()
                            if grad_after_raw is None:
                                self._log(f"Не удалось измерить градиент после "
                                          f"изменения: {msg}. Возвращаем исходную скорость.")
                                self.camera.set_fan_speed(old_speed)
                                self.current_fan_speed = old_speed
                            else:
                                abs_grad_after = abs(grad_after_raw)
                                delta = abs(abs_grad_after - abs_grad_before)
                                self._log(
                                    f"|grad| до: {abs_grad_before:.2f}°C, "
                                    f"после: {abs_grad_after:.2f}°C, "
                                    f"изменение: {delta:.2f}°C"
                                )
                                if delta <= 0.3:
                                    self._log(
                                        "Изменение незначительное (≤0.3°C), "
                                        "возвращаем исходную скорость и пропускаем "
                                        "основной подбор."
                                    )
                                    self.camera.set_fan_speed(old_speed)
                                    self.current_fan_speed = old_speed
                                    skip_main_fan_adjustment = True
                                else:
                                    self._log("Изменение существенное (>0.3°C), "
                                              "оставляем новую скорость.")

            # ============ ШАГ 7: Основной подбор скорости вентилятора ============
            if self.fan_control_enabled and not skip_main_fan_adjustment:
                self._log("Подбор скорости вентилятора по целевому градиенту")
                grad, _ = self.camera.get_gradient()
                if grad is None:
                    self._log("Не удалось измерить градиент — пропуск регулировки")
                else:
                    abs_grad = abs(grad)
                    max_fan_attempts = 20
                    fan_attempt = 0

                    while (abs(abs_grad - self.target_gradient) > 0.5
                           and fan_attempt < max_fan_attempts
                           and not self._stop_event.is_set()):
                        if abs_grad > self.target_gradient:
                            new_speed = min(self.current_fan_speed + 100, self.max_fan_speed)
                            self._log(f"Градиент {abs_grad:.2f} > "
                                      f"{self.target_gradient}, увеличиваем до {new_speed}")
                        else:
                            new_speed = max(self.current_fan_speed - 100, self.min_fan_speed)
                            self._log(f"Градиент {abs_grad:.2f} < "
                                      f"{self.target_gradient}, уменьшаем до {new_speed}")

                        success, msg = self.camera.set_fan_speed(new_speed)
                        if not success:
                            self._log(f"Ошибка установки скорости: {msg}")
                            break
                        self.current_fan_speed = new_speed

                        if not self._wait_for_stabilization(timeout=600):
                            self._log("Ошибка стабилизации после смены скорости")
                            return False

                        grad, _ = self.camera.get_gradient()
                        if grad is None:
                            self._log("Не удалось измерить градиент — прекращаем подбор")
                            break
                        abs_grad = abs(grad)
                        fan_attempt += 1
                        self._log(f"После смены скорости градиент = {abs_grad:.2f}°C")

                    if abs(abs_grad - self.target_gradient) <= 0.5:
                        self._log(f"Градиент достиг целевого диапазона: {abs_grad:.2f}°C")
                    else:
                        self._log("Не удалось точно настроить градиент")

                # Проверка температуры после вентилятора
                sensors = self._read_sensors()
                current_temp = sensors['current_temp']
                if not self._correct_setpoint_stepwise(target, current_temp):
                    self._log("Не удалось вернуть температуру в допуск после "
                              "регулировки вентилятора")
                    return False

            # ============ ШАГ 8: Финальная стабилизация и сохранение ============
            self._log("Финальная стабилизация перед выдержкой")
            if not self._wait_for_stabilization(timeout=600):
                self._log("Ошибка финальной стабилизации")
                return False

            self._save_stabilization_results(target)
            self._save_current_pid()
            return True

        finally:
            # --- Возвращаем проверку вала ---
            self.shaft_check_enabled = prev_shaft_check_enabled




    def _adaptive_stabilize_temperature(self, target: float) -> bool:
        """
        Адаптивная стабилизация с динамической настройкой PID параметров.
        
        Использует адаптивные PID параметры в зависимости от целевой температуры
        и условий работы камеры.
        """
        if not self.adaptive_stabilization_enabled:
            return self._stabilize_temperature(target)

        # Сохраняем текущее состояние
        prev_shaft_check_enabled = self.shaft_check_enabled
        self.shaft_check_enabled = False
        self._reset_shaft_heating()

        try:
            # === Фаза 1: Быстрое приближение с адаптивными PID ===
            self._log("=== Фаза 1: Быстрое приближение с адаптивными PID ===")
            
            # Настраиваем PID в зависимости от целевой температуры
            p_factor = 1.0 + (target / self.temp_range) * 0.5
            i_factor = 1.0 + (target / self.temp_range) * 0.3
            d_factor = 1.0 + (target / self.temp_range) * 0.2

            p = self.base_p * p_factor
            i = self.base_i * i_factor
            d = self.base_d * d_factor

            self.camera.set_pid_parameters(P=p, I=i, D=d, channel=0)
            self.camera.set_temperature(target, channel=0)
            self._current_setpoint = target
            self._update_data(current_setpoint=target)

            default_fan = self._get_default_fan_speed(target)
            self.current_fan_speed = default_fan
            self.camera.set_fan_speed(default_fan)

            self._log(f"Адаптивные PID параметры: P={p:.1f}, I={i:.1f}, D={d:.1f}")

            # Ждём первичной стабилизации с более мягкими критериями
            if not self._wait_for_stabilization(
                timeout=900,  # 15 минут
                epsilon_stable=0.3,  # Более мягкий критерий
                required_stable=5
            ):
                self._log("Не удалось достичь первичной стабилизации")
                return False

            self._log("Первичная стабилизация достигнута")

            # === Фаза 2: Тонкая настройка с сохраненными PID ===
            self._log("=== Фаза 2: Тонкая настройка ===")

            # Загружаем сохранённые PID параметры для этой температуры
            if self._program is None:
                if self._apply_pid_for_target(target):
                    self._log("Применены сохранённые PID параметры из temp_pid.json")
                else:
                    # Если нет сохранённых параметров, используем улучшенные стандартные
                    improved_p = 3.0
                    improved_i = 8
                    improved_d = 100
                    self.camera.set_pid_parameters(
                        P=improved_p, I=improved_i, D=improved_d, channel=0
                    )
                    self._log(f"Используем улучшенные стандартные PID: P={improved_p}, I={improved_i}, D={improved_d}")
            else:
                # Для программного режима
                pid_data = self._load_pid_for_step(self.current_step_index, target)
                if pid_data:
                    ok, msg = self.camera.set_pid_parameters(
                        P=pid_data['p'], I=pid_data['i'], D=pid_data['d'], channel=0
                    )
                    if ok:
                        if pid_data.get('setpoint') is not None:
                            self.camera.set_temperature(pid_data['setpoint'], channel=0)
                            self._current_setpoint = pid_data['setpoint']
                            self._update_data(current_setpoint=self._current_setpoint)
                        if pid_data.get('fan_speed') is not None:
                            self.camera.set_fan_speed(pid_data['fan_speed'])
                            self.current_fan_speed = pid_data['fan_speed']
                        self._log("Применены PID параметры из программы")
                    else:
                        self._log(f"Не удалось применить PID: {msg}", level="ERROR")
                else:
                    self._log("PID параметры для программы не найдены")

            # Ждём точной стабилизации
            if not self._wait_for_stabilization(
                timeout=self.stabilization_timeout_saved,  # 15 минут
                epsilon_stable=self.epsilon_stable,
                required_stable=5
            ):
                self._log("Не удалось достичь точной стабилизации")
                return False

            self._log("Точная стабилизация достигнута")

            # === Фаза 3: Оптимизация (опционально) ===
            if self.auto_apply_pid:
                self._save_stabilization_results(target)

            return True

        finally:
            self.shaft_check_enabled = prev_shaft_check_enabled

    def _wait_for_stabilization(self, timeout: float = 1800,
                                epsilon_stable: float = None,
                                required_stable: int = None) -> bool:
        if epsilon_stable is None:
            epsilon_stable = self.epsilon_stable
        if required_stable is None:
            required_stable = 5

        start = time.time()
        stable_count = 0
        prev_temp = None

        while not self._stop_event.is_set() and (time.time() - start) < timeout:
            sensors = self._read_sensors()
            current_temp = sensors['current_temp']
            self._update_data(**sensors)
            # Обновляем остаток выдержки, если отсчёт уже стартовал (флаг «Пред. выдержка»)
            if self._pre_hold_start_time is not None and self._current_hold_seconds > 0:
                elapsed = time.time() - self._pre_hold_start_time
                remaining = max(0.0, self._current_hold_seconds - elapsed)
                self._update_data(hold_remaining=remaining)

            # Проверяем вентилятор КАЖДУЮ итерацию
            self._ensure_fan_running()

            # Фактические обороты: если < порога — замер не учитываем
            fan_speed = sensors.get('fan_speed') or 0
            fan_ok = (fan_speed >= getattr(self, 'FAN_MIN_RUNNING_SPEED', 50)
                      if self.fan_control_enabled else True)

            self._check_and_heat_shaft(current_temp)
            self._manage_shaft_heating_series()

            if not fan_ok:
                if stable_count > 0:
                    self._log(
                        f"СТАБИЛИЗАЦИЯ: T={current_temp:.2f}°C, "
                        f"вентилятор {fan_speed} об/мин — счётчик сброшен",
                        level="WARNING"
                    )
                stable_count = 0
                prev_temp = current_temp
                time.sleep(self.stability_interval)
                continue

            if prev_temp is not None:
                delta = abs(current_temp - prev_temp)
                if delta <= epsilon_stable:
                    stable_count += 1
                    self._log(
                        f"СТАБИЛИЗАЦИЯ: T={current_temp:.2f}°C, "
                        f"стабильность {stable_count}/{required_stable} "
                        f"(eps={epsilon_stable:.2f})"
                    )
                    if stable_count >= required_stable:
                        return True
                else:
                    stable_count = 0
                    self._log(
                        f"СТАБИЛИЗАЦИЯ: T={current_temp:.2f}°C, изменение "
                        f"{delta:.2f} > {epsilon_stable:.2f}, сброс счётчика"
                    )
            else:
                self._log(f"СТАБИЛИЗАЦИЯ: первое измерение T={current_temp:.2f}°C")

            prev_temp = current_temp
            time.sleep(self.stability_interval)

        self._log("Таймаут или остановка при ожидании стабилизации")
        return False

    def _save_stabilization_results(self, target_temp: float):
        """
        Сохраняет итоговые параметры стабилизации в JSON-файл.
        Файл: stabilization_results.json (в рабочей директории).
        Добавляет запись в массив.
        """
        sensors = self._read_sensors()
        result = {
            "timestamp": datetime.now().isoformat(),
            "step_index": (self.current_step_index
                           if self._program and self.current_step_index is not None
                           else -1),
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
            data = self._safe_load_json(filename, default=[])
            if not isinstance(data, list):
                # на случай, если в файле был одиночный объект или мусор
                data = [data] if isinstance(data, dict) else []

            data.append(result)

            # атомарная запись
            tmp = filename + ".tmp"
            with open(tmp, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=4, ensure_ascii=False)
            os.replace(tmp, filename)

            step_no = (self.current_step_index + 1
                       if self.current_step_index is not None
                       else '')
            self._log(f"Результаты стабилизации ступени {step_no} сохранены в {filename}")
        except Exception as e:
            self._log(f"Ошибка сохранения результатов стабилизации: {e}")

    def _save_stabilization_results_1(self, target_temp: float):
        """
        Сохраняет итоговые параметры стабилизации в JSON-файл.
        Файл: stabilization_results.json (в рабочей директории)
        Добавляет запись в массив.
        """
        sensors = self._read_sensors()
        result = {
            "timestamp": datetime.now().isoformat(),
            "step_index": self.current_step_index if self._program and self.current_step_index is not None else -1,
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
            self._update_data(current_setpoint=self._current_setpoint)
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

        Если включён флаг «Пред. выдержка» и первичная стабилизация уже
        завершилась ранее — отсчёт ведётся с момента её окончания.
        """
        if self.pre_hold_enabled and self._pre_hold_start_time is not None:
            start_hold = self._pre_hold_start_time
            elapsed = time.time() - start_hold
            self._log(
                f"Пред. выдержка: отсчёт ведётся с момента окончания "
                f"первичной стабилизации (уже прошло {elapsed / 60:.1f} мин)."
            )
            # Если время уже истекло на этапе стабилизации — выдержку пропускаем
            if elapsed >= duration:
                self._log(
                    f"Время выдержки уже истекло во время стабилизации "
                    f"({elapsed / 60:.1f} мин >= {duration / 60:.1f} мин). "
                    f"Этап выдержки пропущен."
                )
                self._update_data(hold_remaining=0)
                return
        else:
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
            time.sleep(self.update_interval)

    def _smart_hold_temperature(self, target: float, duration: float):
        """
        Интеллектуальное удержание температуры с предсказанием и адаптацией.
        
        Использует предсказательную коррекцию на основе:
        - Текущего отклонения
        - Скорости изменения
        - Тренда (второе производное)
        - Адаптивного управления вентилятором
        """
        if not self.smart_hold_enabled:
            return self._hold_temperature(target, duration)

        if self.pre_hold_enabled and self._pre_hold_start_time is not None:
            start_hold = self._pre_hold_start_time
            elapsed = time.time() - start_hold
            self._log(
                f"Пред. выдержка: время истекло ({elapsed / 60:.1f} мин). "
                f"Начата выдержка при достигнутой стабильности."
            )
            self._update_data(hold_remaining=0)
            start_hold = time.time()
            duration = self._current_hold_seconds
        else:
            start_hold = time.time()

        # История для предсказания
        temp_history = deque(maxlen=10)
        time_history = deque(maxlen=10)

        # Параметры адаптивного управления
        integral_error = 0.0
        last_error = 0.0
        last_correction_time = 0
        last_fan_adjust_time = 0

        while not self._stop_event.is_set() and (time.time() - start_hold) < duration:
            elapsed = time.time() - start_hold
            remaining = duration - elapsed
            sensors = self._read_sensors()
            current = sensors['current_temp']
            current_time = time.time()

            # Обновляем историю
            temp_history.append(current)
            time_history.append(current_time)

            self._update_data(**sensors, hold_remaining=remaining)
            self._ensure_fan_running()
            self._check_and_heat_shaft(current)
            self._manage_shaft_heating_series()

            diff = abs(current - target)
            error = current - target

            self._log(
                f"ВЫДЕРЖКА: T={current:.2f}°C, цель={target:.2f}°C, "
                f"разница={diff:.2f}°C, осталось={remaining / 60:.1f} мин"
            )

            # === Предсказание тренда ===
            if len(temp_history) >= 3:
                # Вычисляем скорость изменения
                if len(time_history) >= 2 and (time_history[-1] - time_history[-2]) > 0:
                    velocity = (temp_history[-1] - temp_history[-2]) / (time_history[-1] - time_history[-2])
                else:
                    velocity = 0

                # Вычисляем ускорение
                if len(time_history) >= 3:
                    dt1 = time_history[-1] - time_history[-2]
                    dt2 = time_history[-2] - time_history[-3]
                    if dt1 > 0 and dt2 > 0:
                        acceleration = ((temp_history[-1] - temp_history[-2]) / dt1 -
                                       (temp_history[-2] - temp_history[-3]) / dt2) / ((dt1 + dt2) / 2)
                    else:
                        acceleration = 0
                else:
                    acceleration = 0

                # Предсказываем температуру через prediction_horizon секунд
                predicted_temp = current + velocity * self.prediction_horizon + 0.5 * acceleration * (self.prediction_horizon ** 2)
                predicted_error = predicted_temp - target

                self._log(
                    f"Предсказание: через {self.prediction_horizon:.0f}с T={predicted_temp:.2f}°C, "
                    f"скорость={velocity:.3f}°C/с, ускорение={acceleration:.4f}°C/с²"
                )

                # === Адаптивная коррекция ===
                now = time.time()

                # Корректируем setpoint на основе предсказания
                if now - last_correction_time >= self.correction_cooldown:
                    # Используем ПИД-регулятор для коррекции
                    p_term = self.kp_adaptive * error
                    integral_error += error * (now - last_correction_time)
                    i_term = self.ki_adaptive * integral_error

                    if last_error != 0 and (now - last_correction_time) > 0:
                        d_term = self.kd_adaptive * (error - last_error) / (now - last_correction_time)
                    else:
                        d_term = 0

                    # Общая коррекция
                    correction = p_term + i_term + d_term
                    correction = max(-self.max_correction, min(self.max_correction, correction))

                    # Применяем коррекцию только если предсказанная ошибка значительна
                    if abs(predicted_error) > self.epsilon_reach or abs(error) > self.epsilon_reach:
                        new_setpoint = target + correction
                        self.camera.set_temperature(new_setpoint, channel=0)
                        self._current_setpoint = new_setpoint
                        self._update_data(current_setpoint=new_setpoint)

                        self._log(
                            f"Коррекция setpoint: {self._current_setpoint:.2f} → {new_setpoint:.2f}°C "
                            f"(P={p_term:.3f}, I={i_term:.3f}, D={d_term:.3f})"
                        )
                        last_correction_time = now
                        last_error = error

                # === Адаптивное управление вентилятором ===
                if self.fan_control_enabled and now - last_fan_adjust_time >= self.fan_adjust_interval:
                    if diff < self.epsilon_stable and abs(velocity) < 0.05:
                        # Температура стабильна - уменьшаем вентилятор для экономии энергии
                        new_fan_speed = max(self.min_fan_speed, self.current_fan_speed - 100)
                        if new_fan_speed < self.current_fan_speed:
                            self.camera.set_fan_speed(new_fan_speed)
                            self.current_fan_speed = new_fan_speed
                            self._log(f"Уменьшение скорости вентилятора: {self.current_fan_speed + 100} → {new_fan_speed} об/мин")
                            last_fan_adjust_time = now
                    elif diff > self.epsilon_reach * 2 and velocity > 0.1:
                        # Температура растёт слишком быстро - увеличиваем вентилятор
                        new_fan_speed = min(self.max_fan_speed, self.current_fan_speed + 100)
                        if new_fan_speed > self.current_fan_speed:
                            self.camera.set_fan_speed(new_fan_speed)
                            self.current_fan_speed = new_fan_speed
                            self._log(f"Увеличение скорости вентилятора: {self.current_fan_speed - 100} → {new_fan_speed} об/мин")
                            last_fan_adjust_time = now

            time.sleep(self.update_interval)

    def _detect_load_change(self, current_temp: float, velocity: float) -> bool:
        """
        Обнаружение изменения нагрузки по резкому изменению температуры или скорости.
        """
        if not self.load_adaptation_enabled:
            return False

        if len(self._temp_history) < 3:
            return False

        # Вычисляем среднюю скорость за последние N измерений
        recent_velocities = []
        for i in range(1, len(self._temp_history)):
            if self._time_history[i] - self._time_history[i-1] > 0:
                v = (self._temp_history[i] - self._temp_history[i-1]) / (self._time_history[i] - self._time_history[i-1])
                recent_velocities.append(v)

        if not recent_velocities:
            return False

        avg_velocity = sum(recent_velocities) / len(recent_velocities)
        velocity_change = abs(velocity - avg_velocity)

        # Если скорость изменилась резко
        if velocity_change > self.velocity_change_threshold:
            self._log(f"Обнаружено изменение нагрузки! Δv = {velocity_change:.2f}°C/с")
            return True

        return False

    def _adapt_to_load_change(self, target: float):
        """
        Адаптация PID параметров при изменении нагрузки.
        """
        if not self.load_adaptation_enabled:
            return

        # Увеличиваем P и D для более быстрого отклика
        current_pid = self.camera.get_pid_parameters(channel=0) or {}

        new_p = current_pid.get('P', self.base_p) * self.load_adaptation_factor_p
        new_i = current_pid.get('I', self.base_i) * self.load_adaptation_factor_i
        new_d = current_pid.get('D', self.base_d) * self.load_adaptation_factor_d

        self.camera.set_pid_parameters(P=new_p, I=new_i, D=new_d, channel=0)
        self._log(f"Адаптация к изменению нагрузки: P={new_p:.1f}, I={new_i:.1f}, D={new_d:.1f}")

    def apply_preset(self):
        """Установка рекомендуемых параметров PID и скорости нагрева."""
        self.camera.set_pid_parameters(P=0.5, I=3, D=200, deadband=0.0,
                                       output_min=0.0, output_max=100.0, channel=0)
        self.set_heating_rate(self._heating_rate)

        # Раньше писали в trm12 напрямую — теперь через обёртку CameraController
        self.camera.trm12_write_parameter("DB.D", 0.05, channel=0)  # минимальный ход
        self.camera.trm12_write_parameter("U.NOT", 5, channel=0)  # полное время хода
        self.camera.trm12_write_parameter("U.GAP", 5, channel=0)  # выборка люфта
        self.camera.trm12_write_parameter("UR.EU", 0.5, channel=0)  # время реверса

    def apply_preset_old(self):
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


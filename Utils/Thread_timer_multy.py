import time
import threading
from typing import Callable, Union, Dict, Optional


class Timer_D_Multy:

    def __init__(self, dpg,
                 value_func: Callable[[], Union[Dict[str, str], str, float]] = None,
                 display: Optional[Union[str, Dict[str, str]]] = None,
                 sleep_time: float = 0.5,
                 display_time: Optional[str] = None,
                 time_storage_var: Optional[str] = None):
        self.start_time = None
        self.elapsed_time = 0
        self.running = False
        self.stopped = True
        self.thread = None
        self.dpg = dpg
        self.func = value_func
        self.sleep_time = sleep_time
        self.display_time = display_time  # Тег для отображения времени
        self.time_storage_var = time_storage_var  # Переменная для сохранения времени
        self.current_start_time = None

        # Обработка параметров для обратной совместимости
        self.display_map = {}

        if isinstance(display, dict):
            self.display_map = display


    def start(self):
        if not self.running:
            if self.stopped:
                self.start_time = time.time()
                self.current_start_time = time.time()
                self.stopped = False
            self.running = True
            self.thread = threading.Thread(target=self.update_timer)
            self.thread.start()

    def stop(self):
        self.running = False

        if self.thread is not None:
            if self.thread != threading.current_thread():
                self.thread.join(timeout=1.0)
        self.stopped = True

    def reset(self):
        self.stop()
        self.elapsed_time = 0
        self.start_time = None
        # Сброс отображения времени при reset
        if self.display_time:
            self.dpg.set_value(self.display_time, "00:00")


    def reset_time(self):
        self.current_start_time = time.time()

    def update_timer(self):
        while self.running:
            current_time = time.time()
            elapsed_curr = current_time - self.current_start_time
            mins, secs = divmod(elapsed_curr, 60)
            hours, mins = divmod(mins, 60)
            timer_str = f"{int(mins):02d}:{int(secs):02d}"

            # Обновление отображения времени (если указано)
            if self.display_time:
                self.dpg.set_value(self.display_time, timer_str)
            result = self.func()

            # Обработка результатов функции
            if isinstance(result, dict):
                # Если функция возвращает словарь {tag: value}
                for tag, value in result.items():
                    self.dpg.set_value(tag, str(value))
            elif self.display_map:
                # Обратная совместимость: одиночное значение + маппинг
                str_result = str(result)
                for data_key, tag in self.display_map.items():
                    if data_key == 'default' or data_key == self.data_type:
                        self.dpg.set_value(tag, str_result)

            time.sleep(self.sleep_time)

        # Сохраняем прошедшее время при остановке
        if self.start_time is not None:
            self.elapsed_time += time.time() - self.start_time





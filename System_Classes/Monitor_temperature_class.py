# temperature_monitor_integrated.py
import time
from collections import deque
from typing import Optional, Tuple

MAX_DATA_POINTS = 100
MIN_UPDATE_INTERVAL = 10.0  # Минимальный интервал между точками на графике


class TemperatureMonitorWindow:
    """Окно мониторинга температуры с интеграцией с TPM12 и BLSD-20"""

    def __init__(self, dpg_context):
        self.dpg = dpg_context
        self.time_data = deque(maxlen=MAX_DATA_POINTS)
        self.temp_data = deque(maxlen=MAX_DATA_POINTS)
        self.fan_data = deque(maxlen=MAX_DATA_POINTS)
        self.gradient_data = deque(maxlen=MAX_DATA_POINTS)

        self.start_time = time.time()
        self.paused = False
        self.is_visible = False

        self.window_tag = "temperature_monitor_window"

        # Ссылки на GUI устройств
        self.tpm12_gui = None
        self.motor_gui = None

        # Переменные для контроля интервалов добавления точек
        self.last_data_update_time = 0.0  # Время последнего добавления точки
        self.pending_data = None  # Данные, ожидающие добавления
        self.last_values = (0.0, 0.0, 0.0)  # Последние значения (temp, fan, grad)

    def set_devices(self, tpm12_gui, motor_gui):
        """Установить ссылки на GUI устройств"""
        self.tpm12_gui = tpm12_gui
        self.motor_gui = motor_gui

    def get_real_data(self) -> Tuple[float, float, float, float]:
        """Получение реальных данных с устройств"""
        current_time = time.time() - self.start_time

        # Получаем данные с TPM12
        if self.tpm12_gui:
            try:
                temperature = float(self.tpm12_gui.temp_ch1)
                gradient = float(self.tpm12_gui.temp_ch2)
            except (ValueError, TypeError, AttributeError):
                temperature = self.last_values[0]
                gradient = self.last_values[2]
        else:
            temperature = self.last_values[0]
            gradient = self.last_values[2]

        # Получаем данные с двигателя
        if self.motor_gui:
            try:
                # Преобразуем обороты в проценты (0-4000 об/мин -> 0-100%)
                fan_speed = float(self.motor_gui.current_speed)
                fan_percent = (fan_speed / 4000) * 100 if fan_speed > 0 else 0
            except (ValueError, TypeError, AttributeError):
                fan_percent = self.last_values[1]
        else:
            fan_percent = self.last_values[1]

        # Сохраняем текущие значения для использования в случае ошибок
        self.last_values = (temperature, fan_percent, gradient)

        return current_time, temperature, fan_percent, gradient

    def should_add_data_point(self) -> bool:
        """Проверка, нужно ли добавлять новую точку на график"""
        current_time = time.time()
        time_since_last_update = current_time - self.last_data_update_time
        return time_since_last_update >= MIN_UPDATE_INTERVAL

    def add_data_point(self):
        """Добавление новой точки на график"""
        if self.paused or not self.is_visible:
            return

        try:
            # Получение реальных данных с устройств
            t, temp, fan, grad = self.get_real_data()

            # Добавление данных
            self.time_data.append(t)
            self.temp_data.append(temp)
            self.fan_data.append(fan)
            self.gradient_data.append(grad)

            # Обновление всех графиков
            if len(self.time_data) > 0:
                self.dpg.set_value(f"{self.window_tag}_temp_series", [list(self.time_data), list(self.temp_data)])
                self.dpg.set_value(f"{self.window_tag}_fan_series", [list(self.time_data), list(self.fan_data)])
                self.dpg.set_value(f"{self.window_tag}_gradient_series",
                                   [list(self.time_data), list(self.gradient_data)])

            # Обновление статуса
            status = (f"Время: {t:.0f} с | "
                      f"Температура: {temp:.1f}°C | "
                      f"Вентилятор: {fan:.1f}% | "
                      f"Градиент: {grad:.2f}°C/мин | "
                      f"Интервал: {MIN_UPDATE_INTERVAL} сек")
            self.dpg.set_value(f"{self.window_tag}_status", status)

            # Автомасштабирование оси X (последние 30 минут)
            if len(self.time_data) > 10:
                # Показываем последние 30 минут данных (1800 секунд)
                time_span = min(1800, max(60, t))
                self.dpg.set_axis_limits(f"{self.window_tag}_x_axis", max(0, t - time_span), t + 60)
            elif len(self.time_data) > 1:
                self.dpg.fit_axis_data(f"{self.window_tag}_x_axis")

            # Обновление информационной панели
            self.update_info_display()

            # Обновление времени последнего добавления
            self.last_data_update_time = time.time()

        except Exception as e:
            print(f"Ошибка добавления точки на график: {e}")

    def create_window(self):
        """Создание окна мониторинга"""
        if self.dpg.does_item_exist(self.window_tag):
            return self.window_tag

        # Размеры и позиция окна
        window_width = 1020
        window_height = 500
        pos_x = 860
        pos_y = 705

        # Создаем окно
        with self.dpg.window(
                label="Мониторинг температуры и скорости",
                tag=self.window_tag,
                width=window_width,
                height=window_height,
                pos=[pos_x, pos_y],
        ):
            # График
            with self.dpg.plot(label="", height=360, width=-1, tag=f"{self.window_tag}_plot"):
                self.dpg.add_plot_legend()
                self.dpg.add_plot_axis(self.dpg.mvXAxis, label="Время, с", tag=f"{self.window_tag}_x_axis")
                with self.dpg.plot_axis(self.dpg.mvYAxis, label="Значения", tag=f"{self.window_tag}_y_axis"):
                    self.dpg.add_line_series([], [], label="Температура, °C", tag=f"{self.window_tag}_temp_series")
                    self.dpg.add_line_series([], [], label="Скорость вент., %", tag=f"{self.window_tag}_fan_series")
                    self.dpg.add_line_series([], [], label="Градиент, °C/мин", tag=f"{self.window_tag}_gradient_series")

            # Панель управления (без чекбоксов)
            with self.dpg.group(horizontal=True):
                self.dpg.add_spacer(width=5)
                self.dpg.add_button(label="Очистить", callback=self.clear_data, width=80)
                self.dpg.add_button(label="Пауза", tag=f"{self.window_tag}_pause_btn",
                                    callback=self.toggle_pause, width=80)
                self.dpg.add_button(label="Экспорт", callback=self.export_data, width=80)
                self.dpg.add_spacer(width=5)

            # Статусная строка
            self.dpg.add_text("", tag=f"{self.window_tag}_status")

            # Информация о данных
            with self.dpg.group(horizontal=True):
                self.dpg.add_text("Обновление: ", tag=f"{self.window_tag}_update_info")
                self.dpg.add_text("Точек на графике: 0", tag=f"{self.window_tag}_points_info")
                self.dpg.add_text(f" | Интервал: {MIN_UPDATE_INTERVAL} сек",
                                  tag=f"{self.window_tag}_interval_info")

            # Кнопка для ручного добавления точки
            self.dpg.add_button(label="Добавить точку сейчас",
                                callback=lambda: self.add_data_point(),
                                width=150)

        # Настройка цветов линий
        self.set_line_colors()

        return self.window_tag

    def set_line_colors(self):
        """Настройка цветов линий на графике"""
        temp_color = self.create_series_theme(255, 100, 100)  # Красный для температуры
        fan_color = self.create_series_theme(100, 200, 100)  # Зеленый для скорости
        grad_color = self.create_series_theme(100, 100, 255)  # Синий для градиента

        self.dpg.bind_item_theme(f"{self.window_tag}_temp_series", temp_color)
        self.dpg.bind_item_theme(f"{self.window_tag}_fan_series", fan_color)
        self.dpg.bind_item_theme(f"{self.window_tag}_gradient_series", grad_color)

    def create_series_theme(self, r, g, b):
        """Создание темы для серии данных"""
        with self.dpg.theme() as series_theme:
            with self.dpg.theme_component(self.dpg.mvLineSeries):
                self.dpg.add_theme_color(self.dpg.mvPlotCol_Line, (r, g, b), category=self.dpg.mvThemeCat_Plots)
        return series_theme

    def toggle_pause(self):
        """Пауза/продолжение обновления данных"""
        self.paused = not self.paused
        btn_text = "Продолжить" if self.paused else "Пауза"
        self.dpg.set_value(f"{self.window_tag}_pause_btn", btn_text)

        # Если снимаем паузу, сбрасываем таймер, чтобы сразу добавить точку
        if not self.paused:
            self.last_data_update_time = 0

    def clear_data(self):
        """Очистка всех данных"""
        self.time_data.clear()
        self.temp_data.clear()
        self.fan_data.clear()
        self.gradient_data.clear()
        self.start_time = time.time()
        # Сбрасываем таймер при очистке
        self.last_data_update_time = time.time()

        self.dpg.set_value(f"{self.window_tag}_temp_series", [[], []])
        self.dpg.set_value(f"{self.window_tag}_fan_series", [[], []])
        self.dpg.set_value(f"{self.window_tag}_gradient_series", [[], []])

        self.update_info_display()

    def export_data(self):
        """Экспорт данных в файл"""
        try:
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            filename = f"monitor_data_{timestamp}.csv"

            with open(filename, 'w', encoding='utf-8') as f:
                f.write("Время (с);Температура (°C);Скорость (%);Градиент (°C/мин);Интервал (сек)\n")
                for i in range(len(self.time_data)):
                    t = self.time_data[i] if i < len(self.time_data) else 0
                    temp = self.temp_data[i] if i < len(self.temp_data) else 0
                    fan = self.fan_data[i] if i < len(self.fan_data) else 0
                    grad = self.gradient_data[i] if i < len(self.gradient_data) else 0
                    interval = MIN_UPDATE_INTERVAL
                    f.write(f"{t:.1f};{temp:.2f};{fan:.1f};{grad:.2f};{interval}\n")

            print(f"Данные экспортированы в {filename}")
        except Exception as e:
            print(f"Ошибка экспорта данных: {e}")

    def update_info_display(self):
        """Обновление информационной панели"""
        points_count = len(self.time_data)
        update_time = time.strftime("%H:%M:%S")

        self.dpg.set_value(f"{self.window_tag}_update_info", f"Обновление: {update_time}")
        self.dpg.set_value(f"{self.window_tag}_points_info", f"Точек на графике: {points_count}")

        # Вычисляем время до следующей точки
        if points_count > 0:
            next_update = max(0, MIN_UPDATE_INTERVAL - (time.time() - self.last_data_update_time))
            self.dpg.set_value(f"{self.window_tag}_interval_info",
                               f" | Интервал: {MIN_UPDATE_INTERVAL} сек | Следующая точка через: {next_update:.0f} сек")
        else:
            self.dpg.set_value(f"{self.window_tag}_interval_info",
                               f" | Интервал: {MIN_UPDATE_INTERVAL} сек")

    def set_paused(self, paused: bool):
        """
        Установить состояние паузы обновления графика.
        """
        self.paused = paused
        # Если окно открыто, обновляем текст кнопки паузы
        if self.dpg.does_item_exist(f"{self.window_tag}_pause_btn"):
            self.dpg.set_value(f"{self.window_tag}_pause_btn", "Продолжить" if paused else "Пауза")

    def update(self):
        """Метод для вызова из главного цикла приложения"""
        if not self.is_visible or not self.dpg.does_item_exist(self.window_tag):
            return

        # Проверяем, нужно ли добавлять новую точку
        if self.should_add_data_point():
            self.add_data_point()

        # Обновляем информационную панель даже если не добавляем точку
        self.update_info_display()

    def show(self):
        """Показать окно"""
        if not self.dpg.does_item_exist(self.window_tag):
            self.create_window()

        self.dpg.show_item(self.window_tag)
        self.is_visible = True

        # Сбрасываем таймер при показе окна, чтобы сразу добавить точку
        self.last_data_update_time = 0

    def hide(self):
        """Скрыть окно"""
        if self.dpg.does_item_exist(self.window_tag):
            self.dpg.hide_item(self.window_tag)
            self.is_visible = False

    def toggle_visibility(self):
        """Переключить видимость окна"""
        if not self.dpg.does_item_exist(self.window_tag):
            self.create_window()

        if self.is_visible:
            self.hide()
        else:
            self.show()

    def is_open(self):
        """Проверка, открыто ли окно"""
        return self.is_visible and self.dpg.does_item_exist(self.window_tag)
import os
import sys
import time
import dearpygui.dearpygui as dpg
from typing import Optional

from Chamber.temperature_program import TemperatureProgram
from Chamber.chamber_process import ChamberProcess
from Ports_COM.Devices_Data import DEVICES_DATA


class TemperatureProgramGUI:
    """Графический интерфейс для работы с многоступенчатой программой."""

    def __init__(self, chamber_process: Optional[ChamberProcess] = None):
        self.step_temp = None
        self.rate = None
        self.hold_time = None
        self.end_temp = None
        self.start_temp = None
        self.step_label = None
        self.status_label = None
        self.stop_btn = None
        self.start_btn = None
        self.program = TemperatureProgram()
        self.chamber_process = chamber_process
        self.tag = "program"
        self.window_tag = f"{self.tag}_window"
        self.table_tag = f"{self.tag}_table"
        self.status_text_tag = f"{self.tag}_status"
        self.step_counter_tag = f"{self.tag}_step_counter"
        self.is_running = False

        self._create_themes()

    def _create_themes(self):
        """Создание тем для элементов (аналогично algorithm_settings)."""
        # Тема окна
        if not dpg.does_item_exist(f"{self.tag}_window_theme"):
            with dpg.theme(tag=f"{self.tag}_window_theme"):
                with dpg.theme_component(dpg.mvAll):
                    dpg.add_theme_color(dpg.mvThemeCol_WindowBg, (70, 130, 180, 200))
                    dpg.add_theme_color(dpg.mvThemeCol_Text, (255, 255, 255, 255))
                    dpg.add_theme_color(dpg.mvThemeCol_TitleBg, (85, 110, 140, 255))
                    dpg.add_theme_color(dpg.mvThemeCol_TitleBgActive, (105, 135, 170, 255))
                    dpg.add_theme_color(dpg.mvThemeCol_Border, (150, 165, 185, 255))
                    dpg.add_theme_style(dpg.mvStyleVar_WindowBorderSize, 1.5)
                    dpg.add_theme_style(dpg.mvStyleVar_WindowRounding, 6)

        # Тема для input float (синий текст)
        if not dpg.does_item_exist(f"{self.tag}_input_float_theme"):
            with dpg.theme(tag=f"{self.tag}_input_float_theme"):
                with dpg.theme_component(dpg.mvInputFloat):
                    dpg.add_theme_color(dpg.mvThemeCol_Text, (255, 255, 255, 255))

        # Тема для синих кнопок
        if not dpg.does_item_exist(f"{self.tag}_button_theme"):
            with dpg.theme(tag=f"{self.tag}_button_theme"):
                with dpg.theme_component(dpg.mvButton):
                    dpg.add_theme_color(dpg.mvThemeCol_Button, (65, 95, 135, 255))
                    dpg.add_theme_color(dpg.mvThemeCol_ButtonHovered, (85, 115, 160, 255))
                    dpg.add_theme_color(dpg.mvThemeCol_ButtonActive, (55, 80, 115, 255))
                    dpg.add_theme_color(dpg.mvThemeCol_Text, (255, 255, 255, 255))
                    dpg.add_theme_style(dpg.mvStyleVar_FrameRounding, 4)

        # Тема для серых кнопок
        if not dpg.does_item_exist(f"{self.tag}_button_gray_theme"):
            with dpg.theme(tag=f"{self.tag}_button_gray_theme"):
                with dpg.theme_component(dpg.mvButton):
                    dpg.add_theme_color(dpg.mvThemeCol_Button, (140, 155, 175, 255))
                    dpg.add_theme_color(dpg.mvThemeCol_ButtonHovered, (165, 180, 195, 255))
                    dpg.add_theme_color(dpg.mvThemeCol_ButtonActive, (120, 135, 155, 255))
                    dpg.add_theme_color(dpg.mvThemeCol_Text, (255, 255, 255, 255))
                    dpg.add_theme_style(dpg.mvStyleVar_FrameRounding, 4)

        # Тема для таблицы
        if not dpg.does_item_exist(f"{self.tag}_table_theme"):
            with dpg.theme(tag=f"{self.tag}_table_theme"):
                with dpg.theme_component(dpg.mvTable):
                    dpg.add_theme_color(dpg.mvThemeCol_TableHeaderBg, (60, 60, 60, 255))
                    dpg.add_theme_color(dpg.mvThemeCol_TableBorderStrong, (80, 80, 80, 255))
                    dpg.add_theme_color(dpg.mvThemeCol_TableBorderLight, (60, 60, 60, 255))
                    dpg.add_theme_style(dpg.mvStyleVar_CellPadding, 4, 3)

        # Темы для строк таблицы
        if not dpg.does_item_exist(f"{self.tag}_row_theme"):
            with dpg.theme(tag=f"{self.tag}_row_theme"):
                with dpg.theme_component(dpg.mvTableRow):
                    dpg.add_theme_color(dpg.mvThemeCol_TableRowBg, (35, 35, 35, 255))
        if not dpg.does_item_exist(f"{self.tag}_row_alt_theme"):
            with dpg.theme(tag=f"{self.tag}_row_alt_theme"):
                with dpg.theme_component(dpg.mvTableRow):
                    dpg.add_theme_color(dpg.mvThemeCol_TableRowBg, (30, 30, 30, 255))
        if not dpg.does_item_exist(f"{self.tag}_row_current_theme"):
            with dpg.theme(tag=f"{self.tag}_row_current_theme"):
                with dpg.theme_component(dpg.mvTableRow):
                    dpg.add_theme_color(dpg.mvThemeCol_TableRowBg, (30, 60, 90, 150))

    def create_window(self):
        """Создание основного окна программы."""
        if dpg.does_item_exist(self.window_tag):
            dpg.delete_item(self.window_tag)

        width, height = 850, 660
        pos_x = 0
        pos_y = 490

        with dpg.window(
            tag=self.window_tag,
            label="Температурная программа",
            width=width,
            height=height,
            pos=[pos_x, pos_y],
            no_resize=True,
            no_collapse=True
        ) as win:
            dpg.bind_item_theme(win, f"{self.tag}_window_theme")

            # Верхняя панель с кнопками запуска/остановки
            with dpg.group(horizontal=True):
                self.start_btn = dpg.add_button(label="Запустить", width=120, height=30, callback=self._start_program)
                dpg.bind_item_theme(self.start_btn, f"{self.tag}_button_theme")
                self.stop_btn = dpg.add_button(label="Остановить", width=120, height=30, callback=self._stop_program)
                dpg.bind_item_theme(self.stop_btn, f"{self.tag}_button_gray_theme")
                dpg.add_spacer(width=20)
                self.status_label = dpg.add_text("Статус: Готов", tag=self.status_text_tag)
                dpg.add_spacer(width=10)
                self.step_label = dpg.add_text("Ступеней: 0", tag=self.step_counter_tag)

            dpg.add_spacer(height=10)

            # Панель быстрого создания
            with dpg.child_window(height=120, border=True):
                dpg.add_text("Быстрое создание программы")
                with dpg.table(header_row=False, borders_innerV=True, policy=dpg.mvTable_SizingStretchSame):
                    dpg.add_table_column()
                    dpg.add_table_column()
                    dpg.add_table_column()
                    dpg.add_table_column()

                    with dpg.table_row():
                        self.start_temp = dpg.add_input_float(label="Начальная, °C", default_value=20.0, step=0.1, width=120, format="%.1f")
                        dpg.bind_item_theme(self.start_temp, f"{self.tag}_input_float_theme")
                        self.end_temp = dpg.add_input_float(label="Конечная, °C", default_value=100.0, step=0.1, width=120, format="%.1f")
                        dpg.bind_item_theme(self.end_temp, f"{self.tag}_input_float_theme")
                        self.step_temp = dpg.add_input_float(label="Шаг, °C", default_value=10.0, step=0.1, width=120, format="%.1f")
                        dpg.bind_item_theme(self.step_temp, f"{self.tag}_input_float_theme")
                        self.rate = dpg.add_input_float(label="Скорость, °C/мин", default_value=5.0, step=0.1, width=130, format="%.1f")
                        dpg.bind_item_theme(self.rate, f"{self.tag}_input_float_theme")

                    with dpg.table_row():
                        self.hold_time = dpg.add_input_float(label="Выдержка, мин", default_value=10.0, step=0.1, width=120, format="%.1f")
                        dpg.bind_item_theme(self.hold_time, f"{self.tag}_input_float_theme")
                        dpg.add_spacer(width=120)
                        dpg.add_spacer(width=120)
                        generate_btn = dpg.add_button(label="Сгенерировать", width=130, callback=self._generate_table)
                        dpg.bind_item_theme(generate_btn, f"{self.tag}_button_theme")

            dpg.add_spacer(height=10)

            # Панель управления таблицей
            with dpg.group(horizontal=True):
                add_btn = dpg.add_button(label="+ Добавить ступень", width=140, callback=self._add_row)
                dpg.bind_item_theme(add_btn, f"{self.tag}_button_theme")
                # Кнопка удаления последней ступени
                delete_last_btn = dpg.add_button(label="Удалить последнюю", width=140, callback=self._delete_last_step)
                dpg.bind_item_theme(delete_last_btn, f"{self.tag}_button_gray_theme")
                dpg.add_spacer(width=20)
                save_btn = dpg.add_button(label="Сохранить", width=100, callback=self._save_program)
                dpg.bind_item_theme(save_btn, f"{self.tag}_button_theme")
                load_btn = dpg.add_button(label="Загрузить", width=100, callback=self._load_program)
                dpg.bind_item_theme(load_btn, f"{self.tag}_button_theme")
                clear_btn = dpg.add_button(label="Очистить", width=80, callback=self._clear_table)
                dpg.bind_item_theme(clear_btn, f"{self.tag}_button_gray_theme")

            dpg.add_spacer(height=10)

            # Таблица
            with dpg.child_window(height=300, border=True):
                self.table_id = dpg.add_table(
                    tag=self.table_tag,
                    header_row=True,
                    borders_innerH=True,
                    borders_outerH=True,
                    borders_innerV=True,
                    borders_outerV=True,
                    resizable=True,
                    policy=dpg.mvTable_SizingFixedFit
                )
                dpg.bind_item_theme(self.table_id, f"{self.tag}_table_theme")

                # Колонки: №, Температура, Скорость, Выдержка
                dpg.add_table_column(parent=self.table_id, label="№", width_fixed=True, width=50)
                dpg.add_table_column(parent=self.table_id, label="Температура, °C", width_stretch=True,
                                     init_width_or_weight=150)
                dpg.add_table_column(parent=self.table_id, label="Скорость, °C/мин", width_stretch=True,
                                     init_width_or_weight=120)
                dpg.add_table_column(parent=self.table_id, label="Выдержка, мин", width_stretch=True,
                                     init_width_or_weight=120)

        self._refresh_table()
        # Запуск цикла обновления подсветки текущей ступени
        dpg.set_frame_callback(dpg.get_frame_count() + 10, self._update_ui_callback)

    def _delete_last_step(self):
        """Удалить последнюю ступень из программы."""
        if len(self.program.steps) > 0:
            self.program.remove_step(len(self.program.steps) - 1)
            self._refresh_table()
            dpg.set_value(self.status_text_tag, "Последняя ступень удалена")
        else:
            dpg.set_value(self.status_text_tag, "Нет ступеней для удаления")

    def _sync_steps_from_ui(self):
        for i in range(len(self.program.steps)):
            temp_tag = f"{self.tag}_temp_{i}"
            rate_tag = f"{self.tag}_rate_{i}"
            hold_tag = f"{self.tag}_hold_{i}"
            if dpg.does_item_exist(temp_tag):
                self.program.steps[i]['temperature'] = round(dpg.get_value(temp_tag), 1)
            if dpg.does_item_exist(rate_tag):
                self.program.steps[i]['rate'] = round(dpg.get_value(rate_tag), 1)
            if dpg.does_item_exist(hold_tag):
                self.program.steps[i]['hold_time'] = round(dpg.get_value(hold_tag), 1)

    def _add_table_row_1(self, index: int, temperature: float, rate: float, hold_time: float):
        row_tag = f"{self.tag}_row_{index}"
        with dpg.table_row(parent=self.table_tag, tag=row_tag):
            dpg.add_text(str(index + 1))
            # Температура
            temp_input = dpg.add_input_float(default_value=temperature, step=0.1, width=100, format="%.1f",
                                             tag=f"{self.tag}_temp_{index}")
            dpg.bind_item_theme(temp_input, f"{self.tag}_input_float_theme")
            dpg.set_item_callback(temp_input, lambda s, a, idx=index: self._update_step(idx, 'temperature', a))
            # Скорость
            rate_input = dpg.add_input_float(default_value=rate, step=0.1, width=100, format="%.1f",
                                             tag=f"{self.tag}_rate_{index}")
            dpg.bind_item_theme(rate_input, f"{self.tag}_input_float_theme")
            dpg.set_item_callback(rate_input, lambda s, a, idx=index: self._update_step(idx, 'rate', a))
            # Выдержка
            hold_input = dpg.add_input_float(default_value=hold_time, step=0.1, width=100, format="%.1f",
                                             tag=f"{self.tag}_hold_{index}")
            dpg.bind_item_theme(hold_input, f"{self.tag}_input_float_theme")
            dpg.set_item_callback(hold_input, lambda s, a, idx=index: self._update_step(idx, 'hold_time', a))
        self._apply_row_theme(index)

    def _add_table_row(self, index: int, temperature: float, rate: float, hold_time: float):
        row_tag = f"{self.tag}_row_{index}"
        with dpg.table_row(parent=self.table_tag, tag=row_tag):
            dpg.add_text(str(index + 1))
            # Температура
            temp_input = dpg.add_input_float(default_value=temperature, step=0.1, width=100, format="%.1f",
                                             tag=f"{self.tag}_temp_{index}")
            dpg.bind_item_theme(temp_input, f"{self.tag}_input_float_theme")
            dpg.set_item_user_data(temp_input, (index, 'temperature'))
            dpg.set_item_callback(temp_input, self._update_step_callback)
            # Скорость
            rate_input = dpg.add_input_float(default_value=rate, step=0.1, width=100, format="%.1f",
                                             tag=f"{self.tag}_rate_{index}")
            dpg.bind_item_theme(rate_input, f"{self.tag}_input_float_theme")
            dpg.set_item_user_data(rate_input, (index, 'rate'))
            dpg.set_item_callback(rate_input, self._update_step_callback)
            # Выдержка
            hold_input = dpg.add_input_float(default_value=hold_time, step=0.1, width=100, format="%.1f",
                                             tag=f"{self.tag}_hold_{index}")
            dpg.bind_item_theme(hold_input, f"{self.tag}_input_float_theme")
            dpg.set_item_user_data(hold_input, (index, 'hold_time'))
            dpg.set_item_callback(hold_input, self._update_step_callback)
        self._apply_row_theme(index)

    def _update_step_callback(self, sender, app_data):
        """Обработчик изменений полей ввода, извлекает user_data из отправителя."""
        user_data = dpg.get_item_user_data(sender)
        if user_data is None:
            return
        index, field = user_data
        if app_data is None:
            return
        self._update_step(index, field, app_data)

    def _refresh_table(self):
        """Обновить отображение таблицы в соответствии с self.program.steps."""
        if dpg.does_item_exist(self.table_tag):
            # Удаляем все строки, оставляя колонки
            children = dpg.get_item_children(self.table_tag, slot=1)
            if children:
                for child in children:
                    dpg.delete_item(child)

        for i, step in enumerate(self.program.get_all_steps()):
            self._add_table_row(i, step['temperature'], step['rate'], step['hold_time'])

        dpg.set_value(self.step_counter_tag, f"Ступеней: {len(self.program.steps)}")

    def _apply_row_theme(self, index: int):
        """Применить тему к строке в зависимости от текущей выбранной."""
        row_tag = f"{self.tag}_row_{index}"
        if not dpg.does_item_exist(row_tag):
            return
        if index == self.program.current_index:
            dpg.bind_item_theme(row_tag, f"{self.tag}_row_current_theme")
        else:
            theme = f"{self.tag}_row_theme" if index % 2 == 0 else f"{self.tag}_row_alt_theme"
            dpg.bind_item_theme(row_tag, theme)

    def _update_step_1(self, index: int, field: str, value: float):
        """Обновить значение ступени в программе."""
        if 0 <= index < len(self.program.steps):
            self.program.steps[index][field] = round(value, 1)

    def _update_step(self, index: int, field: str, value):
        """Обновить значение ступени в программе с проверками."""
        # Проверка, что steps существует и является списком
        if not hasattr(self.program, 'steps') or not isinstance(self.program.steps, list):
            return
        # Проверка, что index целое число и в допустимом диапазоне
        if not isinstance(index, int) or index < 0 or index >= len(self.program.steps):
            return
        # Преобразование value в число, если возможно
        try:
            num_value = float(value)
        except (TypeError, ValueError):
            return
        # Обновление значения
        self.program.steps[index][field] = round(num_value, 1)

    def _select_row(self, index: int):
        """Выбрать строку как текущую."""
        self.program.set_current(index)
        for i in range(len(self.program.steps)):
            self._apply_row_theme(i)

    def _delete_row(self, index: int):
        """Удалить строку по индексу."""
        if self.program.remove_step(index):
            self._refresh_table()

    def _delete_current_row(self):
        """Удалить текущую выбранную строку."""
        if self.program.current_index is not None:
            self._delete_row(self.program.current_index)

    def _add_row(self):
        if self.program.steps:
            last = self.program.steps[-1]
            temp, rate, hold = last['temperature'], last['rate'], last['hold_time']
        else:
            # Если ступеней нет, берём значения из полей быстрого создания
            temp = dpg.get_value(self.start_temp)
            rate = dpg.get_value(self.rate)
            hold = dpg.get_value(self.hold_time)
        self.program.add_step(temp, rate, hold)
        self._refresh_table()

    def _generate_table(self):
        """Сгенерировать ступени по диапазону."""
        start = dpg.get_value(self.start_temp)
        end = dpg.get_value(self.end_temp)
        step = dpg.get_value(self.step_temp)
        rate = dpg.get_value(self.rate)
        hold = dpg.get_value(self.hold_time)

        if step == 0:
            dpg.set_value(self.status_text_tag, "Ошибка: шаг не может быть 0")
            return

        self.program.clear()
        if start <= end:
            t = start
            while t <= end + 0.0001:
                self.program.add_step(t, rate, hold)
                t += step
        else:
            t = start
            while t >= end - 0.0001:
                self.program.add_step(t, rate, hold)
                t -= step

        self._refresh_table()
        dpg.set_value(self.status_text_tag, f"Сгенерировано {len(self.program.steps)} ступеней")

    def _clear_table(self):
        """Очистить программу."""
        self.program.clear()
        self._refresh_table()
        dpg.set_value(self.status_text_tag, "Программа очищена")

    def _save_program(self):
        """Вызвать диалог сохранения файла."""
        '''
        setups_dir = os.path.join(os.path.dirname(__file__), "..", "setups")
        os.makedirs(setups_dir, exist_ok=True)
        '''
        setups_dir = self._get_setups_dir()
        os.makedirs(setups_dir, exist_ok=True)

        dialog_tag = f"{self.tag}_save_dialog"
        # Удаляем старый диалог, если он существует
        if dpg.does_item_exist(dialog_tag):
            dpg.delete_item(dialog_tag)

        with dpg.file_dialog(
                directory_selector=False,
                show=False,
                callback=self._save_file_callback,
                tag=dialog_tag,
                width=650,
                height=400,
                default_path=setups_dir,
                default_filename="program.json"
        ):
            dpg.add_file_extension(".json", color=(0, 255, 0, 255))
        dpg.show_item(dialog_tag)

    def _save_file_callback(self, sender, app_data):
        self._sync_steps_from_ui()
        if 'file_path_name' in app_data:
            path = app_data['file_path_name']
        elif 'selections' in app_data:
            path = list(app_data['selections'].values())[0]
        else:
            return
        self.program.save(path)
        dpg.set_value(self.status_text_tag, f"Сохранено в {os.path.basename(path)}")

    def _load_program(self):
        """Вызвать диалог загрузки файла."""
        '''
        setups_dir = os.path.join(os.path.dirname(__file__), "..", "setups")
        d
        '''
        setups_dir = self._get_setups_dir()
        os.makedirs(setups_dir, exist_ok=True)
        dialog_tag = f"{self.tag}_load_dialog"
        if dpg.does_item_exist(dialog_tag):
            dpg.delete_item(dialog_tag)

        with dpg.file_dialog(
                directory_selector=False,
                show=False,
                callback=self._load_file_callback,
                tag=dialog_tag,
                width=650,
                height=400,
                default_path=setups_dir
        ):
            dpg.add_file_extension(".json", color=(0, 255, 0, 255))
        dpg.show_item(dialog_tag)

    def _load_file_callback(self, sender, app_data):
        if 'file_path_name' in app_data:
            path = app_data['file_path_name']
        elif 'selections' in app_data:
            path = list(app_data['selections'].values())[0]
        else:
            return
        self.program.load(path)
        self._refresh_table()
        dpg.set_value(self.status_text_tag, f"Загружено {os.path.basename(path)}")

    def _start_program(self):
        """Запустить выполнение программы."""
        self._sync_steps_from_ui()
        if not self.chamber_process:
            dpg.set_value(self.status_text_tag, "Ошибка: процесс камеры не инициализирован")
            return
        if len(self.program.steps) == 0:
            dpg.set_value(self.status_text_tag, "Нет ступеней для выполнения")
            return
        if self.chamber_process.is_running():
            dpg.set_value(self.status_text_tag, "Процесс уже запущен")
            return

        # Сброс времени двигателя
        motor_gui = DEVICES_DATA.get_blsd_gui()
        if motor_gui:
            motor_gui.start_time = time.time()
            motor_gui.unfreeze_time()

        # Запуск процесса
        self.chamber_process.start_program(self.program)
        self.is_running = True
        dpg.set_value(self.status_text_tag, "Программа запущена")
        self._set_editable(False)

    def _stop_program(self):
        """Остановить выполнение программы."""
        if not self.chamber_process:
            return
        if self.chamber_process.is_running():
            self.chamber_process.stop_process()
            self.is_running = False
            dpg.set_value(self.status_text_tag, "Программа остановлена")
            self._set_editable(True)
            motor_gui = DEVICES_DATA.get_blsd_gui()
            if motor_gui:
                motor_gui.freeze_time()

    def _set_editable(self, editable: bool):
        """Включить/выключить редактирование таблицы и кнопок."""
        # Простейшая реализация: отключаем все поля ввода и кнопки добавления/удаления/генерации
        # Можно реализовать, проходя по всем дочерним элементам, но для простоты оставим заглушку
        pass

    def _update_ui_callback(self):
        """Периодическое обновление интерфейса (подсветка текущей ступени)."""
        if not dpg.does_item_exist(self.window_tag):
            return
        if self.chamber_process and self.chamber_process.is_running():
            current = self.chamber_process.current_step_index
            if current != self.program.current_index:
                self.program.set_current(current)
                for i in range(len(self.program.steps)):
                    self._apply_row_theme(i)
        # Перезапустить callback
        dpg.set_frame_callback(dpg.get_frame_count() + 30, self._update_ui_callback)

    def close_window(self):
        if dpg.does_item_exist(self.window_tag):
            dpg.delete_item(self.window_tag)

    def _get_setups_dir(self):
        if getattr(sys, 'frozen', False):
            base = os.path.dirname(sys.executable)
        else:
            # В режиме разработки поднимаемся на уровень выше, чтобы папка setups была рядом с исходниками
            base = os.path.dirname(os.path.dirname(__file__))
        return os.path.join(base, "setups")


def show_temperature_program(dpg):
    """Функция для вызова из главного меню."""
    from Ports_COM.Devices_Data import DEVICES_DATA
    owen_gui = DEVICES_DATA.get_owen_gui()
    chamber_process = owen_gui.chamber_process if owen_gui else None
    gui = TemperatureProgramGUI(chamber_process)
    gui.create_window()


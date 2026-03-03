import json
import os
import sys
import time
import dearpygui.dearpygui as dpg

def show_pid_viewer_dialog(dpg_instance, tag_prefix, chamber_process):
    modal_tag = f"{tag_prefix}_pid_viewer_modal"
    if dpg_instance.does_item_exist(modal_tag):
        dpg_instance.delete_item(modal_tag)

    # Увеличена ширина окна для размещения более широких полей
    window_width, window_height = 1100, 650
    vp_w = dpg_instance.get_viewport_width()
    vp_h = dpg_instance.get_viewport_height()
    pos_x = (vp_w - window_width) // 2
    pos_y = (vp_h - window_height) // 2

    # Переменные для хранения состояния
    current_file = None
    current_data = None
    mode = "Ручной режим"

    # Создаём темы (аналогично algorithm_settings_dialog)
    def create_themes():
        if not dpg_instance.does_item_exist(f"{tag_prefix}_pid_viewer_theme"):
            with dpg_instance.theme(tag=f"{tag_prefix}_pid_viewer_theme"):
                with dpg_instance.theme_component(dpg_instance.mvAll):
                    dpg_instance.add_theme_color(dpg_instance.mvThemeCol_WindowBg, (70, 130, 180, 200))
                    dpg_instance.add_theme_color(dpg_instance.mvThemeCol_Text, (255, 255, 255, 255))
                    dpg_instance.add_theme_color(dpg_instance.mvThemeCol_TitleBg, (85, 110, 140, 255))
                    dpg_instance.add_theme_color(dpg_instance.mvThemeCol_TitleBgActive, (105, 135, 170, 255))
                    dpg_instance.add_theme_color(dpg_instance.mvThemeCol_Border, (150, 165, 185, 255))
                    dpg_instance.add_theme_color(dpg_instance.mvThemeCol_FrameBg, (255, 255, 255, 255))
                    dpg_instance.add_theme_color(dpg_instance.mvThemeCol_FrameBgHovered, (235, 242, 250, 255))
                    dpg_instance.add_theme_color(dpg_instance.mvThemeCol_FrameBgActive, (215, 227, 242, 255))
                    dpg_instance.add_theme_color(dpg_instance.mvThemeCol_Button, (85, 110, 140, 255))
                    dpg_instance.add_theme_color(dpg_instance.mvThemeCol_ButtonHovered, (105, 135, 170, 255))
                    dpg_instance.add_theme_color(dpg_instance.mvThemeCol_ButtonActive, (70, 95, 125, 255))
                    dpg_instance.add_theme_style(dpg_instance.mvStyleVar_WindowBorderSize, 1.5)
                    dpg_instance.add_theme_style(dpg_instance.mvStyleVar_WindowRounding, 6)
                    dpg_instance.add_theme_style(dpg_instance.mvStyleVar_FrameBorderSize, 1)
                    dpg_instance.add_theme_style(dpg_instance.mvStyleVar_FrameRounding, 4)
                    dpg_instance.add_theme_style(dpg_instance.mvStyleVar_FramePadding, 10, 6)
        '''
        if not dpg_instance.does_item_exist(f"{tag_prefix}_pid_input_float_theme"):
            with dpg_instance.theme(tag=f"{tag_prefix}_pid_input_float_theme"):
                with dpg_instance.theme_component(dpg_instance.mvInputFloat):
                    dpg_instance.add_theme_color(dpg_instance.mvThemeCol_Text, (0, 0, 255, 255))

        if not dpg_instance.does_item_exist(f"{tag_prefix}_pid_input_int_theme"):
            with dpg_instance.theme(tag=f"{tag_prefix}_pid_input_int_theme"):
                with dpg_instance.theme_component(dpg_instance.mvInputInt):
                    dpg_instance.add_theme_color(dpg_instance.mvThemeCol_Text, (0, 0, 255, 255))
        '''
        if not dpg_instance.does_item_exist(f"{tag_prefix}_pid_input_float_theme"):
            with dpg_instance.theme(tag=f"{tag_prefix}_pid_input_float_theme"):
                with dpg_instance.theme_component(dpg_instance.mvInputFloat):
                    dpg_instance.add_theme_color(dpg_instance.mvThemeCol_Text, (0, 0, 255, 255))
                    # Уменьшаем горизонтальный отступ внутри поля ввода
                    dpg_instance.add_theme_style(dpg_instance.mvStyleVar_FramePadding, 2, 4)  # (left/right, top/bottom)

        if not dpg_instance.does_item_exist(f"{tag_prefix}_pid_input_int_theme"):
            with dpg_instance.theme(tag=f"{tag_prefix}_pid_input_int_theme"):
                with dpg_instance.theme_component(dpg_instance.mvInputInt):
                    dpg_instance.add_theme_color(dpg_instance.mvThemeCol_Text, (0, 0, 255, 255))
                    dpg_instance.add_theme_style(dpg_instance.mvStyleVar_FramePadding, 2, 4)

    create_themes()

    with dpg_instance.window(
        label="Просмотр и редактирование PID",
        modal=False,
        tag=modal_tag,
        width=window_width,
        height=window_height,
        pos=[pos_x, pos_y],
        no_resize=True,
        no_collapse=True
    ) as win:
        dpg_instance.bind_item_theme(win, f"{tag_prefix}_pid_viewer_theme")

        # Радиокнопки
        def on_mode_change(sender, app_data):
            nonlocal mode, current_file, current_data
            mode = dpg_instance.get_value(sender)
            if mode == "Ручной режим":
                load_temp_pid()
            else:
                open_file_dialog()

        dpg_instance.add_radio_button(
            items=["Ручной режим", "Программа"],
            default_value="Ручной режим",
            callback=on_mode_change,
            horizontal=True
        )
        dpg_instance.add_spacer(height=5)

        # Информация о файле
        file_info = dpg_instance.add_text("Файл: не выбран", tag=f"{modal_tag}_file_info")
        dpg_instance.add_spacer(height=5)

        # Таблица (будет пересоздаваться при загрузке)
        table_container = dpg_instance.add_child_window(height=400, border=True)
        table_tag = f"{modal_tag}_table"

        dpg_instance.add_spacer(height=5)

        # Кнопки управления
        with dpg_instance.group(horizontal=True):
            add_btn = dpg_instance.add_button(label="Добавить", width=100, callback=lambda: add_row())
            dpg_instance.bind_item_theme(add_btn, f"{tag_prefix}_pid_viewer_theme")
            save_btn = dpg_instance.add_button(label="Сохранить", width=100, callback=lambda: save_data())
            dpg_instance.bind_item_theme(save_btn, f"{tag_prefix}_pid_viewer_theme")
            close_btn = dpg_instance.add_button(label="Закрыть", width=100, callback=lambda: dpg_instance.delete_item(modal_tag))
            dpg_instance.bind_item_theme(close_btn, f"{tag_prefix}_pid_viewer_theme")

        # Вспомогательные функции
        def clear_table():
            if dpg_instance.does_item_exist(table_container):
                children = dpg_instance.get_item_children(table_container, slot=1)
                if children:
                    for child in children:
                        dpg_instance.delete_item(child)
            # Создаём новую таблицу с заданной шириной колонок
            with dpg_instance.table(
                parent=table_container,
                tag=table_tag,
                header_row=True,
                borders_innerH=True,
                borders_outerH=True,
                borders_innerV=True,
                borders_outerV=True,
                resizable=True,
                policy=dpg_instance.mvTable_SizingStretchProp
            ):
                if mode == "Ручной режим":
                    dpg_instance.add_table_column(label="Температура (°C)", init_width_or_weight=120)
                    dpg_instance.add_table_column(label="P", init_width_or_weight=120)
                    dpg_instance.add_table_column(label="I", init_width_or_weight=120)
                    dpg_instance.add_table_column(label="D", init_width_or_weight=120)
                    dpg_instance.add_table_column(label="Уставка (°C)", init_width_or_weight=180)
                    dpg_instance.add_table_column(label="Скорость вент. (об/мин)", init_width_or_weight=180)
                else:
                    dpg_instance.add_table_column(label="№", init_width_or_weight=50)
                    dpg_instance.add_table_column(label="Температура (°C)", init_width_or_weight=120)
                    dpg_instance.add_table_column(label="Скорость (°C/мин)", init_width_or_weight=120)
                    dpg_instance.add_table_column(label="Выдержка (мин)", init_width_or_weight=120)
                    dpg_instance.add_table_column(label="P", init_width_or_weight=120)
                    dpg_instance.add_table_column(label="I", init_width_or_weight=120)
                    dpg_instance.add_table_column(label="D", init_width_or_weight=120)
                    dpg_instance.add_table_column(label="Уставка (°C)", init_width_or_weight=180)
                    dpg_instance.add_table_column(label="Скорость вент. (об/мин)", init_width_or_weight=180)
            dpg_instance.bind_item_theme(table_tag, f"{tag_prefix}_pid_table_theme")

        def load_temp_pid():
            nonlocal current_file, current_data, mode
            mode = "Ручной режим"
            filepath = chamber_process._temp_pid_file if chamber_process else "temp_pid.json"
            if not os.path.exists(filepath):
                dpg_instance.set_value(file_info, f"Файл {filepath} не найден, будет создан при сохранении")
                current_file = filepath
                current_data = {}
                clear_table()
                return
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                current_file = filepath
                current_data = data
                dpg_instance.set_value(file_info, f"Файл: {os.path.basename(filepath)}")
                clear_table()
                # Заполняем таблицу
                for temp_str, pid in data.items():
                    with dpg_instance.table_row(parent=table_tag):
                        dpg_instance.add_text(temp_str, tag=f"{modal_tag}_key_{temp_str}")
                        p = dpg_instance.add_input_float(default_value=pid.get('p', 0.0), step=0.1, width=100, format="%.2f",
                                                          tag=f"{modal_tag}_p_{temp_str}")
                        dpg_instance.bind_item_theme(p, f"{tag_prefix}_pid_input_float_theme")
                        i = dpg_instance.add_input_int(default_value=pid.get('i', 0), step=1, width=100,
                                                        tag=f"{modal_tag}_i_{temp_str}")
                        dpg_instance.bind_item_theme(i, f"{tag_prefix}_pid_input_int_theme")
                        d = dpg_instance.add_input_int(default_value=pid.get('d', 0), step=1, width=100,
                                                        tag=f"{modal_tag}_d_{temp_str}")
                        dpg_instance.bind_item_theme(d, f"{tag_prefix}_pid_input_int_theme")
                        sp = dpg_instance.add_input_float(default_value=pid.get('setpoint', 0.0), step=0.1, width=100, format="%.1f",
                                                           tag=f"{modal_tag}_sp_{temp_str}")
                        dpg_instance.bind_item_theme(sp, f"{tag_prefix}_pid_input_float_theme")
                        fs = dpg_instance.add_input_int(default_value=pid.get('fan_speed', 0), step=10, width=100,
                                                         tag=f"{modal_tag}_fs_{temp_str}")
                        dpg_instance.bind_item_theme(fs, f"{tag_prefix}_pid_input_int_theme")
            except Exception as e:
                dpg_instance.set_value(file_info, f"Ошибка загрузки: {e}")

        def load_program_file(path):
            nonlocal current_file, current_data, mode
            mode = "Программа"
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    steps = json.load(f)
                if not isinstance(steps, list):
                    raise ValueError("Неверный формат файла программы")
                current_file = path
                current_data = steps
                dpg_instance.set_value(file_info, f"Файл: {os.path.basename(path)}")
                clear_table()
                for i, step in enumerate(steps):
                    with dpg_instance.table_row(parent=table_tag):
                        dpg_instance.add_text(str(i+1), tag=f"{modal_tag}_num_{i}")
                        temp = dpg_instance.add_input_float(default_value=step.get('temperature', 0.0), step=0.1, width=100, format="%.1f",
                                                            tag=f"{modal_tag}_temp_{i}")
                        dpg_instance.bind_item_theme(temp, f"{tag_prefix}_pid_input_float_theme")
                        rate = dpg_instance.add_input_float(default_value=step.get('rate', 0.0), step=0.1, width=100, format="%.1f",
                                                            tag=f"{modal_tag}_rate_{i}")
                        dpg_instance.bind_item_theme(rate, f"{tag_prefix}_pid_input_float_theme")
                        hold = dpg_instance.add_input_float(default_value=step.get('hold_time', 0.0), step=0.1, width=100, format="%.1f",
                                                            tag=f"{modal_tag}_hold_{i}")
                        dpg_instance.bind_item_theme(hold, f"{tag_prefix}_pid_input_float_theme")
                        p = dpg_instance.add_input_float(default_value=step.get('pid_p', 0.0), step=0.1, width=100, format="%.2f",
                                                          tag=f"{modal_tag}_p_{i}")
                        dpg_instance.bind_item_theme(p, f"{tag_prefix}_pid_input_float_theme")
                        ii = dpg_instance.add_input_int(default_value=step.get('pid_i', 0), step=1, width=100,
                                                        tag=f"{modal_tag}_i_{i}")
                        dpg_instance.bind_item_theme(ii, f"{tag_prefix}_pid_input_int_theme")
                        d = dpg_instance.add_input_int(default_value=step.get('pid_d', 0), step=1, width=100,
                                                        tag=f"{modal_tag}_d_{i}")
                        dpg_instance.bind_item_theme(d, f"{tag_prefix}_pid_input_int_theme")
                        sp = dpg_instance.add_input_float(default_value=step.get('setpoint', 0.0), step=0.1, width=100, format="%.1f",
                                                           tag=f"{modal_tag}_sp_{i}")
                        dpg_instance.bind_item_theme(sp, f"{tag_prefix}_pid_input_float_theme")
                        fs = dpg_instance.add_input_int(default_value=step.get('fan_speed', 0), step=10, width=100,
                                                         tag=f"{modal_tag}_fs_{i}")
                        dpg_instance.bind_item_theme(fs, f"{tag_prefix}_pid_input_int_theme")
            except Exception as e:
                dpg_instance.set_value(file_info, f"Ошибка загрузки: {e}")

        def open_file_dialog():
            def file_callback(sender, app_data):
                if 'file_path_name' in app_data:
                    path = app_data['file_path_name']
                elif 'selections' in app_data:
                    path = list(app_data['selections'].values())[0]
                else:
                    return
                load_program_file(path)

            if getattr(sys, 'frozen', False):
                base_dir = os.path.dirname(sys.executable)
            else:
                base_dir = os.path.dirname(os.path.dirname(__file__))
            default_path = os.path.join(base_dir, "setups")

            with dpg_instance.file_dialog(
                directory_selector=False,
                show=False,
                callback=file_callback,
                width=650,
                height=400,
                default_path=default_path
            ):
                dpg_instance.add_file_extension(".json", color=(0,255,0,255))
            dpg_instance.show_item(dpg_instance.last_container())

        def add_row():
            nonlocal current_data, current_file
            if mode == "Ручной режим":
                # Получаем позицию и размер родительского окна
                parent_pos = dpg_instance.get_item_pos(modal_tag)
                parent_width = dpg_instance.get_item_width(modal_tag)
                parent_height = dpg_instance.get_item_height(modal_tag)
                child_width, child_height = 300, 150
                child_pos = [
                    parent_pos[0] + (parent_width - child_width) // 2,
                    parent_pos[1] + (parent_height - child_height) // 2
                ]

                with dpg_instance.window(
                        label="Новая температура",
                        modal=True,
                        width=child_width,
                        height=child_height,
                        pos=child_pos,  # центрируем окно
                        tag=f"{modal_tag}_add_temp_dialog",
                        no_resize=True
                ):
                    dpg_instance.add_text("Введите температуру (°C):")
                    new_temp = dpg_instance.add_input_float(default_value=20.0, step=0.1, format="%.1f")
                    dpg_instance.add_spacer(height=10)
                    with dpg_instance.group(horizontal=True):
                        dpg_instance.add_button(label="OK", width=80, callback=lambda: add_temp_ok(new_temp))
                        dpg_instance.add_button(label="Отмена", width=80,
                                                callback=lambda: dpg_instance.delete_item(
                                                    f"{modal_tag}_add_temp_dialog"))
                dpg_instance.show_item(f"{modal_tag}_add_temp_dialog")
            else:  # Программа
                if current_data is None:
                    current_data = []
                last_temp = current_data[-1]['temperature'] if current_data else 20.0
                new_step = {
                    'temperature': last_temp + 10,
                    'rate': 5.0,
                    'hold_time': 10.0,
                    'pid_p': 2.0,
                    'pid_i': 10,
                    'pid_d': 200,
                    'setpoint': 0.0,
                    'fan_speed': 1000
                }
                current_data.append(new_step)
                refresh_table_from_data()

        def add_temp_ok(temp_input):
            nonlocal current_data, current_file
            temp_val = dpg_instance.get_value(temp_input)
            dpg_instance.delete_item(f"{modal_tag}_add_temp_dialog")
            key = str(round(temp_val, 1))
            if current_data is None:
                current_data = {}
            if key in current_data:
                dpg_instance.set_value(file_info, f"Температура {key} уже существует")
                return
            current_data[key] = {'p': 0.0, 'i': 0, 'd': 0, 'setpoint': 0.0, 'fan_speed': 0}
            refresh_table_from_data()

        def refresh_table_from_data():
            """Перестроить таблицу из current_data"""
            if mode == "Ручной режим":
                clear_table()
                for temp_str, pid in current_data.items():
                    with dpg_instance.table_row(parent=table_tag):
                        dpg_instance.add_text(temp_str, tag=f"{modal_tag}_key_{temp_str}")
                        p = dpg_instance.add_input_float(default_value=pid.get('p', 0.0), step=0.1, width=100, format="%.2f",
                                                          tag=f"{modal_tag}_p_{temp_str}")
                        dpg_instance.bind_item_theme(p, f"{tag_prefix}_pid_input_float_theme")
                        i = dpg_instance.add_input_int(default_value=pid.get('i', 0), step=1, width=100,
                                                        tag=f"{modal_tag}_i_{temp_str}")
                        dpg_instance.bind_item_theme(i, f"{tag_prefix}_pid_input_int_theme")
                        d = dpg_instance.add_input_int(default_value=pid.get('d', 0), step=1, width=100,
                                                        tag=f"{modal_tag}_d_{temp_str}")
                        dpg_instance.bind_item_theme(d, f"{tag_prefix}_pid_input_int_theme")
                        sp = dpg_instance.add_input_float(default_value=pid.get('setpoint', 0.0), step=0.1, width=100, format="%.1f",
                                                           tag=f"{modal_tag}_sp_{temp_str}")
                        dpg_instance.bind_item_theme(sp, f"{tag_prefix}_pid_input_float_theme")
                        fs = dpg_instance.add_input_int(default_value=pid.get('fan_speed', 0), step=10, width=100,
                                                         tag=f"{modal_tag}_fs_{temp_str}")
                        dpg_instance.bind_item_theme(fs, f"{tag_prefix}_pid_input_int_theme")
            else:  # Программа
                clear_table()
                for i, step in enumerate(current_data):
                    with dpg_instance.table_row(parent=table_tag):
                        dpg_instance.add_text(str(i+1), tag=f"{modal_tag}_num_{i}")
                        temp = dpg_instance.add_input_float(default_value=step.get('temperature', 0.0), step=0.1, width=100, format="%.1f",
                                                            tag=f"{modal_tag}_temp_{i}")
                        dpg_instance.bind_item_theme(temp, f"{tag_prefix}_pid_input_float_theme")
                        rate = dpg_instance.add_input_float(default_value=step.get('rate', 0.0), step=0.1, width=100, format="%.1f",
                                                            tag=f"{modal_tag}_rate_{i}")
                        dpg_instance.bind_item_theme(rate, f"{tag_prefix}_pid_input_float_theme")
                        hold = dpg_instance.add_input_float(default_value=step.get('hold_time', 0.0), step=0.1, width=100, format="%.1f",
                                                            tag=f"{modal_tag}_hold_{i}")
                        dpg_instance.bind_item_theme(hold, f"{tag_prefix}_pid_input_float_theme")
                        p = dpg_instance.add_input_float(default_value=step.get('pid_p', 0.0), step=0.1, width=100, format="%.2f",
                                                          tag=f"{modal_tag}_p_{i}")
                        dpg_instance.bind_item_theme(p, f"{tag_prefix}_pid_input_float_theme")
                        ii = dpg_instance.add_input_int(default_value=step.get('pid_i', 0), step=1, width=100,
                                                        tag=f"{modal_tag}_i_{i}")
                        dpg_instance.bind_item_theme(ii, f"{tag_prefix}_pid_input_int_theme")
                        d = dpg_instance.add_input_int(default_value=step.get('pid_d', 0), step=1, width=100,
                                                        tag=f"{modal_tag}_d_{i}")
                        dpg_instance.bind_item_theme(d, f"{tag_prefix}_pid_input_int_theme")
                        sp = dpg_instance.add_input_float(default_value=step.get('setpoint', 0.0), step=0.1, width=100, format="%.1f",
                                                           tag=f"{modal_tag}_sp_{i}")
                        dpg_instance.bind_item_theme(sp, f"{tag_prefix}_pid_input_float_theme")
                        fs = dpg_instance.add_input_int(default_value=step.get('fan_speed', 0), step=10, width=100,
                                                         tag=f"{modal_tag}_fs_{i}")
                        dpg_instance.bind_item_theme(fs, f"{tag_prefix}_pid_input_int_theme")
            dpg_instance.bind_item_theme(table_tag, f"{tag_prefix}_pid_table_theme")

        def save_data():
            nonlocal current_data, current_file
            if current_file is None:
                dpg_instance.set_value(file_info, "Нет загруженного файла для сохранения")
                return
            try:
                if mode == "Ручной режим":
                    new_dict = {}
                    rows = dpg_instance.get_item_children(table_tag, slot=1)
                    if not rows:
                        return
                    for row in rows:
                        cells = dpg_instance.get_item_children(row, slot=1)
                        if len(cells) >= 6:
                            key_cell = cells[0]
                            p_cell = cells[1]
                            i_cell = cells[2]
                            d_cell = cells[3]
                            sp_cell = cells[4]
                            fs_cell = cells[5]
                            key = dpg_instance.get_value(key_cell)
                            p_val = dpg_instance.get_value(p_cell)
                            i_val = dpg_instance.get_value(i_cell)
                            d_val = dpg_instance.get_value(d_cell)
                            sp_val = dpg_instance.get_value(sp_cell)
                            fs_val = dpg_instance.get_value(fs_cell)
                            new_dict[key] = {
                                'p': p_val,
                                'i': i_val,
                                'd': d_val,
                                'setpoint': sp_val,
                                'fan_speed': fs_val,
                                'timestamp': time.time()
                            }
                    with open(current_file, 'w', encoding='utf-8') as f:
                        json.dump(new_dict, f, indent=2, ensure_ascii=False)
                    current_data = new_dict
                else:  # Программа
                    new_data = list(current_data)
                    rows = dpg_instance.get_item_children(table_tag, slot=1)
                    if not rows:
                        return
                    for i, row in enumerate(rows):
                        cells = dpg_instance.get_item_children(row, slot=1)
                        if len(cells) >= 9:
                            temp_val = dpg_instance.get_value(cells[1])
                            rate_val = dpg_instance.get_value(cells[2])
                            hold_val = dpg_instance.get_value(cells[3])
                            p_val = dpg_instance.get_value(cells[4])
                            i_val = dpg_instance.get_value(cells[5])
                            d_val = dpg_instance.get_value(cells[6])
                            sp_val = dpg_instance.get_value(cells[7])
                            fs_val = dpg_instance.get_value(cells[8])
                            if i < len(new_data):
                                new_data[i]['temperature'] = temp_val
                                new_data[i]['rate'] = rate_val
                                new_data[i]['hold_time'] = hold_val
                                new_data[i]['pid_p'] = p_val
                                new_data[i]['pid_i'] = i_val
                                new_data[i]['pid_d'] = d_val
                                new_data[i]['setpoint'] = sp_val
                                new_data[i]['fan_speed'] = fs_val
                    with open(current_file, 'w', encoding='utf-8') as f:
                        json.dump(new_data, f, indent=2, ensure_ascii=False)
                    current_data = new_data

                dpg_instance.set_value(file_info, f"Сохранено в {os.path.basename(current_file)}")
            except Exception as e:
                dpg_instance.set_value(file_info, f"Ошибка сохранения: {e}")

        # Инициализация: загружаем ручной режим
        load_temp_pid()

    dpg_instance.show_item(modal_tag)
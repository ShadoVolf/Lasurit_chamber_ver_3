"""
Диалог для ввода калибровочных данных коррекции температуры.
Добавлен график предварительного просмотра.
"""

import numpy as np  # для построения графика


def show_correction_dialog(dpg_instance, tag_prefix, apply_callback):
    """
    Открывает окно ввода калибровочных данных.
    Теперь содержит выбор канала (1 или 2) и кнопку просмотра графика.
    """
    modal_tag = f"{tag_prefix}_correction_modal"
    if dpg_instance.does_item_exist(modal_tag):
        dpg_instance.delete_item(modal_tag)

    window_width, window_height = 650, 720   # немного увеличим для кнопки графика
    vp_w = dpg_instance.get_viewport_width()
    vp_h = dpg_instance.get_viewport_height()
    pos_x = (vp_w - window_width) // 2
    pos_y = (vp_h - window_height) // 2

    with dpg_instance.window(
        label="Коррекция температуры",
        modal=False,
        tag=modal_tag,
        width=window_width,
        height=window_height,
        pos=[pos_x, pos_y],
        no_resize=True,
        no_collapse=True
    ) as win:
        # Применяем тему, созданную в главном окне
        if dpg_instance.does_item_exist(f"{tag_prefix}_setpoint_theme"):
            dpg_instance.bind_item_theme(win, f"{tag_prefix}_setpoint_theme")

        dpg_instance.add_text("Введите не менее 6 калибровочных точек (датчик → эталон):")
        dpg_instance.add_spacer(height=5)

        # БЛОК ВЫБОРА КАНАЛА
        dpg_instance.add_text("Корректируемый датчик:")
        with dpg_instance.group(horizontal=True):
            dpg_instance.add_radio_button(
                items=("1", "2"),
                default_value="1",
                tag=f"{tag_prefix}_corr_channel",
                horizontal=True
            )
        dpg_instance.add_spacer(height=10)

        # Заголовки таблицы
        with dpg_instance.group(horizontal=True):
            dpg_instance.add_spacer(width=30)
            dpg_instance.add_text("Исп.")
            dpg_instance.add_text("Показание датчика (°C)")
            dpg_instance.add_spacer(width=20)
            dpg_instance.add_text("Эталон (°C)")

        dpg_instance.add_separator()
        dpg_instance.add_spacer(height=5)

        # Контейнер для строк ввода
        container = f"{tag_prefix}_corr_rows"
        with dpg_instance.child_window(tag=container, width=window_width-40, height=350, border=True):
            _create_correction_rows(dpg_instance, tag_prefix, 12)

        dpg_instance.add_spacer(height=10)

        # Поле для степени полинома
        with dpg_instance.group(horizontal=True):
            dpg_instance.add_text("Степень полинома:")
            degree_input = dpg_instance.add_input_int(
                default_value=3,
                min_value=1,
                max_value=10,
                step=1,
                width=100,
                tag=f"{tag_prefix}_corr_degree"
            )
            if dpg_instance.does_item_exist(f"{tag_prefix}_input_theme"):
                dpg_instance.bind_item_theme(degree_input, f"{tag_prefix}_input_theme")

        dpg_instance.add_spacer(height=15)

        # Кнопки
        with dpg_instance.group(horizontal=True):
            # Центрирование: добавим spacer, но проще выровнять по левому краю с отступами
            # Расположим кнопки: График, Применить, Отмена с промежутками
            dpg_instance.add_spacer(width=20)

            # Кнопка "График"
            with dpg_instance.theme() as plot_theme:
                with dpg_instance.theme_component(dpg_instance.mvButton):
                    dpg_instance.add_theme_color(dpg_instance.mvThemeCol_Button, (100, 149, 237, 255))  # cornflower blue
                    dpg_instance.add_theme_color(dpg_instance.mvThemeCol_ButtonHovered, (70, 130, 180, 255))
                    dpg_instance.add_theme_color(dpg_instance.mvThemeCol_ButtonActive, (65, 105, 225, 255))
                    dpg_instance.add_theme_color(dpg_instance.mvThemeCol_Text, (255, 255, 255, 255))
                    dpg_instance.add_theme_style(dpg_instance.mvStyleVar_FramePadding, 18, 12)
                    dpg_instance.add_theme_style(dpg_instance.mvStyleVar_FrameRounding, 4)
            plot_btn = dpg_instance.add_button(
                label="График",
                width=100,
                callback=lambda: _show_plot(dpg_instance, tag_prefix)
            )
            dpg_instance.bind_item_theme(plot_btn, plot_theme)

            dpg_instance.add_spacer(width=20)

            # Кнопка "Применить"
            with dpg_instance.theme() as apply_theme:
                with dpg_instance.theme_component(dpg_instance.mvButton):
                    dpg_instance.add_theme_color(dpg_instance.mvThemeCol_Button, (65, 95, 135, 255))
                    dpg_instance.add_theme_color(dpg_instance.mvThemeCol_ButtonHovered, (85, 115, 160, 255))
                    dpg_instance.add_theme_color(dpg_instance.mvThemeCol_ButtonActive, (55, 80, 115, 255))
                    dpg_instance.add_theme_color(dpg_instance.mvThemeCol_Text, (255, 255, 255, 255))
                    dpg_instance.add_theme_style(dpg_instance.mvStyleVar_FramePadding, 18, 12)
                    dpg_instance.add_theme_style(dpg_instance.mvStyleVar_FrameRounding, 4)
            apply_btn = dpg_instance.add_button(
                label="Применить",
                width=120,
                callback=lambda: _apply_correction(dpg_instance, tag_prefix, apply_callback, modal_tag)
            )
            dpg_instance.bind_item_theme(apply_btn, apply_theme)

            dpg_instance.add_spacer(width=10)

            # Кнопка "Отмена"
            with dpg_instance.theme() as cancel_theme:
                with dpg_instance.theme_component(dpg_instance.mvButton):
                    dpg_instance.add_theme_color(dpg_instance.mvThemeCol_Button, (140, 155, 175, 255))
                    dpg_instance.add_theme_color(dpg_instance.mvThemeCol_ButtonHovered, (165, 180, 195, 255))
                    dpg_instance.add_theme_color(dpg_instance.mvThemeCol_ButtonActive, (120, 135, 155, 255))
                    dpg_instance.add_theme_color(dpg_instance.mvThemeCol_Text, (255, 255, 255, 255))
                    dpg_instance.add_theme_style(dpg_instance.mvStyleVar_FramePadding, 18, 12)
                    dpg_instance.add_theme_style(dpg_instance.mvStyleVar_FrameRounding, 4)
            cancel_btn = dpg_instance.add_button(
                label="Отмена",
                width=120,
                callback=lambda: dpg_instance.delete_item(modal_tag)
            )
            dpg_instance.bind_item_theme(cancel_btn, cancel_theme)

    dpg_instance.show_item(modal_tag)


def _create_correction_rows(dpg_instance, tag_prefix, rows_count):
    """Создаёт заданное количество строк для ввода данных."""
    for i in range(rows_count):
        with dpg_instance.group(horizontal=True, parent=f"{tag_prefix}_corr_rows"):
            dpg_instance.add_spacer(width=10)
            # Чекбокс для активации строки
            dpg_instance.add_checkbox(tag=f"{tag_prefix}_corr_use_{i}", default_value=False)
            dpg_instance.add_spacer(width=15)
            # Поле датчика
            sensor = dpg_instance.add_input_float(
                tag=f"{tag_prefix}_corr_sensor_{i}",
                width=150,
                default_value=0.0,
                step=0.1,
                format="%.2f"
            )
            if dpg_instance.does_item_exist(f"{tag_prefix}_input_float_theme"):
                dpg_instance.bind_item_theme(sensor, f"{tag_prefix}_input_float_theme")
            dpg_instance.add_spacer(width=20)
            # Поле эталона
            real = dpg_instance.add_input_float(
                tag=f"{tag_prefix}_corr_real_{i}",
                width=150,
                default_value=0.0,
                step=0.1,
                format="%.2f"
            )
            if dpg_instance.does_item_exist(f"{tag_prefix}_input_float_theme"):
                dpg_instance.bind_item_theme(real, f"{tag_prefix}_input_float_theme")


def _apply_correction(dpg_instance, tag_prefix, apply_callback, modal_tag):
    """Собирает данные из активных строк и вызывает callback с номером канала."""
    sensor_vals = []
    real_vals = []

    for i in range(12):
        if dpg_instance.get_value(f"{tag_prefix}_corr_use_{i}"):
            sensor = dpg_instance.get_value(f"{tag_prefix}_corr_sensor_{i}")
            real = dpg_instance.get_value(f"{tag_prefix}_corr_real_{i}")
            sensor_vals.append(sensor)
            real_vals.append(real)

    if len(sensor_vals) < 6:
        print("Ошибка: необходимо не менее 6 калибровочных точек")
        # Можно показать всплывающее окно с предупреждением
        return

    degree = dpg_instance.get_value(f"{tag_prefix}_corr_degree")
    if degree < 1:
        degree = 1

    # Получаем выбранный канал
    channel_str = dpg_instance.get_value(f"{tag_prefix}_corr_channel")
    channel = int(channel_str)

    apply_callback(sensor_vals, real_vals, degree, channel)
    dpg_instance.delete_item(modal_tag)


def _show_plot(dpg_instance, tag_prefix):
    """Открывает окно с графиком калибровочных точек и подобранного полинома."""
    # Собираем активные точки
    sensor_vals = []
    real_vals = []

    for i in range(12):
        if dpg_instance.get_value(f"{tag_prefix}_corr_use_{i}"):
            sensor = dpg_instance.get_value(f"{tag_prefix}_corr_sensor_{i}")
            real = dpg_instance.get_value(f"{tag_prefix}_corr_real_{i}")
            sensor_vals.append(sensor)
            real_vals.append(real)

    if len(sensor_vals) < 2:
        # Недостаточно точек для построения графика
        with dpg_instance.window(label="Ошибка", modal=True, tag="tmp_error_popup", width=300, height=100,
                                 pos=[dpg_instance.get_viewport_width()//2-150, dpg_instance.get_viewport_height()//2-50]):
            dpg_instance.add_text("Недостаточно точек для построения графика (минимум 2).")
            dpg_instance.add_button(label="OK", width=80, callback=lambda: dpg_instance.delete_item("tmp_error_popup"))
        return

    degree = dpg_instance.get_value(f"{tag_prefix}_corr_degree")
    if degree < 1:
        degree = 1

    # Подгонка полинома
    try:
        coeffs = np.polyfit(sensor_vals, real_vals, degree)
    except Exception as e:
        print(f"Ошибка подгонки полинома: {e}")
        with dpg_instance.window(label="Ошибка", modal=True, tag="tmp_error_popup2", width=300, height=100,
                                 pos=[dpg_instance.get_viewport_width()//2-150, dpg_instance.get_viewport_height()//2-50]):
            dpg_instance.add_text(f"Ошибка подгонки полинома: {e}")
            dpg_instance.add_button(label="OK", width=80, callback=lambda: dpg_instance.delete_item("tmp_error_popup2"))
        return

    # Генерация плавной линии
    x_min, x_max = min(sensor_vals), max(sensor_vals)
    if x_min == x_max:
        x_min -= 1
        x_max += 1
    x_smooth = np.linspace(x_min, x_max, 200)
    y_smooth = np.polyval(coeffs, x_smooth)

    # Создаём окно для графика
    plot_tag = f"{tag_prefix}_corr_plot_window"
    if dpg_instance.does_item_exist(plot_tag):
        dpg_instance.delete_item(plot_tag)

    # Определяем размер окна графика
    plot_width, plot_height = 600, 500
    vp_w = dpg_instance.get_viewport_width()
    vp_h = dpg_instance.get_viewport_height()
    pos_x = (vp_w - plot_width) // 2
    pos_y = (vp_h - plot_height) // 2

    with dpg_instance.window(label="График коррекции", tag=plot_tag, width=plot_width, height=plot_height,
                             pos=[pos_x, pos_y], no_resize=False, no_collapse=True):
        # Создаём plot
        with dpg_instance.plot(label="Калибровочные точки и полином", height=-1, width=-1):
            # Ось X
            dpg_instance.add_plot_axis(dpg_instance.mvXAxis, label="Показание датчика (°C)")
            # Ось Y
            with dpg_instance.plot_axis(dpg_instance.mvYAxis, label="Эталон (°C)"):
                # Точки (scatter)
                dpg_instance.add_scatter_series(
                    x=sensor_vals,
                    y=real_vals,
                    label="Измеренные точки",
                    show=True
                )
                # Линия полинома
                dpg_instance.add_line_series(
                    x=x_smooth,
                    y=y_smooth,
                    label=f"Полином (степень {degree})",
                    show=True
                )

    dpg_instance.show_item(plot_tag)
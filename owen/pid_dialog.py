"""
Диалог просмотра и редактирования PID-коэффициентов регулятора ТРМ12.
Стилизован под общий дизайн algorithm_settings_dialog.
"""

def show_pid_dialog(dpg_instance, tag_prefix, gui):
    """
    Открывает окно настройки PID-коэффициентов.
    Параметры:
        dpg_instance: экземпляр dearpygui
        tag_prefix: префикс для тегов элементов
        gui: экземпляр TPM12_GUI (содержит driver)
    """
    modal_tag = f"{tag_prefix}_pid_modal"
    if dpg_instance.does_item_exist(modal_tag):
        dpg_instance.delete_item(modal_tag)

    # Получаем текущие параметры PID из драйвера (канал 0 – камера)
    driver = gui.driver
    pid_params = None
    if driver and hasattr(driver, 'get_pid_parameters'):
        pid_params = driver.get_pid_parameters(channel=0)
    if pid_params is None:
        # Если не удалось получить, используем заглушку
        pid_params = {
            'P': 30.0, 'I': 60, 'D': 5,
            'deadband': 0.5, 'output_min': 0.0, 'output_max': 100.0,
            'hysteresis': 0.5
        }
        print("Не удалось прочитать PID-параметры, используются значения по умолчанию")

    window_width, window_height = 480, 520
    vp_w = dpg_instance.get_viewport_width()
    vp_h = dpg_instance.get_viewport_height()
    pos_x = (vp_w - window_width) // 2
    pos_y = (vp_h - window_height) // 2

    with dpg_instance.window(
        label="Настройки PID регулятора",
        modal=False,
        tag=modal_tag,
        width=window_width,
        height=window_height,
        pos=[pos_x, pos_y],
        no_resize=True,
        no_collapse=True
    ) as win:

        # Применяем тему, аналогичную correction_dialog / algorithm_settings_dialog
        if dpg_instance.does_item_exist(f"{tag_prefix}_setpoint_theme"):
            dpg_instance.bind_item_theme(win, f"{tag_prefix}_setpoint_theme")

        dpg_instance.add_text("Коэффициенты ПИД-регулятора (канал 1):")
        dpg_instance.add_spacer(height=5)

        # Контейнер для полей ввода (child_window для прокрутки)
        container = f"{modal_tag}_container"
        with dpg_instance.child_window(tag=container, width=window_width-40, height=350, border=True):
            # Создаём поля ввода в таблице
            _create_pid_fields(dpg_instance, container, modal_tag, pid_params, tag_prefix)

        dpg_instance.add_spacer(height=10)

        # Кнопки управления в одну горизонтальную линию
        with dpg_instance.group(horizontal=True):
            dpg_instance.add_spacer(width=5)  # отступ слева

            # Кнопка "По умолчанию"
            with dpg_instance.theme() as default_theme:
                with dpg_instance.theme_component(dpg_instance.mvButton):
                    dpg_instance.add_theme_color(dpg_instance.mvThemeCol_Button, (140, 155, 175, 255))
                    dpg_instance.add_theme_color(dpg_instance.mvThemeCol_ButtonHovered, (165, 180, 195, 255))
                    dpg_instance.add_theme_color(dpg_instance.mvThemeCol_ButtonActive, (120, 135, 155, 255))
                    dpg_instance.add_theme_color(dpg_instance.mvThemeCol_Text, (255, 255, 255, 255))
                    dpg_instance.add_theme_style(dpg_instance.mvStyleVar_FramePadding, 18, 12)
                    dpg_instance.add_theme_style(dpg_instance.mvStyleVar_FrameRounding, 4)
            default_btn = dpg_instance.add_button(
                label="По умолчанию",
                width=120,
                callback=lambda: _set_default_pid(dpg_instance, modal_tag)
            )
            dpg_instance.bind_item_theme(default_btn, default_theme)

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
                callback=lambda: _apply_pid_and_close(dpg_instance, modal_tag, driver)
            )
            dpg_instance.bind_item_theme(apply_btn, apply_theme)

            dpg_instance.add_spacer(width=10)

        dpg_instance.add_spacer(height=5)

    dpg_instance.show_item(modal_tag)


def _create_pid_fields(dpg_instance, parent_tag, base_tag, pid_params, tag_prefix):
    """Создаёт поля ввода для PID-параметров, используя таблицу для выравнивания."""
    # Список параметров: (ключ, название, тип, шаг, минимум, максимум)
    params = [
        ("P", "Пропорциональный (P)", "float", 0.1, 0.0, 1000.0),
        ("I", "Интегральный (I, сек)", "int", 1, 0, 3600),
        ("D", "Дифференциальный (D, сек)", "int", 1, 0, 3600),
        ("deadband", "Зона нечувствительности (°C)", "float", 0.1, 0.0, 100.0),
        ("output_min", "Мин. выход (%)", "float", 0.1, 0.0, 100.0),
        ("output_max", "Макс. выход (%)", "float", 0.1, 0.0, 100.0),
        ("hysteresis", "Гистерезис (°C)", "float", 0.1, 0.0, 100.0),
    ]

    with dpg_instance.table(
        parent=parent_tag,
        header_row=False,
        borders_innerH=False,
        borders_outerH=False,
        borders_innerV=False,
        borders_outerV=False,
        policy=dpg_instance.mvTable_SizingStretchProp,
        width=-1,
    ):
        dpg_instance.add_table_column(label="Параметр")
        dpg_instance.add_table_column(label="Значение")

        for key, label, typ, step, vmin, vmax in params:
            with dpg_instance.table_row():
                dpg_instance.add_text(label)
                value = pid_params.get(key, 0.0)
                if typ == "int":
                    item = dpg_instance.add_input_int(
                        tag=f"{base_tag}_{key}",
                        default_value=int(value),
                        step=int(step),
                        min_value=int(vmin),
                        max_value=int(vmax),
                        width=150
                    )
                    if dpg_instance.does_item_exist(f"{tag_prefix}_input_theme"):
                        dpg_instance.bind_item_theme(item, f"{tag_prefix}_input_theme")
                else:  # float
                    item = dpg_instance.add_input_float(
                        tag=f"{base_tag}_{key}",
                        default_value=float(value),
                        step=step,
                        min_value=vmin,
                        max_value=vmax,
                        format="%.2f",
                        width=150
                    )
                    if dpg_instance.does_item_exist(f"{tag_prefix}_input_float_theme"):
                        dpg_instance.bind_item_theme(item, f"{tag_prefix}_input_float_theme")


def _set_default_pid(dpg_instance, base_tag):
    """Устанавливает значения PID по умолчанию (типовые для ТРМ12)."""
    defaults = {
        "P": 30.0,
        "I": 60,
        "D": 5,
        "deadband": 0.5,
        "output_min": 0.0,
        "output_max": 100.0,
        "hysteresis": 0.5,
    }
    for key, value in defaults.items():
        tag = f"{base_tag}_{key}"
        if dpg_instance.does_item_exist(tag):
            dpg_instance.set_value(tag, value)


def _apply_pid_and_close(dpg_instance, base_tag, driver):
    """Собирает значения из полей, применяет через драйвер и закрывает окно."""
    # Собираем значения
    new_params = {}
    keys = ["P", "I", "D", "deadband", "output_min", "output_max", "hysteresis"]
    for key in keys:
        tag = f"{base_tag}_{key}"
        if dpg_instance.does_item_exist(tag):
            new_params[key] = dpg_instance.get_value(tag)

    # Применяем через драйвер (канал 0)
    if driver and hasattr(driver, 'set_pid_parameters'):
        success, message = driver.set_pid_parameters(
            P=new_params.get("P"),
            I=new_params.get("I"),
            D=new_params.get("D"),
            deadband=new_params.get("deadband"),
            output_min=new_params.get("output_min"),
            output_max=new_params.get("output_max"),
            channel=0
        )
        print(f"Установка PID: {message}")
    else:
        print("Драйвер не поддерживает установку PID")

    dpg_instance.delete_item(base_tag)
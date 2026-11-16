"""
Диалог для изменения уставки температуры.

"""

"""
Диалог для изменения уставки температуры.
"""

"""
Диалог для изменения уставки температуры.
"""


def show_setpoint_dialog(dpg_instance, tag_prefix, current_value, apply_callback):
    """
    Открывает окно ввода новой уставки.

    Args:
        dpg_instance: экземпляр dearpygui
        tag_prefix: префикс тегов основного окна
        current_value: текущее значение уставки
        apply_callback: функция, принимающая новое значение (float)
    """
    modal_tag = f"{tag_prefix}_setpoint_modal"
    if dpg_instance.does_item_exist(modal_tag):
        dpg_instance.delete_item(modal_tag)

    window_width, window_height = 450, 210
    vp_w = dpg_instance.get_viewport_width()
    vp_h = dpg_instance.get_viewport_height()
    pos_x = (vp_w - window_width) // 2
    pos_y = (vp_h - window_height) // 2

    with dpg_instance.window(
        label="Установка уставки температуры",
        modal=False,                # ← ВАЖНО: должно быть False для top-level окна
        tag=modal_tag,
        width=window_width,
        height=window_height,
        pos=[pos_x, pos_y],
        no_resize=True,
        no_collapse=True
    ) as win:
        if dpg_instance.does_item_exist(f"{tag_prefix}_setpoint_theme"):
            dpg_instance.bind_item_theme(win, f"{tag_prefix}_setpoint_theme")

        dpg_instance.add_spacer(height=5)

        with dpg_instance.child_window(width=window_width - 40, height=90, border=True):
            dpg_instance.add_spacer(height=8)
            with dpg_instance.group(horizontal=True):
                dpg_instance.add_spacer(width=20)
                input_field = dpg_instance.add_input_float(
                    default_value=float(current_value),
                    step=0.5,
                    step_fast=5.0,
                    min_value=-70.0,
                    max_value=150.0,
                    width=240,
                    tag=f"{tag_prefix}_setpoint_input",
                    min_clamped=True,
                    max_clamped=True,
                    format="%.1f"
                )
                if dpg_instance.does_item_exist(f"{tag_prefix}_input_float_theme"):
                    dpg_instance.bind_item_theme(input_field, f"{tag_prefix}_input_float_theme")
                dpg_instance.add_spacer(width=3)
                dpg_instance.add_text("°C", bullet=True)
            dpg_instance.add_spacer(height=8)

        dpg_instance.add_spacer(height=8)

        with dpg_instance.group(horizontal=True):
            dpg_instance.add_spacer(width=(window_width - 340) // 2)

            # Кнопка Отмена
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

            dpg_instance.add_spacer(width=5)

            # Кнопка Применить
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
                callback=lambda: _apply_setpoint(dpg_instance, tag_prefix, apply_callback, modal_tag)
            )
            dpg_instance.bind_item_theme(apply_btn, apply_theme)

            dpg_instance.add_spacer(width=(window_width - 340) // 2)

    dpg_instance.focus_item(f"{tag_prefix}_setpoint_input")
    dpg_instance.set_value(f"{tag_prefix}_setpoint_input", float(current_value))
    dpg_instance.show_item(modal_tag)


def _apply_setpoint(dpg_instance, tag_prefix, apply_callback, modal_tag):
    """Считывает значение из поля и вызывает callback."""
    try:
        new_value = dpg_instance.get_value(f"{tag_prefix}_setpoint_input")
        apply_callback(float(new_value))
        dpg_instance.delete_item(modal_tag)
    except Exception as e:
        print(f"Ошибка применения уставки: {e}")
        # Окно намеренно не закрываем — пользователь может исправить значение

def show_setpoint_dialog_old1(dpg_instance, tag_prefix, current_value, apply_callback):
    """
    Открывает окно ввода новой уставки.

    Args:
        dpg_instance: экземпляр dearpygui
        tag_prefix: префикс тегов основного окна
        current_value: текущее значение уставки
        apply_callback: функция, принимающая новое значение (float)
    """
    modal_tag = f"{tag_prefix}_setpoint_modal"
    if dpg_instance.does_item_exist(modal_tag):
        dpg_instance.delete_item(modal_tag)

    window_width, window_height = 450, 210
    vp_w = dpg_instance.get_viewport_width()
    vp_h = dpg_instance.get_viewport_height()
    pos_x = (vp_w - window_width) // 2
    pos_y = (vp_h - window_height) // 2

    with dpg_instance.window(
        label="Установка уставки температуры",
        modal=True,                 # ← ИЗМЕНЕНО: было False
        tag=modal_tag,
        width=window_width,
        height=window_height,
        pos=[pos_x, pos_y],
        no_resize=True,
        no_collapse=True
    ) as win:
        if dpg_instance.does_item_exist(f"{tag_prefix}_setpoint_theme"):
            dpg_instance.bind_item_theme(win, f"{tag_prefix}_setpoint_theme")

        dpg_instance.add_spacer(height=5)

        with dpg_instance.child_window(width=window_width - 40, height=90, border=True):
            dpg_instance.add_spacer(height=8)
            with dpg_instance.group(horizontal=True):
                dpg_instance.add_spacer(width=20)
                input_field = dpg_instance.add_input_float(
                    default_value=float(current_value),
                    step=0.5,
                    step_fast=5.0,
                    min_value=-70.0,
                    max_value=150.0,
                    width=240,
                    tag=f"{tag_prefix}_setpoint_input",
                    min_clamped=True,
                    max_clamped=True,
                    format="%.1f"
                )
                if dpg_instance.does_item_exist(f"{tag_prefix}_input_float_theme"):
                    dpg_instance.bind_item_theme(input_field, f"{tag_prefix}_input_float_theme")
                dpg_instance.add_spacer(width=3)
                dpg_instance.add_text("°C", bullet=True)
            dpg_instance.add_spacer(height=8)

        dpg_instance.add_spacer(height=8)

        with dpg_instance.group(horizontal=True):
            dpg_instance.add_spacer(width=(window_width - 340) // 2)

            # Кнопка Отмена
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

            dpg_instance.add_spacer(width=5)

            # Кнопка Применить
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
                callback=lambda: _apply_setpoint(dpg_instance, tag_prefix, apply_callback, modal_tag)
            )
            dpg_instance.bind_item_theme(apply_btn, apply_theme)

            dpg_instance.add_spacer(width=(window_width - 340) // 2)

    dpg_instance.focus_item(f"{tag_prefix}_setpoint_input")
    dpg_instance.set_value(f"{tag_prefix}_setpoint_input", float(current_value))
    dpg_instance.show_item(modal_tag)


def _apply_setpoint_old1(dpg_instance, tag_prefix, apply_callback, modal_tag):
    """
    Считывает значение из поля и вызывает callback.

    Если callback выбрасывает исключение (например, запрет изменения уставки
    во время активного процесса), модальное окно НЕ закрывается — пользователь
    видит ошибку и может исправить значение.
    """
    try:
        new_value = dpg_instance.get_value(f"{tag_prefix}_setpoint_input")
        apply_callback(float(new_value))
        dpg_instance.delete_item(modal_tag)
    except Exception as e:
        print(f"Ошибка применения уставки: {e}")
        # Окно намеренно не закрываем, чтобы пользователь мог исправить значение

def show_setpoint_dialog_old(dpg_instance, tag_prefix, current_value, apply_callback):
    """
    Открывает окно ввода новой уставки.

    Args:
        dpg_instance: экземпляр dearpygui
        tag_prefix: префикс тегов основного окна
        current_value: текущее значение уставки
        apply_callback: функция, принимающая новое значение (float)
    """
    modal_tag = f"{tag_prefix}_setpoint_modal"
    if dpg_instance.does_item_exist(modal_tag):
        dpg_instance.delete_item(modal_tag)

    window_width, window_height = 450, 210
    vp_w = dpg_instance.get_viewport_width()
    vp_h = dpg_instance.get_viewport_height()
    pos_x = (vp_w - window_width) // 2
    pos_y = (vp_h - window_height) // 2

    with dpg_instance.window(
        label="Установка уставки температуры",
        modal=False,
        tag=modal_tag,
        width=window_width,
        height=window_height,
        pos=[pos_x, pos_y],
        no_resize=True,
        no_collapse=True
    ) as win:
        if dpg_instance.does_item_exist(f"{tag_prefix}_setpoint_theme"):
            dpg_instance.bind_item_theme(win, f"{tag_prefix}_setpoint_theme")

        dpg_instance.add_spacer(height=5)

        with dpg_instance.child_window(width=window_width-40, height=90, border=True):
            dpg_instance.add_spacer(height=8)
            with dpg_instance.group(horizontal=True):
                dpg_instance.add_spacer(width=20)
                input_field = dpg_instance.add_input_float(
                    default_value=float(current_value),
                    step=0.5,
                    step_fast=5.0,
                    min_value=-70.0,
                    max_value=150.0,
                    width=240,
                    tag=f"{tag_prefix}_setpoint_input",
                    min_clamped=True,
                    max_clamped=True,
                    format="%.1f"
                )
                if dpg_instance.does_item_exist(f"{tag_prefix}_input_float_theme"):
                    dpg_instance.bind_item_theme(input_field, f"{tag_prefix}_input_float_theme")
                dpg_instance.add_spacer(width=3)
                dpg_instance.add_text("°C", bullet=True)
            dpg_instance.add_spacer(height=8)

        dpg_instance.add_spacer(height=8)

        with dpg_instance.group(horizontal=True):
            dpg_instance.add_spacer(width=(window_width - 340) // 2)

            # Кнопка Отмена
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

            dpg_instance.add_spacer(width=5)

            # Кнопка Применить
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
                callback=lambda: _apply_setpoint(dpg_instance, tag_prefix, apply_callback, modal_tag)
            )
            dpg_instance.bind_item_theme(apply_btn, apply_theme)

            dpg_instance.add_spacer(width=(window_width - 340) // 2)

    dpg_instance.focus_item(f"{tag_prefix}_setpoint_input")
    dpg_instance.set_value(f"{tag_prefix}_setpoint_input", float(current_value))
    dpg_instance.show_item(modal_tag)


def _apply_setpoint_old(dpg_instance, tag_prefix, apply_callback, modal_tag):
    """
    Считывает значение из поля и вызывает callback.

    Если callback выбрасывает исключение (например, запрет изменения уставки
    во время активного процесса), модальное окно НЕ закрывается — пользователь
    видит ошибку и может исправить значение.
    """
    try:
        new_value = dpg_instance.get_value(f"{tag_prefix}_setpoint_input")
        apply_callback(float(new_value))
        dpg_instance.delete_item(modal_tag)
    except Exception as e:
        print(f"Ошибка применения уставки: {e}")
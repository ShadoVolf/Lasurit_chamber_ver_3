"""
Диалог настройки параметров алгоритма нагрева и скорости нагрева.
Стилизован под общий дизайн correction_dialog.
"""
import json
import os
import sys


def get_config_path():
    """
    Возвращает путь к файлу конфигурации в рабочей директории.
    Для скомпилированного exe – рядом с исполняемым файлом,
    для скрипта – в текущей рабочей директории.
    """
    if getattr(sys, 'frozen', False):
        # Если приложение запущено как скомпилированный exe
        base_dir = os.path.dirname(sys.executable)
    else:
        # Если запущено как обычный скрипт Python
        base_dir = os.getcwd()
    return os.path.join(base_dir, "chamber_algorithm_config.json")

CONFIG_FILE = get_config_path()

def _load_settings_from_file(chamber_process):
    """Загружает настройки из файла. Если файла нет, создаёт дефолтные и сохраняет."""
    defaults = {
        "epsilon_reach": getattr(chamber_process, "epsilon_reach", 0.2),
        "epsilon_stable": getattr(chamber_process, "epsilon_stable", 0.1),
        "stability_interval": getattr(chamber_process, "stability_interval", 5),
        "pid_adjust_interval": getattr(chamber_process, "pid_adjust_interval", 120),
        "setpoint_adjust_interval": getattr(chamber_process, "setpoint_adjust_interval", 200),
        "update_interval": getattr(chamber_process, "update_interval", 1.0),
        "heating_rate": 0.0,
        "shaft_stabilization_interval": 2.0,
        "shaft_final_delay": 20.0,
        "shaft_temp_update_interval": 60.0,
        "shaft_max_attempts": 15,
        "max_correction": 0.1,
        "correction_cooldown": 30,
        "target_gradient": 2.0,
        "fan_adjust_interval": 30.0,
        "temp_threshold_for_shaft_heating": 50.0,
        "shaft_min_temp_for_heating": 20.0,
        "shaft_heating_duration": 5.0,
        "shaft_heating_repetitions": 3,
        "shaft_heating_interval": 60.0,
        "fan_control_enabled": True,
        "shaft_check_enabled": True,

    }

    config_path = CONFIG_FILE  # используем переменную
    if os.path.exists(config_path):
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                loaded = json.load(f)
                defaults.update(loaded)
        except Exception as e:
            print(f"Ошибка загрузки {config_path}: {e}")
    else:
        try:
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(defaults, f, indent=4, ensure_ascii=False)
        except Exception as e:
            print(f"Ошибка создания {config_path}: {e}")
    return defaults

def _save_settings_to_file(settings):
    try:
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(settings, f, indent=4, ensure_ascii=False)
    except Exception as e:
        print(f"Ошибка сохранения {CONFIG_FILE}: {e}")

def show_algorithm_settings_dialog(dpg_instance, tag_prefix, chamber_process, current_settings, apply_callback):
    """
    Открывает окно настроек алгоритма.
    Параметры:
        dpg_instance: экземпляр dearpygui
        tag_prefix: префикс для тегов элементов
        chamber_process: объект ChamberProcess (для доступа к параметрам по умолчанию)
        current_settings: словарь с текущими значениями (epsilon_reach, epsilon_stable, ...)
        apply_callback: функция, принимающая словарь новых значений
    """
    if current_settings is None:
        current_settings = _load_settings_from_file(chamber_process)

    modal_tag = f"{tag_prefix}_algorithm_settings_modal"
    if dpg_instance.does_item_exist(modal_tag):
        dpg_instance.delete_item(modal_tag)

    window_width, window_height = 610, 630  # увеличена высота для новых полей
    vp_w = dpg_instance.get_viewport_width()
    vp_h = dpg_instance.get_viewport_height()
    pos_x = (vp_w - window_width) // 2
    pos_y = (vp_h - window_height) // 2

    with dpg_instance.window(
        label="Настройки алгоритма",
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

        dpg_instance.add_text("Параметры алгоритма нагрева/выдержки:")
        dpg_instance.add_spacer(height=5)

        container = f"{modal_tag}_container"
        with dpg_instance.child_window(tag=container, width=window_width-40, height=430, border=True):
            _create_input_fields(dpg_instance, container, modal_tag, current_settings, tag_prefix)

        dpg_instance.add_spacer(height=10)

        with dpg_instance.group(horizontal=True):
            dpg_instance.add_spacer(width=5)

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
                callback=lambda: _set_default_values(dpg_instance, modal_tag, chamber_process)
            )
            dpg_instance.bind_item_theme(default_btn, default_theme)

            dpg_instance.add_spacer(width=10)

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
                callback=lambda: _apply_and_close(dpg_instance, modal_tag, apply_callback)
            )
            dpg_instance.bind_item_theme(apply_btn, apply_theme)

            dpg_instance.add_spacer(width=10)

        dpg_instance.add_spacer(height=5)

    dpg_instance.show_item(modal_tag)


def _create_input_fields(dpg_instance, parent_tag, base_tag, current_settings, tag_prefix):
    """Создаёт поля ввода для всех параметров, используя таблицу для выравнивания."""
    # Список параметров: (ключ, название, формат, шаг, минимум, максимум)
    params = [
        ("epsilon_reach", "Точность установки (°C)", "float", 0.01, 0.01, 10.0),
        ("epsilon_stable", "Стабильность (°C)", "float", 0.01, 0.01, 5.0),
        ("stability_interval", "Интервал стабильности (сек)", "int", 1, 1, 300),
        ("pid_adjust_interval", "Коррекция PID.I (сек)", "int", 10, 10, 3600),
        ("setpoint_adjust_interval", "Коррекция уставки (сек)", "int", 10, 10, 3600),
        ("update_interval", "Интервал обновления (сек)", "float", 0.1, 0.1, 10.0),
        ("heating_rate", "Скорость нагрева (°C/сек)", "float", 0.1, 0.0, 100.0),

        # Параметры измерения вала
        ("shaft_stabilization_interval", "Стабилизация температуры вала (сек)", "float", 0.5, 0.5, 30.0),
        ("shaft_final_delay", "Финальная задержка вала (сек)", "float", 1.0, 1.0, 60.0),
        ("shaft_temp_update_interval", "Интервал обновления температуры вала (сек)", "float", 1.0, 1.0, 300.0),
        ("shaft_max_attempts", "Кол-во попыток измерения вала", "int", 1, 1, 50),

        # Новые параметры для коррекции уставки
        ("max_correction", "Макс. изменение уставки (°C)", "float", 0.01, 0.0, 5.0),
        ("correction_cooldown", "Интервал между коррекциями (сек)", "int", 1, 1, 300),
        ("target_gradient", "Целевой градиент (°C)", "float", 0.1, 0.1, 20.0),
        ("fan_adjust_interval", "Интервал коррекции скорости вентилятора (сек)", "float", 1.0, 1.0, 300.0),
        ("temp_threshold_for_shaft_heating", "Порог температуры камеры для нагрева вала (°C)", "float", 0.1, -100, 500),
        ("shaft_min_temp_for_heating", "Мин. температура вала для включения нагрева (°C)", "float", 0.1, -50, 200),
        ("shaft_heating_duration", "Длительность нагрева вала (сек)", "float", 0.5, 0.1, 600),
        ("shaft_heating_repetitions", "Количество повторений нагрева", "int", 1, 0, 100),
        ("shaft_heating_interval", "Интервал между повторениями (сек)", "float", 1, 1, 3600),
        ("fan_control_enabled", "Регулировка вентилятора", "bool", None, None, None),
        ("shaft_check_enabled", "Проверка температуры вала", "bool", None, None, None)
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
                value = current_settings.get(key, 0.0)
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
                elif typ == "float":
                    item = dpg_instance.add_input_float(
                        tag=f"{base_tag}_{key}",
                        default_value=float(value),
                        step=step,
                        min_value=vmin,
                        max_value=vmax,
                        format="%.2f",
                        width=150
                    )
                elif typ == "bool":
                    item = dpg_instance.add_checkbox(
                     tag=f"{base_tag}_{key}",
                    default_value=bool(value)
                     )
                    if dpg_instance.does_item_exist(f"{tag_prefix}_input_float_theme"):
                        dpg_instance.bind_item_theme(item, f"{tag_prefix}_input_float_theme")


def _set_default_values(dpg_instance, base_tag, chamber_process):
    """Устанавливает значения по умолчанию из атрибутов chamber_process."""
    defaults = {
        "epsilon_reach": getattr(chamber_process, "epsilon_reach", 0.2),
        "epsilon_stable": getattr(chamber_process, "epsilon_stable", 0.1),
        "stability_interval": getattr(chamber_process, "stability_interval", 5),
        "pid_adjust_interval": getattr(chamber_process, "pid_adjust_interval", 120),
        "setpoint_adjust_interval": getattr(chamber_process, "setpoint_adjust_interval", 200),
        "update_interval": getattr(chamber_process, "update_interval", 1.0),
        "heating_rate": 0.0,
        "shaft_stabilization_interval": 2.0,
        "shaft_final_delay": 20.0,
        "shaft_temp_update_interval": 60.0,
        "shaft_max_attempts": 15,
        # Значения по умолчанию для новых параметров
        "max_correction": 0.1,
        "correction_cooldown": 30,
        "target_gradient": 2.0,
        "fan_adjust_interval": 30.0,
        "temp_threshold_for_shaft_heating": 50.0,
        "shaft_min_temp_for_heating": 20.0,
        "shaft_heating_duration": 5.0,
        "shaft_heating_repetitions": 3,
        "shaft_heating_interval": 60.0,
        "fan_control_enabled": True,
        "shaft_check_enabled": True,
    }
    for key, value in defaults.items():
        tag = f"{base_tag}_{key}"
        if dpg_instance.does_item_exist(tag):
            dpg_instance.set_value(tag, value)



def _apply_and_close(dpg_instance, base_tag, apply_callback):
    """Собирает значения из полей, вызывает callback и сохраняет в файл."""
    new_settings = {}
    keys = [
        "epsilon_reach", "epsilon_stable", "stability_interval",
        "pid_adjust_interval", "setpoint_adjust_interval",
        "update_interval", "heating_rate",
        "shaft_stabilization_interval", "shaft_final_delay",
        "shaft_temp_update_interval", "shaft_max_attempts",
        "max_correction", "correction_cooldown",
        "target_gradient",
        "fan_adjust_interval",
        "temp_threshold_for_shaft_heating",
        "shaft_min_temp_for_heating",
        "shaft_heating_duration",
        "shaft_heating_repetitions",
        "shaft_heating_interval",
        "fan_control_enabled",  # <-- добавить
        "shaft_check_enabled",
    ]
    for key in keys:
        tag = f"{base_tag}_{key}"
        if dpg_instance.does_item_exist(tag):
            new_settings[key] = dpg_instance.get_value(tag)
        else:
            new_settings[key] = None

    if apply_callback:
        apply_callback(new_settings)

    # Сохраняем новые настройки в файл
    _save_settings_to_file(new_settings)

    dpg_instance.delete_item(base_tag)
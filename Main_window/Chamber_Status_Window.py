from Chamber.Connect_Options import ConnectionOptionsWindow, ConnectionOptionsManager
from Chamber.chamber_driver import CameraController
from Chamber.chamber_gui_driver import _camera_power_on, _activate_camera, _camera_power_off, _emergency_stop, \
    _update_status, _toggle_auto_update, _initialize_ui_state, _update_system_status
from Chamber.read_config import read_serial_number_from_config

from Utils import Options

# Импортируем обработчики из отдельного модуля


def show_connection_settings(dpg):
    window = ConnectionOptionsWindow(dpg)
    window.show()


def create_info_window(dpg):
    # Создаём контроллер камеры
    camera_controller = CameraController()

    # Читаем серийный номер из конфигурационного файла
    serial_number = read_serial_number_from_config()
    ConnectionOptionsManager.save_to_file("connection_settings.json")
    with dpg.window(
            label="Управление камерой - Подключение",
            tag="camera_connected_window",
            width=850,
            height=480,
            pos=[0, 5]
    ):
        # Заголовок с версией ПО и серийным номером
        with dpg.group(horizontal=True):
            with dpg.group():
                dpg.add_text(
                    f"Система управления камерой ПО версия {Options.get_version()}",
                    color=[100, 150, 255]
                )
                dpg.add_text(
                    f"Серийный номер: {serial_number}",
                    color=[150, 200, 255]
                )

        dpg.add_separator()

        # Панель управления камерой
        with dpg.group(tag="camera_control_panel"):
            with dpg.group(horizontal=True):
                dpg.add_text('Камера')
                dpg.add_button(
                    label="Соединение",
                    width=140,
                    callback=lambda: _camera_power_on(dpg, camera_controller),
                    tag='camera_power_on_button',
                    enabled=True
                )
                dpg.add_button(
                    label="Включить камеру",
                    width=140,
                    callback=lambda: _activate_camera(dpg, camera_controller),
                    tag='camera_activate_button',
                    enabled=True
                )
                dpg.add_button(
                    label="Отключить камеру",
                    width=140,
                    callback=lambda: _camera_power_off(dpg, camera_controller),
                    tag='camera_power_off_button',
                )
                dpg.add_button(
                    label="Аварийная остановка",
                    width=140,
                    callback=lambda: _emergency_stop(dpg, camera_controller),
                    tag='emergency_stop_button',
                    enabled=True
                )
                dpg.add_button(
                    label="Настройки соединения",
                    callback=lambda: show_connection_settings(dpg),
                    width=160
                )

                dpg.add_text("КАМЕРА ВЫКЛ", tag="camera_overall_status", color=[255, 0, 0])

        dpg.add_separator()

        # Информация о системе
        with dpg.group(horizontal=True):
            # Левая колонка - устройства
            with dpg.child_window(width=400, height=300):
                dpg.add_text("Состояние устройств", color=[200, 200, 200])
                dpg.add_spacer(height=5)

                # Терморегулятор
                with dpg.group(horizontal=True):
                    dpg.add_text("ОВЕН ТРМ12:")
                    dpg.add_text("НЕТ ДАННЫХ", tag="trm12_status_text", color=[255, 100, 100])
                    dpg.add_text(" (", tag="trm12_temp_label")
                    dpg.add_text("--", tag="trm12_temp_value", color=[255, 200, 100])
                    dpg.add_text("°C)", tag="trm12_temp_unit")

                # Двигатель
                with dpg.group(horizontal=True):
                    dpg.add_text("Вентилятор BLSD-20:")
                    dpg.add_text("НЕТ ДАННЫХ", tag="blsd20_status_text", color=[255, 100, 100])
                    dpg.add_text(" (", tag="blsd20_speed_label")
                    dpg.add_text("--", tag="blsd20_speed_value", color=[100, 200, 255])
                    dpg.add_text(" об/мин)", tag="blsd20_speed_unit")

                # Релейная плата
                with dpg.group(horizontal=True):
                    dpg.add_text("Релейная плата:")
                    dpg.add_text("НЕТ ДАННЫХ", tag="relay_status_text", color=[255, 100, 100])
                    dpg.add_text(" (", tag="relay_state_label")
                    dpg.add_text("----", tag="relay_state_value", color=[150, 200, 150])
                    dpg.add_text(")", tag="relay_state_unit")

            dpg.add_spacer(width=5)

            # Правая колонка - общая информация
            with dpg.child_window(width=400, height=300):
                dpg.add_text("Информация системы", color=[200, 200, 200])
                dpg.add_text("Текущий статус", color=[200, 200, 200])

                with dpg.table(header_row=False, borders_innerH=True, borders_outerH=True):
                    dpg.add_table_column(width_fixed=True, width=150)
                    dpg.add_table_column(width_fixed=True, width=50)
                    dpg.add_table_column(width_fixed=True, width=30)

                    with dpg.table_row():
                        dpg.add_text("Режим работы:")
                        dpg.add_text("Ожидание", tag="system_mode_text", color=[200, 200, 100])
                        dpg.add_text("Единицы", tag="system_mode_text_", color=[200, 200, 100])

                    with dpg.table_row():
                        dpg.add_text("Температура камеры:")
                        dpg.add_text("--", tag="chamber_temp_text", color=[255, 200, 100])
                        dpg.add_text("°C", tag="chamber_temp_unit")

                    with dpg.table_row():
                        dpg.add_text("Градиент:")
                        dpg.add_text("--", tag="gradient_text", color=[150, 255, 150])
                        dpg.add_text("°C", tag="gradient_unit")

                    with dpg.table_row():
                        dpg.add_text("Скорость вентилятора:")
                        dpg.add_text("--", tag="motor_speed_text", color=[255, 200, 100])
                        dpg.add_text(" об/мин", tag="motor_speed_unit")

                    with dpg.table_row():
                        dpg.add_text("Ток двигателя:")
                        dpg.add_text("--", tag="motor_current_text", color=[100, 200, 255])
                        dpg.add_text(" мА", tag="motor_current_unit")

                    with dpg.table_row():
                        dpg.add_text("Температура вала:")
                        dpg.add_text("--", tag="motor_temp_text", color=[200, 150, 255])
                        dpg.add_text("°C", tag="motor_temp_unit")

                dpg.add_spacer(height=5)
                dpg.add_text("Версии ПО", color=[200, 200, 200])
                with dpg.table(header_row=False, borders_innerH=True, borders_outerH=True):
                    dpg.add_table_column(width_fixed=True, width=150)
                    dpg.add_table_column(width_stretch=True)

                    with dpg.table_row():
                        dpg.add_text("ОВЕН ТРМ12:")
                        dpg.add_text("Не подключен", tag="trm12_version_text", color=[150, 150, 150])

                    with dpg.table_row():
                        dpg.add_text("BLSD-20:")
                        dpg.add_text("Не подключен", tag="blsd20_version_text", color=[150, 150, 150])

        dpg.add_separator()

        # Быстрые действия
        with dpg.group(horizontal=True):
            dpg.add_text("Быстрые действия:", color=[200, 200, 200])
            dpg.add_button(
                label="Обновить статус",
                width=140,
                callback=lambda: _update_status(dpg, camera_controller),
                tag='update_status_button'
            )
            dpg.add_checkbox(
                label="Автообновление (10 сек)",
                tag="auto_update_checkbox",
                default_value=False,
                callback=lambda s, a: _toggle_auto_update(dpg, camera_controller, a)
            )

        dpg.add_separator()

        # Статус бар
        with dpg.group(horizontal=True):
            dpg.add_text("Статус:", color=[200, 200, 200])
            dpg.add_text("Система не инициализирована", tag="status_text")

        # Инициализируем UI элементы
        _initialize_ui_state(dpg)

        # Запускаем периодическое обновление статуса (раз в 2 секунды для начального обновления)
        dpg.set_frame_callback(5, lambda: _update_system_status(dpg, camera_controller))
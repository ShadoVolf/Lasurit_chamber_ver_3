from Ports_COM.Devices_Data import DEVICES_DATA


def _initialize_ui_state(dpg):
    """Инициализация начального состояния UI"""
    dpg.configure_item('camera_power_off_button', show=False)
    dpg.configure_item('emergency_stop_button', show=False)
    dpg.configure_item('camera_activate_button', show=False)


def _toggle_auto_update(dpg, camera_controller, enabled):
    """Включение/выключение автоматического обновления"""
    if enabled:
        dpg.set_value("status_text", "Автообновление включено (каждые 10 сек)")
        dpg.configure_item("status_text", color=[100, 255, 100])
        dpg.set_frame_callback(dpg.get_frame_count() + 600,
                               lambda: _update_system_status(dpg, camera_controller))
    else:
        dpg.set_value("status_text", "Автообновление выключено")
        dpg.configure_item("status_text", color=[255, 200, 0])


def _camera_power_on(dpg, camera_controller):
    """Подключение ко всем устройствам камеры без их активации"""
    try:
        print('Begin on')
        success, results = camera_controller.connect_and_initialize()
        print(success, results)
        if success:
            dpg.set_value("status_text", "Устройства подключены")
            dpg.configure_item("status_text", color=[0, 255, 0])

            dpg.set_value("camera_overall_status", "КАМЕРА ПОДКЛЮЧЕНА")
            dpg.configure_item("camera_overall_status", color=[0, 255, 0])

            dpg.configure_item('camera_power_on_button', show=False)
            dpg.configure_item('camera_power_off_button', show=True)
            dpg.configure_item('emergency_stop_button', show=False)
            dpg.configure_item('camera_activate_button', show=True)

            _update_status(dpg, camera_controller)
            DEVICES_DATA.set_chamber_controller(camera_controller)

            # Импортируем функции создания окон здесь, чтобы избежать циклических импортов
            from Main_window.Temperature_monitor_window import create_temperature_window
            from Main_window.BLSD_monitor_window import create_blsd20_window
            from Main_window.Temperature_table_window import create_tempearature_table_windows
            create_temperature_window(dpg)
            create_blsd20_window(dpg)
            temperature_monitor = DEVICES_DATA.get_temp_monitor()
            temperature_monitor.set_devices(DEVICES_DATA.get_owen_gui(), DEVICES_DATA.get_blsd_gui())
            temperature_monitor.show()
            create_tempearature_table_windows(dpg)
        else:
            dpg.set_value("status_text", f"Ошибка: {results}")
            dpg.configure_item("status_text", color=[255, 100, 100])

    except Exception as e:
        dpg.set_value("status_text", f"Ошибка: {str(e)}")
        dpg.configure_item("status_text", color=[255, 100, 100])


def _activate_camera(dpg, camera_controller):
    """Активация камеры (включение двигателя и терморегулятора)"""
    try:
        success, message = camera_controller.turn_on_camera()

        if success:
            dpg.set_value("status_text", "Камера активирована")
            dpg.configure_item("status_text", color=[0, 255, 0])

            dpg.set_value("camera_overall_status", "КАМЕРА АКТИВНА")
            dpg.configure_item("camera_overall_status", color=[0, 255, 150])

            dpg.configure_item('camera_power_on_button', show=False)
            dpg.configure_item('camera_power_off_button', show=True)
            dpg.configure_item('emergency_stop_button', show=True)
            dpg.configure_item('camera_activate_button', show=False)
        else:
            dpg.set_value("status_text", f"Ошибка активации: {message}")
            dpg.configure_item("status_text", color=[255, 100, 100])

    except Exception as e:
        dpg.set_value("status_text", f"Ошибка: {str(e)}")
        dpg.configure_item("status_text", color=[255, 100, 100])


def _camera_power_off(dpg, camera_controller):
    """Выключение всей системы камеры"""
    try:
        success, message = camera_controller.turn_off_camera()
        if success:
            dpg.set_value("status_text", "Камера выключена")
            dpg.configure_item("status_text", color=[255, 200, 0])

            dpg.set_value("camera_overall_status", "КАМЕРА ВЫКЛ")
            dpg.configure_item("camera_overall_status", color=[255, 0, 0])

            dpg.configure_item('camera_power_on_button', show=True)
            dpg.configure_item('camera_power_off_button', show=False)
            dpg.configure_item('emergency_stop_button', show=False)
            dpg.configure_item('camera_activate_button', show=False)

            camera_controller.disconnect_all()
            _reset_device_status(dpg)
        else:
            dpg.set_value("status_text", f"Ошибка: {message}")
            dpg.configure_item("status_text", color=[255, 100, 100])

    except Exception as e:
        dpg.set_value("status_text", f"Ошибка: {str(e)}")
        dpg.configure_item("status_text", color=[255, 100, 100])


def _emergency_stop(dpg, camera_controller):
    """Аварийная остановка"""
    try:
        success, message = camera_controller.emergency_stop()

        if success:
            dpg.set_value("status_text", message)
            dpg.configure_item("status_text", color=[255, 100, 0])

            dpg.set_value("camera_overall_status", "АВАРИЙНАЯ ОСТАНОВКА")
            dpg.configure_item("camera_overall_status", color=[255, 100, 0])

            dpg.configure_item('camera_power_on_button', show=True)
            dpg.configure_item('camera_power_off_button', show=False)
            dpg.configure_item('emergency_stop_button', show=False)

            _update_status(dpg, camera_controller)
        else:
            dpg.set_value("status_text", f"Ошибка: {message}")
            dpg.configure_item("status_text", color=[255, 100, 100])

    except Exception as e:
        dpg.set_value("status_text", f"Ошибка: {str(e)}")
        dpg.configure_item("status_text", color=[255, 100, 100])


def _update_status(dpg, camera_controller):
    """Обновление статуса системы"""
    try:
        status = camera_controller.check_connection_status()
        _update_device_status(dpg, status, camera_controller)

        if camera_controller.connected:
            _update_system_data(dpg, camera_controller)

        dpg.set_value("status_text", "Статус обновлен")
        dpg.configure_item("status_text", color=[100, 255, 100])

    except Exception as e:
        dpg.set_value("status_text", f"Ошибка обновления: {str(e)}")
        dpg.configure_item("status_text", color=[255, 100, 100])


def _update_device_status(dpg, status, camera_controller):
    """Обновление статуса отдельных устройств"""
    # TRM12
    trm12_status = status['devices'].get('TRM12', {})
    if trm12_status.get('connected'):
        dpg.set_value("trm12_status_text", "ПОДКЛЮЧЕН")
        dpg.configure_item("trm12_status_text", color=[100, 255, 100])

        try:
            info = camera_controller.trm12.get_device_info()
            if info:
                dpg.set_value("trm12_version_text", f"{str(info['device_id'])} ПО {str(info['firmware_version'])}")

            set_temp = camera_controller.get_chamber_setpoint()
            cur_temp = camera_controller.get_chamber_temperature()
            if set_temp is not None:
                dpg.set_value('trm12_temp_value', f"{float(set_temp[0]):.2f}")
                dpg.set_value('chamber_temp_text', f"{float(cur_temp[0]):.2f}")

            grad_temp, _ = camera_controller.get_gradient()
            if grad_temp is not None:
                dpg.set_value('gradient_text', f"{float(grad_temp):.2f}")

            val_temp, _ = camera_controller.get_shaft_temperature()
            if val_temp is not None:
                dpg.set_value('motor_temp_text', f"{float(val_temp):.2f}")
        except:
            pass
    else:
        dpg.set_value("trm12_status_text", "ОТКЛЮЧЕН")
        dpg.configure_item("trm12_status_text", color=[255, 100, 100])
        dpg.set_value("trm12_version_text", "Не подключен")

    # BLSD-20
    blsd20_status = status['devices'].get('BLSD20', {})
    if blsd20_status.get('connected'):
        dpg.set_value("blsd20_status_text", "ПОДКЛЮЧЕН")
        dpg.configure_item("blsd20_status_text", color=[100, 255, 100])

        try:
            info = camera_controller.blsd20.get_device_info()
            set_speed = camera_controller.blsd20.get_set_speed()
            cur_speed = camera_controller.blsd20.get_speed()
            cur_current = camera_controller.blsd20.get_current()
            if set_speed is not None:
                dpg.set_value('blsd20_speed_value', str(set_speed))
            if cur_speed is not None:
                dpg.set_value('motor_speed_text', str(cur_speed))
            if cur_current is not None:
                dpg.set_value('motor_current_text', str(cur_current))

            if info:
                dpg.set_value("blsd20_version_text",
                              f" Драйвер {str(info['Тип драйвера (hex)'])} ПО {str(info['Версия аппаратной части'])}."
                              f"{str(info['Идентификатор ПО'])}.{str(info['Версия ПО'])}")
        except:
            pass
    else:
        dpg.set_value("blsd20_status_text", "ОТКЛЮЧЕН")
        dpg.configure_item("blsd20_status_text", color=[255, 100, 100])
        dpg.set_value("blsd20_version_text", "Не подключен")

    # Релейная плата
    relay_status = status['devices'].get('Relay', {})
    if relay_status.get('connected'):
        dpg.set_value("relay_status_text", "ПОДКЛЮЧЕНА")
        camera_controller.relay.close_all_relays()
        dpg.configure_item("relay_status_text", color=[100, 255, 100])

        try:
            states = camera_controller.relay.get_relay_states()
            state_str = ""
            for i in range(1, 5):
                state = states.get(f"RELAY{i}")
                state_str += "1" if state and state.value == 1 else "0"
            dpg.set_value("relay_state_value", state_str)
        except:
            dpg.set_value("relay_state_value", "----")
    else:
        dpg.set_value("relay_status_text", "ОТКЛЮЧЕНА")
        dpg.configure_item("relay_status_text", color=[255, 100, 100])
        dpg.set_value("relay_state_value", "----")


def _update_system_data(dpg, camera_controller):
    """Обновление данных системы"""
    try:
        temp, _ = camera_controller.get_chamber_temperature()
        if temp is not None:
            dpg.set_value("chamber_temp_text", f"{temp:.2f}")

        speed = camera_controller.get_fan_speed()
        if speed is not None:
            dpg.set_value("motor_speed_text", str(speed))

        current = camera_controller.get_motor_current()
        if current is not None:
            dpg.set_value("motor_current_text", str(current))

        oven_status = camera_controller.get_oven_status()
        if oven_status:
            mode_map = {
                "Ручной": "РУЧНОЙ",
                "Автоматический": "АВТОМАТИЧЕСКИЙ",
                "Авария": "АВАРИЯ"
            }
            mode = oven_status
            dpg.set_value("system_mode_text", mode_map.get(mode, mode))
            if mode == "Авария":
                dpg.configure_item("system_mode_text", color=[255, 100, 100])
            elif mode == "Автоматический":
                dpg.configure_item("system_mode_text", color=[100, 255, 100])
            else:
                dpg.configure_item("system_mode_text", color=[200, 200, 100])

    except Exception as e:
        print(f"Ошибка обновления данных: {e}")


def _reset_device_status(dpg):
    """Сброс статуса устройств"""
    dpg.set_value("trm12_status_text", "НЕТ ДАННЫХ")
    dpg.configure_item("trm12_status_text", color=[255, 100, 100])
    dpg.set_value("trm12_temp_value", "--")
    dpg.set_value("trm12_version_text", "Не подключен")

    dpg.set_value("blsd20_status_text", "НЕТ ДАННЫХ")
    dpg.configure_item("blsd20_status_text", color=[255, 100, 100])
    dpg.set_value("blsd20_speed_value", "--")
    dpg.set_value("blsd20_version_text", "Не подключен")

    dpg.set_value("relay_status_text", "НЕТ ДАННЫХ")
    dpg.configure_item("relay_status_text", color=[255, 100, 100])
    dpg.set_value("relay_state_value", "----")

    dpg.set_value("system_mode_text", "Ожидание")
    dpg.configure_item("system_mode_text", color=[200, 200, 100])
    dpg.set_value("chamber_temp_text", "--")
    dpg.set_value("motor_current_text", "--")
    dpg.set_value("gradient_text", "--")
    dpg.set_value("motor_speed_text", "--")
    dpg.set_value("motor_temp_text", "--")


def _update_system_status(dpg, camera_controller):
    """Периодическое обновление статуса системы"""
    if camera_controller.connected:
        _update_status(dpg, camera_controller)

    auto_update_enabled = dpg.get_value("auto_update_checkbox")
    if auto_update_enabled:
        dpg.set_frame_callback(dpg.get_frame_count() + 600,
                               lambda: _update_system_status(dpg, camera_controller))
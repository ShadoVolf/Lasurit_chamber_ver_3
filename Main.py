import time

import dearpygui.dearpygui as dpg
from screeninfo import get_monitors
from Ports_COM.Devices_Data import DEVICES_DATA
from Ports_COM.client_GUI import DeviceScannerGUI
from System_Classes.Monitor_temperature_class import TemperatureMonitorWindow
import sklearn.neighbors
import scipy.stats.distributions
from fonts.Font import setup_fonts



def main():
    """Основная функция приложения с GUI сканированием"""
    dpg.create_context()

    # Настройка шрифтов
    setup_fonts(dpg, 'MonoCondensed')

    # Получение информации о мониторе
    monitors = get_monitors()
    primary_monitor = monitors[0]

    # Создаем viewport
    dpg.create_viewport(
        title='Lazurit Temperature',
        width=primary_monitor.width,
        height=primary_monitor.height,
        x_pos=primary_monitor.x,
        y_pos=primary_monitor.y
    )

    # Создаем и показываем окно сканирования
    scanner_gui = DeviceScannerGUI(dpg, primary_monitor)

    # Запускаем сканирование
    scanner_gui.start_scan()
    # Создаем монитор температуры
    temperature_monitor = TemperatureMonitorWindow(dpg)
    DEVICES_DATA.set_temp_monitor(temperature_monitor)

    dpg.setup_dearpygui()
    dpg.show_viewport()

    # Главный цикл обновления
    # Основной цикл приложения
    while dpg.is_dearpygui_running():
        # Обрабатываем сообщения из очереди
        scanner_gui.process_messages()
        if temperature_monitor.is_open():
            temperature_monitor.update()
            time.sleep(0.01)
        dpg.render_dearpygui_frame()

    dpg.destroy_context()


if __name__ == "__main__":
    main()
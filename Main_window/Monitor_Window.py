from System_Classes.Monitor_temperature_class import TemperatureMonitorWindow


def start_temperature_monitor(dpg):
    """Функция для запуска окна мониторинга температуры"""
    temperature_monitor = TemperatureMonitorWindow(dpg)
    # Показываем окно
    temperature_monitor.show()

    return temperature_monitor
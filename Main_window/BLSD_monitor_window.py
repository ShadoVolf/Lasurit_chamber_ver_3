# Создаем окно индикатора температуры
from BLSD.blsd20_gui import MotorGUI
from Ports_COM.Devices_Data import DEVICES_DATA


def create_blsd20_window(dpg):
    motor_gui = MotorGUI(dpg, tag="motor_blsd20")
    # Получение драйвера из глобального объекта
    camera_controller = DEVICES_DATA.get_chamber_controller()
    motor_gui.set_driver(camera_controller)
    DEVICES_DATA.set_blsd_gui(motor_gui)
    motor_gui.create_window(dpg)

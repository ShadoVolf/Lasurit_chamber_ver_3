from Ports_COM.Devices_Data import DEVICES_DATA
from owen.owen_gui import TPM12_GUI

# Создаем окно индикатора температуры
def create_temperature_window(dpg):
    tpm12_gui = TPM12_GUI(dpg, tag="tpm12_device")
    # Получение драйвера из глобального объекта
    camera_controller = DEVICES_DATA.get_chamber_controller()
    driver = camera_controller
    status = driver.check_connection_status()
    print(status)
    trm12_status = status['devices'].get('TRM12', {})
    print(trm12_status)
    if trm12_status.get('connected'):
        tpm12_gui.set_driver(driver)
        DEVICES_DATA.set_owen_gui(tpm12_gui)
        print("Драйвер ТРМ12 подключен к GUI")
        # Создание окна
        tpm12_gui.create_window()
    else:
        print("ВНИМАНИЕ: Драйвер ТРМ12 не найден в DEVICES_DATA")


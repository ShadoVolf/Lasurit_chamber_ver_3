from datetime import datetime

from Ports_COM.Devices_Data import DEVICES_DATA
from Ports_COM.client import UniversalDeviceScanner, DeviceType


# Получения списка подключенных устройств и их выбор если это предусмотренно опциями
def devices_search(gui_callback=None, save_log=True):
    """
    Получение списка подключенных устройств

    Args:
        gui_callback: Функция для вывода сообщений в GUI (опционально)
        save_log: Сохранять ли лог в файл (по умолчанию True)
    """
    log_messages = []

    def log_message(message, level="INFO"):
        """Вспомогательная функция для логирования"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        formatted_message = f"[{timestamp}] {level}: {message}"

        # Добавляем в список лога
        log_messages.append(formatted_message)

        # Отправляем в GUI или консоль
        if gui_callback:
            # Упрощаем сообщение для GUI
            if level == "ERROR":
                gui_callback(f"❌ {message}")
            elif level == "WARNING":
                gui_callback(f"⚠ {message}")
            elif level == "SUCCESS":
                gui_callback(f"✅ {message}")
            else:
                gui_callback(message)
        else:
            print(formatted_message)

    # Начинаем лог
    log_message("Начинаем сканирование COM-портов...")

    # Создаем сканер только для нужных типов устройств
    target_types = []
    if DEVICES_DATA.trm12.auto_select_com:
        target_types.append(DeviceType.TRM12)
        log_message("Включен поиск ТРМ12")
    if DEVICES_DATA.blsd20.auto_select_com:
        target_types.append(DeviceType.BLSD20)
        log_message("Включен поиск BLSD-20")
    if DEVICES_DATA.rs232_relay.auto_select_com:
        target_types.append(DeviceType.RS232_4PIN_RELAY)
        log_message("Включен поиск RS232-4pin-Relay")

    if not target_types:
        log_message("Автоматический выбор COM-портов отключен для всех устройств", "WARNING")
        return

    scanner = UniversalDeviceScanner(verbose=False, target_types=target_types)

    # Переопределяем логгер сканера
    original_log = scanner._log

    def custom_log(message, level="INFO"):
        original_log(message, level)
        log_message(message, level)

    scanner._log = custom_log

    devices = scanner.scan_ports()

    if not gui_callback:  # Выводим в консоль только если нет GUI
        scanner.print_results()

    # Находим устройства по типам
    trm12_device = next((d for d in devices if d.device_type == DeviceType.TRM12), None)
    blsd20_device = next((d for d in devices if d.device_type == DeviceType.BLSD20), None)
    rs232_relay_device = next((d for d in devices if d.device_type == DeviceType.RS232_4PIN_RELAY), None)

    # Сохраняем список подключенных устройств
    DEVICES_DATA.set_devices(devices)

    if DEVICES_DATA.trm12.auto_select_com:
        if trm12_device:
            log_message(f'ТРМ 12 выбран: {trm12_device}', "SUCCESS")
            DEVICES_DATA.trm12.com_port = trm12_device.port
            DEVICES_DATA.trm12.address = trm12_device.address
            DEVICES_DATA.trm12.baudrate = trm12_device.baudrate
        else:
            log_message('ТРМ 12 не найден', "WARNING")

    if DEVICES_DATA.blsd20.auto_select_com:
        if blsd20_device:
            log_message(f'BLSD-20 выбран: {blsd20_device}', "SUCCESS")
            DEVICES_DATA.blsd20.com_port = blsd20_device.port
            DEVICES_DATA.blsd20.address = blsd20_device.address
            DEVICES_DATA.blsd20.baudrate = blsd20_device.baudrate
        else:
            log_message('BLSD-20 не найден', "WARNING")

    if DEVICES_DATA.rs232_relay.auto_select_com:
        if rs232_relay_device:
            log_message(f'RS232-4pin-Relay выбран: {rs232_relay_device}', "SUCCESS")
            DEVICES_DATA.rs232_relay.com_port = rs232_relay_device.port
            DEVICES_DATA.rs232_relay.address = rs232_relay_device.address
            DEVICES_DATA.rs232_relay.baudrate = rs232_relay_device.baudrate
        else:
            log_message('RS232-4pin-Relay не найден', "WARNING")

    log_message(f"Сканирование завершено. Найдено устройств: {len(devices)}", "INFO")

    # Сохраняем лог в файл если требуется
    if save_log:
        try:
            filename = "auto_select.txt"
            with open(filename, 'w', encoding='utf-8') as f:
                f.write("=" * 60 + "\n")
                f.write(f"Лог автоматического выбора устройств\n")
                f.write(f"Дата и время: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write("=" * 60 + "\n\n")

                for message in log_messages:
                    f.write(message + "\n")

                # Итоговая информация
                f.write("\n" + "=" * 60 + "\n")
                f.write("ИТОГИ СКАНИРОВАНИЯ:\n")
                f.write(f"Найдено устройств: {len(devices)}\n")

                for i, device in enumerate(devices, 1):
                    f.write(f"{i}. {device}\n")

                f.write("\nТекущие настройки:\n")
                if DEVICES_DATA.trm12.auto_select_com and DEVICES_DATA.trm12.com_port:
                    f.write(
                        f"ТРМ12: COM{DEVICES_DATA.trm12.com_port}, адрес {DEVICES_DATA.trm12.address}, {DEVICES_DATA.trm12.baudrate} бод\n")
                if DEVICES_DATA.blsd20.auto_select_com and DEVICES_DATA.blsd20.com_port:
                    f.write(
                        f"BLSD-20: COM{DEVICES_DATA.blsd20.com_port}, адрес {DEVICES_DATA.blsd20.address}, {DEVICES_DATA.blsd20.baudrate} бод\n")
                if DEVICES_DATA.rs232_relay.auto_select_com and DEVICES_DATA.rs232_relay.com_port:
                    f.write(
                        f"RS232-4pin-Relay: COM{DEVICES_DATA.rs232_relay.com_port}, {DEVICES_DATA.rs232_relay.baudrate} бод (без адреса)\n")

                f.write("=" * 60 + "\n")

            if not gui_callback:
                print(f"Лог сохранен в файл: {filename}")
        except Exception as e:
            log_message(f"Ошибка сохранения лога: {str(e)}", "ERROR")

    return devices
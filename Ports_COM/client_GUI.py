
from Main_window.Chamber_Status_Window import create_info_window
from Ports_COM.Devices_Data import DEVICES_DATA
from Ports_COM.client import UniversalDeviceScanner, DeviceType
import threading
import queue
import time
from datetime import datetime
import traceback


class DeviceScannerGUI:
    """Класс для графического отображения процесса сканирования устройств"""

    def __init__(self, dpg_context, primary_monitor):
        self.dpg = dpg_context
        self.scanning = False
        self.scan_complete = False
        self.message_queue = queue.Queue()
        self.scan_result = None
        self.log_messages = []  # Список для хранения всех сообщений лога

        # Размеры окна сканирования (увеличено по вертикали)
        scan_width = 650  # Увеличили ширину для большего лога
        scan_height = 730  # Увеличили высоту

        # Создаем окно сканирования
        with self.dpg.window(
                label="Поиск оборудования",
                width=scan_width,
                height=scan_height,
                no_collapse=True,
                no_close=True,
                no_resize=True,
                pos=[
                    (primary_monitor.width - scan_width) // 2,
                    (primary_monitor.height - scan_height) // 2
                ],
                tag="scan_window"
        ):
            # Заголовок
            self.dpg.add_spacer(height=10)
            with self.dpg.group(horizontal=True):
                self.dpg.add_spacer(width=20)
                self.dpg.add_text("🔍", tag="scan_icon", color=(70, 130, 180))
                self.dpg.add_text("Поиск подключенных устройств...", tag="scan_title")

            self.dpg.add_spacer(height=20)
            self.dpg.add_separator()
            self.dpg.add_spacer(height=10)

            # Область вывода сообщений
            self.dpg.add_text("Статус:", tag="status_label")
            self.dpg.add_spacer(height=5)
            with self.dpg.child_window(
                    height=350,  # Увеличиваем область лога для большего объема сообщений
                    width=-20,  # Ширина с небольшим отступом
                    border=True,
                    tag="log_window"
            ):
                self.log_text_item = self.dpg.add_text("Инициализация сканирования...", tag="log_text")

            self.dpg.add_spacer(height=20)

            # Прогресс-бар
            self.dpg.add_text("Прогресс:", tag="progress_label")
            self.dpg.add_spacer(height=5)
            self.progress_bar = self.dpg.add_progress_bar(
                default_value=0,
                width=-1,
                height=20,
                tag="progress_bar"
            )

            # Индикатор работы
            self.dpg.add_spacer(height=10)
            with self.dpg.group(horizontal=True):
                self.dpg.add_spacer(width=20)
                self.status_indicator = self.dpg.add_text("●", color=(255, 50, 50), tag="status_indicator")
                self.status_text_item = self.dpg.add_text("Сканирование...", tag="status_text")

            self.dpg.add_spacer(height=20)

            # Статистика найденных устройств
            with self.dpg.group(horizontal=True, tag="stats_group"):
                self.dpg.add_text("Найдено устройств: ", tag="stats_label")
                self.stats_count = self.dpg.add_text("0", tag="stats_count", color=(0, 200, 0))
                self.dpg.add_spacer(width=20)
                self.dpg.add_text("Активных поисков: ", tag="search_label")
                self.search_count = self.dpg.add_text("0", tag="search_count", color=(255, 165, 0))

            self.dpg.add_spacer(height=15)

            # Группа кнопок
            with self.dpg.group(horizontal=True, tag="buttons_group"):
                self.dpg.add_spacer()
                # Кнопка отмены (скрыта по умолчанию)
                self.cancel_button = self.dpg.add_button(
                    label="Отмена",
                    width=100,
                    height=30,
                    tag="cancel_button",
                    callback=self.cancel_scan,
                    show=True
                )
                # Кнопка ОК (скрыта до завершения)
                self.ok_button = self.dpg.add_button(
                    label="ОК",
                    width=100,
                    height=30,
                    tag="ok_button",
                    callback=lambda: self.close_window(),
                    show=False,
                    enabled=False
                )
                self.dpg.add_spacer()

    def add_log_message(self, message):
        """Добавляет сообщение в список лога"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_messages.append(f"[{timestamp}] {message}")

    def update_log(self, message):
        """Обновление лога в GUI"""
        try:
            if not self.dpg.does_item_exist("scan_window"):
                return

            current_text = self.dpg.get_value("log_text")
            # Ограничиваем длину лога для производительности
            if len(current_text) > 3000:
                lines = current_text.split('\n')
                current_text = '\n'.join(lines[-40:])  # Оставляем последние 40 строк

            new_text = current_text + "\n" + message
            self.dpg.set_value("log_text", new_text)
            self.add_log_message(message)  # Сохраняем в список

            # Автопрокрутка
            self.dpg.configure_item("log_window", autosize_y=False, height=350)
            self.dpg.set_y_scroll("log_window", -1.0)
        except Exception as e:
            print(f"Ошибка обновления лога: {e}")
            print(traceback.format_exc())

    def update_stats(self, found_count, active_searches):
        """Обновление статистики найденных устройств"""
        try:
            if self.dpg.does_item_exist("stats_count"):
                self.dpg.set_value("stats_count", str(found_count))

            if self.dpg.does_item_exist("search_count"):
                self.dpg.set_value("search_count", str(active_searches))
        except Exception as e:
            print(f"Ошибка обновления статистики: {e}")

    def save_log_to_file(self):
        """Сохранение лога в файл"""
        try:
            filename = "auto_select.txt"
            with open(filename, 'w', encoding='utf-8') as f:
                f.write("=" * 70 + "\n")
                f.write(f"Лог автоматического выбора устройств\n")
                f.write(f"Дата и время: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write("=" * 70 + "\n\n")

                for message in self.log_messages:
                    f.write(message + "\n")

                # Добавляем итоговую информацию
                f.write("\n" + "=" * 70 + "\n")
                f.write("ИТОГИ СКАНИРОВАНИЯ:\n")

                if self.scan_result:
                    f.write(f"Найдено устройств: {len(self.scan_result)}\n")
                    for i, device in enumerate(self.scan_result, 1):
                        f.write(f"{i}. {device}\n")
                        # Добавляем дополнительную информацию об устройстве
                        if hasattr(device, 'additional_info') and device.additional_info:
                            for key, value in device.additional_info.items():
                                if key == 'relay_states' and isinstance(value, dict):
                                    f.write(f"     Состояния реле:\n")
                                    for relay, state in value.items():
                                        f.write(f"       {relay}: {state}\n")
                                else:
                                    f.write(f"     {key}: {value}\n")
                else:
                    f.write("Устройства не найдены\n")

                f.write("\nТекущие настройки:\n")
                if DEVICES_DATA.trm12.auto_select_com:
                    trm12_port = getattr(DEVICES_DATA.trm12, 'com_port', 'не указан')
                    trm12_address = getattr(DEVICES_DATA.trm12, 'address', 'не указан')
                    trm12_baudrate = getattr(DEVICES_DATA.trm12, 'baudrate', 'не указан')
                    f.write(f"ТРМ12: COM{trm12_port}, адрес {trm12_address}, {trm12_baudrate} бод\n")
                if DEVICES_DATA.blsd20.auto_select_com:
                    blsd20_port = getattr(DEVICES_DATA.blsd20, 'com_port', 'не указан')
                    blsd20_address = getattr(DEVICES_DATA.blsd20, 'address', 'не указан')
                    blsd20_baudrate = getattr(DEVICES_DATA.blsd20, 'baudrate', 'не указан')
                    f.write(f"BLSD-20: COM{blsd20_port}, адрес {blsd20_address}, {blsd20_baudrate} бод\n")
                if DEVICES_DATA.rs232_relay.auto_select_com:
                    relay_port = getattr(DEVICES_DATA.rs232_relay, 'com_port', 'не указан')
                    relay_baudrate = getattr(DEVICES_DATA.rs232_relay, 'baudrate', 'не указан')
                    f.write(f"RS232-4pin-Relay: COM{relay_port}, {relay_baudrate} бод (без адреса)\n")

                f.write("=" * 70 + "\n")

            self.update_log(f"Лог сохранен в файл: {filename}")
            return True
        except Exception as e:
            self.update_log(f"Ошибка сохранения лога: {str(e)}")
            return False

    def update_progress(self, value):
        """Обновление прогресс-бара"""
        try:
            if self.dpg.does_item_exist("progress_bar"):
                self.dpg.set_value("progress_bar", value / 100)
        except Exception as e:
            print(f"Ошибка обновления прогресс-бара: {e}")

    def update_status(self, text, color=None):
        """Обновление статуса"""
        try:
            if self.dpg.does_item_exist("status_text"):
                self.dpg.set_value("status_text", text)
                if color and self.dpg.does_item_exist("status_indicator"):
                    self.dpg.configure_item("status_indicator", color=color)
        except Exception as e:
            print(f"Ошибка обновления статуса: {e}")

    def cancel_scan(self):
        """Отмена сканирования"""
        if not self.scan_complete:
            self.scanning = False
            self.update_status("Сканирование отменено", (255, 165, 0))
            self.update_log("Сканирование было отменено пользователем")

    def close_window(self):
        """Закрытие окна сканирования"""
        if self.scan_complete:
            # Сохраняем лог перед закрытием
            self.save_log_to_file()

            # Закрываем окно
            if self.dpg.does_item_exist("scan_window"):
                self.dpg.delete_item("scan_window")

            # Создаем основное окно приложения

            create_info_window(self.dpg)


    def show_ok_button(self):
        """Показать кнопку ОК и скрыть кнопку Отмена"""
        try:
            if self.dpg.does_item_exist("cancel_button"):
                self.dpg.configure_item("cancel_button", show=False)
            if self.dpg.does_item_exist("ok_button"):
                self.dpg.configure_item("ok_button", show=True, enabled=True)
        except Exception as e:
            print(f"Ошибка при обновлении кнопок: {e}")

    def scan_devices_thread(self):
        """Поток для сканирования устройств с GUI обновлением"""
        try:
            self.scanning = True
            self.scan_complete = False

            # Используем очередь для передачи сообщений в основной поток
            def send_to_gui(message_type, data):
                self.message_queue.put((message_type, data))

            send_to_gui("log", "Начинаем сканирование COM-портов...")
            send_to_gui("progress", 5)

            # Определяем типы устройств для сканирования
            target_types = []
            active_search_count = 0

            if DEVICES_DATA.trm12.auto_select_com:
                target_types.append(DeviceType.TRM12)
                active_search_count += 1
                send_to_gui("log", "Включен поиск ТРМ12")

            if DEVICES_DATA.blsd20.auto_select_com:
                target_types.append(DeviceType.BLSD20)
                active_search_count += 1
                send_to_gui("log", "Включен поиск BLSD-20")

            if DEVICES_DATA.rs232_relay.auto_select_com:
                target_types.append(DeviceType.RS232_4PIN_RELAY)
                active_search_count += 1
                send_to_gui("log", "Включен поиск RS232-4pin-Relay")

            send_to_gui("stats", (0, active_search_count))
            send_to_gui("progress", 10)
            time.sleep(0.5)

            if not target_types:
                send_to_gui("log", "Автоматический выбор COM-портов отключен для всех устройств")
                send_to_gui("status", ("Завершено", (0, 255, 0)))
                send_to_gui("progress", 100)
                self.scanning = False
                self.scan_complete = True
                send_to_gui("show_ok", True)
                return

            # Создаем сканер
            send_to_gui("log", "Создание сканера устройств...")
            scanner = UniversalDeviceScanner(verbose=False, target_types=target_types)

            # Переопределяем метод _log для вывода в GUI
            original_log = scanner._log

            def gui_log(message, level="INFO"):
                original_log(message, level)
                log_message = message
                if level == "ERROR":
                    log_message = f"❌ {message}"
                elif level == "WARNING":
                    log_message = f"⚠ {message}"
                elif level == "SUCCESS":
                    log_message = f"✅ {message}"
                send_to_gui("log", log_message)

            scanner._log = gui_log

            send_to_gui("progress", 15)
            send_to_gui("log", "Получение списка COM-портов...")

            # Получаем порты
            try:
                import serial.tools.list_ports
                ports = list(serial.tools.list_ports.comports())
                send_to_gui("log", f"Найдено {len(ports)} COM-портов")
                send_to_gui("progress", 20)

                for i, port in enumerate(ports):
                    if not self.scanning:
                        send_to_gui("log", "Сканирование прервано")
                        self.scan_complete = True
                        send_to_gui("show_ok", True)
                        return

                    progress = 20 + (i / len(ports) * 50)
                    send_to_gui("progress", int(progress))
                    send_to_gui("log", f"Сканируем порт: {port.device} - {port.description}")
                    time.sleep(0.05)

            except Exception as e:
                send_to_gui("log", f"Ошибка получения портов: {str(e)}")

            send_to_gui("progress", 70)
            send_to_gui("log", "Запуск сканирования устройств...")

            # Запускаем сканирование
            devices = scanner.scan_ports()

            send_to_gui("progress", 85)
            send_to_gui("stats", (len(devices), active_search_count))

            # Находим устройства по типам
            trm12_device = next((d for d in devices if d.device_type == DeviceType.TRM12), None)
            blsd20_device = next((d for d in devices if d.device_type == DeviceType.BLSD20), None)
            rs232_relay_device = next((d for d in devices if d.device_type == DeviceType.RS232_4PIN_RELAY), None)

            # Сохраняем список подключенных устройств
            DEVICES_DATA.set_devices(devices)

            send_to_gui("progress", 90)

            if DEVICES_DATA.trm12.auto_select_com:
                if trm12_device:
                    send_to_gui("log", f'✅ ТРМ 12 найден: {trm12_device}')
                    DEVICES_DATA.trm12.com_port = trm12_device.port
                    DEVICES_DATA.trm12.address = trm12_device.address
                    DEVICES_DATA.trm12.baudrate = trm12_device.baudrate
                else:
                    send_to_gui("log", '❌ ТРМ 12 не найден')

            if DEVICES_DATA.blsd20.auto_select_com:
                if blsd20_device:
                    send_to_gui("log", f'✅ BLSD-20 найден: {blsd20_device}')
                    DEVICES_DATA.blsd20.com_port = blsd20_device.port
                    DEVICES_DATA.blsd20.address = blsd20_device.address
                    DEVICES_DATA.blsd20.baudrate = blsd20_device.baudrate
                else:
                    send_to_gui("log", '❌ BLSD-20 не найден')

            if DEVICES_DATA.rs232_relay.auto_select_com:
                if rs232_relay_device:
                    send_to_gui("log", f'✅ RS232-4pin-Relay найден: {rs232_relay_device}')
                    DEVICES_DATA.rs232_relay.com_port = rs232_relay_device.port
                    DEVICES_DATA.rs232_relay.address = rs232_relay_device.address
                    DEVICES_DATA.rs232_relay.baudrate = rs232_relay_device.baudrate
                else:
                    send_to_gui("log", '❌ RS232-4pin-Relay не найден')

            send_to_gui("progress", 95)

            # Выводим итоговую информацию о найденных устройствах
            send_to_gui("log", "\n" + "=" * 50)
            send_to_gui("log", "ИТОГИ СКАНИРОВАНИЯ:")
            device_count = len(devices)
            send_to_gui("log", f"Всего найдено устройств: {device_count}")

            for i, device in enumerate(devices, 1):
                device_type_str = device.device_type.value
                port_str = device.port
                baud_str = f", {device.baudrate} бод" if device.baudrate else ""
                addr_str = f", адрес {device.address}" if device.address != 0 else ""
                send_to_gui("log", f"  {i}. {device_type_str} на {port_str}{addr_str}{baud_str}")

            send_to_gui("progress", 100)
            send_to_gui("status", ("Завершено", (0, 255, 0)))
            send_to_gui("log", "=" * 50)
            send_to_gui("log", f"Сканирование завершено.")

            # Сохраняем результат
            self.scan_result = devices

            # Меняем кнопки
            self.scanning = False
            self.scan_complete = True
            send_to_gui("show_ok", True)

        except Exception as e:
            send_to_gui("log", f"❌ Ошибка при сканировании: {str(e)}")
            send_to_gui("status", ("Ошибка", (255, 0, 0)))
            self.scanning = False
            self.scan_complete = True
            send_to_gui("show_ok", True)

    def start_scan(self):
        """Запуск сканирования в отдельном потоке"""
        scan_thread = threading.Thread(target=self.scan_devices_thread, daemon=True)
        scan_thread.start()
        return scan_thread

    def process_messages(self):
        """Обработка сообщений из очереди в основном потоке"""
        try:
            while True:
                message_type, data = self.message_queue.get_nowait()

                if message_type == "log":
                    self.update_log(data)
                elif message_type == "progress":
                    self.update_progress(data)
                elif message_type == "status":
                    self.update_status(data[0], data[1])
                elif message_type == "show_ok":
                    self.show_ok_button()
                elif message_type == "stats":
                    self.update_stats(data[0], data[1])

        except queue.Empty:
            pass
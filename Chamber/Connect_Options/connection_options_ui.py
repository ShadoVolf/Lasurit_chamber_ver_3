from typing import List

from Ports_COM.Devices_Data import DEVICES_DATA


class ConnectionOptionsUI:
    """UI компоненты для окна настроек соединения (только для просмотра)"""

    def __init__(self, dpg_module, tag_prefix: str = "connection_options"):
        self.dpg = dpg_module
        self.tag_prefix = tag_prefix

        # Списки допустимых значений
        self.baudrates = [110, 300, 600, 1200, 2400, 4800, 9600, 14400,
                          19200, 38400, 57600, 115200, 128000, 256000]
        self.parity_options = ["N", "E", "O", "M", "S"]
        self.data_bits_options = [5, 6, 7, 8]
        self.stop_bits_options = [1, 1.5, 2]

    def create_window(self) -> str:
        """Создание окна настроек (только для просмотра)"""
        dpg = self.dpg
        tag = self.tag_prefix + "_window"

        with dpg.window(
                label="Настройки соединения RS485/RS232",
                tag=tag,
                width=850,
                height=700,  # Уменьшена высота окна
                show=False,
                no_resize=True,
                no_collapse=True,
                no_close=False,
                no_move=False,
                no_scrollbar=False,
                no_title_bar=False,
                modal=False
        ):
            # Основной контейнер
            with dpg.group():
                # Вкладки для разных устройств
                with dpg.tab_bar():
                    # Вкладка с общими настройками
                    with dpg.tab(label="Общие настройки"):
                        self._create_common_settings_tab()

                    # Вкладка для TRM-12
                    with dpg.tab(label="TRM-12"):
                        self._create_device_tab("TRM-12", DEVICES_DATA.trm12, "Контроллер температуры")

                    # Вкладка для BLSD-20
                    with dpg.tab(label="BLSD-20"):
                        self._create_device_tab("BLSD-20", DEVICES_DATA.blsd20, "Контроллер вентилятора")

                    # Вкладка для RS232-4pin-Relay
                    with dpg.tab(label="RS232-4pin-Relay"):
                        self._create_relay_tab()

                dpg.add_spacer(height=15)
                dpg.add_separator()
                dpg.add_spacer(height=10)

                # Кнопка закрытия
                with dpg.group(horizontal=True):
                    dpg.add_spacer(width=320)
                    dpg.add_button(
                        label="Закрыть",
                        callback=lambda: dpg.hide_item(tag),
                        width=120,
                        height=35
                    )
                    dpg.add_spacer(width=320)

        return tag

    def _create_common_settings_tab(self):
        """Создание вкладки общих настроек (только чтение)"""
        dpg = self.dpg

        with dpg.group():
            dpg.add_text("Общие параметры подключения", color=[255, 255, 255])
            dpg.add_separator()
            dpg.add_spacer(height=15)

            # Информация о настройках
            with dpg.group():
                dpg.add_text("Режим работы системы:", color=[200, 200, 255])
                dpg.add_spacer(height=5)

                # Информация о файле настроек
                with dpg.group(horizontal=True):
                    dpg.add_text("Файл настроек:", color=[200, 200, 200])
                    dpg.add_text("connection_settings.json", color=[255, 255, 255])

                dpg.add_spacer(height=5)

                # Последнее обновление
                with dpg.group(horizontal=True):
                    dpg.add_text("Настройки загружены:", color=[200, 200, 200])
                    dpg.add_text("Из активного конфигурационного файла", color=[100, 255, 100])

            dpg.add_spacer(height=20)

            # Информация о доступных портах
            dpg.add_text("Доступные COM порты в системе:", color=[200, 200, 255])
            dpg.add_spacer(height=5)

            # Получаем список доступных портов
            available_ports = self._get_available_ports()

            if available_ports:
                with dpg.table(header_row=False, borders_innerH=True, borders_outerH=True,
                               borders_innerV=True, borders_outerV=True):
                    dpg.add_table_column(width=100)
                    dpg.add_table_column(width=200)
                    dpg.add_table_column(width=100)

                    for i, port in enumerate(available_ports):
                        with dpg.table_row():
                            dpg.add_text(f"Порт {i + 1}:", color=[200, 200, 200])
                            dpg.add_text(port, color=[255, 255, 255])
                            dpg.add_text("Доступен", color=[100, 255, 100])
            else:
                dpg.add_text("COM порты не обнаружены", color=[255, 100, 100])

            dpg.add_spacer(height=20)

            # Системная информация
            dpg.add_text("Системная информация:", color=[200, 200, 255])
            dpg.add_spacer(height=5)

            with dpg.group():
                with dpg.group(horizontal=True):
                    dpg.add_text("Активных драйверов устройств:", color=[200, 200, 200])
                    driver_count = len(DEVICES_DATA.device_drivers_dict) if hasattr(DEVICES_DATA,
                                                                                    'device_drivers_dict') else 0
                    dpg.add_text(str(driver_count), color=[255, 255, 255])

                with dpg.group(horizontal=True):
                    dpg.add_text("Подключенных устройств:", color=[200, 200, 200])
                    connected_count = len(DEVICES_DATA.connected_devices) if DEVICES_DATA.connected_devices else 0
                    dpg.add_text(str(connected_count), color=[255, 255, 255])

    def _create_device_tab(self, device_name: str, device_params, description: str):
        """Создание вкладки для устройства (только чтение)"""
        dpg = self.dpg

        with dpg.group():
            # Заголовок
            with dpg.group(horizontal=True):
                dpg.add_text(device_name, color=[100, 200, 255])
                dpg.add_text(description, color=[200, 200, 200])

            dpg.add_separator()
            dpg.add_spacer(height=15)

            # Настройки COM порта
            dpg.add_text("Настройки COM порта", color=[255, 255, 255])
            dpg.add_spacer(height=5)

            with dpg.table(header_row=False, borders_innerH=True):
                dpg.add_table_column(width=250)
                dpg.add_table_column(width=200)

                with dpg.table_row():
                    dpg.add_text("Автоматический выбор COM порта:", color=[200, 200, 200])
                    dpg.add_text("Включен" if device_params.auto_select_com else "Отключен",
                                 color=[100, 255, 100] if device_params.auto_select_com else [255, 100, 100])

                with dpg.table_row():
                    dpg.add_text("COM порт:", color=[200, 200, 200])
                    dpg.add_text(device_params.com_port, color=[255, 255, 255])

            dpg.add_spacer(height=15)

            # Основные параметры
            dpg.add_text("Основные параметры", color=[255, 255, 255])
            dpg.add_spacer(height=5)

            with dpg.table(header_row=False, borders_innerH=True):
                dpg.add_table_column(width=200)
                dpg.add_table_column(width=150)

                with dpg.table_row():
                    dpg.add_text("Адрес устройства Modbus:", color=[200, 200, 200])
                    dpg.add_text(str(device_params.address), color=[255, 255, 255])

                with dpg.table_row():
                    dpg.add_text("Скорость передачи (baudrate):", color=[200, 200, 200])
                    dpg.add_text(str(device_params.baudrate), color=[255, 255, 255])

            dpg.add_spacer(height=15)

            # Параметры связи
            dpg.add_text("Параметры связи", color=[255, 255, 255])
            dpg.add_spacer(height=5)

            with dpg.table(header_row=False, borders_innerH=True):
                dpg.add_table_column(width=120)
                dpg.add_table_column(width=120)
                dpg.add_table_column(width=120)

                with dpg.table_row():
                    dpg.add_text("Биты данных:", color=[200, 200, 200])
                    dpg.add_text(str(device_params.data_bits), color=[255, 255, 255])

                    dpg.add_text("Стоповые биты:", color=[200, 200, 200])
                    dpg.add_text(str(device_params.stop_bits), color=[255, 255, 255])

                    dpg.add_text("Четность:", color=[200, 200, 200])
                    parity_display = {"N": "None", "E": "Even", "O": "Odd", "M": "Mark", "S": "Space"}
                    dpg.add_text(parity_display.get(device_params.parity, "Unknown"), color=[255, 255, 255])

            dpg.add_spacer(height=15)

            # Таймауты
            dpg.add_text("Таймауты", color=[255, 255, 255])
            dpg.add_spacer(height=5)

            with dpg.table(header_row=False, borders_innerH=True):
                dpg.add_table_column(width=200)
                dpg.add_table_column(width=100)

                with dpg.table_row():
                    dpg.add_text("Таймаут чтения (секунды):", color=[200, 200, 200])
                    dpg.add_text(f"{device_params.timeout:.1f}", color=[255, 255, 255])

                with dpg.table_row():
                    dpg.add_text("Таймаут записи (секунды):", color=[200, 200, 200])
                    if hasattr(device_params, 'write_timeout'):
                        dpg.add_text(f"{device_params.write_timeout:.1f}", color=[255, 255, 255])
                    else:
                        dpg.add_text("1.0", color=[255, 255, 255])

            dpg.add_spacer(height=15)

            # Статус подключения
            dpg.add_text("Статус подключения", color=[255, 255, 255])
            dpg.add_spacer(height=5)

            with dpg.group(horizontal=True):
                status_color = [100, 255, 100] if device_params.connected else [255, 100, 100]
                status_text = "ПОДКЛЮЧЕНО" if device_params.connected else "НЕ ПОДКЛЮЧЕНО"

                dpg.add_text("Состояние: ", color=[200, 200, 200])
                dpg.add_text(status_text, color=status_color)

    def _create_relay_tab(self):
        """Создание вкладки для реле (только чтение)"""
        dpg = self.dpg
        relay_params = DEVICES_DATA.rs232_relay

        with dpg.group():
            # Заголовок
            with dpg.group(horizontal=True):
                dpg.add_text("RS232-4pin-Relay", color=[100, 200, 255])
                dpg.add_text("Релейный модуль RS232", color=[200, 200, 200])

            dpg.add_separator()
            dpg.add_spacer(height=15)

            # Настройки COM порта
            dpg.add_text("Настройки COM порта", color=[255, 255, 255])
            dpg.add_spacer(height=5)

            with dpg.table(header_row=False, borders_innerH=True):
                dpg.add_table_column(width=250)
                dpg.add_table_column(width=200)

                with dpg.table_row():
                    dpg.add_text("Автоматический выбор COM порта:", color=[200, 200, 200])
                    dpg.add_text("Включен" if relay_params.auto_select_com else "Отключен",
                                 color=[100, 255, 100] if relay_params.auto_select_com else [255, 100, 100])

                with dpg.table_row():
                    dpg.add_text("COM порт:", color=[200, 200, 200])
                    dpg.add_text(relay_params.com_port, color=[255, 255, 255])

            dpg.add_spacer(height=15)

            # Основные параметры
            dpg.add_text("Основные параметры", color=[255, 255, 255])
            dpg.add_spacer(height=5)

            with dpg.table(header_row=False, borders_innerH=True):
                dpg.add_table_column(width=200)
                dpg.add_table_column(width=150)

                with dpg.table_row():
                    dpg.add_text("Адрес устройства:", color=[200, 200, 200])
                    dpg.add_text(str(relay_params.address), color=[255, 255, 255])

                with dpg.table_row():
                    dpg.add_text("Скорость передачи (baudrate):", color=[200, 200, 200])
                    dpg.add_text(str(relay_params.baudrate), color=[255, 255, 255])

            dpg.add_spacer(height=15)

            # Параметры связи
            dpg.add_text("Параметры связи", color=[255, 255, 255])
            dpg.add_spacer(height=5)

            with dpg.table(header_row=False, borders_innerH=True):
                dpg.add_table_column(width=120)
                dpg.add_table_column(width=120)
                dpg.add_table_column(width=120)

                with dpg.table_row():
                    dpg.add_text("Биты данных:", color=[200, 200, 200])
                    dpg.add_text(str(relay_params.data_bits), color=[255, 255, 255])

                    dpg.add_text("Стоповые биты:", color=[200, 200, 200])
                    dpg.add_text(str(relay_params.stop_bits), color=[255, 255, 255])

                    dpg.add_text("Четность:", color=[200, 200, 200])
                    parity_display = {"N": "None", "E": "Even", "O": "Odd", "M": "Mark", "S": "Space"}
                    dpg.add_text(parity_display.get(relay_params.parity, "Unknown"), color=[255, 255, 255])

            dpg.add_spacer(height=15)

            # Таймауты
            dpg.add_text("Таймауты", color=[255, 255, 255])
            dpg.add_spacer(height=5)

            with dpg.table(header_row=False, borders_innerH=True):
                dpg.add_table_column(width=200)
                dpg.add_table_column(width=100)

                with dpg.table_row():
                    dpg.add_text("Таймаут чтения (секунды):", color=[200, 200, 200])
                    dpg.add_text(f"{relay_params.timeout:.1f}", color=[255, 255, 255])

            dpg.add_spacer(height=15)

            # Статус подключения
            dpg.add_text("Статус подключения", color=[255, 255, 255])
            dpg.add_spacer(height=5)

            with dpg.group(horizontal=True):
                status_color = [100, 255, 100] if relay_params.connected else [255, 100, 100]
                status_text = "ПОДКЛЮЧЕНО" if relay_params.connected else "НЕ ПОДКЛЮЧЕНО"

                dpg.add_text("Состояние: ", color=[200, 200, 200])
                dpg.add_text(status_text, color=status_color)

    def _get_available_ports(self) -> List[str]:
        """Получение списка доступных COM портов"""
        try:
            import serial.tools.list_ports
            ports = [port.device for port in serial.tools.list_ports.comports()]
            return ports
        except ImportError:
            return ["COM1", "COM2", "COM3", "COM4"]
        except Exception:
            return []
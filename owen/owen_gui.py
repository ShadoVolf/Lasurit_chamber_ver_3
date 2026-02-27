"""
Модуль графического интерфейса для контроллера ТРМ12.
Добавлена функциональность коррекции температуры по полиному.
"""
import json
import time
import threading
import numpy as np
from typing import Optional
from enum import Enum
from pathlib import Path

from Chamber.chamber_process import ChamberProcess, ProcessStatus
from Ports_COM.Devices_Data import DEVICES_DATA
from owen.Temp_Corrector_class import PolynomialCorrector
from owen.algorithm_settings_dialog import show_algorithm_settings_dialog
from owen.correction_dialog import show_correction_dialog
from owen.correction_plot_dialog import show_correction_plot_dialog
from owen.hold_time_dialog import show_hold_time_dialog
from owen.pid_dialog import show_pid_dialog
from owen.setpoint_dialog import show_setpoint_dialog
from owen.algorithm_settings_dialog import _load_settings_from_file, _save_settings_to_file

# Импорты вынесенных диалогов



class ChamberStatus(Enum):
    HEATING = "Нагрев"
    COOLING = "Охлаждение"
    STOPPED = "Остановка"
    STANDBY = "Ожидание"
    ALARM = "Авария"
    STABILIZING = "Стабилизация"   # новое
    HOLDING = "Выдержка"           # новое


# Глобальный флаг для проверки создания тем
_TPM12_THEMES_CREATED = False


def create_tpm12_themes(dpg, str_tag):
    """Создание тем для индикаторов ТРМ12 (вызывается один раз)"""
    global _TPM12_THEMES_CREATED

    if _TPM12_THEMES_CREATED:
        return

    # Тема для температуры канала 1
    with dpg.theme(tag="temp_theme_pv1"):
        with dpg.theme_component(dpg.mvChildWindow):
            dpg.add_theme_color(dpg.mvThemeCol_ChildBg, (204, 153, 255, 80))
            dpg.add_theme_style(dpg.mvStyleVar_ChildRounding, 12)
            dpg.add_theme_style(dpg.mvStyleVar_WindowPadding, 20, 20)
        with dpg.theme_component(dpg.mvText):
            dpg.add_theme_color(dpg.mvThemeCol_Text, (204, 153, 255))

    # Тема для температуры канала 2
    with dpg.theme(tag="temp_theme_pv2"):
        with dpg.theme_component(dpg.mvChildWindow):
            dpg.add_theme_color(dpg.mvThemeCol_ChildBg, (135, 206, 250, 80))
            dpg.add_theme_style(dpg.mvStyleVar_ChildRounding, 12)
            dpg.add_theme_style(dpg.mvStyleVar_WindowPadding, 20, 20)
        with dpg.theme_component(dpg.mvText):
            dpg.add_theme_color(dpg.mvThemeCol_Text, (135, 206, 250))

    # Тема для статуса
    with dpg.theme(tag="status_theme"):
        with dpg.theme_component(dpg.mvChildWindow):
            dpg.add_theme_color(dpg.mvThemeCol_ChildBg, (144, 238, 144, 80))
            dpg.add_theme_style(dpg.mvStyleVar_ChildRounding, 12)
            dpg.add_theme_style(dpg.mvStyleVar_WindowPadding, 20, 20)
        with dpg.theme_component(dpg.mvText):
            dpg.add_theme_color(dpg.mvThemeCol_Text, (50, 205, 50))

    # Тема для уставки
    with dpg.theme(tag="setpoint_theme"):
        with dpg.theme_component(dpg.mvChildWindow):
            dpg.add_theme_color(dpg.mvThemeCol_ChildBg, (255, 182, 193, 80))
            dpg.add_theme_style(dpg.mvStyleVar_ChildRounding, 12)
            dpg.add_theme_style(dpg.mvStyleVar_WindowPadding, 20, 20)
        with dpg.theme_component(dpg.mvText):
            dpg.add_theme_color(dpg.mvThemeCol_Text, (255, 105, 180))

    # Тема для мощности
    with dpg.theme(tag="power_theme"):
        with dpg.theme_component(dpg.mvChildWindow):
            dpg.add_theme_color(dpg.mvThemeCol_ChildBg, (255, 215, 0, 80))
            dpg.add_theme_style(dpg.mvStyleVar_ChildRounding, 12)
            dpg.add_theme_style(dpg.mvStyleVar_WindowPadding, 20, 20)
        with dpg.theme_component(dpg.mvText):
            dpg.add_theme_color(dpg.mvThemeCol_Text, (255, 215, 0))

    # Тема для времени
    with dpg.theme(tag="time_theme"):
        with dpg.theme_component(dpg.mvChildWindow):
            dpg.add_theme_color(dpg.mvThemeCol_ChildBg, (147, 112, 219, 80))
            dpg.add_theme_style(dpg.mvStyleVar_ChildRounding, 12)
            dpg.add_theme_style(dpg.mvStyleVar_WindowPadding, 20, 20)
        with dpg.theme_component(dpg.mvText):
            dpg.add_theme_color(dpg.mvThemeCol_Text, (147, 112, 219))

    # Тема для кнопок управления
    with dpg.theme(tag="control_button_theme"):
        with dpg.theme_component(dpg.mvButton):
            dpg.add_theme_color(dpg.mvThemeCol_Button, (70, 130, 180, 150))
            dpg.add_theme_color(dpg.mvThemeCol_ButtonHovered, (100, 149, 237, 180))
            dpg.add_theme_color(dpg.mvThemeCol_ButtonActive, (65, 105, 225, 200))
            dpg.add_theme_style(dpg.mvStyleVar_FrameRounding, 8)
            dpg.add_theme_style(dpg.mvStyleVar_FramePadding, 8, 4)

    # Тема для тревоги
    with dpg.theme(tag="alarm_theme"):
        with dpg.theme_component(dpg.mvChildWindow):
            dpg.add_theme_color(dpg.mvThemeCol_ChildBg, (255, 0, 0, 80))
            dpg.add_theme_style(dpg.mvStyleVar_ChildRounding, 12)
            dpg.add_theme_style(dpg.mvStyleVar_WindowPadding, 20, 20)
        with dpg.theme_component(dpg.mvText):
            dpg.add_theme_color(dpg.mvThemeCol_Text, (255, 255, 0))

    # Тема для крупного текста значений
    with dpg.theme(tag="large_value_theme"):
        with dpg.theme_component(dpg.mvText):
            dpg.add_theme_color(dpg.mvThemeCol_Text, (255, 255, 255, 255))

    # Создаём тему для окна выдержки
    if not dpg.does_item_exist(f"{str_tag}_holdtime_theme"):
        with dpg.theme(tag=f"{str_tag}_holdtime_theme"):
            with dpg.theme_component(dpg.mvAll):
                dpg.add_theme_color(dpg.mvThemeCol_WindowBg, (70, 130, 180, 200))
                dpg.add_theme_color(dpg.mvThemeCol_Text, (255, 255, 255, 255))
                dpg.add_theme_color(dpg.mvThemeCol_TitleBg, (85, 110, 140, 255))
                dpg.add_theme_color(dpg.mvThemeCol_TitleBgActive, (105, 135, 170, 255))
                dpg.add_theme_color(dpg.mvThemeCol_Border, (150, 165, 185, 255))
                dpg.add_theme_color(dpg.mvThemeCol_FrameBg, (255, 255, 255, 255))
                dpg.add_theme_color(dpg.mvThemeCol_FrameBgHovered, (235, 242, 250, 255))
                dpg.add_theme_color(dpg.mvThemeCol_FrameBgActive, (215, 227, 242, 255))
                dpg.add_theme_color(dpg.mvThemeCol_Button, (85, 110, 140, 255))
                dpg.add_theme_color(dpg.mvThemeCol_ButtonHovered, (105, 135, 170, 255))
                dpg.add_theme_color(dpg.mvThemeCol_ButtonActive, (70, 95, 125, 255))
                dpg.add_theme_style(dpg.mvStyleVar_WindowBorderSize, 1.5)
                dpg.add_theme_style(dpg.mvStyleVar_WindowRounding, 6)
                dpg.add_theme_style(dpg.mvStyleVar_FrameBorderSize, 1)
                dpg.add_theme_style(dpg.mvStyleVar_FrameRounding, 4)
                dpg.add_theme_style(dpg.mvStyleVar_FramePadding, 10, 6)

    # Создаём тему для поля ввода (синий текст)
    if not dpg.does_item_exist(f"{str_tag}_input_theme"):
        with dpg.theme(tag=f"{str_tag}_input_theme"):
            with dpg.theme_component(dpg.mvInputInt):
                dpg.add_theme_color(dpg.mvThemeCol_Text, (0, 0, 255, 255))

    # Создаём тему для окна установки уставки
    if not dpg.does_item_exist(f"{str_tag}_setpoint_theme"):
        with dpg.theme(tag=f"{str_tag}_setpoint_theme"):
            with dpg.theme_component(dpg.mvAll):
                dpg.add_theme_color(dpg.mvThemeCol_WindowBg, (70, 130, 180, 200))
                dpg.add_theme_color(dpg.mvThemeCol_Text, (255, 255, 255, 255))
                dpg.add_theme_color(dpg.mvThemeCol_TitleBg, (85, 110, 140, 255))
                dpg.add_theme_color(dpg.mvThemeCol_TitleBgActive, (105, 135, 170, 255))
                dpg.add_theme_color(dpg.mvThemeCol_Border, (150, 165, 185, 255))
                dpg.add_theme_color(dpg.mvThemeCol_FrameBg, (255, 255, 255, 255))
                dpg.add_theme_color(dpg.mvThemeCol_FrameBgHovered, (235, 242, 250, 255))
                dpg.add_theme_color(dpg.mvThemeCol_FrameBgActive, (215, 227, 242, 255))
                dpg.add_theme_color(dpg.mvThemeCol_Button, (85, 110, 140, 255))
                dpg.add_theme_color(dpg.mvThemeCol_ButtonHovered, (105, 135, 170, 255))
                dpg.add_theme_color(dpg.mvThemeCol_ButtonActive, (70, 95, 125, 255))
                dpg.add_theme_style(dpg.mvStyleVar_WindowBorderSize, 1.5)
                dpg.add_theme_style(dpg.mvStyleVar_WindowRounding, 6)
                dpg.add_theme_style(dpg.mvStyleVar_FrameBorderSize, 1)
                dpg.add_theme_style(dpg.mvStyleVar_FrameRounding, 4)
                dpg.add_theme_style(dpg.mvStyleVar_ChildBorderSize, 1)
                dpg.add_theme_style(dpg.mvStyleVar_ChildRounding, 4)
                dpg.add_theme_style(dpg.mvStyleVar_ButtonTextAlign, 0.5, 0.5)
                dpg.add_theme_style(dpg.mvStyleVar_FramePadding, 10, 6)
                dpg.add_theme_style(dpg.mvStyleVar_ItemSpacing, 12, 8)

    # Создаём тему для поля ввода (синий текст) для float
    if not dpg.does_item_exist(f"{str_tag}_input_float_theme"):
        with dpg.theme(tag=f"{str_tag}_input_float_theme"):
            with dpg.theme_component(dpg.mvInputFloat):
                dpg.add_theme_color(dpg.mvThemeCol_Text, (0, 0, 255, 255))

    _TPM12_THEMES_CREATED = True


class TPM12_GUI:
    """
    Графический интерфейс для контроллера ТРМ12.
    """

    def __init__(self, dpg, tag: str = "tpm12"):
        """
        Инициализация GUI.

        Args:
            tag: Уникальный идентификатор для элементов GUI
        """
        self._remaining_hold = 0

        self.tag = tag
        self.start_time = time.time()
        self.setpoint = 25.0
        self.status = ChamberStatus.STOPPED
        self.connected_status = False
        self.dpg = dpg

        # Данные с устройства
        self.temp_ch1 = 20.0
        self.temp_ch2 = 20.0
        self.power_level = 0.0

        # Флаги
        self.running = False
        self.update_thread = None
        self.driver = None

        # Статус устройства
        self.device_status = "Нет связи"
        self.device_error = ""

        # Флаг для хранения состояния шрифта
        self.large_font_loaded = False

        # Коррекция температуры
        self.corrector: Optional[PolynomialCorrector] = None
        self.correction_file = Path("tpm12_correction.pkl")

        self.chamber_process: Optional[ChamberProcess] = None
        self.hold_minutes = 0  # будет обновляться из поля "Выдержка"

        self.current_setpoint = 0.0

        self.user_setpoint = 25.0  # заданная пользователем уставка
        self.device_setpoint = 25.0  # текущая уставка прибора (может меняться автоматически)
        self.control_mode = "Неизвестно"  # режим управления
        self.user_setpoint_initialized = False  # флаг первой инициализации
        self.user_setpoint_manually_set = False

        #self.config_file = Path(__file__).parent / "chamber_algorithm_config.json"
        self.corrector_ch1: Optional[PolynomialCorrector] = None
        self.corrector_ch2: Optional[PolynomialCorrector] = None
        self.correction_file_ch1 = Path("tpm12_correction_ch1.pkl")
        self.correction_file_ch2 = Path("tpm12_correction_ch2.pkl")
        self._prev_process_status = ProcessStatus.IDLE

        # Словарь для преобразования статусов процесса в статусы GUI
        self._process_status_map = {
            ProcessStatus.HEATING: ChamberStatus.HEATING,
            ProcessStatus.STABILIZING: ChamberStatus.STABILIZING,
            ProcessStatus.HOLDING: ChamberStatus.HOLDING,
            ProcessStatus.COMPLETED: ChamberStatus.STOPPED,
            ProcessStatus.STOPPED: ChamberStatus.STOPPED,
            ProcessStatus.ERROR: ChamberStatus.ALARM,
            ProcessStatus.IDLE: ChamberStatus.STANDBY,
        }

    def set_driver(self, driver):
        self.driver = driver
        status = driver.check_connection_status()
        self.connected_status = status['devices'].get('TRM12', {})
        if self.connected_status:
            print("Драйвер устройства установлен")
        else:
            print("ВНИМАНИЕ: Драйвер не установлен")
        # Попытка загрузить сохранённые модели коррекции
        self._load_corrections()
        camera_controller = DEVICES_DATA.get_chamber_controller()
        if camera_controller:
            self.chamber_process = ChamberProcess(camera_controller)
        else:
            print("CameraController не найден, процесс недоступен")
        self._load_algorithm_config()

    def _load_algorithm_config(self):
        """Загрузить настройки алгоритма из файла и применить их."""
        if not self.chamber_process:
            print("ChamberProcess не инициализирован, настройки не загружены")
            return
        settings = _load_settings_from_file(self.chamber_process)
        self._apply_algorithm_settings(settings)



    def _save_algorithm_config(self, settings):
        """Сохранить настройки алгоритма в файл."""
        _save_settings_to_file(settings)


    def _load_corrections(self):
        camera_controller = DEVICES_DATA.get_chamber_controller()
        if not camera_controller:
            print("CameraController не доступен")
            return

        # Канал 1 GUI -> камера (channel 0)
        if self.correction_file_ch1.exists():
            try:
                corrector = PolynomialCorrector.load(str(self.correction_file_ch1))
                self.corrector_ch1 = corrector
                camera_controller.set_corrector(0, corrector)
                print(f"Корректор камеры загружен из {self.correction_file_ch1}")
            except Exception as e:
                print(f"Ошибка загрузки корректора камеры: {e}")

        # Канал 2 GUI -> вал (channel 1)
        if self.correction_file_ch2.exists():
            try:
                corrector = PolynomialCorrector.load(str(self.correction_file_ch2))
                self.corrector_ch2 = corrector
                camera_controller.set_corrector(1, corrector)
                print(f"Корректор вала загружен из {self.correction_file_ch2}")
            except Exception as e:
                print(f"Ошибка загрузки корректора вала: {e}")



    def _get_data_from_device(self):
        """Получение данных с устройства."""
        if not self.connected_status:
            self.device_error = "Драйвер не установлен"
            return {}
        try:
            set_temp = self.driver.get_chamber_setpoint()
            cur_temp = self.driver.get_chamber_temperature()
            if set_temp is not None:
                temp_ch1 = float(cur_temp[0])
                setpoint = float(set_temp[0])
            else:
                temp_ch1 = 0.0
                setpoint = 0.0
            grad_temp, msg_g = self.driver.get_gradient()
            if grad_temp is not None:
                grad = grad_temp
            else:
                grad = 0.0

            mode_dice = self.driver.trm12.get_control_mode()

            return {
                'temp_ch1': temp_ch1,
                'setpoints': setpoint,
                'gradient': grad,
                'control_mode': mode_dice,
            }

        except Exception as e:
            self.device_error = f"Ошибка чтения: {str(e)}"
            return {}


    def _determine_status(self):
        """Определяет статус на основе режима и сравнения температуры с пользовательской уставкой."""
        if not self.chamber_process or not self.chamber_process.is_running():
            self.status = ChamberStatus.STANDBY
            return
        if self.control_mode == "Автоматический":
            if self.temp_ch1 < self.user_setpoint - 0.1:
                self.status = ChamberStatus.HEATING
            elif self.temp_ch1 > self.user_setpoint + 0.1:
                self.status = ChamberStatus.COOLING
            else:
                self.status = ChamberStatus.STANDBY
        else:
            # Ручной режим или неизвестный – считаем ожиданием
            self.status = ChamberStatus.STANDBY

    def update_data(self):
        # Получение данных с устройства
        data = self._get_data_from_device()
        if not data:
            self.device_status = f"Ошибка: {self.device_error}"
            return

        #raw_temp_ch1 = data.get('temp_ch1', 0.0)
        #raw_temp_ch2 = data.get('gradient', 0.0)
        device_sp = data.get('setpoints', 0.0)  # текущая уставка с прибора
        mode_info = data.get('control_mode', {})
        self.control_mode = mode_info.get('name', 'Неизвестно')

        # Применяем коррекцию температуры

        self.temp_ch1 = data.get('temp_ch1', 0.0)
        self.temp_ch2 = data.get('gradient', 0.0)
        # Если процесс запущен, используем данные из него
        if self.chamber_process and self.chamber_process.is_running():
            proc_data = self.chamber_process.get_data()

            self.temp_ch1 = proc_data.current_temp
            self.temp_ch2 = proc_data.gradient
            self.device_setpoint = proc_data.current_setpoint  # обновляем текущую уставку из процесса
            # Статус уже установлен процессом
            status_map = {
                ProcessStatus.HEATING: ChamberStatus.HEATING,
                ProcessStatus.STABILIZING: ChamberStatus.STABILIZING,
                ProcessStatus.HOLDING: ChamberStatus.HOLDING,
                ProcessStatus.COMPLETED: ChamberStatus.STOPPED,
                ProcessStatus.STOPPED: ChamberStatus.STOPPED,
                ProcessStatus.ERROR: ChamberStatus.ALARM,
                ProcessStatus.IDLE: ChamberStatus.STANDBY,
            }
            self.status = status_map.get(proc_data.process_status, ChamberStatus.STOPPED)
            self._remaining_hold = proc_data.hold_remaining
            # Контроль заморозки времени двигателя при завершении программы
            if self._prev_process_status not in (ProcessStatus.COMPLETED, ProcessStatus.STOPPED) and \
                    proc_data.process_status in (ProcessStatus.COMPLETED, ProcessStatus.STOPPED):
                motor_gui = DEVICES_DATA.get_blsd_gui()
                if motor_gui:
                    motor_gui.freeze_time()
            self._prev_process_status = proc_data.process_status
        else:
            # Процесс не запущен – используем данные напрямую с прибора
            self.device_setpoint = device_sp
            self._prev_process_status = ProcessStatus.IDLE
            # Инициализация пользовательской уставки при первом чтении
            if not self.user_setpoint_initialized:
                self.user_setpoint = device_sp
                self.user_setpoint_initialized = True
            # Определяем статус вручную
            self._determine_status()
            self._remaining_hold = 0  # <-- добавить эту строку

        # Обновление отображения
        self._update_display()

    def _update_display(self):
        """Обновление отображения в интерфейсе."""
        dpg = self.dpg
        try:
            # Температура канала 1 (уже скорректированная)
            if dpg.does_item_exist(f"{self.tag}_temp_ch1_val"):
                dpg.set_value(f"{self.tag}_temp_ch1_val", f"{self.temp_ch1:3.2f}°C")

            # Температура канала 2 (градиент)
            if dpg.does_item_exist(f"{self.tag}_temp_ch2_val"):
                dpg.set_value(f"{self.tag}_temp_ch2_val", f"{self.temp_ch2:3.2f}°C")

            # Уставка
            if dpg.does_item_exist(f"{self.tag}_setpoint_val"):
                dpg.set_value(f"{self.tag}_setpoint_val", f"{self.setpoint:3.1f}°C")

            # Статус
            status_text = self.status.value
            if dpg.does_item_exist(f"{self.tag}_status_val"):
                dpg.set_value(f"{self.tag}_status_val", status_text)

            # Применяем тему тревоги при аварии
            if self.status == ChamberStatus.ALARM:
                if dpg.does_item_exist(f"{self.tag}_status_panel"):
                    dpg.bind_item_theme(f"{self.tag}_status_panel", "alarm_theme")


            # Пользовательская уставка (старое поле setpoint_val)
            if dpg.does_item_exist(f"{self.tag}_setpoint_val"):
               dpg.set_value(f"{self.tag}_setpoint_val", f"{self.user_setpoint:3.1f}°C")

            # Текущая уставка прибора (новое поле)
            if dpg.does_item_exist(f"{self.tag}_current_setpoint_val"):
               dpg.set_value(f"{self.tag}_current_setpoint_val", f"{self.device_setpoint:3.1f}°C")

                # Время выдержки
            if hasattr(self, '_remaining_hold') and self._remaining_hold > 0:
                hours = int(self._remaining_hold // 3600)
                minutes = int((self._remaining_hold % 3600) // 60)
                seconds = int(self._remaining_hold % 60)
                time_str = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
                if dpg.does_item_exist(f"{self.tag}_power_val"):
                    dpg.set_value(f"{self.tag}_power_val", time_str)

        except Exception as e:
            print(f"Ошибка обновления отображения: {e}")

    def _open_algorithm_settings(self):
        """Открыть окно настроек алгоритма и скорости нагрева."""
        if not self.chamber_process:
            print("Процесс не инициализирован")
            return

        # Текущие значения параметров
        current = {
            "epsilon_reach": self.chamber_process.epsilon_reach,
            "epsilon_stable": self.chamber_process.epsilon_stable,
            "stability_interval": self.chamber_process.stability_interval,
            "pid_adjust_interval": self.chamber_process.pid_adjust_interval,
            "setpoint_adjust_interval": self.chamber_process.setpoint_adjust_interval,
            "update_interval": self.chamber_process.update_interval,
            "heating_rate": self.chamber_process.get_heating_rate(),
            "shaft_stabilization_interval": self.chamber_process.shaft_stabilization_interval,
            "shaft_final_delay": self.chamber_process.shaft_final_delay,
            "shaft_temp_update_interval": self.chamber_process.shaft_temp_update_interval,
            "shaft_max_attempts": self.chamber_process.shaft_max_attempts,
            # Новые параметры
            "max_correction": self.chamber_process.max_correction,
            "correction_cooldown": self.chamber_process.correction_cooldown,
            "target_gradient": self.chamber_process.target_gradient,
            "fan_adjust_interval": self.chamber_process.fan_adjust_interval,
            "temp_threshold_for_shaft_heating": self.chamber_process.temp_threshold_for_shaft_heating,
            "shaft_min_temp_for_heating": self.chamber_process.shaft_min_temp_for_heating,
            "shaft_heating_duration": self.chamber_process.shaft_heating_duration,
            "shaft_heating_repetitions": self.chamber_process.shaft_heating_repetitions,
            "shaft_heating_interval": self.chamber_process.shaft_heating_interval,
            "fan_control_enabled": self.chamber_process.fan_control_enabled,
            "shaft_check_enabled": self.chamber_process.shaft_check_enabled,
        }

        show_algorithm_settings_dialog(
            dpg_instance=self.dpg,
            tag_prefix=self.tag,
            chamber_process=self.chamber_process,
            current_settings=current,
            apply_callback=self._apply_algorithm_settings
        )



    def _apply_algorithm_settings(self, new_settings):
        """Применить новые настройки алгоритма и скорости нагрева."""
        if not self.chamber_process:
            return

        # Обновляем атрибуты процесса через универсальный метод
        self.chamber_process.update_algorithm_params(new_settings)

        # Устанавливаем интервал обновления температуры вала в MotorGUI (если требуется)
        shaft_update = new_settings.get("shaft_temp_update_interval")
        if shaft_update is not None:
            motor_gui = DEVICES_DATA.get_blsd_gui()
            if motor_gui:
                motor_gui.set_shaft_temp_update_interval(shaft_update)

        # Сохраняем конфигурацию
        self._save_algorithm_config(new_settings)

        print("Настройки алгоритма обновлены")


    def create_window(self):
        """Создание окна индикации ТРМ12."""
        dpg = self.dpg
        dpg.delete_item(f"{self.tag}_window")
        create_tpm12_themes(dpg, self.tag)

        if dpg.does_item_exist("large_font"):
            self.large_font_loaded = True

        print('Создание индикатора', self.tag)
        with dpg.window(tag=f"{self.tag}_window",
                        width=525,
                        height=700,
                        label=f'Контроллер температуры',
                        pos=(1350, 0)):
            # Панель температуры канала 1 (PV1)
            with dpg.child_window(width=500, height=120, tag=f"{self.tag}_pv1_panel"):
                dpg.add_text("Температура:", indent=20)
                temp_ch1_val = dpg.add_text("---", tag=f"{self.tag}_temp_ch1_val", indent=20)
                if self.large_font_loaded:
                    dpg.bind_item_font(temp_ch1_val, "large_font")
                else:
                    dpg.bind_item_theme(temp_ch1_val, "large_value_theme")

            # Панель температуры канала 2 (PV2)
            with dpg.child_window(width=500, height=120, tag=f"{self.tag}_pv2_panel"):
                dpg.add_text("Градиент:", indent=20)
                temp_ch2_val = dpg.add_text("---", tag=f"{self.tag}_temp_ch2_val", indent=20)
                if self.large_font_loaded:
                    dpg.bind_item_font(temp_ch2_val, "large_font")
                else:
                    dpg.bind_item_theme(temp_ch2_val, "large_value_theme")

            # Группа для уставки и статуса
            with dpg.group(horizontal=True, horizontal_spacing=10):
                with dpg.child_window(width=245, height=130, tag=f"{self.tag}_setpoint_panel"):
                    dpg.add_text("Уставка:", indent=20)
                    setpoint_val = dpg.add_text("---", tag=f"{self.tag}_setpoint_val", indent=5)
                    if self.large_font_loaded:
                        dpg.bind_item_font(setpoint_val, "large_font")
                    else:
                        dpg.bind_item_theme(setpoint_val, "large_value_theme")
                    with dpg.popup(f"{self.tag}_setpoint_val", min_size=[120, 30]):
                        dpg.add_button(label="Изменить", width=100, height=25,
                                       callback=lambda: self._open_setpoint_dialog())

                with dpg.child_window(width=245, height=130, tag=f"{self.tag}_status_panel"):
                    dpg.add_text("Текущий статус:", indent=10)
                    status_val = dpg.add_text("---", tag=f"{self.tag}_status_val", indent=5)
                    if self.large_font_loaded:
                        dpg.bind_item_font(status_val, "medium_font")
                    else:
                        dpg.bind_item_theme(status_val, "large_value_theme")

            # Группа для мощности и времени
            with dpg.group(horizontal=True, horizontal_spacing=10):
                with dpg.child_window(width=245, height=120, tag=f"{self.tag}_power_panel"):
                    dpg.add_text("Выдержка:", indent=20)
                    power_val = dpg.add_text("00:00:00", tag=f"{self.tag}_power_val", indent=20)
                    if self.large_font_loaded:
                        dpg.bind_item_font(power_val, "medium_font")
                    else:
                        dpg.bind_item_theme(power_val, "large_value_theme")
                    with dpg.popup(power_val, min_size=[120, 30]):
                        dpg.add_button(label="Изменить", width=100, height=25,
                                       callback=lambda: self._open_hold_time_dialog())

                with dpg.child_window(width=245, height=120, tag=f"{self.tag}_time_panel"):  # тег оставляем
                    dpg.add_text("Текущая уставка:", indent=20)
                    current_sp_val = dpg.add_text("---", tag=f"{self.tag}_current_setpoint_val", indent=20)  # новый тег
                    if self.large_font_loaded:
                        dpg.bind_item_font(current_sp_val, "medium_font")
                    else:
                        dpg.bind_item_theme(current_sp_val, "large_value_theme")

            # Кнопки управления
            with dpg.group(horizontal=True, horizontal_spacing=10):
                buttons = [
                    ("ПУСК", lambda: self._start_auto()),
                    ("СТОП", lambda: self._stop_operation()),
                    ("НАСТРОЙКИ", lambda: self._open_algorithm_settings())   # ← изменено
                ]

                for label, callback in buttons:
                    btn = dpg.add_button(label=label, width=115, height=40,
                                         callback=callback)
                    dpg.bind_item_theme(btn, "control_button_theme")

            # Дополнительные настройки
            with dpg.collapsing_header(label="Дополнительно"):
                with dpg.group(horizontal=True):
                    dpg.add_button(label="PID настройки", width=120,
                                   callback=lambda: self._open_pid_settings())
                    dpg.add_button(label="Коррекция", width=120,
                                   callback=lambda: self._open_correction_dialog())
                    dpg.add_button(label="График коррекции", width=120,
                                   callback=lambda: self._open_correction_plot_dialog())

        # Применяем темы к панелям
        if dpg.does_item_exist(f"{self.tag}_pv1_panel"):
            dpg.bind_item_theme(f"{self.tag}_pv1_panel", "temp_theme_pv1")
        if dpg.does_item_exist(f"{self.tag}_pv2_panel"):
            dpg.bind_item_theme(f"{self.tag}_pv2_panel", "temp_theme_pv2")
        if dpg.does_item_exist(f"{self.tag}_setpoint_panel"):
            dpg.bind_item_theme(f"{self.tag}_setpoint_panel", "setpoint_theme")
        if dpg.does_item_exist(f"{self.tag}_status_panel"):
            dpg.bind_item_theme(f"{self.tag}_status_panel", "status_theme")
        if dpg.does_item_exist(f"{self.tag}_power_panel"):
            dpg.bind_item_theme(f"{self.tag}_power_panel", "power_theme")
        if dpg.does_item_exist(f"{self.tag}_time_panel"):
            dpg.bind_item_theme(f"{self.tag}_time_panel", "time_theme")

        self.start_update_thread()

    def _open_correction_plot_dialog(self):
        # Принудительно загружаем корректоры, если ещё не загружены
        if self.corrector_ch1 is None and self.correction_file_ch1.exists():
            self._load_corrections()
        show_correction_plot_dialog(self)
        show_correction_plot_dialog(self)

    # ---------- Методы открытия диалогов ----------
    def _open_correction_dialog(self):
        show_correction_dialog(
            dpg_instance=self.dpg,
            tag_prefix=self.tag,
            apply_callback=self._apply_correction_data
        )

    def _open_setpoint_dialog(self):
        """Открыть окно установки уставки (блокируется при активном процессе)."""
        if self.chamber_process and self.chamber_process.is_running():
            print("Нельзя изменить уставку во время активного процесса")
            # Опционально можно показать всплывающее сообщение:
            # self.dpg.add_toast("Процесс запущен", "Нельзя изменить уставку", duration=2)
            return
        show_setpoint_dialog(
            dpg_instance=self.dpg,
            tag_prefix=self.tag,
            current_value=self.user_setpoint,
            apply_callback=self._apply_setpoint_value
        )

    def _open_hold_time_dialog(self):
        """Открыть окно установки времени выдержки (блокируется при активном процессе)."""
        if self.chamber_process and self.chamber_process.is_running():
            print("Нельзя изменить время выдержки во время активного процесса")
            return
        show_hold_time_dialog(
            dpg_instance=self.dpg,
            tag_prefix=self.tag,
            apply_callback=self._apply_hold_time_value
        )

    def _open_pid_settings(self):
        """Открыть окно настроек PID."""
        show_pid_dialog(self.dpg, self.tag, self)

    # ---------- Callback-методы для применения данных из диалогов ----------
    def _apply_correction_data(self, sensor_vals, real_vals, degree, channel):
        try:
            corrector = PolynomialCorrector()
            corrector.fit(np.array(sensor_vals), np.array(real_vals), degree)

            # Сохраняем в файл с именем, соответствующим каналу GUI
            filename = f"tpm12_correction_ch{channel}.pkl"
            corrector.save(filename)
            print(f"Модель коррекции для канала {channel} сохранена в {filename}")

            camera_controller = DEVICES_DATA.get_chamber_controller()
            if camera_controller:
                if channel == 1:
                    # Канал 1 GUI -> камера (channel 0)
                    camera_controller.set_corrector(0, corrector)
                    self.corrector_ch1 = corrector
                elif channel == 2:
                    # Канал 2 GUI -> вал (channel 1)
                    camera_controller.set_corrector(1, corrector)
                    self.corrector_ch2 = corrector
                else:
                    print(f"Неизвестный канал: {channel}")
            else:
                print("CameraController не доступен – корректор не установлен в драйвер")
        except Exception as e:
            print(f"Ошибка при обучении/сохранении модели: {e}")

    def _apply_setpoint_value(self, new_value):
        self.user_setpoint = new_value
        self.setpoint = new_value
        self.user_setpoint_manually_set = True  # запомнили, что пользователь задавал
        if self.driver and hasattr(self.driver, 'set_temperature'):
            self.driver.set_temperature(new_value, channel=0)
        print(f"Уставка установлена: {new_value}°C")



    def _apply_hold_time_value(self, minutes):
        self.hold_minutes = minutes
        # Обновить отображение в поле "Выдержка" (статическое заданное время)
        dpg = self.dpg
        if dpg.does_item_exist(f"{self.tag}_power_val"):
            hours = minutes // 60
            mins = minutes % 60
            time_str = f"{hours:02d}:{mins:02d}:00"
            dpg.set_value(f"{self.tag}_power_val", time_str)
        print(f"Установлено время выдержки: {minutes} мин")


    # ---------- Методы управления ----------
    def _start_auto(self):
        if not self.chamber_process:
            print("Процесс не инициализирован")
            return
        if self.chamber_process.is_running():
            print("Процесс уже запущен")
            return

        # Определяем целевую температуру
        if self.user_setpoint_manually_set:
            target = self.user_setpoint
        else:
            target = self.device_setpoint  # текущая уставка прибора

        hold_minutes = self.hold_minutes

        # Сброс времени на графике и двигателе (как раньше)
        from Ports_COM.Devices_Data import DEVICES_DATA
        temp_monitor = DEVICES_DATA.get_temp_monitor()
        if temp_monitor:
            temp_monitor.clear_data()
        motor_gui = DEVICES_DATA.get_blsd_gui()
        if motor_gui:
            motor_gui.start_time = time.time()
            motor_gui.unfreeze_time()

        try:
            self.chamber_process.start_process(target, hold_minutes)
            self.status = ChamberStatus.HEATING
            print(f"Процесс запущен: цель {target}°C, выдержка {hold_minutes} мин")
        except Exception as e:
            print(f"Ошибка запуска процесса: {e}")

    def _stop_operation(self):
        if self.chamber_process and self.chamber_process.is_running():
            self.chamber_process.stop_process()
            self.status = ChamberStatus.STOPPED
            self.user_setpoint = self.temp_ch1
            print("Процесс остановлен")

            # Заморозить время работы двигателя
            from Ports_COM.Devices_Data import DEVICES_DATA
            motor_gui = DEVICES_DATA.get_blsd_gui()
            if motor_gui:
                motor_gui.freeze_time()

    def _reset_operation(self):
        """Сброс операции."""
        self.start_time = time.time()
        print("Сброс времени работы")

    # ---------- Поток обновления ----------
    def start_update_thread(self):
        """Запуск потока обновления данных."""
        if self.update_thread is None or not self.update_thread.is_alive():
            self.running = True
            self.update_thread = threading.Thread(
                target=self._update_loop,
                daemon=True
            )
            self.update_thread.start()
            print("Поток обновления данных ТРМ12 запущен")

    def stop_update_thread(self):
        """Остановка потока обновления данных."""
        self.running = False
        if self.update_thread and self.update_thread.is_alive():
            self.update_thread.join(timeout=2)
            print("Поток обновления данных ТРМ12 остановлен")

    def _update_loop(self):
        """Цикл обновления данных."""
        while self.running:
            try:
                self.update_data()
                time.sleep(1)
            except Exception as e:
                print(f"Ошибка в потоке обновления ТРМ12: {e}")
                time.sleep(1)
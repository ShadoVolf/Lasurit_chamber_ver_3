"""
Модуль графического интерфейса для двигателя BLSD-20.
Для использования в существующем приложении.
"""

import time
import threading
from typing import Optional
from enum import Enum

from BLSD.motor_speed_dialog import MotorSpeedDialog


# Импортируем вынесенный диалог установки скорости



class MotorStatus(Enum):
    """Статусы работы двигателя"""
    RUNNING = "РАБОТА"
    STOPPED = "СТОП"
    FORWARD = "ВПЕРЕД"
    REVERSE = "НАЗАД"
    ERROR = "ОШИБКА"


# Глобальный флаг для проверки создания тем
_MOTOR_THEMES_CREATED = False


def create_motor_themes(dpg, str_tag):
    """Создание тем для индикаторов двигателя (вызывается один раз)"""
    global _MOTOR_THEMES_CREATED

    if _MOTOR_THEMES_CREATED:
        return

    # Тема для текущей скорости
    with dpg.theme(tag="motor_speed_theme"):
        with dpg.theme_component(dpg.mvChildWindow):
            dpg.add_theme_color(dpg.mvThemeCol_ChildBg, (70, 130, 180, 80))  # SteelBlue
            dpg.add_theme_style(dpg.mvStyleVar_ChildRounding, 12)
            dpg.add_theme_style(dpg.mvStyleVar_WindowPadding, 20, 20)
        with dpg.theme_component(dpg.mvText):
            dpg.add_theme_color(dpg.mvThemeCol_Text, (135, 206, 250))  # LightSkyBlue

    # Тема для уставки скорости
    with dpg.theme(tag="motor_setpoint_theme"):
        with dpg.theme_component(dpg.mvChildWindow):
            dpg.add_theme_color(dpg.mvThemeCol_ChildBg, (50, 205, 50, 80))  # LimeGreen
            dpg.add_theme_style(dpg.mvStyleVar_ChildRounding, 12)
            dpg.add_theme_style(dpg.mvStyleVar_WindowPadding, 20, 20)
        with dpg.theme_component(dpg.mvText):
            dpg.add_theme_color(dpg.mvThemeCol_Text, (144, 238, 144))  # LightGreen

    # Тема для температуры вала
    with dpg.theme(tag="motor_temp_theme"):
        with dpg.theme_component(dpg.mvChildWindow):
            dpg.add_theme_color(dpg.mvThemeCol_ChildBg, (220, 20, 60, 80))  # Crimson
            dpg.add_theme_style(dpg.mvStyleVar_ChildRounding, 12)
            dpg.add_theme_style(dpg.mvStyleVar_WindowPadding, 20, 20)
        with dpg.theme_component(dpg.mvText):
            dpg.add_theme_color(dpg.mvThemeCol_Text, (255, 99, 71))  # Tomato

    # Тема для статуса
    with dpg.theme(tag="motor_status_theme"):
        with dpg.theme_component(dpg.mvChildWindow):
            dpg.add_theme_color(dpg.mvThemeCol_ChildBg, (255, 215, 0, 80))  # Gold
            dpg.add_theme_style(dpg.mvStyleVar_ChildRounding, 12)
            dpg.add_theme_style(dpg.mvStyleVar_WindowPadding, 20, 20)
        with dpg.theme_component(dpg.mvText):
            dpg.add_theme_color(dpg.mvThemeCol_Text, (255, 255, 0))  # Yellow

    # Тема для времени работы
    with dpg.theme(tag="motor_time_theme"):
        with dpg.theme_component(dpg.mvChildWindow):
            dpg.add_theme_color(dpg.mvThemeCol_ChildBg, (147, 112, 219, 80))  # MediumPurple
            dpg.add_theme_style(dpg.mvStyleVar_ChildRounding, 12)
            dpg.add_theme_style(dpg.mvStyleVar_WindowPadding, 20, 20)
        with dpg.theme_component(dpg.mvText):
            dpg.add_theme_color(dpg.mvThemeCol_Text, (186, 85, 211))  # MediumOrchid

    # Тема для тока двигателя
    with dpg.theme(tag="motor_current_theme"):
        with dpg.theme_component(dpg.mvChildWindow):
            dpg.add_theme_color(dpg.mvThemeCol_ChildBg, (255, 140, 0, 80))  # DarkOrange
            dpg.add_theme_style(dpg.mvStyleVar_ChildRounding, 12)
            dpg.add_theme_style(dpg.mvStyleVar_WindowPadding, 20, 20)
        with dpg.theme_component(dpg.mvText):
            dpg.add_theme_color(dpg.mvThemeCol_Text, (255, 165, 0))  # Orange

    # Тема для тревоги
    with dpg.theme(tag="motor_alarm_theme"):
        with dpg.theme_component(dpg.mvChildWindow):
            dpg.add_theme_color(dpg.mvThemeCol_ChildBg, (255, 0, 0, 80))
            dpg.add_theme_style(dpg.mvStyleVar_ChildRounding, 12)
            dpg.add_theme_style(dpg.mvStyleVar_WindowPadding, 20, 20)
        with dpg.theme_component(dpg.mvText):
            dpg.add_theme_color(dpg.mvThemeCol_Text, (255, 255, 0))

    # Тема для крупного текста значений
    with dpg.theme(tag="motor_large_value_theme"):
        with dpg.theme_component(dpg.mvText):
            dpg.add_theme_color(dpg.mvThemeCol_Text, (255, 255, 255, 255))

    # Темы для диалога установки скорости создаются в классе MotorSpeedDialog
    _MOTOR_THEMES_CREATED = True


class MotorGUI:
    """
    Графический интерфейс для двигателя BLSD-20.
    Предполагается, что драйвер уже подключен.
    """

    def __init__(self, dpg, tag: str = "motor"):
        """
        Инициализация GUI.

        Args:
            tag: Уникальный идентификатор для элементов GUI
        """
        self.motor_set_speed = 0
        self.tag = tag
        self.start_time = time.time()
        self.setpoint_speed = 0
        self.current_speed = 0
        self.status = MotorStatus.STOPPED
        self.shaft_temperature = 20.0
        self.motor_current = 0.0
        self.dpg = dpg

        # Флаги
        self.running = False
        self.update_thread = None
        self.driver = None  # Драйвер будет получен из CameraController

        # Счетчики для разных интервалов обновления
        self.temp_update_counter = 0
        self.normal_update_counter = 0

        # Статус устройства
        self.device_status = "Нет связи"
        self.device_error = ""

        # Флаг для хранения состояния шрифта
        self.large_font_loaded = False

        # Экземпляр диалога установки скорости (создаётся при первом вызове)
        self.speed_dialog = None

        self._time_frozen = False  # флаг заморозки времени
        self._frozen_time_str = "00:00:00"  # сохранённое значение
        self.shaft_temp_update_interval = 60  # секунд, по умолчанию

    def set_shaft_temp_update_interval(self, interval: float):
        """Установить интервал обновления температуры вала (в секундах)."""
        self.shaft_temp_update_interval = max(1.0, interval)  # защита от слишком малых значений

    def set_driver(self, driver):
        """
        Установить драйвер устройства (CameraController).
        Должен быть вызван после инициализации GUI.
        """
        self.driver = driver
        if self.driver:
            print("Драйвер двигателя установлен")
        else:
            print("ВНИМАНИЕ: Драйвер не установлен")

    def freeze_time(self):
        """Заморозить отображение времени на текущем значении."""
        if not self._time_frozen:
            # Вычислить текущее время и сохранить как строку
            elapsed = time.time() - self.start_time
            hours = int(elapsed // 3600)
            minutes = int((elapsed % 3600) // 60)
            seconds = int(elapsed % 60)
            self._frozen_time_str = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
            self._time_frozen = True

    def unfreeze_time(self):
        """Разморозить время, разрешить обновление."""
        self._time_frozen = False

    def _get_normal_data_from_device(self):
        """
        Получение данных с устройства для обычного обновления (раз в 2 секунды).
        """
        if not self.driver:
            self.device_error = "Драйвер не установлен"
            return {}

        try:
            # Получаем текущую скорость
            current_speed = self.driver.get_fan_speed()

            # Получаем ток двигателя
            motor_current = self.driver.get_motor_current()

            # Получаем статус двигателя
            motor_status, status_msg = self.driver.get_motor_status()

            # Получаем установленную скорость
            set_speed = self.driver.blsd20.get_set_speed()

            return {
                'current_speed': current_speed if current_speed is not None else 0,
                'motor_current': motor_current if motor_current is not None else 0.0,
                'set_speed': set_speed if set_speed is not None else 0.0,
                'motor_status': motor_status,
                'status_message': status_msg
            }

        except Exception as e:
            self.device_error = f"Ошибка чтения: {str(e)}"
            return {}

    def _get_temperature_data_from_device(self):
        """
        Получение температуры вала.
        Приоритет: значение из ChamberProcess (если процесс запущен),
        иначе — прямое измерение через драйвер.
        """
        if not self.driver:
            self.device_error = "Драйвер не установлен"
            return {}

        # 1. Пробуем кэш процесса
        try:
            from Ports_COM.Devices_Data import DEVICES_DATA
            gui = DEVICES_DATA.get_owen_gui()
            process = getattr(gui, "chamber_process", None) if gui else None
            if process is not None and process.is_running():
                data = process.get_data()
                # В ChamberData есть current_temp — но это температура камеры.
                # Для температуры вала используем last_shaft_temp из процесса (кэш).
                shaft_temp = getattr(process, "last_shaft_temp", None)
                if shaft_temp is not None:
                    return {'shaft_temperature': float(shaft_temp),
                            'temp_message': 'из кэша процесса'}
        except Exception as e:
            print(f"MotorGUI: ошибка чтения из процесса: {e}")

        # 2. Прямое измерение (только если процесс не идёт)
        try:
            shaft_temp, temp_msg = self.driver.get_shaft_temperature()
            return {
                'shaft_temperature': shaft_temp if shaft_temp is not None else 0.0,
                'temp_message': temp_msg
            }
        except Exception as e:
            self.device_error = f"Ошибка чтения температуры: {str(e)}"
            return {}

    def _get_temperature_data_from_device_old(self):
        """
        Получение данных о температуре с устройства (раз в 60 секунд).
        """
        if not self.driver:
            self.device_error = "Драйвер не установлен"
            return {}

        try:
            # Получаем температуру вала
            shaft_temp, temp_msg = self.driver.get_shaft_temperature()

            return {
                'shaft_temperature': shaft_temp if shaft_temp is not None else 0.0,
                'temp_message': temp_msg
            }

        except Exception as e:
            self.device_error = f"Ошибка чтения температуры: {str(e)}"
            return {}

    def _get_data_from_device(self):
        """
        Получение данных с устройства через CameraController.
        В случае ошибки возвращает пустой словарь.
        """
        if not self.driver:
            self.device_error = "Драйвер не установлен"
            return {}

        try:
            # Получаем текущую скорость
            current_speed = self.driver.get_fan_speed()
            # Получаем ток двигателя
            motor_current = self.driver.get_motor_current()
            # Получаем статус двигателя
            motor_status, status_msg = self.driver.get_motor_status()
            # Получаем температуру вала
            shaft_temp, temp_msg = self.driver.get_shaft_temperature()
            # Получаем установленную скорость
            set_speed = self.driver.blsd20.get_set_speed()

            return {
                'current_speed': current_speed if current_speed is not None else 0,
                'motor_current': motor_current if motor_current is not None else 0.0,
                'set_speed': set_speed if set_speed is not None else 0.0,
                'motor_status': motor_status,
                'shaft_temperature': shaft_temp if shaft_temp is not None else 0.0,
                'status_message': status_msg,
                'temp_message': temp_msg
            }

        except Exception as e:
            self.device_error = f"Ошибка чтения: {str(e)}"
            return {}

    def update_normal_data(self):
        """Обновление основных данных с устройства (раз в 2 секунды)"""
        data = self._get_normal_data_from_device()
        if not data:
            self.device_status = f"Ошибка: {self.device_error}"
            return

        # Обновляем основные данные
        self.current_speed = data.get('current_speed', 0)
        self.motor_current = data.get('motor_current', 0.0)
        self.setpoint_speed = data.get('set_speed', 0)

        # Преобразуем статус в Enum
        status_text = data.get('motor_status', '')
        if status_text is not None:
            if 'ВПЕРЕД' in status_text:
                self.status = MotorStatus.FORWARD
            elif 'НАЗАД' in status_text:
                self.status = MotorStatus.REVERSE
            elif 'СТОП' in status_text:
                self.status = MotorStatus.STOPPED
            elif 'ОШИБКА' in status_text or 'Error' in status_text:
                self.status = MotorStatus.ERROR
            else:
                self.status = MotorStatus.STOPPED

        self._update_normal_display()

    def update_temperature_data(self):
        """Обновление данных температуры с устройства (раз в 60 секунд)"""
        data = self._get_temperature_data_from_device()
        if not data:
            self.device_status = f"Ошибка: {self.device_error}"
            return

        # Обновляем температуру
        self.shaft_temperature = data.get('shaft_temperature', 0.0)
        self._update_temperature_display()



    # Функция открытия диалога установки скорости (делегирует вынесенному классу)
    def _open_speed_dialog(self):
        """Открыть диалог изменения скорости двигателя"""
        if self.speed_dialog is None:
            self.speed_dialog = MotorSpeedDialog(self.dpg, self.tag, self.setpoint_speed, self._apply_set_speed_callback)
        self.speed_dialog.open()

    def _apply_set_speed_callback(self, new_speed):
        """Callback для применения новой скорости из диалога"""
        self.setpoint_speed = new_speed
        if self.driver:
            success = self.set_speed(self.setpoint_speed)
            if success:
                print(f"Скорость изменена на: {self.setpoint_speed} об/мин")
            else:
                print("Ошибка отправки скорости на устройство")
        else:
            print("Драйвер не установлен")

    def _update_normal_display(self):
        try:
            dpg = self.dpg
            if dpg.does_item_exist(f"{self.tag}_current_speed_val"):
                dpg.set_value(f"{self.tag}_current_speed_val", f"{self.current_speed:4d} об/мин")
            if dpg.does_item_exist(f"{self.tag}_setpoint_speed_val"):
                display_setpoint = self.setpoint_speed if self.setpoint_speed > 0 else self.current_speed
                dpg.set_value(f"{self.tag}_setpoint_speed_val", f"{display_setpoint:4d} об/мин")
            if dpg.does_item_exist(f"{self.tag}_status_val"):
                dpg.set_value(f"{self.tag}_status_val", self.status.value)
            if dpg.does_item_exist(f"{self.tag}_current_val"):
                dpg.set_value(f"{self.tag}_current_val", f"{self.motor_current:3.1f} мА")
            if dpg.does_item_exist(f"{self.tag}_time_val"):
                elapsed = time.time() - self.start_time
                hours = int(elapsed // 3600)
                minutes = int((elapsed % 3600) // 60)
                seconds = int(elapsed % 60)
                dpg.set_value(f"{self.tag}_time_val", f"{hours:02d}:{minutes:02d}:{seconds:02d}")

            if self.status == MotorStatus.ERROR:
                if dpg.does_item_exist(f"{self.tag}_status_panel"):
                    dpg.bind_item_theme(f"{self.tag}_status_panel", "motor_alarm_theme")
            else:
                if dpg.does_item_exist(f"{self.tag}_status_panel"):
                    dpg.bind_item_theme(f"{self.tag}_status_panel", "motor_status_theme")
        except Exception as e:
            print(f"Ошибка обновления отображения основных параметров: {e}")

    def _update_normal_display_old(self):
        """Обновление отображения основных параметров"""
        try:
            dpg = self.dpg

            # Текущая скорость
            if dpg.does_item_exist(f"{self.tag}_current_speed_val"):
                dpg.set_value(f"{self.tag}_current_speed_val", f"{self.current_speed:4d} об/мин")

            # Уставка скорости
            if dpg.does_item_exist(f"{self.tag}_setpoint_speed_val"):
                display_setpoint = self.setpoint_speed if self.setpoint_speed > 0 else self.current_speed
                dpg.set_value(f"{self.tag}_setpoint_speed_val", f"{display_setpoint:4d} об/мин")

            # Статус
            status_text = self.status.value
            if dpg.does_item_exist(f"{self.tag}_status_val"):
                dpg.set_value(f"{self.tag}_status_val", status_text)

            # Ток двигателя
            if dpg.does_item_exist(f"{self.tag}_current_val"):
                dpg.set_value(f"{self.tag}_current_val", f"{self.motor_current:3.1f} мА")

            # Время работы
            if dpg.does_item_exist(f"{self.tag}_time_val"):
                elapsed = time.time() - self.start_time
                hours = int(elapsed // 3600)
                minutes = int((elapsed % 3600) // 60)
                seconds = int(elapsed % 60)
                time_str = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
                dpg.set_value(f"{self.tag}_time_val", time_str)

            # Применяем тему тревоги при ошибке
            if self.status == MotorStatus.ERROR:
                if dpg.does_item_exist(f"{self.tag}_status_panel"):
                    dpg.bind_item_theme(f"{self.tag}_status_panel", "motor_alarm_theme")
            else:
                if dpg.does_item_exist(f"{self.tag}_status_panel"):
                    dpg.bind_item_theme(f"{self.tag}_status_panel", "motor_status_theme")

        except Exception as e:
            print(f"Ошибка обновления отображения основных параметров: {e}")

    def _update_temperature_display(self):
        """Обновление отображения температуры"""
        try:
            dpg = self.dpg

            # Температура вала
            if dpg.does_item_exist(f"{self.tag}_shaft_temp_val"):
                dpg.set_value(f"{self.tag}_shaft_temp_val", f"{self.shaft_temperature:3.1f}°C")

        except Exception as e:
            print(f"Ошибка обновления отображения температуры: {e}")

    def _update_display(self):
        """Обновление отображения в интерфейсе"""
        dpg = self.dpg
        try:
            # Текущая скорость
            if dpg.does_item_exist(f"{self.tag}_current_speed_val"):
                dpg.set_value(f"{self.tag}_current_speed_val", f"{self.current_speed:4d} об/мин")

            # Уставка скорости (может быть такой же как текущая или отдельно задаваемой)
            if dpg.does_item_exist(f"{self.tag}_setpoint_speed_val"):
                # Если уставка не задана отдельно, показываем текущую
                display_setpoint = self.setpoint_speed if self.setpoint_speed > 0 else self.current_speed
                dpg.set_value(f"{self.tag}_setpoint_speed_val", f"{display_setpoint:4d} об/мин")

            # Температура вала
            if dpg.does_item_exist(f"{self.tag}_shaft_temp_val"):
                dpg.set_value(f"{self.tag}_shaft_temp_val", f"{self.shaft_temperature:3.1f}°C")

            # Статус
            status_text = self.status.value
            if dpg.does_item_exist(f"{self.tag}_status_val"):
                dpg.set_value(f"{self.tag}_status_val", status_text)

            # Ток двигателя
            if dpg.does_item_exist(f"{self.tag}_current_val"):
                dpg.set_value(f"{self.tag}_current_val", f"{self.motor_current:3.1f} мА")

            # Время работы (с учётом заморозки)
            if dpg.does_item_exist(f"{self.tag}_time_val"):
                if self._time_frozen:
                    time_str = self._frozen_time_str
                else:
                    elapsed = time.time() - self.start_time
                    hours = int(elapsed // 3600)
                    minutes = int((elapsed % 3600) // 60)
                    seconds = int(elapsed % 60)
                    time_str = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
                dpg.set_value(f"{self.tag}_time_val", time_str)

            # Применяем тему тревоги при ошибке
            if self.status == MotorStatus.ERROR:
                if dpg.does_item_exist(f"{self.tag}_status_panel"):
                    dpg.bind_item_theme(f"{self.tag}_status_panel", "motor_alarm_theme")

        except Exception as e:
            print(f"Ошибка обновления отображения двигателя: {e}")

    def create_window(self, dpg):
        """
        Создание окна индикации двигателя BLSD-20.
        """
        # Создаем темы
        create_motor_themes(dpg, self.tag)

        # Проверяем, загружен ли крупный шрифт
        if dpg.does_item_exist("large_font"):
            self.large_font_loaded = True
        dpg.delete_item(f"{self.tag}_window")
        print(f'Создание индикатора двигателя: {self.tag}')

        with dpg.window(tag=f"{self.tag}_window",
                        width=475,
                        height=700,  # Меньше чем у TPM12, так как нет кнопок
                        label='Двигатель BLSD-20',
                        pos=(860, 0)):  # Позиция ниже окна TPM12

            # Панель текущей скорости
            with dpg.child_window(width=455, height=120, tag=f"{self.tag}_speed_panel"):
                dpg.add_text("Текущая скорость:", indent=20)
                current_speed_val = dpg.add_text("---", tag=f"{self.tag}_current_speed_val", indent=20)
                if self.large_font_loaded:
                    dpg.bind_item_font(current_speed_val, "large_font")
                else:
                    dpg.bind_item_theme(current_speed_val, "motor_large_value_theme")

            # Панель уставки скорости
            with dpg.child_window(width=455, height=120, tag=f"{self.tag}_setpoint_panel"):
                dpg.add_text("Установленная скорость:", indent=20)
                setpoint_val = dpg.add_text("---", tag=f"{self.tag}_setpoint_speed_val", indent=20)
                if self.large_font_loaded:
                    dpg.bind_item_font(setpoint_val, "large_font")
                else:
                    dpg.bind_item_theme(setpoint_val, "motor_large_value_theme")
                # Добавлен popup для изменения скорости
                with dpg.popup(setpoint_val, min_size=[120, 30]):
                    dpg.add_button(label="Изменить", width=100, height=25,
                                   callback=lambda: self._open_speed_dialog())

            # Группа для температуры и статуса
            with dpg.group(horizontal=True, horizontal_spacing=10):
                # Панель температуры вала
                with dpg.child_window(width=225, height=140, tag=f"{self.tag}_temp_panel"):
                    dpg.add_text("Температура вала:", indent=20)
                    temp_val = dpg.add_text("---", tag=f"{self.tag}_shaft_temp_val", indent=10)
                    if self.large_font_loaded:
                        dpg.bind_item_font(temp_val, "large_font")
                    else:
                        dpg.bind_item_theme(temp_val, "motor_large_value_theme")

                # Панель статуса
                with dpg.child_window(width=225, height=140, tag=f"{self.tag}_status_panel"):
                    dpg.add_text("Статус двигателя:", indent=20)
                    status_val = dpg.add_text("---", tag=f"{self.tag}_status_val", indent=20)
                    if self.large_font_loaded:
                        dpg.bind_item_font(status_val, "medium_font")
                    else:
                        dpg.bind_item_theme(status_val, "motor_large_value_theme")

            # Группа для тока и времени работы
            with dpg.group(horizontal=True, horizontal_spacing=10):
                # Панель тока двигателя
                with dpg.child_window(width=225, height=120, tag=f"{self.tag}_current_panel"):
                    dpg.add_text("Ток двигателя:", indent=20)
                    current_val = dpg.add_text("---", tag=f"{self.tag}_current_val", indent=20)
                    if self.large_font_loaded:
                        dpg.bind_item_font(current_val, "medium_font")
                    else:
                        dpg.bind_item_theme(current_val, "motor_large_value_theme")

                # Панель времени работы
                with dpg.child_window(width=225, height=120, tag=f"{self.tag}_time_panel"):
                    dpg.add_text("Время работы:", indent=20)
                    time_val = dpg.add_text("00:00:00", tag=f"{self.tag}_time_val", indent=20)
                    if self.large_font_loaded:
                        dpg.bind_item_font(time_val, "medium_font")
                    else:
                        dpg.bind_item_theme(time_val, "motor_large_value_theme")

        # Применяем темы к панелям
        if dpg.does_item_exist(f"{self.tag}_speed_panel"):
            dpg.bind_item_theme(f"{self.tag}_speed_panel", "motor_speed_theme")
        if dpg.does_item_exist(f"{self.tag}_setpoint_panel"):
            dpg.bind_item_theme(f"{self.tag}_setpoint_panel", "motor_setpoint_theme")
        if dpg.does_item_exist(f"{self.tag}_temp_panel"):
            dpg.bind_item_theme(f"{self.tag}_temp_panel", "motor_temp_theme")
        if dpg.does_item_exist(f"{self.tag}_status_panel"):
            dpg.bind_item_theme(f"{self.tag}_status_panel", "motor_status_theme")
        if dpg.does_item_exist(f"{self.tag}_current_panel"):
            dpg.bind_item_theme(f"{self.tag}_current_panel", "motor_current_theme")
        if dpg.does_item_exist(f"{self.tag}_time_panel"):
            dpg.bind_item_theme(f"{self.tag}_time_panel", "motor_time_theme")

        self.start_update_thread()

    def set_speed(self, speed: int):
        """
        Установить скорость двигателя.

        Args:
            speed: Скорость в об/мин (0-4000)
        """
        if self.driver:
            try:
                success, message = self.driver.set_fan_speed(speed)
                if success:
                    self.setpoint_speed = speed
                    print(f"Скорость установлена: {speed} об/мин")
                else:
                    print(f"Ошибка установки скорости: {message}")
            except Exception as e:
                print(f"Ошибка при установке скорости: {e}")
        return False

    def start_motor(self):
        """Запустить двигатель"""
        if self.driver and hasattr(self.driver, 'turn_on_camera'):
            try:
                success, message = self.driver.turn_on_camera()
                if success:
                    print("Двигатель запущен")
                else:
                    print(f"Ошибка запуска двигателя: {message}")
            except Exception as e:
                print(f"Ошибка при запуске двигателя: {e}")

    def stop_motor(self):
        """Остановить двигатель"""
        if self.driver and hasattr(self.driver, 'turn_off_camera'):
            try:
                success, message = self.driver.turn_off_camera()
                if success:
                    print("Двигатель остановлен")
                else:
                    print(f"Ошибка остановки двигателя: {message}")
            except Exception as e:
                print(f"Ошибка при остановке двигателя: {e}")

    def start_update_thread(self):
        """Запуск потока обновления данных"""
        if self.update_thread is None or not self.update_thread.is_alive():
            self.running = True
            self.update_thread = threading.Thread(
                target=self._update_loop,
                daemon=True
            )
            self.update_thread.start()
            print("Поток обновления данных двигателя запущен")

    def stop_update_thread(self):
        """Остановка потока обновления данных"""
        self.running = False
        if self.update_thread and self.update_thread.is_alive():
            self.update_thread.join(timeout=2)
            print("Поток обновления данных двигателя остановлен")

    def _update_loop(self):
        """
        Цикл обновления данных:
          - основные параметры: каждые 2 секунды (get_fan_speed/get_current/get_status/set_speed);
          - температура вала: раз в shaft_temp_update_interval (60 сек по умолчанию).
        """
        normal_interval = 2
        normal_counter = 0
        temp_counter = 0

        while self.running:
            try:
                normal_counter += 1
                temp_counter += 1

                if normal_counter >= normal_interval:
                    try:
                        self.update_normal_data()
                    except Exception as e:
                        print(f"MotorGUI normal update: {e}")
                    normal_counter = 0

                if temp_counter >= self.shaft_temp_update_interval:
                    try:
                        self.update_temperature_data()
                    except Exception as e:
                        print(f"MotorGUI temp update: {e}")
                    temp_counter = 0

                time.sleep(1)
            except Exception as e:
                print(f"Ошибка в потоке обновления двигателя: {e}")
                time.sleep(1)

    def _update_loop_old(self):
        """
        Цикл обновления данных с разными интервалами:
        - Основные параметры: каждые 2 секунды
        - Температура: каждые shaft_temp_update_interval секунд
        """
        # Счётчики в секундах (так как пауза 1 секунда)
        normal_interval = 2  # секунд
        normal_counter = 0
        temp_counter = 0

        while self.running:
            try:
                # Увеличиваем счётчики
                normal_counter += 1
                temp_counter += 1

                # Обновляем основные параметры
                if normal_counter >= normal_interval:
                    self.update_normal_data()
                    normal_counter = 0

                # Обновляем температуру с заданным интервалом
                if temp_counter >= self.shaft_temp_update_interval:
                    self.update_temperature_data()
                    temp_counter = 0

                time.sleep(1)

            except Exception as e:
                print(f"Ошибка в потоке обновления двигателя: {e}")
                time.sleep(1)


    def update_data(self):
        """
        Полное обновление всех данных (для ручного вызова).
        """
        self.update_normal_data()
        self.update_temperature_data()

"""
Модуль диалога установки скорости для двигателя BLSD-20.
Используется вместе с motor_gui.py.
"""

class MotorSpeedDialog:
    """
    Диалоговое окно для изменения скорости двигателя.
    Создаётся один раз и может быть открыто多次.
    """

    def __init__(self, dpg, tag: str, initial_speed: int, apply_callback):
        """
        Инициализация диалога.

        Args:
            dpg: экземпляр dearpygui
            tag: базовый тег родительского окна двигателя
            initial_speed: начальное значение скорости
            apply_callback: функция, вызываемая при применении нового значения
        """
        self.dpg = dpg
        self.tag = tag
        self.initial_speed = initial_speed
        self.apply_callback = apply_callback
        self._create_themes()

    def _create_themes(self):
        """Создание тем для диалога (если ещё не созданы)"""
        dpg = self.dpg
        # Тема для окна диалога
        if not dpg.does_item_exist(f"{self.tag}_speed_theme"):
            with dpg.theme(tag=f"{self.tag}_speed_theme"):
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

        # Тема для поля ввода (синий текст)
        if not dpg.does_item_exist(f"{self.tag}_input_theme"):
            with dpg.theme(tag=f"{self.tag}_input_theme"):
                with dpg.theme_component(dpg.mvInputInt):
                    dpg.add_theme_color(dpg.mvThemeCol_Text, (0, 0, 255, 255))

        # Темы для кнопок
        if not dpg.does_item_exist(f"{self.tag}_cancel_theme"):
            with dpg.theme(tag=f"{self.tag}_cancel_theme"):
                with dpg.theme_component(dpg.mvButton):
                    dpg.add_theme_color(dpg.mvThemeCol_Button, (140, 155, 175, 255))
                    dpg.add_theme_color(dpg.mvThemeCol_ButtonHovered, (165, 180, 195, 255))
                    dpg.add_theme_color(dpg.mvThemeCol_ButtonActive, (120, 135, 155, 255))
                    dpg.add_theme_color(dpg.mvThemeCol_Text, (255, 255, 255, 255))
                    dpg.add_theme_style(dpg.mvStyleVar_FramePadding, 18, 12)
                    dpg.add_theme_style(dpg.mvStyleVar_FrameRounding, 4)

        if not dpg.does_item_exist(f"{self.tag}_apply_theme"):
            with dpg.theme(tag=f"{self.tag}_apply_theme"):
                with dpg.theme_component(dpg.mvButton):
                    dpg.add_theme_color(dpg.mvThemeCol_Button, (65, 95, 135, 255))
                    dpg.add_theme_color(dpg.mvThemeCol_ButtonHovered, (85, 115, 160, 255))
                    dpg.add_theme_color(dpg.mvThemeCol_ButtonActive, (55, 80, 115, 255))
                    dpg.add_theme_color(dpg.mvThemeCol_Text, (255, 255, 255, 255))
                    dpg.add_theme_style(dpg.mvStyleVar_FramePadding, 18, 12)
                    dpg.add_theme_style(dpg.mvStyleVar_FrameRounding, 4)

    def open(self):
        """Открыть диалог установки скорости"""
        dpg = self.dpg
        # Если окно уже существует, удалим его перед созданием нового
        if dpg.does_item_exist(f"{self.tag}_speed_modal"):
            dpg.delete_item(f"{self.tag}_speed_modal")

        print('Открытие диалога установки скорости')

        window_width = 450
        window_height = 210

        viewport_width = dpg.get_viewport_width()
        viewport_height = dpg.get_viewport_height()
        pos_x = (viewport_width - window_width) // 2
        pos_y = (viewport_height - window_height) // 2

        with dpg.window(
                label="Установка скорости двигателя",
                modal=False,
                tag=f"{self.tag}_speed_modal",
                width=window_width,
                height=window_height,
                pos=[pos_x, pos_y],
                no_resize=True,
                no_collapse=True,
                no_close=False,
                no_title_bar=False
        ):
            # Применяем тему к окну
            dpg.bind_item_theme(f"{self.tag}_speed_modal", f"{self.tag}_speed_theme")
            dpg.add_spacer(height=5)

            # Область ввода скорости
            with dpg.child_window(
                    width=window_width - 40,
                    height=90,
                    border=True,
                    tag=f"{self.tag}_speed_input_area"
            ):
                dpg.add_spacer(height=8)
                with dpg.group(horizontal=True):
                    dpg.add_spacer(width=20)
                    input_field = dpg.add_input_int(
                        default_value=int(self.initial_speed),
                        step=10,
                        step_fast=100,
                        min_value=0,
                        max_value=4000,
                        width=240,
                        tag=f"{self.tag}_speed_input",
                        min_clamped=True,
                        max_clamped=True
                    )
                    # Применяем тему с синим текстом
                    dpg.bind_item_theme(input_field, f"{self.tag}_input_theme")
                    dpg.add_spacer(width=3)
                    dpg.add_text("об/мин", bullet=True)  # цвет наследуется из темы окна (белый)
                dpg.add_spacer(height=8)

            dpg.add_spacer(height=8)

            # Кнопки
            with dpg.group(horizontal=True):
                dpg.add_spacer(width=(window_width - 340) // 2)

                cancel_btn = dpg.add_button(
                    label="Отмена",
                    width=120,
                    callback=lambda: dpg.delete_item(f"{self.tag}_speed_modal")
                )
                dpg.bind_item_theme(cancel_btn, f"{self.tag}_cancel_theme")

                dpg.add_spacer(width=5)

                apply_btn = dpg.add_button(
                    label="Применить",
                    width=120,
                    callback=self._apply
                )
                dpg.bind_item_theme(apply_btn, f"{self.tag}_apply_theme")

                dpg.add_spacer(width=(window_width - 340) // 2)

        # Устанавливаем фокус и значение
        dpg.focus_item(f"{self.tag}_speed_input")
        dpg.set_value(f"{self.tag}_speed_input", int(self.initial_speed))
        dpg.show_item(f"{self.tag}_speed_modal")

    def _apply(self):
        """Обработчик нажатия кнопки 'Применить'"""
        dpg = self.dpg
        try:
            new_value = dpg.get_value(f"{self.tag}_speed_input")
            # Вызываем callback, переданный из MotorGUI
            self.apply_callback(int(new_value))
            # Закрываем диалог
            dpg.delete_item(f"{self.tag}_speed_modal")
        except Exception as e:
            print(f"Ошибка в диалоге установки скорости: {e}")
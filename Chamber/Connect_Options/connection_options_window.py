

from Chamber.Connect_Options.connection_options_ui import ConnectionOptionsUI


class ConnectionOptionsWindow:
    """Окно просмотра настроек соединения (только для чтения) с использованием DEVICES_DATA"""

    def __init__(self, dpg_module):
        """
        Args:
            dpg_module: Модуль dearpygui (dpg)
        """
        self.dpg = dpg_module
        self.ui = ConnectionOptionsUI(dpg_module)
        self.tag = "connection_options_window"
        self.is_created = False

    def create(self):
        """Создание окна (однократно, если еще не создано)"""
        if self.is_created and self.dpg.does_item_exist(self.tag):
            return

        if self.dpg.does_item_exist(self.tag):
            self.dpg.delete_item(self.tag)

        # Создаем окно через UI
        self.ui.create_window()

        self.is_created = True

    def show(self):
        """Показать окно настроек"""
        dpg = self.dpg

        if not self.is_created:
            self.create()

        dpg.show_item(self.tag)
        dpg.focus_item(self.tag)
        self._center_window()

    def hide(self):
        """Скрыть окно настроек"""
        dpg = self.dpg
        if dpg.does_item_exist(self.tag):
            dpg.hide_item(self.tag)

    def toggle(self):
        """Переключить видимость окна"""
        dpg = self.dpg
        if dpg.does_item_exist(self.tag) and dpg.is_item_visible(self.tag):
            self.hide()
        else:
            self.show()

    def _center_window(self):
        """Центрирование окна на экране"""
        dpg = self.dpg
        if not dpg.does_item_exist(self.tag):
            return

        viewport_width = dpg.get_viewport_width()
        viewport_height = dpg.get_viewport_height()
        window_width = dpg.get_item_width(self.tag)
        window_height = dpg.get_item_height(self.tag)

        pos_x = (viewport_width - window_width) // 2
        pos_y = (viewport_height - window_height) // 2

        dpg.set_item_pos(self.tag, [pos_x, pos_y])

    def is_visible(self) -> bool:
        """Проверить, видимо ли окно"""
        dpg = self.dpg
        return dpg.does_item_exist(self.tag) and dpg.is_item_visible(self.tag)

    def destroy(self):
        """Уничтожить окно"""
        dpg = self.dpg
        if dpg.does_item_exist(self.tag):
            dpg.delete_item(self.tag)
        self.is_created = False
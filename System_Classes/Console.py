import dearpygui.dearpygui as dpg
import sys
from io import StringIO


class ConsoleManager:
    def __init__(self):
        self.console_window_tag = "##CONSOLE_WINDOW"
        self.console_widget_tag = "##CONSOLE_WIDGET"
        self.original_stdout = sys.stdout
        self.original_stderr = sys.stderr
        self.capture_buffer = StringIO()

        # Перенаправляем вывод
        sys.stdout = self
        sys.stderr = self

    def write(self, text):
        # Записываем в буфер и оригинальный вывод
        self.capture_buffer.write(text)
        self.original_stdout.write(text)

        # Если консоль существует - выводим в нее
        if dpg.does_item_exist(self.console_widget_tag):
            current_text = dpg.get_value(self.console_widget_tag)
            new_text = f"{current_text}{text}"
            dpg.set_value(self.console_widget_tag, new_text)

            # Автопрокрутка
            dpg.configure_item(self.console_widget_tag, tracked=True, track_offset=1.0)

    def flush(self):
        self.capture_buffer.flush()
        self.original_stdout.flush()

    def create_console(self):
        if not dpg.does_item_exist(self.console_window_tag):
            with dpg.window(
                    tag=self.console_window_tag,
                    label="Консоль",
                    width=1200,
                    height=800,
                    show=True,
                    on_close=self.close_console
            ):
                dpg.add_input_text(
                    tag=self.console_widget_tag,
                    multiline=True,
                    readonly=True,
                    width=-1,
                    height=-1,
                    tracked=True,
                    track_offset=1.0
                )
            # Переносим сохраненный вывод
            dpg.set_value(self.console_widget_tag, self.capture_buffer.getvalue())

    def close_console(self):
        if dpg.does_item_exist(self.console_window_tag):
            dpg.delete_item(self.console_window_tag)

    def toggle_console(self):
        if dpg.does_item_exist(self.console_window_tag):
            self.close_console()
        else:
            self.create_console()
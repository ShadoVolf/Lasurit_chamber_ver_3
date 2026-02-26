"""
Диалог для отображения графика коррекции температуры и таблицы узлов.
"""

import numpy as np


def show_correction_plot_dialog(gui):
    """
    Открывает окно с графиком коррекции и таблицей значений.

    Args:
        gui: экземпляр TPM12_GUI, содержащий dpg, tag, корректоры.
    """
    dpg = gui.dpg
    tag_prefix = gui.tag
    modal_tag = f"{tag_prefix}_correction_plot_modal"

    if dpg.does_item_exist(modal_tag):
        dpg.delete_item(modal_tag)

    with dpg.window(
        label="График коррекции температуры",
        modal=True,
        tag=modal_tag,
        width=750,
        height=800,
        pos=[200, 50],
        no_resize=False
    ):
        dpg.add_text("Выберите канал и нажмите 'Построить'")
        dpg.add_spacer(height=5)

        with dpg.group(horizontal=True):
            dpg.add_radio_button(
                items=("Канал 1", "Канал 2"),
                default_value="Канал 1",
                tag=f"{tag_prefix}_plot_channel",
                horizontal=True
            )
            dpg.add_button(
                label="Построить",
                callback=lambda: _update_correction_plot(gui, modal_tag)
            )

        dpg.add_spacer(height=10)

        # Область графика
        with dpg.plot(label="Коррекция", height=350, width=700):
            dpg.add_plot_axis(dpg.mvXAxis, label="Показание датчика (°C)",
                              tag=f"{tag_prefix}_plot_xaxis")
            with dpg.plot_axis(dpg.mvYAxis, label="Скорректированное значение (°C)",
                               tag=f"{tag_prefix}_plot_yaxis"):
                dpg.add_line_series([], [], label="Коррекция",
                                    tag=f"{tag_prefix}_plot_series")

        dpg.add_spacer(height=10)

        # --- Таблица значений ---
        dpg.add_text("Значения в узлах через 10°C:")
        with dpg.child_window(tag=f"{tag_prefix}_plot_table_container",
                              width=700, height=200, border=True):
            pass  # будет заполнено позже

        dpg.add_spacer(height=5)
        dpg.add_text("", tag=f"{tag_prefix}_plot_status", color=(255, 0, 0))
        dpg.add_spacer(height=10)

        with dpg.group(horizontal=True):
            dpg.add_button(label="Закрыть", width=100,
                           callback=lambda: dpg.delete_item(modal_tag))

    dpg.show_item(modal_tag)


def _update_correction_plot(gui, modal_tag):
    """Обновить график и таблицу."""
    dpg = gui.dpg
    tag_prefix = gui.tag

    channel_str = dpg.get_value(f"{tag_prefix}_plot_channel")
    channel = 1 if "Канал 1" in channel_str else 2
    corrector = gui.corrector_ch1 if channel == 1 else gui.corrector_ch2

    if corrector is None:
        dpg.set_value(f"{tag_prefix}_plot_status",
                      f"Модель коррекции для канала {channel} не загружена.")
        _clear_plot_and_table(dpg, tag_prefix)
        return
    else:
        dpg.set_value(f"{tag_prefix}_plot_status", "")

    # Данные для графика (шаг 1°C)
    x_min, x_max = -60, 120
    x_plot = np.arange(x_min, x_max + 1, 1)
    try:
        y_plot = corrector.predict(x_plot)
    except Exception as e:
        dpg.set_value(f"{tag_prefix}_plot_status", f"Ошибка вычислений: {e}")
        _clear_plot_and_table(dpg, tag_prefix)
        return

    # Обновляем график
    series_tag = f"{tag_prefix}_plot_series"
    if dpg.does_item_exist(series_tag):
        dpg.set_value(series_tag, [x_plot.tolist(), y_plot.tolist()])
    dpg.fit_axis_data(f"{tag_prefix}_plot_xaxis")
    dpg.fit_axis_data(f"{tag_prefix}_plot_yaxis")

    # Данные для таблицы (шаг 10°C)
    x_table = np.arange(x_min, x_max + 10, 10)
    y_table = corrector.predict(x_table)
    delta = y_table - x_table  # разница (скорректированное - измеренное)

    _fill_table(dpg, tag_prefix, x_table, y_table, delta)


def _clear_plot_and_table(dpg, tag_prefix):
    """Очистить график и таблицу."""
    series = f"{tag_prefix}_plot_series"
    if dpg.does_item_exist(series):
        dpg.set_value(series, [[], []])

    container = f"{tag_prefix}_plot_table_container"
    if dpg.does_item_exist(container):
        for child in dpg.get_item_children(container, 1) or []:
            dpg.delete_item(child)


def _fill_table(dpg, tag_prefix, x_vals, y_vals, delta_vals):
    """Создать таблицу с узлами и разницей."""
    container = f"{tag_prefix}_plot_table_container"
    if not dpg.does_item_exist(container):
        return

    # Очищаем контейнер
    for child in dpg.get_item_children(container, 1) or []:
        dpg.delete_item(child)

    with dpg.table(parent=container, header_row=True,
                   borders_outerH=True, borders_outerV=True,
                   borders_innerH=True, borders_innerV=True,
                   resizable=True, policy=dpg.mvTable_SizingStretchProp):
        dpg.add_table_column(label="Датчик (°C)")
        dpg.add_table_column(label="Скорректировано (°C)")
        dpg.add_table_column(label="Разница (°C)")

        for x, y, d in zip(x_vals, y_vals, delta_vals):
            with dpg.table_row():
                dpg.add_text(f"{x:.1f}")
                dpg.add_text(f"{y:.2f}")
                dpg.add_text(f"{d:+.2f}")

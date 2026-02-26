import os
from datetime import date
from datetime import datetime
from urllib.parse import urlparse


# Параметры подключения
server = 'SQL4\\SQLAPPS'  # Имя сервера и экземпляра
database = 'RqSql'  # Имя базы данных
username = 'msql'  # Логин
password = 'MkndKfEquAqDexj'  # Пароль

version_ = '0.0.1'


def get_connection_string():
    sqlengine = 'mysql+mysqlconnector://xampp:43FPa!29S8HQeAW@MES1:3306/coordinator'
    return sqlengine

def get_version():
    return version_


def parse_connection_string():
    """Парсит URI подключения и извлекает параметры."""
    try:
        parsed = urlparse(get_connection_string())
        return {
            'user': parsed.username,
            'password': parsed.password,
            'host': parsed.hostname,
            'port': parsed.port,
            'database': parsed.path.lstrip('/')
        }
    except Exception as e:
        print(f"Ошибка парсинга URI: {e}")
        return None


def get_MSSQL_connection_string():
    sqlengine = f"mssql+pyodbc://{username}:{password}@{server}/{database}?driver=ODBC+Driver+17+for+SQL+Server"
    return sqlengine


# Возвращает путь к папке с катинками для программы
def get_pict_path():
    """Возвращает путь к файлам протоколов"""
    # Получаем текущую директорию запуска программы
    current_directory = os.getcwd()

    # Формируем путь к папке "Pictures"
    path = os.path.join(current_directory, "Pictures")

    # Создаем папку, если она не существует
    os.makedirs(path, exist_ok=True)
    return path


# Возвращает текущую диекторию запуска программы
def get_system_path():
    return os.getcwd()


def get_current_date() -> str:
    """Возвращает текущую дату в формате 'dd.mm.yyyy'"""
    return date.today().strftime("%d.%m.%Y")


def get_current_datetime() -> str:
    """Возвращает текущую дату и время в формате 'dd.mm.yyyy HH.MM.SS'"""
    return datetime.now().strftime("%d.%m.%Y %H:%M:%S")


def get_current_time() -> str:
    """Возвращает текущую дату и время в формате 'dd.mm.yyyy HH.MM.SS'"""
    return datetime.now().strftime("%H:%M:%S")


# Центрирует заданное окно в контексте
def center_window(dpg, name_window):
    viewport_width = dpg.get_viewport_client_width()
    viewport_height = dpg.get_viewport_client_height()
    window_width = dpg.get_item_width(name_window)
    window_height = dpg.get_item_height(name_window)
    x = (viewport_width - window_width) // 2
    y = (viewport_height - window_height) // 2
    dpg.set_item_pos(name_window, [x, y])





# Выводит окно с сообщением
def show_message(dpg, header, message):
    with dpg.window(width=300, height=300,
                    label=header,
                    tag=f'Message_windows_{header}'):
        for row in message:
            dpg.add_text(row)
    center_window(dpg, f'Message_windows_{header}')


def show_message_inf(dpg, header, message):
    dpg.delete_item(f'Message_windows_{header}')
    dpg.delete_item(f'Message_windows_text_{header}')
    with dpg.window(width=900, height=150,
                    label=header,
                    tag=f'Message_windows_{header}'):
        dpg.add_input_text(tag=f'Message_windows_text_{header}',
                           multiline=True,
                           readonly=True,
                           width=-1,
                           height=-1,
                           tracked=True,
                           track_offset=1.0
                           )
        temp = ""
        for row in message:
            temp = f'{temp}\n{row}'
        dpg.set_value(f'Message_windows_text_{header}', temp)
        dpg.set_item_height(f'Message_windows_text_{header}', -1)
    center_window(dpg, f'Message_windows_{header}')

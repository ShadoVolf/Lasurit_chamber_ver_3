import os
import logging
from datetime import datetime
from pathlib import Path

class ChamberLogger:
    """
    Единый логгер для всех операций, связанных с камерой.
    Создаёт новый файл лога при инициализации с меткой времени.
    """
    def __init__(self, log_dir: str = "logs", prefix: str = "chamber_log"):
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(exist_ok=True)

        # Генерация имени файла с текущей датой и временем
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.log_file = self.log_dir / f"{prefix}_{timestamp}.log"

        # Настройка logging
        self.logger = logging.getLogger("ChamberLogger")
        self.logger.setLevel(logging.DEBUG)

        # Обработчик для файла
        file_handler = logging.FileHandler(self.log_file, encoding="utf-8")
        file_handler.setLevel(logging.DEBUG)
        file_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        file_handler.setFormatter(file_formatter)

        # Обработчик для консоли (stderr)
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        console_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        console_handler.setFormatter(console_formatter)

        # Удаляем существующие обработчики, чтобы избежать дублирования
        if self.logger.hasHandlers():
            self.logger.handlers.clear()

        self.logger.addHandler(file_handler)
        self.logger.addHandler(console_handler)

        self.logger.info(f"Лог-файл создан: {self.log_file}")

    def log(self, message: str, level: str = "INFO"):
        """Универсальный метод логирования."""
        level = level.upper()
        if level == "DEBUG":
            self.logger.debug(message)
        elif level == "INFO":
            self.logger.info(message)
        elif level == "WARNING":
            self.logger.warning(message)
        elif level == "ERROR":
            self.logger.error(message)
        elif level == "CRITICAL":
            self.logger.critical(message)
        else:
            self.logger.info(message)

# Глобальный экземпляр (создаётся при первом импорте)
_logger = None

def get_logger():
    """Получить или создать глобальный логгер."""
    global _logger
    if _logger is None:
        _logger = ChamberLogger()
    return _logger
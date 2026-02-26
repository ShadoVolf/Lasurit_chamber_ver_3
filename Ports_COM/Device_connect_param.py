from dataclasses import dataclass, asdict
from typing import Dict, Any, List


@dataclass
class DeviceConnectionParams:
    """Параметры подключения к устройству через COM-порт."""

    com_port: str = "COM1"
    baudrate: int = 9600
    data_bits: int = 8
    stop_bits: int = 1
    parity: str = "N"
    timeout: float = 1.0
    address: int = 1
    connected: bool = False
    auto_select_com: bool = True  # Добавлена аннотация типа

    @classmethod
    def from_dict(cls, data: dict) -> 'DeviceConnectionParams':
        """Создание из словаря."""
        return cls(**{k: v for k, v in data.items()
                      if k in cls.__dataclass_fields__})

    def to_dict(self) -> Dict[str, Any]:
        """Преобразование в словарь."""
        return asdict(self)

    def validate(self) -> List[str]:
        """Проверка корректности параметров."""
        errors = []

        if not self.com_port:
            errors.append("Не указан COM-порт")

        if self.baudrate <= 0:
            errors.append("Некорректная скорость передачи")

        if self.data_bits not in (5, 6, 7, 8):
            errors.append("Биты данных должны быть 5, 6, 7 или 8")

        if self.stop_bits not in (1, 2):
            errors.append("Стоповые биты должны быть 1 или 2")

        if self.parity not in ("N", "E", "O"):
            errors.append("Четность должна быть N, E или O")

        if not (1 <= self.address <= 247):
            errors.append("Адрес должен быть в диапазоне 1-247")

        return errors
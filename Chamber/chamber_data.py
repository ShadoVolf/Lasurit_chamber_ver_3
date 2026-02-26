from dataclasses import dataclass
from enum import Enum


class ProcessStatus(Enum):
    IDLE = "Ожидание"
    HEATING = "Нагрев"
    STABILIZING = "Стабилизация"
    HOLDING = "Выдержка"
    COMPLETED = "Завершён"
    STOPPED = "Остановлен"
    ERROR = "Ошибка"

@dataclass
class ChamberData:
    """Текущие данные камеры для отображения в GUI"""
    current_temp: float = 0.0
    target_temp: float = 0.0
    gradient: float = 0.0
    fan_speed: int = 0
    motor_current: float = 0.0
    hold_remaining: float = 0.0          # секунд до окончания выдержки
    process_status: ProcessStatus = ProcessStatus.IDLE
    p_value: float = 0.0
    i_value: int = 0
    d_value: int = 0
    current_setpoint: float = 0.0  # текущая уставка прибора


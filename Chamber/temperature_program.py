import os
import json
from typing import List, Dict, Optional

class TemperatureProgram:
    """Логика температурной программы (список ступеней)."""
    def __init__(self):
        self.steps: List[Dict] = []          # каждая ступень: {'temperature': float, 'rate': float, 'hold_time': float}
        self.current_index: Optional[int] = None
        self.filename: Optional[str] = None

    def add_step_1(self, temperature: float, rate: float, hold_time: float) -> int:
        """Добавить ступень, вернуть индекс."""
        step = {
            'temperature': round(temperature, 1),
            'rate': round(rate, 1),
            'hold_time': round(hold_time, 1)
        }
        self.steps.append(step)
        return len(self.steps) - 1

    def add_step(self, temperature: float, rate: float, hold_time: float,
                 pid_p: float = None, pid_i: int = None, pid_d: int = None) -> int:
        """Добавить ступень с опциональными PID."""
        step = {
            'temperature': round(temperature, 1),
            'rate': round(rate, 1),
            'hold_time': round(hold_time, 1)
        }
        if pid_p is not None:
            step['pid_p'] = round(pid_p, 2)
        if pid_i is not None:
            step['pid_i'] = int(pid_i)
        if pid_d is not None:
            step['pid_d'] = int(pid_d)
        self.steps.append(step)
        return len(self.steps) - 1

    def update_step_pid(self, index: int, p: float, i: int, d: int):
        """Обновить PID для существующей ступени."""
        if 0 <= index < len(self.steps):
            self.steps[index]['pid_p'] = round(p, 2)
            self.steps[index]['pid_i'] = int(i)
            self.steps[index]['pid_d'] = int(d)

    def load(self, filepath: str):
        """Загрузить программу из JSON с поддержкой PID."""
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        self.steps = []
        for item in data:
            step = {
                'temperature': float(item['temperature']),
                'rate': float(item['rate']),
                'hold_time': float(item['hold_time'])
            }
            if 'pid_p' in item:
                step['pid_p'] = float(item['pid_p'])
            if 'pid_i' in item:
                step['pid_i'] = int(item['pid_i'])
            if 'pid_d' in item:
                step['pid_d'] = int(item['pid_d'])
            self.steps.append(step)
        self.current_index = None
        self.filename = filepath

    def remove_step(self, index: int) -> bool:
        """Удалить ступень по индексу."""
        if 0 <= index < len(self.steps):
            del self.steps[index]
            if self.current_index is not None:
                if index < self.current_index:
                    self.current_index -= 1
                elif index == self.current_index:
                    self.current_index = None
            return True
        return False

    def clear(self):
        """Очистить программу."""
        self.steps.clear()
        self.current_index = None

    def get_step(self, index: int) -> Optional[Dict]:
        """Получить копию ступени."""
        if 0 <= index < len(self.steps):
            return self.steps[index].copy()
        return None

    def get_all_steps(self) -> List[Dict]:
        """Получить копию всех ступеней."""
        return self.steps.copy()

    def set_current(self, index: int) -> bool:
        """Установить текущую ступень."""
        if 0 <= index < len(self.steps):
            self.current_index = index
            return True
        return False

    def move_to_next(self) -> bool:
        """Перейти к следующей ступени. Вернуть True, если успешно."""
        if self.current_index is None:
            if self.steps:
                self.current_index = 0
                return True
            return False
        if self.current_index + 1 < len(self.steps):
            self.current_index += 1
            return True
        return False

    def save(self, filepath: str):
        """Сохранить программу в JSON."""
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(self.steps, f, indent=2, ensure_ascii=False)
        self.filename = filepath

    def load(self, filepath: str):
        """Загрузить программу из JSON."""
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        self.steps = []
        for item in data:
            if isinstance(item, dict) and 'temperature' in item and 'rate' in item and 'hold_time' in item:
                self.steps.append({
                    'temperature': float(item['temperature']),
                    'rate': float(item['rate']),
                    'hold_time': float(item['hold_time'])
                })
        self.current_index = None
        self.filename = filepath
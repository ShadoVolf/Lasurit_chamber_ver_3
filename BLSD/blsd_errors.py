import time

from BLSD.Blsd_data import BLSD_DATA


class BLSD20ErrorHandler:
    """Класс для обработки и описания ошибок BLSD-20Modbus устройства."""

    # Словарь с полным описанием ошибок согласно документации
    ERROR_DESCRIPTIONS = {
        0: {
            "bit": 0,
            "code": "POWER_SUPPLY_RANGE",
            "short": "Выход за диапазон питающего напряжения",
            "full": "Напряжение питания вышло за допустимый диапазон (20-51В). Проверьте источник питания.",
            "severity": "CRITICAL",
            "action": "Проверьте напряжение питания. Убедитесь, что оно в пределах 24-48В."
        },
        1: {
            "bit": 1,
            "code": "MOTOR_OVERLOAD",
            "short": "Перегрузка или замыкание обмоток двигателя",
            "full": "Превышен допустимый ток в обмотках двигателя или обнаружено замыкание.",
            "severity": "CRITICAL",
            "action": "Проверьте двигатель и его подключение. Уменьшите нагрузку или ограничение тока."
        },
        2: {
            "bit": 2,
            "code": "BRAKE_OVERLOAD",
            "short": "Перегрузка тормозной схемы",
            "full": "Тормозная схема перегружена. Возможно, слишком интенсивное торможение.",
            "severity": "WARNING",
            "action": "Увеличьте время торможения. Проверьте тормозной резистор."
        },
        3: {
            "bit": 3,
            "code": "POWER_STAGE_OVERLOAD",
            "short": "Перегрузка силовой части",
            "full": "Перегрузка ключей MOSFET силовой части.",
            "severity": "CRITICAL",
            "action": "Дайте устройству остыть. Проверьте вентиляцию. Уменьшите ток или нагрузку."
        },
        4: {
            "bit": 4,
            "code": "HALL_SENSOR_ERROR",
            "short": "Ошибка подключения датчиков Холла",
            "full": "Неисправность или неправильное подключение датчиков Холла двигателя.",
            "severity": "CRITICAL",
            "action": "Проверьте подключение датчиков Холла (клеммы 10-13). Проверьте двигатель."
        },
        5: {
            "bit": 5,
            "code": "PARAMETER_ERROR",
            "short": "Ошибка установки параметров",
            "full": "Некорректное значение параметров в регистрах настройки.",
            "severity": "WARNING",
            "action": "Проверьте установленные параметры. Выполните сброс к заводским настройкам."
        },
        6: {
            "bit": 6,
            "code": "CPU_OVERLOAD",
            "short": "Перегрузка процессора",
            "full": "Процессор не успевает обрабатывать задачи.",
            "severity": "WARNING",
            "action": "Упростите пользовательскую программу. Уменьшите частоту обновления."
        },
        7: {
            "bit": 7,
            "code": "CONTROL_PROGRAM_ERROR",
            "short": "Ошибка управляющей программы",
            "full": "Ошибка во встроенном ПО устройства.",
            "severity": "CRITICAL",
            "action": "Перезагрузите устройство. При повторении - обратитесь к производителю."
        },
        8: {
            "bit": 8,
            "code": "USER_PROGRAM_ERROR",
            "short": "Ошибка выполнения пользовательской программы",
            "full": "Ошибка в пользовательской программе (некорректная команда, деление на ноль и т.д.).",
            "severity": "WARNING",
            "action": "Проверьте пользовательскую программу. Используйте отладку."
        },
        9: {
            "bit": 9,
            "code": "MEMORY_ERROR",
            "short": "Ошибка чтения/записи настроек",
            "full": "Ошибка доступа к энергонезависимой памяти.",
            "severity": "WARNING",
            "action": "Выполните сохранение настроек повторно. При повторении - сбросьте настройки."
        },
        10: {
            "bit": 10,
            "code": "KEY_ERROR",
            "short": "Ошибка работы с ключами",
            "full": "Ошибка управления силовыми ключами MOSFET.",
            "severity": "CRITICAL",
            "action": "Выключите питание. Проверьте двигатель и силовые цепи. Включите снова."
        },
        11: {
            "bit": 11,
            "code": "MODBUS_PARITY_ERROR",
            "short": "Ошибка четности Modbus",
            "full": "Ошибка проверки четности в принятой по Modbus команде.",
            "severity": "WARNING",
            "action": "Проверьте настройки Modbus (четность, скорость). Проверьте качество линии связи."
        }
    }

    # Регистр ошибок
    REG_ERROR = 0x5021

    @classmethod
    def get_error_description(cls, error_code: int) -> dict:
        """
        Получение полного описания ошибки по коду.

        Args:
            error_code: 16-битный код ошибки из регистра 0x5021

        Returns:
            Словарь с полной информацией об ошибке
        """
        if error_code == 0:
            return {
                "has_errors": False,
                "error_code": 0,
                "error_code_hex": "0x0000",
                "message": "Ошибок нет",
                "errors": [],
                "summary": "Устройство работает нормально"
            }

        active_errors = []
        error_summary = []

        # Проверяем каждый бит
        for bit in range(16):
            if error_code & (1 << bit):
                if bit in cls.ERROR_DESCRIPTIONS:
                    error_info = cls.ERROR_DESCRIPTIONS[bit].copy()
                    error_info["bit_mask"] = 1 << bit
                    error_info["bit_mask_hex"] = hex(1 << bit)
                    active_errors.append(error_info)
                    error_summary.append(f"{bit}: {error_info['short']}")
                else:
                    # Неизвестная ошибка
                    active_errors.append({
                        "bit": bit,
                        "code": f"UNKNOWN_{bit}",
                        "short": f"Неизвестная ошибка (бит {bit})",
                        "full": f"Неизвестная ошибка в бите {bit}. Код: {error_code:04X}",
                        "severity": "UNKNOWN",
                        "action": "Обратитесь к документации или производителю",
                        "bit_mask": 1 << bit,
                        "bit_mask_hex": hex(1 << bit)
                    })
                    error_summary.append(f"{bit}: Неизвестная ошибка")

        # Определяем общую критичность
        severities = [err["severity"] for err in active_errors]
        if "CRITICAL" in severities:
            overall_severity = "CRITICAL"
        elif "WARNING" in severities:
            overall_severity = "WARNING"
        else:
            overall_severity = "INFO"

        error_dict = {
            "has_errors": True,
            "error_code": error_code,
            "error_code_hex": hex(error_code),
            "error_count": len(active_errors),
            "severity": overall_severity,
            "errors": active_errors,
            "summary": " | ".join(error_summary),
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
        }
        BLSD_DATA.apppend_error(error_dict)
        return error_dict
#Лог ошибок двигателя
from datetime import datetime


class BLSD_DATA:
    rotor_error_log =[]

    @staticmethod
    def get_rotor_error_log():
        return BLSD_DATA.rotor_error_log

    @staticmethod
    def apppend_error(value: dict):
        current_time = datetime.now()
        formatted_time = current_time.strftime("%d.%m.%y  %H:%M:%S")
        value['Date'] = formatted_time
        BLSD_DATA.rotor_error_log.append(value)

    @staticmethod
    def clear_rotor_error_log():
        """Очистка лога ошибок двигателя"""
        BLSD_DATA.rotor_error_log.clear()

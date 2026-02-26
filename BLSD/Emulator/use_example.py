"""
Пример использования эмулятора BLSD-20Modbus.
"""

import time
import sys

from BLSD.Emulator.BLSD_Emulator import BLSDEmulator
from blsd_emulator_helpers import BLSDEmulatorHelper


def example_usage():
    """Пример использования эмулятора."""

    # Создаем эмулятор
    print("Создание эмулятора BLSD-20...")
    emulator = BLSDEmulator(
        slave_id=1,
        motor_type='FL42BLS02',
        simulation_speed=2.0  # Ускоренная симуляция
    )

    # Обработчики событий
    def on_motor_started(data):
        print(f"Двигатель запущен: {data}")

    def on_motor_stopped(data):
        print(f"Двигатель остановлен: {data}")

    def on_error_occurred(data):
        error_code = data.get('error_code', 0)
        errors = BLSDEmulatorHelper.parse_error_code(error_code)
        print(f"Произошла ошибка: 0x{error_code:04X}")
        print(f"Описание ошибок: {', '.join(errors)}")

    def on_position_reached(data):
        print(f"Достигнута позиция: {data}")

    def on_temperature_warning(data):
        warnings = data.get('warnings', [])
        for component, temp in warnings:
            print(f"Внимание: {component} перегрет ({temp:.1f}°C)")

    # Подписываемся на события
    emulator.subscribe_event('motor_started', on_motor_started)
    emulator.subscribe_event('motor_stopped', on_motor_stopped)
    emulator.subscribe_event('error_occurred', on_error_occurred)
    emulator.subscribe_event('position_reached', on_position_reached)
    emulator.subscribe_event('temperature_warning', on_temperature_warning)

    # Запускаем эмулятор
    print("Запуск эмулятора...")
    emulator.start()

    try:
        # Даем эмулятору время на инициализацию
        time.sleep(1.0)

        # Получаем начальное состояние
        state = emulator.get_state()
        print(BLSDEmulatorHelper.format_state_report(state))

        # Тестируем команды Modbus
        print("\nТестирование команд Modbus...")

        # Чтение регистров состояния
        print("Чтение регистров состояния:")
        speed = emulator.read_input_registers(0x3002, 1)
        print(f"  Скорость: {speed[0]} об/мин")

        position = emulator.read_input_registers(0x3003, 2)
        pos_value = (position[1] << 16) | position[0]
        print(f"  Позиция: {pos_value}")

        # Настройка параметров
        print("\nНастройка параметров:")
        emulator.write_registers(0x500B, [1500])  # Установка скорости
        emulator.write_registers(0x500C, [200])  # Установка ускорения
        emulator.write_registers(0x500D, [200])  # Установка замедления

        # Запуск двигателя
        print("\nЗапуск двигателя...")
        emulator.write_coil(0x2000, True)

        # Даем двигателю поработать
        print("Двигатель работает...")
        time.sleep(3.0)

        # Получаем обновленное состояние
        state = emulator.get_state()
        print(BLSDEmulatorHelper.format_state_report(state))

        # Имитация ошибки
        print("\nИмитация ошибки перегрева...")
        emulator.inject_error(0x0001)
        time.sleep(1.0)

        # Остановка двигателя
        print("\nОстановка двигателя...")
        emulator.write_coil(0x2001, True)
        time.sleep(2.0)

        # Получение дампа регистров
        print("\nПолучение дампа регистров...")
        reg_dump = emulator.get_register_dump()

        # Сохранение состояния в файл
        BLSDEmulatorHelper.save_state_to_file(
            {'state': state, 'registers': reg_dump},
            'blsd_emulator_state.json'
        )
        print("Состояние сохранено в файл 'blsd_emulator_state.json'")

        # Информация о подключении
        print("\nИнформация о подключении:")
        conn_info = emulator.get_connection_info()
        for key, value in conn_info.items():
            print(f"  {key}: {value}")

        print("\nТест завершен успешно!")

    except KeyboardInterrupt:
        print("\nТест прерван пользователем")
    except Exception as e:
        print(f"\nОшибка во время теста: {e}")
    finally:
        # Останавливаем эмулятор
        print("\nОстановка эмулятора...")
        emulator.stop()


def interactive_demo():
    """Интерактивная демонстрация эмулятора."""
    import cmd

    class BLSDEmulatorShell(cmd.Cmd):
        """Интерактивная оболочка для управления эмулятором."""

        intro = "Добро пожаловать в интерактивную оболочку BLSD-20 эмулятора.\nВведите 'help' для списка команд."
        prompt = 'blsd> '

        def __init__(self):
            super().__init__()
            self.emulator = None

        def preloop(self):
            """Инициализация перед началом цикла."""
            print("Инициализация эмулятора...")
            self.emulator = BLSDEmulator(slave_id=1, motor_type='FL42BLS02')
            self.emulator.start()
            time.sleep(0.5)

        def postloop(self):
            """Очистка после завершения цикла."""
            if self.emulator:
                self.emulator.stop()

        def do_start(self, arg):
            """Запуск двигателя: start"""
            self.emulator.write_coil(0x2000, True)
            print("Двигатель запущен")

        def do_stop(self, arg):
            """Остановка двигателя: stop"""
            self.emulator.write_coil(0x2001, True)
            print("Двигатель остановлен")

        def do_emergency(self, arg):
            """Аварийная остановка: emergency"""
            self.emulator.write_coil(0x2002, True)
            print("Аварийная остановка")

        def do_speed(self, arg):
            """Установка скорости: speed <значение>"""
            try:
                speed = int(arg)
                if 0 <= speed <= 4000:
                    self.emulator.write_registers(0x500B, [speed])
                    print(f"Скорость установлена: {speed} об/мин")
                else:
                    print("Скорость должна быть от 0 до 4000 об/мин")
            except ValueError:
                print("Неверное значение скорости")

        def do_state(self, arg):
            """Показать состояние: state"""
            state = self.emulator.get_state()
            print(BLSDEmulatorHelper.format_state_report(state))

        def do_registers(self, arg):
            """Показать регистры: registers"""
            reg_dump = self.emulator.get_register_dump()

            print("\nHolding Registers:")
            for name, data in reg_dump.get('holding_registers', {}).items():
                print(f"  {name}: {data.get('value')} (0x{data.get('hex')[2:].upper()})")

            print("\nInput Registers:")
            for name, data in reg_dump.get('input_registers', {}).items():
                print(f"  {name}: {data.get('value')} (0x{data.get('hex')[2:].upper()})")

        def do_inject_error(self, arg):
            """Имитация ошибки: inject_error <код>"""
            try:
                error_code = int(arg, 0)  # Поддерживает hex (0x...)
                self.emulator.inject_error(error_code)
                print(f"Ошибка 0x{error_code:04X} имитирована")
            except ValueError:
                print("Неверный код ошибки")

        def do_clear_errors(self, arg):
            """Сброс ошибок: clear_errors"""
            self.emulator.clear_errors()
            print("Ошибки сброшены")

        def do_save(self, arg):
            """Сохранение настроек: save"""
            self.emulator.write_registers(0x5022, [0x37FA])
            print("Настройки сохранены")

        def do_restart(self, arg):
            """Перезагрузка устройства: restart"""
            self.emulator.write_registers(0x5024, [0x95AF])
            print("Устройство перезагружается...")
            time.sleep(1.0)

        def do_quit(self, arg):
            """Выход из программы: quit"""
            print("Завершение работы...")
            return True

        def do_exit(self, arg):
            """Выход из программы: exit"""
            return self.do_quit(arg)

    # Запуск интерактивной оболочки
    shell = BLSDEmulatorShell()
    shell.cmdloop()


if __name__ == "__main__":
    print("BLSD-20Modbus эмулятор - примеры использования")
    print("=" * 50)

    if len(sys.argv) > 1 and sys.argv[1] == '--interactive':
        interactive_demo()
    else:
        example_usage()
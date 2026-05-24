"""Запуск всех тестов Telegram клиента"""

import unittest
import sys
import os

# Добавляем родительский каталог в путь для абсолютных импортов
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Импортируем все тестовые модули
from tests.test_tg_handlers import TestTelegramHandlers
from tests.test_tg_game import TestTelegramGameLogic
from tests.test_tg_integration import TestTelegramIntegration

def run_all_tests():
    """Запуск всех тестов Telegram клиента"""
    print("🚀 Запуск всех тестов Telegram клиента")
    print("=" * 50)

    # Создаем тестовый набор
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    # Добавляем тесты
    suite.addTests(loader.loadTestsFromTestCase(TestTelegramHandlers))
    suite.addTests(loader.loadTestsFromTestCase(TestTelegramGameLogic))
    suite.addTests(loader.loadTestsFromTestCase(TestTelegramIntegration))

    # Запускаем тесты
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    # Выводим результаты
    print("\n" + "=" * 50)
    print(f"📊 Результаты тестирования:")
    print(f"✅ Успешно: {result.testsRun - len(result.failures) - len(result.errors)}")
    print(f"❌ Провалено: {len(result.failures)}")
    print(f"💥 Ошибок: {len(result.errors)}")
    print(f"📈 Всего тестов: {result.testsRun}")

    if result.failures:
        print("\n📋 Проваленные тесты:")
        for test, traceback in result.failures:
            print(f"  - {test}: {traceback}")

    if result.errors:
        print("\n📋 Ошибки тестов:")
        for test, traceback in result.errors:
            print(f"  - {test}: {traceback}")

    return result.wasSuccessful()

if __name__ == '__main__':
    success = run_all_tests()
    sys.exit(0 if success else 1)
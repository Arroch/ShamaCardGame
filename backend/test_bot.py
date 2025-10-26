"""
Тестовый скрипт для проверки функциональности Telegram бота.

Запускает бота и проверяет его основные компоненты.
"""

import os
import logging
from dotenv import load_dotenv

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

def test_bot_config():
    """Проверяет наличие конфигурации для бота."""
    load_dotenv()
    
    # Проверяем наличие токена
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        logger.error("Не указан токен бота! Установите переменную окружения TELEGRAM_BOT_TOKEN")
        return False
    
    # Получаем тип хранилища
    storage_type = os.environ.get("STORAGE_TYPE", "file")
    logger.info(f"Тип хранилища: {storage_type}")
    
    if storage_type == "postgres":
        # Проверяем настройки PostgreSQL
        db_host = os.environ.get("DB_HOST")
        db_port = os.environ.get("DB_PORT")
        db_name = os.environ.get("DB_NAME")
        db_user = os.environ.get("DB_USER")
        db_password = os.environ.get("DB_PASSWORD")
        
        if not all([db_host, db_port, db_name, db_user]):
            logger.warning("Не указаны все параметры для подключения к PostgreSQL!")
    elif storage_type == "file":
        # Проверяем настройки файлового хранилища
        storage_dir = os.environ.get("STORAGE_DIR")
        if storage_dir:
            logger.info(f"Директория для хранения файлов: {storage_dir}")
        else:
            logger.info("Будет использована директория по умолчанию: ./storage")
    else:
        logger.warning(f"Неизвестный тип хранилища: {storage_type}. Будет использовано файловое хранилище.")
    
    logger.info("Конфигурация бота загружена успешно")
    return True

def test_imports():
    """Проверяет, что все необходимые модули импортируются без ошибок."""
    try:
        from telegram_bot import TelegramBotHandler, GameSession, GameSessionManager
        from core import GameEngine, MatchState, Player, Card
        from game_constants import GameConstants
        
        # Проверяем импорт обоих вариантов хранилища
        try:
            from database_manager import DatabaseManager
            logger.info("Модуль PostgreSQL импортирован успешно")
        except ImportError:
            logger.warning("Модуль PostgreSQL не импортирован, но это не критично")
            
        try:
            from file_storage import FileStorage
            from storage_factory import StorageFactory
            logger.info("Модули файлового хранилища импортированы успешно")
        except ImportError as e:
            logger.error(f"Ошибка импорта модулей файлового хранилища: {e}")
            return False
        
        logger.info("Все необходимые модули импортируются успешно")
        return True
    except ImportError as e:
        logger.error(f"Ошибка импорта модулей: {e}")
        return False

def test_storage_factory():
    """Проверяет работу фабрики хранилища."""
    try:
        from storage_factory import StorageFactory
        storage_types = StorageFactory.get_storage_types()
        
        logger.info(f"Доступные типы хранилищ: {', '.join(storage_types.keys())}")
        for storage_type, description in storage_types.items():
            logger.info(f"  - {storage_type}: {description}")
        
        return True
    except Exception as e:
        logger.error(f"Ошибка при проверке фабрики хранилища: {e}")
        return False

def run_tests():
    """Запускает все тесты."""
    tests = [
        ("Проверка конфигурации", test_bot_config),
        ("Проверка импорта модулей", test_imports),
        ("Проверка фабрики хранилища", test_storage_factory),
    ]
    
    results = []
    
    print("\n=== Запуск тестов Telegram бота ===\n")
    
    for name, test_func in tests:
        print(f"Выполняется тест: {name}...")
        try:
            result = test_func()
            results.append((name, result))
            status = "УСПЕШНО" if result else "ОШИБКА"
            print(f"Результат: {status}\n")
        except Exception as e:
            results.append((name, False))
            print(f"Результат: ИСКЛЮЧЕНИЕ - {e}\n")
    
    # Вывод общего результата
    print("\n=== Результаты тестов ===")
    all_passed = all(result for _, result in results)
    
    for name, result in results:
        status = "✓ Успешно" if result else "✗ Ошибка"
        print(f"{status} - {name}")
    
    print(f"\nОбщий результат: {'УСПЕШНО' if all_passed else 'ЕСТЬ ОШИБКИ'}")
    
    if all_passed:
        print("\nБот готов к запуску! Выполните команду: python telegram_bot.py")
    else:
        print("\nИсправьте ошибки перед запуском бота.")
    
    return all_passed

if __name__ == "__main__":
    run_tests()

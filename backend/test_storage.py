"""
Тестовый скрипт для проверки функциональности хранилища данных.

Проверяет работу фабрики хранилищ и файлового хранилища.

Автор: ShamaVibe Team
"""

import os
import logging
import asyncio
import shutil
from dotenv import load_dotenv

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

async def test_storage_factory():
    """Проверяет работу фабрики хранилища."""
    try:
        from storage_factory import StorageFactory
        
        # Получаем доступные типы хранилищ
        storage_types = StorageFactory.get_storage_types()
        
        print("Доступные типы хранилищ:")
        for storage_type, description in storage_types.items():
            print(f"  - {storage_type}: {description}")
        
        # Пробуем создать экземпляр файлового хранилища
        storage = await StorageFactory.create_storage("file")
        if storage:
            print("✓ Файловое хранилище успешно создано")
            return True
        else:
            print("✗ Не удалось создать файловое хранилище")
            return False
    except Exception as e:
        logger.error(f"Ошибка при проверке фабрики хранилища: {e}")
        return False

async def test_file_storage():
    """Проверяет работу файлового хранилища."""
    try:
        from file_storage import FileStorage
        
        # Создаем тестовую директорию
        test_dir = os.path.join(os.path.dirname(__file__), 'test_storage')
        if os.path.exists(test_dir):
            shutil.rmtree(test_dir)
        
        # Создаем экземпляр файлового хранилища
        file_storage = FileStorage(test_dir)
        
        # Инициализируем хранилище
        await file_storage.init_database()
        
        # Проверяем создание игрока
        player_id = await file_storage.create_player(123456789, "Test Player")
        if player_id:
            print("✓ Создание игрока работает")
        else:
            print("✗ Ошибка при создании игрока")
            return False
        
        # Проверяем получение игрока
        player = await file_storage.get_player_by_tg_id(123456789)
        if player and player['name'] == "Test Player":
            print("✓ Получение игрока работает")
        else:
            print("✗ Ошибка при получении игрока")
            return False
        
        # Проверяем логирование событий
        event_id = await file_storage.log_event(
            123456789, 
            "test_event",
            {"test": "data"}
        )
        if event_id:
            print("✓ Логирование событий работает")
        else:
            print("✗ Ошибка при логировании событий")
            return False
        
        # Очищаем тестовую директорию
        file_storage.close()
        if os.path.exists(test_dir):
            shutil.rmtree(test_dir)
        
        return True
    except Exception as e:
        logger.error(f"Ошибка при тестировании файлового хранилища: {e}")
        return False

async def run_tests():
    """Запускает все тесты."""
    tests = [
        ("Проверка фабрики хранилища", test_storage_factory),
        ("Проверка файлового хранилища", test_file_storage),
    ]
    
    results = []
    
    print("\n=== Запуск тестов хранилища данных ===\n")
    
    for name, test_func in tests:
        print(f"Выполняется тест: {name}...")
        try:
            result = await test_func()
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
        print("\nХранилище данных готово к использованию!")
    else:
        print("\nИсправьте ошибки в хранилище данных перед запуском бота.")
    
    return all_passed

if __name__ == "__main__":
    # Загружаем переменные окружения
    load_dotenv()
    
    # Запускаем тесты
    asyncio.run(run_tests())
